#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any, List, Optional, Callable, Protocol
import time
from datetime import datetime, timedelta

from ..data_providers.vnstat_provider import VnStatDataProvider
from ..config.settings import ThresholdConfig, MonitorConfig
from ..state_manager import StateManager


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
        
        # Initialize state manager for persistent notification tracking
        self.state_manager = StateManager()
        
        # Set up thresholds from configuration
        self.total_limit = threshold_config.total_limit  # in GB
        self.interval = threshold_config.interval  # in GB
        self.critical_percentage = threshold_config.critical_percentage
        self.critical_threshold = (self.total_limit * self.critical_percentage) / 100
        
        # Set up check interval from monitor config (in seconds)
        self.check_interval = self.monitor_config.check_interval  # default: 1 hour
        
        # Scheduled reporting settings
        self.enable_startup_notification = self.monitor_config.reporting.enable_startup_notification
        self.enable_daily_report = self.monitor_config.reporting.enable_daily_report
        self.daily_report_hour = self.monitor_config.reporting.daily_report_hour
        self.include_traffic_trend = self.monitor_config.reporting.include_traffic_trend
        self.include_daily_breakdown = self.monitor_config.reporting.include_daily_breakdown
        
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
        # Get already notified thresholds from persistent state
        notified_thresholds = self.state_manager.get_notified_thresholds()
        
        # Check if we've exceeded a new interval threshold
        for i in range(1, int(self.total_limit / self.interval) + 1):
            threshold = i * self.interval
            if current_usage >= threshold and threshold not in notified_thresholds:
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
        # Calculate percentage
        percentage = (current_usage / self.total_limit) * 100
        
        # Calculate traffic until next threshold
        next_threshold = 0
        for i in range(1, int(self.total_limit / self.interval) + 1):
            threshold = i * self.interval
            if current_usage < threshold:
                next_threshold = threshold
                break
        
        # Calculate traffic until shutdown threshold
        remaining_to_critical = self.critical_threshold - current_usage if current_usage < self.critical_threshold else 0
        
        # Calculate remaining days in current month
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        next_month = current_month + 1 if current_month < 12 else 1
        next_year = current_year if current_month < 12 else current_year + 1
        next_month_date = datetime(next_year, next_month, 1)
        remaining_days = (next_month_date - now).days
        
        # Estimate daily average usage
        daily_average = current_usage / now.day
        
        # Estimate total usage by end of month
        estimated_end_of_month = current_usage + (daily_average * remaining_days)
        
        # Build status summary
        summary = f"""Traffic Monitoring System Status Report

Current Traffic Usage Summary:
----------------------
Current Date: {now.strftime('%Y-%m-%d %H:%M:%S')}
Current Month Usage: {current_usage:.2f}GB / {self.total_limit}GB ({percentage:.1f}%)
{"⚠️ Warning: Shutdown threshold exceeded!" if current_usage >= self.critical_threshold else ""}

Daily Average Usage: {daily_average:.2f}GB/day
Remaining Days in Month: {remaining_days} days
Estimated Month-End Total: {estimated_end_of_month:.2f}GB
"""

        if next_threshold > 0:
            summary += f"\nTraffic until next threshold ({next_threshold}GB): {next_threshold - current_usage:.2f}GB"

        if remaining_to_critical > 0:
            summary += f"\nTraffic until shutdown threshold ({self.critical_threshold}GB): {remaining_to_critical:.2f}GB"
        
        # If configuration requires traffic trend, try to add past 7 days traffic data
        if self.include_traffic_trend:
            try:
                # Get daily usage for past 7 days
                daily_usage = self.data_provider.get_daily_usage(days=7)
                if daily_usage:
                    summary += "\n\nLast 7 Days Traffic Trend:"
                    for i in range(7, 0, -1):
                        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                        usage = daily_usage.get(date, 0.0)
                        summary += f"\n- {date}: {usage:.2f}GB"
            except Exception as e:
                self.logger.warning(f"Unable to get traffic trend: {e}")
            
        summary += f"""

Traffic Monitor Settings:
----------------------
Total Traffic Limit: {self.total_limit}GB
Warning Threshold Interval: Warning sent every {self.interval}GB
Shutdown Threshold: {self.critical_threshold}GB ({self.critical_percentage}%)
Check Interval: {self.check_interval} seconds

This is an automated notification email, please do not reply.
"""
        return summary
    
    def _get_daily_report(self) -> str:
        """Generate a daily report with traffic statistics."""
        try:
            # Get current month usage
            current_usage = self.data_provider.get_current_month_usage()
            
            # Get yesterday's date
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_str = yesterday.strftime("%Y-%m-%d")
            
            # Get daily traffic for past 30 days
            daily_usage = {}
            if self.include_traffic_trend or self.include_daily_breakdown:
                daily_usage = self.data_provider.get_daily_usage(days=30)
            
            # Get yesterday's traffic usage
            yesterday_usage = daily_usage.get(yesterday_str, 0.0)
            
            # Calculate daily average for current month
            now = datetime.now()
            daily_average = current_usage / now.day
            
            # Calculate remaining days in current month
            current_month = now.month
            current_year = now.year
            next_month = current_month + 1 if current_month < 12 else 1
            next_year = current_year if current_month < 12 else current_year + 1
            next_month_date = datetime(next_year, next_month, 1)
            remaining_days = (next_month_date - now).days
            
            # Estimate total usage by end of month
            estimated_end_of_month = current_usage + (daily_average * remaining_days)
            
            # Calculate percentage
            percentage = (current_usage / self.total_limit) * 100
            
            # Build daily report
            report = f"""Traffic Monitoring System - Daily Traffic Report

Date: {now.strftime('%Y-%m-%d')}

Yesterday's Traffic Usage:
----------------------
Yesterday's Total Usage: {yesterday_usage:.2f}GB
{"⚠️ Yesterday's traffic was high!" if yesterday_usage > daily_average * 1.5 else ""}

Current Month Cumulative Traffic Usage:
----------------------
Current Month Total: {current_usage:.2f}GB / {self.total_limit}GB ({percentage:.1f}%)
Daily Average Usage: {daily_average:.2f}GB/day
Remaining Days: {remaining_days} days
Month-End Estimate: {estimated_end_of_month:.2f}GB
"""
            
            # Add traffic trend (if configured)
            if self.include_traffic_trend and daily_usage:
                report += "\nTraffic Trend:\n----------------------\n"
                report += "Last 7 Days Traffic Trend:\n"
                for i in range(7, 0, -1):
                    date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                    usage = daily_usage.get(date, 0.0)
                    report += f"- {date}: {usage:.2f}GB\n"
            
            # Warning messages
            if percentage > 70:
                report += f"\n⚠️ Warning: Current traffic has used {percentage:.1f}% of monthly quota!\n"
            
            if estimated_end_of_month > self.total_limit:
                report += f"\n⚠️ Warning: At current usage rate, you will exceed your total traffic limit this month!\n"
                
            if current_usage >= self.critical_threshold:
                report += f"\n🔴 Critical Warning: Shutdown threshold reached ({self.critical_percentage}%)! System may shut down at any time.\n"
                
            report += "\nThis is an automated traffic report, please do not reply."
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating daily report: {e}")
            return f"Error generating daily traffic report: {e}"

    def send_startup_notification(self) -> None:
        """Send a notification about system startup and current traffic status."""
        # If startup notification is disabled in configuration, return immediately
        if not self.enable_startup_notification:
            self.logger.info("Startup notification disabled in configuration")
            return
            
        try:
            # Get current month usage
            current_usage = self.data_provider.get_current_month_usage()
            
            # Create status summary
            status_summary = self._get_status_summary(current_usage)
            
            # Set notification level
            level = "info"
            if current_usage >= self.critical_threshold:
                level = "critical"
            elif current_usage >= self.total_limit * 0.7:  # If usage exceeds 70%, use warning level
                level = "warning"
            
            # Send notification
            subject = f"Traffic Monitoring System Started - Current Usage: {current_usage:.2f}GB ({(current_usage/self.total_limit*100):.1f}%)"
            self.notifier.notify(subject, status_summary, level)
            
            self.logger.info("System startup notification sent")
            
        except Exception as e:
            self.logger.error(f"Error sending startup notification: {e}")
    
    def send_daily_report(self) -> None:
        """Send a daily traffic report."""
        # If daily report is disabled in configuration, return immediately
        if not self.enable_daily_report:
            return
            
        try:
            # Get current date
            now = datetime.now()
            today = now.date()
            
            # Check if a daily report has already been sent today
            last_report_date_str = self.state_manager.get_last_daily_report_date()
            if last_report_date_str == today.isoformat():
                return
                
            # Check if it's time to send the daily report
            if now.hour == self.daily_report_hour:
                # Get current month usage
                current_usage = self.data_provider.get_current_month_usage()
                
                # Create daily report
                daily_report = self._get_daily_report()
                
                # Set notification level
                level = "info"
                if current_usage >= self.critical_threshold:
                    level = "critical"
                elif current_usage >= self.total_limit * 0.7:
                    level = "warning"
                
                # Send notification
                percentage = (current_usage / self.total_limit) * 100
                subject = f"Traffic Daily Report - {today} - Usage: {current_usage:.2f}GB ({percentage:.1f}%)"
                self.notifier.notify(subject, daily_report, level)
                
                # Update the date of the last daily report sent
                self.state_manager.set_last_daily_report_date(today.isoformat())
                
                self.logger.info(f"Daily traffic report for {today} sent")
        
        except Exception as e:
            self.logger.error(f"Error sending daily report: {e}")

    def check_traffic(self) -> None:
        """Check current traffic usage and take appropriate actions."""
        try:
            # Get current month's usage in GB
            current_usage = self.data_provider.get_current_month_usage()
            self.logger.debug(f"Current month usage: {current_usage}GB")
            
            # Check if we need to send a daily report
            self.send_daily_report()
            
            # Check for all thresholds that need notification
            while True:
                threshold = self._should_notify(current_usage)
                if not threshold:
                    break
                    
                self.logger.info(f"Threshold reached: {threshold}GB")
                subject = f"Traffic Alert: {threshold}GB threshold reached"
                message = (
                    f"Your network traffic has reached {threshold}GB out of "
                    f"your {self.total_limit}GB limit. "
                    f"Current usage: {current_usage:.2f}GB."
                )
                self.notifier.notify(subject, message, "warning")
                self.state_manager.add_notified_threshold(threshold)
            
            # Check if we've reached the critical threshold
            if self._is_critical(current_usage) and not self.state_manager.is_critical_notification_sent():
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
                self.state_manager.set_critical_notification_sent(True)
                
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
            # Send status notification at startup
            self.send_startup_notification()
            
            # Start monitoring loop
            while True:
                self.check_traffic()
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            self.logger.info("Traffic monitoring stopped by user")
            return 0
        
        except Exception as e:
            self.logger.exception(f"Unhandled exception: {e}")
            return 1 