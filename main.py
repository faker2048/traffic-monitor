#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import sys

from config.settings import load_settings, AppConfig
from monitors.traffic_monitor import TrafficMonitor
from notifiers.email_notifier import EmailNotifier
from actions.shutdown import ShutdownAction

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
    parser.add_argument('--config', type=str, default='config/settings.yaml',
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
        
        # Initialize notifier
        notifier = EmailNotifier(config.email)
        
        # Initialize action handler
        shutdown_action = ShutdownAction(config=config.action)
        
        # Initialize and run traffic monitor
        monitor = TrafficMonitor(
            threshold_config=config.thresholds,
            notifier=notifier,
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