#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Email Notifier Test Module

This module provides functionality to test the email notification system.
It can be run directly as a script to send a test email using the configured settings.

Usage:
    python email_notifier_test.py [config_path]
    
    If config_path is not provided, it defaults to 'config/settings.yaml'
"""

import logging
import os
import sys

# Make sure parent directory is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import load_settings, EmailConfig
from notifiers.email_notifier import EmailNotifier


def setup_logging():
    """Configure logging output"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )


def send_test_email(config_path='config/settings.yaml'):
    """
    Send a test email
    
    Args:
        config_path: Path to the configuration file
    
    Returns:
        Boolean indicating whether sending was successful
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Load settings from configuration file
        logger.info(f"Loading configuration from {config_path}")
        config = load_settings(config_path)
        email_config = config.email
        
        # Display effective email configuration
        logger.info(f"SMTP server: {email_config.smtp_server}:{email_config.smtp_port}")
        logger.info(f"Sender: {email_config.sender}")
        logger.info(f"Recipients: {', '.join(email_config.recipients)}")
        logger.info(f"Using TLS: {email_config.use_tls}")
        
        # Initialize email sender
        logger.info("Initializing Email notifier")
        notifier = EmailNotifier(email_config)
        
        # Send test email
        subject = "Traffic Monitoring System Test Email"
        message = "This is a test email from the traffic monitoring system to verify that the email sending functionality is working properly."
        
        logger.info(f"Sending test email: '{subject}'")
        result = notifier.notify(
            subject=subject,
            message=message,
            level="info"
        )
        
        if result:
            logger.info("✓ Email sent successfully!")
            return True
        else:
            logger.error("✗ Email sending failed")
            return False
            
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False


def main():
    """Main entry point"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting email sending test program")
    
    # Determine configuration file path
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = 'config/settings.yaml'
    
    # Send test email
    success = send_test_email(config_path)
    
    # Return appropriate exit code
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main()) 