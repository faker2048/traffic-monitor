#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import subprocess
import re
from datetime import datetime
from typing import Dict, Optional, List

from ..config.settings import MonitorConfig


class VnStatDataProvider:
    """
    数据提供者，使用vnstat获取网络流量信息。
    
    此提供者要求系统上已安装并正确配置vnstat。
    """
    
    def __init__(self, interface: Optional[str] = None, config: Optional[MonitorConfig] = None) -> None:
        """
        初始化VnStat数据提供者。
        
        参数:
            interface: 要监控的网络接口。如果为None，则使用配置中的接口。
            config: 监控配置，可用于替代直接接口参数。
        """
        self.logger = logging.getLogger(__name__)
        
        # 使用接口参数或从配置中获取
        if interface is not None:
            self.interface = interface
        elif config is not None:
            self.interface = config.interface
        else:
            self.interface = None
        
        # 验证vnstat是否已安装
        self._verify_vnstat()
    
    def _verify_vnstat(self) -> None:
        """验证vnstat是否已安装且可用。"""
        try:
            subprocess.run(
                ["vnstat", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=True
            )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            self.logger.error(f"无法验证vnstat安装: {e}")
            raise RuntimeError("vnstat未安装或不在PATH中")
    
    def _run_vnstat_command(self, args: List[str]) -> str:
        """
        使用给定参数运行vnstat并返回文本输出。
        
        参数:
            args: 传递给vnstat的参数列表
            
        返回:
            包含命令输出的字符串
        """
        cmd = ["vnstat"]
        if self.interface:
            cmd.extend(["-i", self.interface])
        cmd.extend(args)
            
        self.logger.debug(f"运行命令: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )
            
            return result.stdout
        
        except subprocess.SubprocessError as e:
            self.logger.error(f"运行vnstat命令失败: {e}")
            if e.stderr:
                self.logger.error(f"错误输出: {e.stderr}")
            raise RuntimeError(f"无法从vnstat获取数据: {e}")
    
    def _parse_size_to_gb(self, size_str: str) -> float:
        """
        解析大小字符串（例如'10.5 GiB'或'800 MiB'）为GB。
        
        参数:
            size_str: 要解析的大小字符串
            
        返回:
            以GB为单位的大小（浮点数）
        """
        try:
            # 提取数值和单位
            match = re.match(r'([\d.]+)\s+(\w+)', size_str)
            if not match:
                self.logger.warning(f"解析大小字符串失败: {size_str}")
                return 0.0
                
            value, unit = match.groups()
            value = float(value)
            unit = unit.lower()
            
            # 转换为GB
            if 'gib' in unit:
                return value  # 已经是GB
            elif 'mib' in unit:
                return value / 1024.0  # MB转GB
            elif 'kib' in unit:
                return value / (1024.0 * 1024.0)  # KB转GB
            elif 'tib' in unit:
                return value * 1024.0  # TB转GB
            else:
                self.logger.warning(f"大小字符串中未知单位: {size_str}")
                return value  # 假设已经是GB
                
        except Exception as e:
            self.logger.error(f"解析大小字符串'{size_str}'时出错: {e}")
            return 0.0
    
    def get_current_month_usage(self) -> float:
        """
        获取当前月份的总流量（GB）。
        
        返回:
            表示总流量的浮点数（GB）
        """
        try:
            # 获取月度数据输出
            output = self._run_vnstat_command(["-m"])
            self.logger.debug(f"vnstat -m 输出:\n{output}")
            
            # 当前月份标识
            current_month = datetime.now().strftime("%Y-%m")
            
            # 查找当前月行及其total数据
            # 使用正则表达式匹配形如 "2025-04     51.47 GiB |   50.73 GiB |  102.20 GiB" 的行
            month_pattern = re.compile(
                r'(\d{4}-\d{2})\s+(\d+\.\d+)\s+(\w+)\s+\|\s+(\d+\.\d+)\s+(\w+)\s+\|\s+(\d+\.\d+)\s+(\w+)',
                re.IGNORECASE
            )
            
            for line in output.split('\n'):
                # 检查是否包含当前月份
                if current_month in line:
                    match = month_pattern.search(line)
                    if match:
                        # 提取total数据（第6,7组是总量和单位）
                        total_value = float(match.group(6))
                        total_unit = match.group(7)
                        size_str = f"{total_value} {total_unit}"
                        total_gb = self._parse_size_to_gb(size_str)
                        self.logger.debug(f"找到当前月份({current_month})的流量: {total_gb}GB")
                        return total_gb
            
            # 如果没有找到精确的当前月份，尝试找出最后一个非estimated的月份数据
            lines = output.split('\n')
            for line in lines:
                # 跳过包含"estimated"的行
                if "estimated" in line.lower():
                    continue
                    
                match = month_pattern.search(line)
                if match:
                    # 提取total数据
                    total_value = float(match.group(6))
                    total_unit = match.group(7)
                    size_str = f"{total_value} {total_unit}"
                    total_gb = self._parse_size_to_gb(size_str)
                    self.logger.debug(f"找到最近月份({match.group(1)})的流量: {total_gb}GB")
                    return total_gb
            
            self.logger.warning("未能找到当前月份的流量数据")
            return 0.0
            
        except Exception as e:
            self.logger.error(f"获取当前月份使用量时出错: {e}")
            raise RuntimeError(f"获取当前月份使用量失败: {e}") from e
    
    def get_daily_usage(self, days: int = 30) -> Dict[str, float]:
        """
        获取指定天数的每日流量。
        
        参数:
            days: 要检索的天数
            
        返回:
            字典，以日期为键，以GB为单位的使用量为值
        """
        try:
            # 获取日数据输出
            output = self._run_vnstat_command(["-d"])
            
            daily_usage = {}
            
            # 使用正则表达式匹配日期和流量数据
            # 匹配形如 "2025-04-11    4.83 GiB |    4.76 GiB |    9.59 GiB"
            day_pattern = re.compile(
                r'((?:\d{4}-\d{2}-\d{2})|(?:today|yesterday))\s+(\d+\.\d+)\s+(\w+)\s+\|\s+(\d+\.\d+)\s+(\w+)\s+\|\s+(\d+\.\d+)\s+(\w+)',
                re.IGNORECASE
            )
            
            for line in output.split('\n'):
                match = day_pattern.search(line)
                if not match:
                    continue
                
                date_str = match.group(1).lower()
                # 处理特殊日期
                if date_str == 'today':
                    date_str = datetime.now().strftime("%Y-%m-%d")
                elif date_str == 'yesterday':
                    yesterday = datetime.now()
                    yesterday = yesterday.replace(day=yesterday.day-1)
                    date_str = yesterday.strftime("%Y-%m-%d")
                
                # 提取total数据
                total_value = float(match.group(6))
                total_unit = match.group(7)
                size_str = f"{total_value} {total_unit}"
                total_gb = self._parse_size_to_gb(size_str)
                
                daily_usage[date_str] = total_gb
            
            return daily_usage
            
        except Exception as e:
            self.logger.error(f"获取每日使用量时出错: {e}")
            raise RuntimeError(f"获取每日使用量失败: {e}") from e 