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
    parser.add_argument('--webhook-url', type=str,
                      help='Override webhook URL for testing')
    parser.add_argument('--force', action='store_true',
                      help='Force sending even if Discord is disabled in config')
    parser.add_argument('--level', type=str, default='info',
                       choices=['info', 'warning', 'critical'],
                       help='Notification level to test')
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
            if args.force:
                logger.warning("Discord notifications are disabled in the configuration. Forcing enabled for test.")
                discord_config.enabled = True
            else:
                logger.error("Discord notifications are disabled in the configuration. Use --force to test anyway.")
                return 1
                
        # Override webhook URL if provided
        if args.webhook_url:
            logger.info(f"Overriding webhook URL with provided value")
            discord_config.webhook_url = args.webhook_url
        
        # Initialize Discord notifier
        logger.info("Initializing Discord notifier")
        notifier = DiscordNotifier(discord_config)
        
        # Generate test message
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = args.level
        
        # Emoji prefixes based on level
        emoji_prefix = "ℹ️" if level == "info" else "⚠️" if level == "warning" else "🚨"
        
        subject = f"Traffic Monitor Test - {current_time}"
        message = f"""✨ This is a test message to verify Discord webhook notification functionality! ✨

🚦 **Traffic Monitor Status Report**:
- Current traffic usage: 850GB/2000GB (42.5%)
- Daily average: 28.33GB/day
- Threshold limit: 100GB intervals
- Next threshold: 900GB (in 50GB)

⏱️ **Test Information**:
- Current time: {current_time}
- This is a {level.upper()} level notification
- Notification level: {emoji_prefix} {level.upper()}

📊 **Recent Traffic Trend**:
- Yesterday: 25GB
- Today: 35GB (trending up)
- Estimated month-end: 1250GB

🔍 **Test Purpose**:
- Verifying Discord notification feature
- Testing emoji rendering
- Checking message formatting

If you receive this message, your Discord webhook configuration is working correctly! 🎉"""
        
        # Send the test message
        logger.info(f"Sending test {level} notification")
        result = notifier.notify(
            subject=subject,
            message=message,
            level=level
        )
        
        if result:
            logger.info("Test notification sent successfully! 🎉")
            return 0
        else:
            logger.error("Failed to send test notification. Check the webhook URL in your config. ❌")
            return 1
            
    except Exception as e:
        logger.exception(f"Error during testing: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 