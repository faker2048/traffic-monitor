#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import yaml
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Union


@dataclass
class EmailConfig:
    """Email notification configuration."""
    smtp_server: str = "smtp.example.com"
    smtp_port: int = 587
    username: str = "your_username"
    password: str = "your_password"
    sender: str = "traffic-monitor@example.com"
    recipients: List[str] = field(default_factory=lambda: ["admin@example.com"])
    use_tls: bool = True


@dataclass
class ThresholdConfig:
    """Threshold configuration for traffic monitoring."""
    total_limit: int = 2000  # 2TB in GB
    interval: int = 100  # 100GB intervals
    critical_percentage: int = 90  # Percentage for critical alert


@dataclass
class ActionConfig:
    """Configuration for actions like shutdown."""
    delay_seconds: int = 60  # Delay before shutdown in seconds
    force: bool = False  # Whether to force shutdown


@dataclass
class ReportConfig:
    """Configuration for traffic reports."""
    enable_startup_notification: bool = True  # 启动时发送通知
    enable_daily_report: bool = True  # 每日发送流量报告
    daily_report_hour: int = 8  # 每日报告发送时间(小时，0-23)
    include_traffic_trend: bool = True  # 包含流量趋势
    include_daily_breakdown: bool = True  # 包含每日详细流量


@dataclass
class MonitorConfig:
    """Configuration for monitoring behavior."""
    check_interval: int = 3600  # Check every hour
    interface: Optional[str] = None  # Default interface
    reporting: ReportConfig = field(default_factory=ReportConfig)  # 报告设置


@dataclass
class AppConfig:
    """Main application configuration."""
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    action: ActionConfig = field(default_factory=ActionConfig)


def load_settings(config_path: str) -> AppConfig:
    """
    Load settings from a YAML configuration file into a dataclass.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        AppConfig object containing the configuration
        
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
            config_dict = yaml.safe_load(file)
        
        if not isinstance(config_dict, dict):
            logger.error(f"Invalid configuration format")
            raise ValueError("Configuration must be a dictionary")
        
        # Create configuration objects
        config = AppConfig()
        
        # Parse thresholds section
        if 'thresholds' in config_dict and isinstance(config_dict['thresholds'], dict):
            thresh_dict = config_dict['thresholds']
            config.thresholds = ThresholdConfig(
                total_limit=thresh_dict.get('total_limit', config.thresholds.total_limit),
                interval=thresh_dict.get('interval', config.thresholds.interval),
                critical_percentage=thresh_dict.get('critical_percentage', config.thresholds.critical_percentage)
            )
        
        # Parse email section
        if 'email' in config_dict and isinstance(config_dict['email'], dict):
            email_dict = config_dict['email']
            config.email = EmailConfig(
                smtp_server=email_dict.get('smtp_server', config.email.smtp_server),
                smtp_port=email_dict.get('smtp_port', config.email.smtp_port),
                username=email_dict.get('username', config.email.username),
                password=email_dict.get('password', config.email.password),
                sender=email_dict.get('sender', config.email.sender),
                recipients=email_dict.get('recipients', config.email.recipients),
                use_tls=email_dict.get('use_tls', config.email.use_tls)
            )
        
        # Parse monitor section
        if 'monitor' in config_dict and isinstance(config_dict['monitor'], dict):
            monitor_dict = config_dict['monitor']
            
            # Parse reporting subsection if available
            reporting_config = config.monitor.reporting
            if 'reporting' in monitor_dict and isinstance(monitor_dict['reporting'], dict):
                reporting_dict = monitor_dict['reporting']
                reporting_config = ReportConfig(
                    enable_startup_notification=reporting_dict.get('enable_startup_notification', 
                                                                  config.monitor.reporting.enable_startup_notification),
                    enable_daily_report=reporting_dict.get('enable_daily_report', 
                                                          config.monitor.reporting.enable_daily_report),
                    daily_report_hour=reporting_dict.get('daily_report_hour', 
                                                        config.monitor.reporting.daily_report_hour),
                    include_traffic_trend=reporting_dict.get('include_traffic_trend', 
                                                            config.monitor.reporting.include_traffic_trend),
                    include_daily_breakdown=reporting_dict.get('include_daily_breakdown', 
                                                              config.monitor.reporting.include_daily_breakdown)
                )
            
            config.monitor = MonitorConfig(
                check_interval=monitor_dict.get('check_interval', config.monitor.check_interval),
                interface=monitor_dict.get('interface', config.monitor.interface),
                reporting=reporting_config
            )
            
        # Parse action section
        if 'action' in config_dict and isinstance(config_dict['action'], dict):
            action_dict = config_dict['action']
            config.action = ActionConfig(
                delay_seconds=action_dict.get('delay_seconds', config.action.delay_seconds),
                force=action_dict.get('force', config.action.force)
            )
        
        logger.debug(f"Loaded configuration: {config}")
        return config
        
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        raise ValueError(f"Invalid YAML in configuration file: {e}")
    
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise


def save_settings(config: AppConfig, output_path: str) -> None:
    """
    Save application configuration to a YAML file.
    
    Args:
        config: AppConfig object to save
        output_path: Path where the configuration file will be saved
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Convert dataclass to dictionary
        config_dict = asdict(config)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Write the configuration to file
        with open(output_path, 'w') as file:
            yaml.dump(config_dict, file, default_flow_style=False)
        
        logger.info(f"Saved configuration to {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        raise


def create_default_config(output_path: str) -> None:
    """
    Create a default configuration file.
    
    Args:
        output_path: Path where the configuration file will be saved
    """
    logger = logging.getLogger(__name__)
    
    # Create default configuration object
    config = AppConfig()
    
    # Save the configuration to file
    save_settings(config, output_path)
    
    logger.info(f"Created default configuration at {output_path}")


if __name__ == "__main__":
    # If run directly, create a default configuration
    logging.basicConfig(level=logging.INFO)
    create_default_config('config/settings.yaml') 