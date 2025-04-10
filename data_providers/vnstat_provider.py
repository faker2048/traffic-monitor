#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import subprocess
from typing import Dict, Any, Optional, List

class VnStatDataProvider:
    """
    Data provider that uses vnstat to obtain network traffic information.
    
    This provider requires vnstat to be installed and properly configured
    on the system.
    """
    
    def __init__(self, interface: Optional[str] = None) -> None:
        """
        Initialize the VnStat data provider.
        
        Args:
            interface: Network interface to monitor. If None, the default 
                      interface from vnstat will be used.
        """
        self.logger = logging.getLogger(__name__)
        self.interface = interface
        
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
    
    def _run_vnstat_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Run vnstat with given arguments and return the result as JSON.
        
        Args:
            args: List of arguments to pass to vnstat
            
        Returns:
            Dictionary containing the parsed JSON output
        """
        cmd = ["vnstat"] + args
        if self.interface:
            cmd.extend(["-i", self.interface])
            
        self.logger.debug(f"Running command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )
            
            return json.loads(result.stdout)
        
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to run vnstat command: {e}")
            if e.stderr:
                self.logger.error(f"Error output: {e.stderr}")
            raise RuntimeError(f"Failed to get data from vnstat: {e}")
        
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse vnstat output as JSON: {e}")
            raise RuntimeError(f"Invalid JSON output from vnstat: {e}")
    
    def get_current_month_usage(self) -> float:
        """
        Get the current month's total traffic usage in GB.
        
        Returns:
            Float representing total traffic in GB
        """
        try:
            # Get current month's data
            data = self._run_vnstat_command(["--json", "-m"])
            
            # Extract the current month's data (last entry in the array)
            interfaces = data.get("interfaces", [])
            if not interfaces:
                raise RuntimeError("No interface data found in vnstat output")
            
            traffic = interfaces[0].get("traffic", {})
            months = traffic.get("months", [])
            
            if not months:
                self.logger.warning("No monthly data found in vnstat output")
                return 0.0
            
            # Get the latest month entry
            current_month = months[-1]
            
            # Calculate total (rx + tx) in GB
            rx_bytes = current_month.get("rx", 0)
            tx_bytes = current_month.get("tx", 0)
            total_bytes = rx_bytes + tx_bytes
            
            # Convert to GB (bytes to GB: divide by 1024^3)
            total_gb = total_bytes / (1024 ** 3)
            
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
            data = self._run_vnstat_command(["--json", "-d"])
            
            interfaces = data.get("interfaces", [])
            if not interfaces:
                raise RuntimeError("No interface data found in vnstat output")
            
            daily_usage = {}
            days_data = interfaces[0].get("traffic", {}).get("days", [])
            
            for day in days_data[-days:]:
                date = day.get("date", {})
                date_str = f"{date.get('year')}-{date.get('month'):02d}-{date.get('day'):02d}"
                
                rx_bytes = day.get("rx", 0)
                tx_bytes = day.get("tx", 0)
                total_bytes = rx_bytes + tx_bytes
                total_gb = total_bytes / (1024 ** 3)
                
                daily_usage[date_str] = total_gb
            
            return daily_usage
        
        except Exception as e:
            self.logger.error(f"Error getting daily usage: {e}")
            raise RuntimeError(f"Failed to get daily usage: {e}") from e 