#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import json
import requests
from typing import Dict, Any, Optional

from config.settings import DiscordConfig


class DiscordNotifier:
    """
    Discord webhook notification service for sending alerts.
    """
    
    def __init__(self, config: DiscordConfig) -> None:
        """
        Initialize the Discord webhook notifier.
        
        Args:
            config: Discord configuration containing webhook settings
        """
        self.logger = logging.getLogger(__name__)
        
        # Store configuration
        self.config = config
        self.enabled = config.enabled
        self.webhook_url = config.webhook_url
        self.username = config.username
        self.message_template = config.message_template
        
        # Optional configuration
        self.avatar_url = getattr(config, 'avatar_url', None)
        
        # Validate required configuration
        if not self.webhook_url or "your-webhook-url" in self.webhook_url:
            msg = "Missing or invalid webhook URL in Discord configuration"
            self.logger.error(msg)
            raise ValueError(msg)
        
        self.logger.info(f"Initialized DiscordNotifier with webhook URL")

    def _create_payload(self, subject: str, message: str, level: str) -> Dict[str, Any]:
        """
        Create the Discord webhook payload.
        
        Args:
            subject: Message subject
            message: Message body
            level: Notification level ('info', 'warning', 'critical')
            
        Returns:
            Dictionary with the webhook payload
        """
        # Define colors based on level (Discord uses decimal color values)
        colors = {
            'info': 3447003,     # Blue
            'warning': 16098851, # Orange/Yellow
            'critical': 15746887 # Red
        }
        color = colors.get(level.lower(), colors['info'])
        
        # Format the message
        formatted_message = message.replace('\n\n', '\n')
        if self.message_template:
            formatted_message = self.message_template.format(message=formatted_message)
        
        # Create the basic payload
        payload = {
            "username": self.username,
            "embeds": [{
                "title": subject,
                "description": formatted_message,
                "color": color,
                "timestamp": None  # Will be filled by Discord
            }]
        }
        
        # Add avatar URL if specified
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
            
        return payload

    def notify(self, subject: str, message: str, level: str = "info") -> bool:
        """
        Send a Discord webhook notification.
        
        Args:
            subject: Message subject
            message: Message body
            level: Notification level ('info', 'warning', 'critical')
            
        Returns:
            True if the message was sent successfully, False otherwise
        """
        if not self.enabled:
            self.logger.debug("Discord notifications are disabled, skipping")
            return False
            
        try:
            payload = self._create_payload(subject, message, level)
            
            # Convert the payload to JSON
            json_payload = json.dumps(payload)
            
            # Set the headers
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Send the request to the webhook URL
            response = requests.post(
                self.webhook_url,
                data=json_payload,
                headers=headers
            )
            
            # Check if the request was successful
            if response.status_code in (200, 204):
                self.logger.info(
                    f"Sent {level} Discord notification with subject '{subject}'"
                )
                return True
            else:
                self.logger.error(
                    f"Failed to send Discord notification: {response.status_code} - {response.text}"
                )
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to send Discord notification: {e}")
            return False 