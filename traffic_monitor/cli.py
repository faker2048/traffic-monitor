#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import click
import logging
import sys
import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional

from .config.settings import load_settings, AppConfig, save_settings
from .monitors.traffic_monitor import TrafficMonitor
from .notifiers.email_notifier import EmailNotifier
from .notifiers.discord_notifier import DiscordNotifier
from .actions.shutdown import ShutdownAction
from . import MultiNotifier, setup_logging


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "traffic-monitor"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "settings.toml"
SERVICE_NAME = "traffic-monitor"


def ensure_config_dir():
    """Ensure configuration directory exists."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def create_default_config(discord_webhook: Optional[str] = None, email_config: Optional[dict] = None) -> AppConfig:
    """Create default configuration with optional Discord webhook."""
    config = AppConfig()
    
    if discord_webhook:
        config.notifiers.discord.enabled = True
        config.notifiers.discord.webhook_url = discord_webhook
        # Disable email by default if Discord is provided
        config.notifiers.email.enabled = False
    
    if email_config:
        config.notifiers.email.enabled = True
        for key, value in email_config.items():
            setattr(config.notifiers.email, key, value)
    
    return config


def install_systemd_service(config_path: Path) -> bool:
    """Install systemd service for traffic monitor."""
    try:
        # Get the current executable path
        python_exe = sys.executable
        
        # Create service file content
        service_content = f"""[Unit]
Description=Traffic Monitor Service
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart={python_exe} -m traffic_monitor.cli run --config {config_path}
Restart=on-failure
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
        
        service_file = f"/etc/systemd/system/{SERVICE_NAME}.service"
        
        # Write service file (requires sudo)
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        # Reload systemd and enable service
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", SERVICE_NAME], check=True)
        subprocess.run(["systemctl", "start", SERVICE_NAME], check=True)
        
        click.echo(f"✅ Service installed and started successfully!")
        click.echo(f"   Service file: {service_file}")
        click.echo(f"   Config file: {config_path}")
        click.echo(f"\nService management commands:")
        click.echo(f"   sudo systemctl status {SERVICE_NAME}")
        click.echo(f"   sudo systemctl stop {SERVICE_NAME}")
        click.echo(f"   sudo systemctl restart {SERVICE_NAME}")
        click.echo(f"   sudo journalctl -u {SERVICE_NAME} -f")
        
        return True
        
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Failed to install service: {e}", err=True)
        return False
    except PermissionError:
        click.echo(f"❌ Permission denied. Please run with sudo for service installation.", err=True)
        return False
    except Exception as e:
        click.echo(f"❌ Error installing service: {e}", err=True)
        return False


def uninstall_systemd_service() -> bool:
    """Uninstall systemd service."""
    try:
        service_file = f"/etc/systemd/system/{SERVICE_NAME}.service"
        
        # Stop and disable service
        subprocess.run(["systemctl", "stop", SERVICE_NAME], check=False)
        subprocess.run(["systemctl", "disable", SERVICE_NAME], check=False)
        
        # Remove service file
        if os.path.exists(service_file):
            os.remove(service_file)
        
        # Reload systemd
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        
        click.echo(f"✅ Service uninstalled successfully!")
        return True
        
    except Exception as e:
        click.echo(f"❌ Error uninstalling service: {e}", err=True)
        return False


@click.group()
@click.option('--log-level', default='INFO', 
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
              help='Set the logging level')
@click.pass_context
def cli(ctx, log_level):
    """Traffic Monitor - Network traffic monitoring and alerting system."""
    ctx.ensure_object(dict)
    ctx.obj['log_level'] = log_level
    setup_logging(log_level)


@cli.command()
@click.option('--discord', help='Discord webhook URL for notifications')
@click.option('--email-server', help='SMTP server for email notifications')
@click.option('--email-user', help='Email username')
@click.option('--email-pass', help='Email password')
@click.option('--email-sender', help='Email sender address')
@click.option('--email-recipients', help='Comma-separated list of email recipients')
@click.option('--limit', default=2000, type=int, help='Total traffic limit in GB (default: 2000)')
@click.option('--interval', default=100, type=int, help='Alert interval in GB (default: 100)')
@click.option('--critical', default=90, type=int, help='Critical threshold percentage (default: 90)')
@click.option('--config', type=click.Path(), help='Configuration file path')
@click.option('--install', is_flag=True, help='Install as system service (requires sudo)')
@click.pass_context
def run(ctx, discord, email_server, email_user, email_pass, email_sender, 
        email_recipients, limit, interval, critical, config, install):
    """Run the traffic monitor."""
    
    # Determine config file path
    if config:
        config_path = Path(config)
    else:
        ensure_config_dir()
        config_path = DEFAULT_CONFIG_FILE
    
    # Create configuration
    if not config_path.exists() or discord or email_server:
        click.echo(f"Creating configuration at {config_path}")
        
        # Prepare email config if provided
        email_config = None
        if email_server:
            email_config = {
                'smtp_server': email_server,
                'username': email_user or '',
                'password': email_pass or '',
                'sender': email_sender or '',
                'recipients': email_recipients.split(',') if email_recipients else ['admin@example.com']
            }
        
        # Create config with provided options
        app_config = create_default_config(discord, email_config)
        app_config.thresholds.total_limit = limit
        app_config.thresholds.interval = interval
        app_config.thresholds.critical_percentage = critical
        
        # Save configuration
        save_settings(app_config, str(config_path))
        click.echo(f"✅ Configuration saved to {config_path}")
    
    # Install service if requested
    if install:
        if os.geteuid() != 0:
            click.echo("❌ Service installation requires sudo privileges.", err=True)
            click.echo("Please run: sudo uvx traffic-monitor run --discord <url> --install")
            return
        
        if install_systemd_service(config_path):
            return
        else:
            sys.exit(1)
    
    # Load and validate configuration
    try:
        app_config = load_settings(str(config_path))
    except Exception as e:
        click.echo(f"❌ Error loading configuration: {e}", err=True)
        sys.exit(1)
    
    # Validate at least one notifier is enabled
    if not app_config.notifiers.email.enabled and not app_config.notifiers.discord.enabled:
        click.echo("❌ No notification methods enabled. Please configure email or Discord notifications.", err=True)
        sys.exit(1)
    
    # Run the monitor
    logger = logging.getLogger(__name__)
    logger.info("Starting traffic monitor service")
    
    try:
        # Create composite notifier
        multi_notifier = MultiNotifier()
        
        # Initialize email notifier if enabled
        if app_config.notifiers.email.enabled:
            logger.info("Email notifications enabled")
            email_notifier = EmailNotifier(app_config.notifiers.email)
            multi_notifier.add_notifier(email_notifier)
        
        # Initialize Discord notifier if enabled
        if app_config.notifiers.discord.enabled:
            logger.info("Discord notifications enabled")
            discord_notifier = DiscordNotifier(app_config.notifiers.discord)
            multi_notifier.add_notifier(discord_notifier)
        
        # Initialize action handler
        shutdown_action = ShutdownAction(config=app_config.action)
        
        # Initialize and run traffic monitor
        monitor = TrafficMonitor(
            threshold_config=app_config.thresholds,
            notifier=multi_notifier,
            action=shutdown_action,
            monitor_config=app_config.monitor
        )
        
        # Run the monitoring process
        exit_code = monitor.run()
        sys.exit(exit_code)
        
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


@cli.command()
@click.option('--config', type=click.Path(), help='Configuration file path')
def status(config):
    """Show current traffic status."""
    # Determine config file path
    if config:
        config_path = Path(config)
    else:
        config_path = DEFAULT_CONFIG_FILE
    
    if not config_path.exists():
        click.echo(f"❌ Configuration file not found: {config_path}", err=True)
        sys.exit(1)
    
    try:
        from .data_providers.vnstat_provider import VnStatDataProvider
        from .config.settings import load_settings
        
        app_config = load_settings(str(config_path))
        data_provider = VnStatDataProvider(config=app_config.monitor)
        
        current_usage = data_provider.get_current_month_usage()
        percentage = (current_usage / app_config.thresholds.total_limit) * 100
        critical_threshold = (app_config.thresholds.total_limit * app_config.thresholds.critical_percentage) / 100
        
        click.echo(f"📊 Traffic Monitor Status")
        click.echo(f"   Current Usage: {current_usage:.2f}GB / {app_config.thresholds.total_limit}GB ({percentage:.1f}%)")
        click.echo(f"   Critical Threshold: {critical_threshold:.2f}GB ({app_config.thresholds.critical_percentage}%)")
        
        if current_usage >= critical_threshold:
            click.echo(f"   🔴 Status: CRITICAL - Shutdown threshold exceeded!")
        elif percentage > 70:
            click.echo(f"   🟡 Status: WARNING - High usage")
        else:
            click.echo(f"   🟢 Status: OK")
        
    except Exception as e:
        click.echo(f"❌ Error getting status: {e}", err=True)
        sys.exit(1)


@cli.command()
def service():
    """Manage system service."""
    click.echo("Service management commands:")
    click.echo(f"   sudo systemctl status {SERVICE_NAME}")
    click.echo(f"   sudo systemctl stop {SERVICE_NAME}")
    click.echo(f"   sudo systemctl start {SERVICE_NAME}")
    click.echo(f"   sudo systemctl restart {SERVICE_NAME}")
    click.echo(f"   sudo journalctl -u {SERVICE_NAME} -f")


@cli.command()
def uninstall():
    """Uninstall system service."""
    if os.geteuid() != 0:
        click.echo("❌ Service uninstallation requires sudo privileges.", err=True)
        click.echo("Please run: sudo uvx traffic-monitor uninstall")
        return
    
    uninstall_systemd_service()


@cli.command()
@click.option('--config', type=click.Path(), help='Configuration file path')
def config_show(config):
    """Show current configuration."""
    # Determine config file path
    if config:
        config_path = Path(config)
    else:
        config_path = DEFAULT_CONFIG_FILE
    
    if not config_path.exists():
        click.echo(f"❌ Configuration file not found: {config_path}", err=True)
        click.echo(f"Run 'traffic-monitor run' to create a default configuration.")
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            content = f.read()
        click.echo(f"Configuration file: {config_path}")
        click.echo("=" * 50)
        click.echo(content)
    except Exception as e:
        click.echo(f"❌ Error reading configuration: {e}", err=True)
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main()