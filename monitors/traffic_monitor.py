#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any, List, Optional, Callable, Protocol
import time

from data_providers.vnstat_provider import VnStatDataProvider


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
        threshold_config: Dict[str, Any],
        notifier: Notifier,
        action: Action,
        data_provider: Optional[Any] = None
    ) -> None:
        """
        Initialize the traffic monitor.
        
        Args:
            threshold_config: Configuration for traffic thresholds
            notifier: Notification service
            action: Action to perform when critical threshold is reached
            data_provider: Data provider for traffic information
        """
        self.logger = logging.getLogger(__name__)
        self.threshold_config = threshold_config
        self.notifier = notifier
        self.action = action
        
        # Initialize the data provider (default is VnStat)
        self.data_provider = data_provider or VnStatDataProvider()
        
        # Set up thresholds
        self.total_limit = threshold_config.get('total_limit', 2000)  # in GB
        self.interval = threshold_config.get('interval', 100)  # in GB
        self.critical_percentage = threshold_config.get('critical_percentage', 90)
        self.critical_threshold = (self.total_limit * self.critical_percentage) / 100
        
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

    def check_traffic(self) -> None:
        """Check current traffic usage and take appropriate actions."""
        try:
            # Get current month's usage in GB
            current_usage = self.data_provider.get_current_month_usage()
            self.logger.debug(f"Current month usage: {current_usage}GB")
            
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
    
    def run(self, check_interval: int = 3600) -> int:
        """
        Run the traffic monitor in a loop.
        
        Args:
            check_interval: Time between checks in seconds (default: 1 hour)
            
        Returns:
            Exit code
        """
        self.logger.info(f"Starting traffic monitoring with {check_interval}s interval")
        
        try:
            while True:
                self.check_traffic()
                time.sleep(check_interval)
        
        except KeyboardInterrupt:
            self.logger.info("Traffic monitoring stopped by user")
            return 0
        
        except Exception as e:
            self.logger.exception(f"Unhandled exception: {e}")
            return 1 