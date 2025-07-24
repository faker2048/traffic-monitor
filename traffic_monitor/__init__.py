#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import sys

from .config.settings import load_settings, AppConfig
from .monitors.traffic_monitor import TrafficMonitor
from .notifiers.email_notifier import EmailNotifier
from .notifiers.discord_notifier import DiscordNotifier
from .actions.shutdown import ShutdownAction


class MultiNotifier:
    """Composite notifier that sends notifications to multiple services."""
    
    def __init__(self, notifiers=None):
        """
        Initialize the multi-notifier.
        
        Args:
            notifiers: List of notifier instances
        """
        self.logger = logging.getLogger(__name__)
        self.notifiers = notifiers or []
        
    def add_notifier(self, notifier):
        """Add a notifier to the list of notifiers."""
        self.notifiers.append(notifier)
        
    def notify(self, subject: str, message: str, level: str = "info") -> bool:
        """
        Send notifications using all configured notifiers.
        
        Args:
            subject: Notification subject
            message: Notification message
            level: Notification level ('info', 'warning', 'critical')
            
        Returns:
            True if at least one notification was successful, False otherwise
        """
        if not self.notifiers:
            self.logger.warning("No notifiers configured, skipping notification")
            return False
            
        results = []
        for notifier in self.notifiers:
            try:
                result = notifier.notify(subject, message, level)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error in notifier {notifier.__class__.__name__}: {e}")
                results.append(False)
        
        # Return True if at least one notification was successful
        return any(results)


def setup_logging(log_level: str = 'INFO') -> None:
    """Configure logging for the application."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Traffic Monitor and Alert System')
    parser.add_argument('--config', type=str, default='config/settings.toml',
                      help='Path to configuration file')
    parser.add_argument('--log-level', type=str, default='INFO',
                      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                      help='Set the logging level')
    return parser.parse_args()


def main() -> int:
    """Main entry point for the application."""
    args = parse_arguments()
    setup_logging(args.log_level)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting traffic monitor service")
    
    try:
        # Load configuration
        config = load_settings(args.config)
        
        # Create composite notifier
        multi_notifier = MultiNotifier()
        
        # Initialize email notifier if enabled
        if config.notifiers.email.enabled:
            logger.info("Email notifications enabled")
            email_notifier = EmailNotifier(config.notifiers.email)
            multi_notifier.add_notifier(email_notifier)
        else:
            logger.info("Email notifications disabled")
        
        # Initialize Discord notifier if enabled
        if config.notifiers.discord.enabled:
            logger.info("Discord notifications enabled")
            discord_notifier = DiscordNotifier(config.notifiers.discord)
            multi_notifier.add_notifier(discord_notifier)
        else:
            logger.info("Discord notifications disabled")
            
        # Verify at least one notifier is configured
        if not multi_notifier.notifiers:
            logger.warning("No notification methods enabled. Please enable at least one in the configuration.")
            return 1
        
        # Initialize action handler
        shutdown_action = ShutdownAction(config=config.action)
        
        # Initialize and run traffic monitor
        monitor = TrafficMonitor(
            threshold_config=config.thresholds,
            notifier=multi_notifier,
            action=shutdown_action,
            monitor_config=config.monitor
        )
        
        # Run the monitoring process
        return monitor.run()
        
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main()) 