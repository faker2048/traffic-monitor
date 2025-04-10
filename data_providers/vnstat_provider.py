#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import subprocess
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

from config.settings import MonitorConfig


class VnStatDataProvider:
    """
    Data provider that uses vnstat to obtain network traffic information.
    
    This provider requires vnstat to be installed and properly configured
    on the system.
    """
    
    def __init__(self, interface: Optional[str] = None, config: Optional[MonitorConfig] = None) -> None:
        """
        Initialize the VnStat data provider.
        
        Args:
            interface: Network interface to monitor. If None, the interface from config is used.
            config: Monitor configuration, can be used instead of direct interface parameter.
        """
        self.logger = logging.getLogger(__name__)
        
        # Use interface parameter or get from config
        if interface is not None:
            self.interface = interface
        elif config is not None:
            self.interface = config.interface
        else:
            self.interface = None
        
        # Verify vnstat is installed
        self._verify_vnstat()
    
    def _verify_vnstat(self) -> None:
        """Verify that vnstat is installed and available."""
        try:
            subprocess.run(
                ["vnstat", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=True
            )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            self.logger.error(f"Failed to verify vnstat installation: {e}")
            raise RuntimeError("vnstat is not installed or not in PATH")
    
    def _run_vnstat_command(self, args: List[str]) -> str:
        """
        Run vnstat with given arguments and return the text output.
        
        Args:
            args: List of arguments to pass to vnstat
            
        Returns:
            String containing the command output
        """
        cmd = ["vnstat"]
        if self.interface:
            cmd.extend(["-i", self.interface])
        cmd.extend(args)
            
        self.logger.debug(f"Running command: {' '.join(cmd)}")
        
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
            self.logger.error(f"Failed to run vnstat command: {e}")
            if e.stderr:
                self.logger.error(f"Error output: {e.stderr}")
            raise RuntimeError(f"Failed to get data from vnstat: {e}")
    
    def _parse_size_to_gb(self, size_str: str) -> float:
        """
        Parse a size string (e.g., '10.5 GiB' or '800 MiB') to GB.
        
        Args:
            size_str: Size string to parse
            
        Returns:
            Size in GB as float
        """
        try:
            # 提取数值和单位
            match = re.match(r'([\d.]+)\s+(\w+)', size_str)
            if not match:
                self.logger.warning(f"Failed to parse size string: {size_str}")
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
                self.logger.warning(f"Unknown unit in size string: {size_str}")
                return value  # 假设已经是GB
                
        except Exception as e:
            self.logger.error(f"Error parsing size string '{size_str}': {e}")
            return 0.0
    
    def get_current_month_usage(self) -> float:
        """
        Get the current month's total traffic usage in GB.
        
        Returns:
            Float representing total traffic in GB
        """
        try:
            # 获取月度数据输出
            output = self._run_vnstat_command(["-m"])
            
            # 解析输出找到当前月份行
            current_month = datetime.now().strftime("%Y-%m")
            month_abbr = datetime.now().strftime("%b").lower()
            
            lines = output.strip().split('\n')
            total_gb = 0.0
            
            # 寻找当前月份行
            for line in lines:
                # 尝试匹配当前月份
                if current_month in line.lower() or month_abbr in line.lower():
                    # 提取流量数据
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if i > 0 and ('gib' in part.lower() or 'mib' in part.lower() or 'tib' in part.lower()):
                            size_str = f"{parts[i-1]} {part}"
                            if 'total' in line.lower() and ':' in line:
                                # 已经找到总量
                                total_gb = self._parse_size_to_gb(size_str)
                                break
                            elif i > 2 and parts[i-2].lower() in ['total', '|']:
                                # 总量列
                                total_gb = self._parse_size_to_gb(size_str)
                                break
            
            if total_gb == 0.0:
                # 如果未找到总量，尝试手动计算（找RX和TX列）
                for line in lines:
                    if current_month in line.lower() or month_abbr in line.lower():
                        rx_gb = 0.0
                        tx_gb = 0.0
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if i > 0 and ('gib' in part.lower() or 'mib' in part.lower() or 'tib' in part.lower()):
                                if 'rx' in line.lower() and rx_gb == 0.0:
                                    rx_gb = self._parse_size_to_gb(f"{parts[i-1]} {part}")
                                elif 'tx' in line.lower() and tx_gb == 0.0:
                                    tx_gb = self._parse_size_to_gb(f"{parts[i-1]} {part}")
                        
                        if rx_gb > 0.0 or tx_gb > 0.0:
                            total_gb = rx_gb + tx_gb
                            break
            
            self.logger.debug(f"Current month usage: {total_gb:.2f}GB")
            return total_gb
            
        except Exception as e:
            self.logger.error(f"Error getting current month usage: {e}")
            raise RuntimeError(f"Failed to get current month usage: {e}") from e
    
    def get_daily_usage(self, days: int = 30) -> Dict[str, float]:
        """
        Get daily traffic for the specified number of days.
        
        Args:
            days: Number of days to retrieve
            
        Returns:
            Dictionary with dates as keys and usage in GB as values
        """
        try:
            # 获取日数据输出
            output = self._run_vnstat_command(["-d"])
            
            lines = output.strip().split('\n')
            daily_usage = {}
            
            # 查找日期行和对应的流量
            date_pattern = re.compile(r'(\d{2}/\d{2}/\d{2}|\d{4}-\d{2}-\d{2}|yesterday|today)')
            current_date = None
            
            for line in lines:
                # 尝试查找日期
                date_match = date_pattern.search(line.lower())
                if date_match:
                    date_str = date_match.group(1)
                    
                    # 处理特殊日期
                    if date_str == 'today':
                        date_str = datetime.now().strftime("%Y-%m-%d")
                    elif date_str == 'yesterday':
                        yesterday = datetime.now()
                        yesterday = yesterday.replace(day=yesterday.day-1)
                        date_str = yesterday.strftime("%Y-%m-%d")
                    
                    current_date = date_str
                    continue
                
                # 如果有日期且行包含流量数据
                if current_date and ('gib' in line.lower() or 'mib' in line.lower() or 'tib' in line.lower()):
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if i > 0 and 'total' in parts[i-1].lower() and ('gib' in part.lower() or 'mib' in part.lower() or 'tib' in part.lower()):
                            total_gb = self._parse_size_to_gb(f"{parts[i]} {part}")
                            daily_usage[current_date] = total_gb
                            break
            
            return daily_usage
            
        except Exception as e:
            self.logger.error(f"Error getting daily usage: {e}")
            raise RuntimeError(f"Failed to get daily usage: {e}") from e 