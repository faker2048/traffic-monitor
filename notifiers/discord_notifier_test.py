#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord Notifier Test Module

This module provides functionality to test the Discord webhook notification system.

Example:
    To run the test with the default config file:
    
    ```
    python discord_notifier_test.py [config_path]
    ```
"""

import logging
import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from notifiers.discord_notifier import DiscordNotifier
from config.settings import load_settings


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Test Discord webhook notifications')
    parser.add_argument('config_path', type=str, nargs='?', default='config/settings.toml',
                        help='Path to config file (default: config/settings.toml)')
    parser.add_argument('--log-level', type=str, default='INFO',
                      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                      help='Set the logging level')
    return parser.parse_args()


def setup_logging(log_level):
    """Set up logging configuration"""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Main entry point for the test script"""
    args = parse_arguments()
    setup_logging(args.log_level)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Testing Discord webhook notifications with config from {args.config_path}")
    
    try:
        # Load configuration
        config = load_settings(args.config_path)
        discord_config = config.notifiers.discord
        
        # Check if Discord notifications are enabled
        if not discord_config.enabled:
            logger.warning("Discord notifications are disabled in the configuration. Testing anyway.")
        
        # Initialize Discord notifier
        logger.info("Initializing Discord notifier")
        notifier = DiscordNotifier(discord_config)
        
        # Generate test message
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = f"Discord Notification Test - {current_time}"
        message = f"""这是一条测试消息，用于验证Discord webhook通知功能。

当前时间：{current_time}
这是一个信息级别的通知。

测试信息体：
- 这是一个测试项目
- 仅用于验证Discord通知功能是否正常
- 请勿回复

如果您收到此消息，则说明Discord webhook配置正确。"""
        
        # Send the test message
        logger.info("Sending test notification")
        result = notifier.notify(
            subject=subject,
            message=message,
            level="info"
        )
        
        if result:
            logger.info("Test notification sent successfully")
            return 0
        else:
            logger.error("Failed to send test notification")
            return 1
            
    except Exception as e:
        logger.exception(f"Error during testing: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 