#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional

from ..config.settings import EmailConfig


class EmailNotifier:
    """
    Email notification service for sending alerts.
    """
    
    def __init__(self, config: EmailConfig) -> None:
        """
        Initialize the email notifier.
        
        Args:
            config: Email configuration containing SMTP settings
        """
        self.logger = logging.getLogger(__name__)
        
        # Store configuration
        self.config = config
        self.smtp_server = config.smtp_server
        self.smtp_port = config.smtp_port
        self.username = config.username
        self.password = config.password
        self.sender = config.sender
        self.recipients = config.recipients
        self.use_tls = config.use_tls
        
        # Validate required configuration
        if not all([self.smtp_server, self.smtp_port, self.sender, self.recipients]):
            missing = []
            if not self.smtp_server:
                missing.append('smtp_server')
            if not self.smtp_port:
                missing.append('smtp_port')
            if not self.sender:
                missing.append('sender')
            if not self.recipients:
                missing.append('recipients')
            
            msg = f"Missing required email configuration: {', '.join(missing)}"
            self.logger.error(msg)
            raise ValueError(msg)
        
        self.logger.info(f"Initialized EmailNotifier with server {self.smtp_server}:{self.smtp_port}")

    def _create_message(self, subject: str, message: str, level: str) -> MIMEMultipart:
        """
        Create an email message with proper formatting.
        
        Args:
            subject: Email subject
            message: Email body
            level: Notification level ('info', 'warning', 'critical')
            
        Returns:
            MIMEMultipart message object
        """
        # Create the email container
        email = MIMEMultipart()
        email['Subject'] = subject
        email['From'] = self.sender
        email['To'] = ', '.join(self.recipients)
        
        # Add some styling based on the level
        color = {
            'info': '#2196F3',      # Blue
            'warning': '#FF9800',   # Orange
            'critical': '#F44336'   # Red
        }.get(level.lower(), '#2196F3')
        
        # 使用三重引号创建HTML内容，避免f-string中的转义问题
        formatted_message = message.replace('\n', '<br>')
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .message {{ padding: 20px; border-left: 4px solid {color}; background-color: #f8f8f8; }}
                .footer {{ font-size: 12px; color: #666; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="message">
                {formatted_message}
            </div>
            <div class="footer">
                This is an automated message from the Traffic Monitor system.
            </div>
        </body>
        </html>
        """
        
        # Attach the HTML content
        email.attach(MIMEText(html_content, 'html'))
        
        # Also attach a plain text version
        email.attach(MIMEText(message, 'plain'))
        
        return email

    def notify(self, subject: str, message: str, level: str = "info") -> bool:
        """
        Send an email notification.
        
        Args:
            subject: Email subject
            message: Email body
            level: Notification level ('info', 'warning', 'critical')
            
        Returns:
            True if the email was sent successfully, False otherwise
        """
        if not self.recipients:
            self.logger.warning("No recipients configured, skipping email notification")
            return False
            
        try:
            email = self._create_message(subject, message, level)
            
            if self.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.send_message(email)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    if self.username and self.password:
                        server.starttls()
                        server.login(self.username, self.password)
                    server.send_message(email)
            
            self.logger.info(
                f"Sent {level} email notification with subject '{subject}' "
                f"to {len(self.recipients)} recipients"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False 