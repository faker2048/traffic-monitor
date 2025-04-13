#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import subprocess
import re
from datetime import datetime
from typing import Dict, Optional, List

from config.settings import MonitorConfig


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
            
            # 当前月份标识
            current_month = datetime.now().strftime("%Y-%m")
            month_abbr = datetime.now().strftime("%b").lower()
            
            lines = output.strip().split('\n')
            
            # 查找包含当前月份的行
            month_line = None
            for i, line in enumerate(lines):
                if current_month in line.lower() or month_abbr in line.lower():
                    month_line = line
                    # 查找total数据行（通常在月份行之后几行）
                    for j in range(i, min(i+5, len(lines))):
                        if "total" in lines[j].lower() and "|" in lines[j]:
                            # 使用正则表达式匹配total列的数据
                            match = re.search(r'total\s*\|\s*([\d.]+)\s+(\w+)', lines[j], re.IGNORECASE)
                            if match:
                                size_str = f"{match.group(1)} {match.group(2)}"
                                return self._parse_size_to_gb(size_str)
            
            # 如果找不到明确的total列，尝试直接从月份行解析
            if month_line:
                # 使用更精确的正则表达式匹配标准vnstat输出格式中的total部分
                total_pattern = re.compile(r'\|\s*([\d.]+)\s+(\w+)\s*\|', re.IGNORECASE)
                matches = total_pattern.findall(month_line)
                
                # 通常第三个匹配结果是total（第一个是rx，第二个是tx）
                if len(matches) >= 3:
                    size_str = f"{matches[2][0]} {matches[2][1]}"
                    return self._parse_size_to_gb(size_str)
            
            # 备用方法：解析示例中显示的格式
            total_pattern = re.compile(r'total\s*\|\s*([\d.]+)\s+(\w+)', re.IGNORECASE)
            for line in lines:
                match = total_pattern.search(line)
                if match:
                    size_str = f"{match.group(1)} {match.group(2)}"
                    return self._parse_size_to_gb(size_str)
            
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
            
            lines = output.strip().split('\n')
            daily_usage = {}
            
            # 查找日期和对应的流量
            date_pattern = re.compile(r'(\d{2}/\d{2}/\d{2}|\d{4}-\d{2}-\d{2}|yesterday|today)')
            
            for i, line in enumerate(lines):
                date_match = date_pattern.search(line.lower())
                if not date_match:
                    continue
                    
                date_str = date_match.group(1)
                
                # 处理特殊日期
                if date_str == 'today':
                    date_str = datetime.now().strftime("%Y-%m-%d")
                elif date_str == 'yesterday':
                    yesterday = datetime.now()
                    yesterday = yesterday.replace(day=yesterday.day-1)
                    date_str = yesterday.strftime("%Y-%m-%d")
                
                # 查找与该日期相关的total数据
                total_gb = 0.0
                
                # 检查当前行和下一行是否包含total数据
                for j in range(i, min(i+3, len(lines))):
                    if "total" in lines[j].lower():
                        total_match = re.search(r'total\s*([\d.]+)\s+(\w+)', lines[j], re.IGNORECASE)
                        if total_match:
                            size_str = f"{total_match.group(1)} {total_match.group(2)}"
                            total_gb = self._parse_size_to_gb(size_str)
                            break
                
                if total_gb > 0.0:
                    daily_usage[date_str] = total_gb
            
            return daily_usage
            
        except Exception as e:
            self.logger.error(f"获取每日使用量时出错: {e}")
            raise RuntimeError(f"获取每日使用量失败: {e}") from e 