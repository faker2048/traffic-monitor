#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import yaml
from typing import Dict, Any, Optional


def load_settings(config_path: str) -> Dict[str, Any]:
    """
    Load settings from a YAML configuration file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Dictionary containing the configuration
        
    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        ValueError: If the configuration file is invalid
    """
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        logger.info(f"Loading configuration from {config_path}")
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        if not isinstance(config, dict):
            logger.error(f"Invalid configuration format: {config}")
            raise ValueError("Configuration must be a dictionary")
        
        # Validate and set defaults for required settings
        _validate_and_set_defaults(config)
        
        return config
        
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        raise ValueError(f"Invalid YAML in configuration file: {e}")
    
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise


def _validate_and_set_defaults(config: Dict[str, Any]) -> None:
    """
    Validate the configuration and set default values for missing fields.
    
    Args:
        config: Configuration dictionary to validate and update
    """
    logger = logging.getLogger(__name__)
    
    # Ensure thresholds section exists
    if 'thresholds' not in config:
        logger.warning("Thresholds section missing, using defaults")
        config['thresholds'] = {}
    
    # Set default threshold values if missing
    thresholds = config['thresholds']
    thresholds.setdefault('total_limit', 2000)  # 2TB default
    thresholds.setdefault('interval', 100)  # 100GB intervals
    thresholds.setdefault('critical_percentage', 90)  # 90% critical threshold
    
    # Ensure email section exists
    if 'email' not in config:
        logger.warning("Email configuration missing, notifications will be disabled")
        config['email'] = {}


def create_default_config(output_path: str) -> None:
    """
    Create a default configuration file.
    
    Args:
        output_path: Path where the configuration file will be saved
    """
    logger = logging.getLogger(__name__)
    
    # Create default configuration
    default_config = {
        'thresholds': {
            'total_limit': 2000,  # 2TB in GB
            'interval': 100,  # 100GB intervals
            'critical_percentage': 90  # Percentage for critical alert
        },
        'email': {
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'username': 'your_username',
            'password': 'your_password',
            'sender': 'traffic-monitor@example.com',
            'recipients': ['admin@example.com'],
            'use_tls': True
        },
        'monitor': {
            'check_interval': 3600,  # Check every hour
            'interface': None  # Default interface
        }
    }
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write the configuration to file
    with open(output_path, 'w') as file:
        yaml.dump(default_config, file, default_flow_style=False)
    
    logger.info(f"Created default configuration at {output_path}")


if __name__ == "__main__":
    # If run directly, create a default configuration
    logging.basicConfig(level=logging.INFO)
    create_default_config('config/settings.yaml') 