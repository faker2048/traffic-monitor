#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime

from ..config.settings import DiscordConfig


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
        
        # Validate required configuration only if enabled
        # Skip webhook validation for easier testing
        if self.enabled and not self.webhook_url:
            msg = "Missing webhook URL in Discord configuration"
            self.logger.error(msg)
            raise ValueError(msg)
        
        self.logger.info(f"✅ Initialized DiscordNotifier with webhook URL (enabled: {self.enabled})")

    def _get_level_emoji(self, level: str) -> str:
        """
        Get an appropriate emoji for the notification level.
        
        Args:
            level: Notification level ('info', 'warning', 'critical')
            
        Returns:
            Emoji string appropriate for the level
        """
        return {
            'info': '📊',       # Chart/info
            'warning': '⚠️',    # Warning
            'critical': '🚨'    # Alert/siren
        }.get(level.lower(), '📢')  # Default to megaphone
        
    def _get_additional_emojis(self, level: str, message: str) -> Dict[str, str]:
        """
        Get additional contextual emojis based on message content and level.
        
        Args:
            level: Notification level
            message: Message content
            
        Returns:
            Dictionary of emoji contexts
        """
        emojis = {}
        
        # Traffic related emojis
        if "traffic" in message.lower():
            emojis['traffic'] = '🚦'
        if "limit" in message.lower():
            emojis['limit'] = '🔄'
        if "threshold" in message.lower():
            emojis['threshold'] = '📈'
            
        # Status emojis based on level
        if level == 'info':
            emojis['status'] = '✅'
        elif level == 'warning':
            emojis['status'] = '⚠️'
        elif level == 'critical':
            emojis['status'] = '❌'
            
        # Time related emoji
        emojis['time'] = '⏰'
        
        return emojis

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
        
        # Get level emoji
        level_emoji = self._get_level_emoji(level)
        
        # Get additional contextual emojis
        emojis = self._get_additional_emojis(level, message)
        
        # Current time with emoji
        current_time = f"{emojis.get('time', '⏰')} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Format the message with emojis
        formatted_message = message.replace('\n\n', '\n')
        
        # Add emoji to subject
        emoji_subject = f"{level_emoji} {subject}"
        
        # Apply message template if provided
        if self.message_template:
            # Add emojis to the formatted message
            formatted_message = self.message_template.format(
                message=formatted_message,
                level_emoji=level_emoji,
                traffic_emoji=emojis.get('traffic', ''),
                time=current_time,
                status_emoji=emojis.get('status', '')
            )
        else:
            # Add a footer with emojis if no template
            formatted_message += f"\n\n{emojis.get('status', '')} Status as of {current_time}"
        
        # Create the basic payload
        payload = {
            "username": self.username,
            "embeds": [{
                "title": emoji_subject,
                "description": formatted_message,
                "color": color,
                "footer": {
                    "text": f"Traffic Monitor {emojis.get('traffic', '🚦')} | {level.upper()} {level_emoji}"
                },
                "timestamp": datetime.now().isoformat()
            }]
        }
        
        # Add avatar URL if specified
        if self.avatar_url and self.avatar_url.strip():
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
            self.logger.debug("🔕 Discord notifications are disabled, skipping")
            return False
            
        # Warn if using example webhook URL
        if "your-webhook-url" in self.webhook_url:
            self.logger.warning("⚠️ Using example webhook URL. This will likely fail to send notifications.")
            
        try:
            payload = self._create_payload(subject, message, level)
            
            # Convert the payload to JSON
            json_payload = json.dumps(payload)
            
            # Set the headers
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Log the request (without sensitive info)
            self.logger.debug(f"🚀 Sending Discord webhook to {self.webhook_url[:20]}...")
            
            # Send the request to the webhook URL
            response = requests.post(
                self.webhook_url,
                data=json_payload,
                headers=headers,
                timeout=10  # Add timeout
            )
            
            # Check if the request was successful
            if response.status_code in (200, 204):
                self.logger.info(
                    f"✅ Sent {level} Discord notification with subject '{subject}'"
                )
                return True
            else:
                self.logger.error(
                    f"❌ Failed to send Discord notification: HTTP {response.status_code} - {response.text}"
                )
                return False
            
        except requests.RequestException as e:
            self.logger.error(f"🌐❌ Network error sending Discord notification: {e}")
            return False
        except Exception as e:
            self.logger.error(f"💥 Failed to send Discord notification: {e}")
            return False 