# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Installation and Usage
```bash
# Install and run with Discord webhook (using uvx)
uvx traffic-monitor run --discord <discord_webhook_url>

# Install as system service with auto-start
sudo uvx traffic-monitor run --discord <discord_webhook_url> --install

# Run with email notifications
uvx traffic-monitor run --email-server smtp.gmail.com --email-user user@gmail.com --email-pass password

# Run with custom configuration
uvx traffic-monitor run --config /path/to/config.toml

# Install from local development
pip install -e .
traffic-monitor run --discord <webhook_url>
```

### Service Management
```bash
# Check service status
sudo systemctl status traffic-monitor

# View logs
sudo journalctl -u traffic-monitor -f

# Stop/start service
sudo systemctl stop traffic-monitor
sudo systemctl start traffic-monitor

# Uninstall service
sudo uvx traffic-monitor uninstall
```

### CLI Commands
```bash
# Show current traffic status
uvx traffic-monitor status

# Show configuration
uvx traffic-monitor config-show

# Service management help
uvx traffic-monitor service
```

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest traffic_monitor/

# Run individual test files
python traffic_monitor/notifiers/discord_notifier_test.py
python traffic_monitor/notifiers/email_notifier_test.py
python traffic_monitor/data_providers/vnstat_provider_test.py
```

### System Dependencies
```bash
# Required system dependency
sudo apt install vnstat  # Ubuntu/Debian
sudo yum install vnstat   # CentOS/RHEL
brew install vnstat       # macOS
```

## Architecture

### Core Components

**Main Application** (`main.py`):
- Entry point that orchestrates all components
- Implements `MultiNotifier` composite pattern for handling multiple notification channels
- Manages application lifecycle and error handling

**Traffic Monitor** (`monitors/traffic_monitor.py`):
- Core monitoring logic with configurable thresholds and intervals
- Implements Protocol-based design for `Notifier` and `Action` interfaces
- Handles startup notifications, daily reports, and threshold-based alerts
- Supports traffic trend analysis and usage estimation

**Data Provider** (`data_providers/vnstat_provider.py`):
- Abstracts vnstat system interaction
- Parses network traffic data from vnstat output
- Converts various units (GiB, MiB, KiB, TiB) to GB consistently
- Provides monthly and daily usage statistics

**Configuration System** (`config/settings.py`):
- TOML-based configuration using dataclasses
- Hierarchical structure: thresholds, notifiers (email/discord), monitor, action
- Type-safe configuration loading with validation

**Notification System**:
- Email notifications via SMTP (`notifiers/email_notifier.py`)
- Discord webhook notifications (`notifiers/discord_notifier.py`)
- Composite pattern allows multiple simultaneous notification channels

**Action System** (`actions/shutdown.py`):
- Handles critical threshold responses (system shutdown)
- Configurable delay and force options

### Key Design Patterns

- **Protocol Pattern**: Used for `Notifier` and `Action` interfaces to enable dependency injection
- **Composite Pattern**: `MultiNotifier` manages multiple notification channels
- **Data Provider Pattern**: Abstracts traffic data sources (currently vnstat)
- **Configuration as Code**: TOML-based configuration with dataclass validation

### Configuration Structure

The application uses a hierarchical TOML configuration:
- `thresholds`: Traffic limits and alert intervals
- `notifiers.email`: SMTP configuration for email alerts
- `notifiers.discord`: Webhook configuration for Discord alerts  
- `monitor`: Check intervals, interface selection, and reporting settings
- `action`: Shutdown behavior configuration

### Traffic Monitoring Logic

1. **Threshold Monitoring**: Sends alerts at configurable GB intervals (e.g., every 100GB)
2. **Critical Threshold**: Triggers shutdown action at configurable percentage of total limit
3. **Daily Reporting**: Sends comprehensive usage reports at specified hour
4. **Startup Notifications**: Provides current status when service starts
5. **Traffic Trend Analysis**: Includes historical usage patterns in reports