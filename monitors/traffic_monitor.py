#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any, List, Optional, Callable, Protocol
import time
from datetime import datetime, timedelta

from data_providers.vnstat_provider import VnStatDataProvider
from config.settings import ThresholdConfig, MonitorConfig


class Notifier(Protocol):
    """Protocol for notification implementations."""
    
    def notify(self, subject: str, message: str, level: str = "info") -> bool:
        """Send a notification with the given subject and message."""
        ...


class Action(Protocol):
    """Protocol for action implementations."""
    
    def execute(self) -> bool:
        """Execute the action and return success status."""
        ...


class TrafficMonitor:
    """
    Monitors network traffic and triggers notifications and actions
    based on configured thresholds.
    """
    
    def __init__(
        self, 
        threshold_config: ThresholdConfig,
        notifier: Notifier,
        action: Action,
        monitor_config: Optional[MonitorConfig] = None,
        data_provider: Optional[Any] = None
    ) -> None:
        """
        Initialize the traffic monitor.
        
        Args:
            threshold_config: Configuration for traffic thresholds
            notifier: Notification service
            action: Action to perform when critical threshold is reached
            monitor_config: Additional monitoring configuration
            data_provider: Data provider for traffic information
        """
        self.logger = logging.getLogger(__name__)
        self.threshold_config = threshold_config
        self.notifier = notifier
        self.action = action
        self.monitor_config = monitor_config or MonitorConfig()
        
        # Initialize the data provider (default is VnStat)
        self.data_provider = data_provider or VnStatDataProvider(config=self.monitor_config)
        
        # Set up thresholds from configuration
        self.total_limit = threshold_config.total_limit  # in GB
        self.interval = threshold_config.interval  # in GB
        self.critical_percentage = threshold_config.critical_percentage
        self.critical_threshold = (self.total_limit * self.critical_percentage) / 100
        
        # Set up check interval from monitor config (in seconds)
        self.check_interval = self.monitor_config.check_interval  # default: 1 hour
        
        # 定时报告设置
        self.enable_startup_notification = self.monitor_config.reporting.enable_startup_notification
        self.enable_daily_report = self.monitor_config.reporting.enable_daily_report
        self.daily_report_hour = self.monitor_config.reporting.daily_report_hour
        self.include_traffic_trend = self.monitor_config.reporting.include_traffic_trend
        self.include_daily_breakdown = self.monitor_config.reporting.include_daily_breakdown
        self.last_daily_report_date = None  # 上次发送日报的日期
        
        # Initialize tracking of sent notifications
        self.notified_thresholds: List[int] = []
        self.critical_notification_sent = False
        
        self.logger.info(
            f"Initialized TrafficMonitor with total limit: {self.total_limit}GB, "
            f"interval: {self.interval}GB, critical threshold: {self.critical_threshold}GB"
        )
    
    def _should_notify(self, current_usage: float) -> Optional[int]:
        """
        Determine if a notification should be sent based on current usage.
        
        Returns:
            The threshold that triggered the notification or None
        """
        # Check if we've exceeded a new interval threshold
        for i in range(1, int(self.total_limit / self.interval) + 1):
            threshold = i * self.interval
            if current_usage >= threshold and threshold not in self.notified_thresholds:
                return threshold
        return None

    def _is_critical(self, current_usage: float) -> bool:
        """
        Determine if the current usage has exceeded the critical threshold.
        
        Returns:
            True if current usage is critical, False otherwise
        """
        return current_usage >= self.critical_threshold
    
    def _get_status_summary(self, current_usage: float) -> str:
        """
        Generate a detailed status summary about the current traffic usage.
        
        Args:
            current_usage: Current traffic usage in GB
            
        Returns:
            Status summary as formatted string
        """
        # 计算百分比
        percentage = (current_usage / self.total_limit) * 100
        
        # 计算距离下一个阈值的流量
        next_threshold = 0
        for i in range(1, int(self.total_limit / self.interval) + 1):
            threshold = i * self.interval
            if current_usage < threshold:
                next_threshold = threshold
                break
        
        # 计算距离关机阈值的流量
        remaining_to_critical = self.critical_threshold - current_usage if current_usage < self.critical_threshold else 0
        
        # 计算当月剩余天数
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        next_month = current_month + 1 if current_month < 12 else 1
        next_year = current_year if current_month < 12 else current_year + 1
        next_month_date = datetime(next_year, next_month, 1)
        remaining_days = (next_month_date - now).days
        
        # 估算日均使用流量
        daily_average = current_usage / now.day
        
        # 估算月底预计总流量
        estimated_end_of_month = current_usage + (daily_average * remaining_days)
        
        # 构建状态摘要
        summary = f"""流量监控系统状态报告

当前流量使用情况摘要:
----------------------
当前日期: {now.strftime('%Y-%m-%d %H:%M:%S')}
当前月流量使用: {current_usage:.2f}GB / {self.total_limit}GB ({percentage:.1f}%)
{"⚠️ 注意：已超过关机阈值！" if current_usage >= self.critical_threshold else ""}

日均流量使用: {daily_average:.2f}GB/天
当月剩余天数: {remaining_days}天
月底预计总流量: {estimated_end_of_month:.2f}GB
"""

        if next_threshold > 0:
            summary += f"\n距离下个阈值 ({next_threshold}GB) 还有: {next_threshold - current_usage:.2f}GB"

        if remaining_to_critical > 0:
            summary += f"\n距离关机阈值 ({self.critical_threshold}GB) 还有: {remaining_to_critical:.2f}GB"
        
        # 如果配置要求包含流量趋势，则尝试添加过去7天的流量数据
        if self.include_traffic_trend:
            try:
                # 获取过去7天的每日流量
                daily_usage = self.data_provider.get_daily_usage(days=7)
                if daily_usage:
                    summary += "\n\n最近7天流量趋势:"
                    for i in range(7, 0, -1):
                        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                        usage = daily_usage.get(date, 0.0)
                        summary += f"\n- {date}: {usage:.2f}GB"
            except Exception as e:
                self.logger.warning(f"无法获取流量趋势: {e}")
            
        summary += f"""

流量监控设置:
----------------------
总流量限制: {self.total_limit}GB
警告阈值间隔: 每{self.interval}GB发送一次警告
关机阈值: {self.critical_threshold}GB ({self.critical_percentage}%)
检查间隔: {self.check_interval}秒

此为自动发送的通知邮件，请勿回复。
"""
        return summary
    
    def _get_daily_report(self) -> str:
        """Generate a daily report with traffic statistics."""
        try:
            # 获取当前月份使用量
            current_usage = self.data_provider.get_current_month_usage()
            
            # 获取昨天的日期
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_str = yesterday.strftime("%Y-%m-%d")
            
            # 获取过去30天的每日流量
            daily_usage = {}
            if self.include_traffic_trend or self.include_daily_breakdown:
                daily_usage = self.data_provider.get_daily_usage(days=30)
            
            # 获取昨天的流量使用情况
            yesterday_usage = daily_usage.get(yesterday_str, 0.0)
            
            # 计算当前月份的日均流量
            now = datetime.now()
            daily_average = current_usage / now.day
            
            # 计算当月剩余天数
            current_month = now.month
            current_year = now.year
            next_month = current_month + 1 if current_month < 12 else 1
            next_year = current_year if current_month < 12 else current_year + 1
            next_month_date = datetime(next_year, next_month, 1)
            remaining_days = (next_month_date - now).days
            
            # 估算月底预计总流量
            estimated_end_of_month = current_usage + (daily_average * remaining_days)
            
            # 计算百分比
            percentage = (current_usage / self.total_limit) * 100
            
            # 构建每日报告
            report = f"""流量监控系统 - 每日流量报告

日期: {now.strftime('%Y-%m-%d')}

昨日流量使用情况:
----------------------
昨日总使用量: {yesterday_usage:.2f}GB
{"⚠️ 昨日流量较高！" if yesterday_usage > daily_average * 1.5 else ""}

本月累计流量使用情况:
----------------------
当月总流量: {current_usage:.2f}GB / {self.total_limit}GB ({percentage:.1f}%)
日均使用量: {daily_average:.2f}GB/天
当月剩余: {remaining_days}天
月底预计: {estimated_end_of_month:.2f}GB
"""
            
            # 添加流量趋势（如果配置要求）
            if self.include_traffic_trend and daily_usage:
                report += "\n流量趋势:\n----------------------\n"
                report += "最近7天流量趋势:\n"
                for i in range(7, 0, -1):
                    date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                    usage = daily_usage.get(date, 0.0)
                    report += f"- {date}: {usage:.2f}GB\n"
            
            # 警告信息
            if percentage > 70:
                report += f"\n⚠️ 警告: 当前流量已使用 {percentage:.1f}% 的月度配额！\n"
            
            if estimated_end_of_month > self.total_limit:
                report += f"\n⚠️ 警告: 按当前使用速度，预计本月将超出总流量限制！\n"
                
            if current_usage >= self.critical_threshold:
                report += f"\n🔴 严重警告: 已达到关机阈值 ({self.critical_percentage}%)！系统随时可能关机。\n"
                
            report += "\n此为自动发送的流量报告，请勿回复。"
            
            return report
            
        except Exception as e:
            self.logger.error(f"生成每日报告时出错: {e}")
            return f"生成每日流量报告时出错: {e}"

    def send_startup_notification(self) -> None:
        """Send a notification about system startup and current traffic status."""
        # 如果配置禁用了启动通知，则直接返回
        if not self.enable_startup_notification:
            self.logger.info("启动通知已在配置中禁用")
            return
            
        try:
            # 获取当前月份使用量
            current_usage = self.data_provider.get_current_month_usage()
            
            # 创建状态摘要
            status_summary = self._get_status_summary(current_usage)
            
            # 设置通知级别
            level = "info"
            if current_usage >= self.critical_threshold:
                level = "critical"
            elif current_usage >= self.total_limit * 0.7:  # 如果使用量超过70%，使用警告级别
                level = "warning"
            
            # 发送通知
            subject = f"流量监控系统已启动 - 当前使用: {current_usage:.2f}GB ({(current_usage/self.total_limit*100):.1f}%)"
            self.notifier.notify(subject, status_summary, level)
            
            self.logger.info("已发送系统启动通知")
            
        except Exception as e:
            self.logger.error(f"发送启动通知时出错: {e}")
    
    def send_daily_report(self) -> None:
        """Send a daily traffic report."""
        # 如果配置禁用了每日报告，则直接返回
        if not self.enable_daily_report:
            return
            
        try:
            # 获取当前日期
            now = datetime.now()
            today = now.date()
            
            # 检查今天是否已经发送过日报
            if self.last_daily_report_date == today:
                return
                
            # 检查是否到了发送日报的时间
            if now.hour == self.daily_report_hour:
                # 获取当前月份使用量
                current_usage = self.data_provider.get_current_month_usage()
                
                # 创建每日报告
                daily_report = self._get_daily_report()
                
                # 设置通知级别
                level = "info"
                if current_usage >= self.critical_threshold:
                    level = "critical"
                elif current_usage >= self.total_limit * 0.7:
                    level = "warning"
                
                # 发送通知
                percentage = (current_usage / self.total_limit) * 100
                subject = f"流量监控日报 - {today} - 使用量: {current_usage:.2f}GB ({percentage:.1f}%)"
                self.notifier.notify(subject, daily_report, level)
                
                # 更新上次发送日报的日期
                self.last_daily_report_date = today
                
                self.logger.info(f"已发送{today}流量日报")
        
        except Exception as e:
            self.logger.error(f"发送每日报告时出错: {e}")

    def check_traffic(self) -> None:
        """Check current traffic usage and take appropriate actions."""
        try:
            # Get current month's usage in GB
            current_usage = self.data_provider.get_current_month_usage()
            self.logger.debug(f"Current month usage: {current_usage}GB")
            
            # 检查是否需要发送每日报告
            self.send_daily_report()
            
            # Check if we've reached a new notification threshold
            threshold = self._should_notify(current_usage)
            if threshold:
                self.logger.info(f"Threshold reached: {threshold}GB")
                subject = f"Traffic Alert: {threshold}GB threshold reached"
                message = (
                    f"Your network traffic has reached {threshold}GB out of "
                    f"your {self.total_limit}GB limit. "
                    f"Current usage: {current_usage:.2f}GB."
                )
                self.notifier.notify(subject, message, "warning")
                self.notified_thresholds.append(threshold)
            
            # Check if we've reached the critical threshold
            if self._is_critical(current_usage) and not self.critical_notification_sent:
                self.logger.critical(
                    f"Critical threshold reached: {current_usage:.2f}GB "
                    f"exceeds {self.critical_threshold}GB"
                )
                subject = "CRITICAL: Traffic Limit Nearly Exceeded - System Shutdown Imminent"
                message = (
                    f"CRITICAL WARNING: Your network traffic has reached {current_usage:.2f}GB, "
                    f"which exceeds the critical threshold of {self.critical_threshold}GB "
                    f"({self.critical_percentage}% of your {self.total_limit}GB limit). "
                    f"The system will now shutdown to prevent exceeding your limit."
                )
                self.notifier.notify(subject, message, "critical")
                self.critical_notification_sent = True
                
                # Execute the shutdown action
                self.logger.critical("Executing shutdown action")
                self.action.execute()
        
        except Exception as e:
            self.logger.error(f"Error checking traffic: {e}")
    
    def run(self) -> int:
        """
        Run the traffic monitor in a loop.
        
        Returns:
            Exit code
        """
        self.logger.info(f"Starting traffic monitoring with {self.check_interval}s interval")
        
        try:
            # 启动时发送状态通知
            self.send_startup_notification()
            
            # 开始监控循环
            while True:
                self.check_traffic()
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            self.logger.info("Traffic monitoring stopped by user")
            return 0
        
        except Exception as e:
            self.logger.exception(f"Unhandled exception: {e}")
            return 1 