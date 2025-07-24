# Traffic Monitor

A Python application that monitors network traffic usage (using vnstat) for various cloud and data center environments. It helps prevent excessive data transfer costs by sending staged email notifications or discord messages at specified intervals, and automatically shuts down the system when a critical threshold is reached. Perfect for:

- **AWS EC2/Lightsail Instance Traffic Monitoring**: Prevent AWS data transfer charges from exceeding your budget
- **Cloud Server Traffic Control**: Suitable for Alibaba Cloud, Tencent Cloud, and other cloud servers with traffic-based billing
- **Data Center Bandwidth Management**: Monitor and manage network traffic usage in data centers


## Features

- Monitors network traffic using vnstat
- Multiple notification methods: Email (SMTP) and Discord webhooks
- Daily traffic reports with usage statistics
- Automatically shuts down when critical threshold is reached
- Cross-platform support (Linux, Windows with WSL, macOS)

## Requirements

- Python 3.6+
- vnstat
- SMTP server (for email) or Discord webhook URL (for Discord notifications)

## Installation

### Quick Start with uvx (Recommended)

1. Install vnstat (system dependency):
   ```bash
   # Ubuntu/Debian
   sudo apt install vnstat
   
   # CentOS/RHEL
   sudo yum install vnstat
   
   # macOS
   brew install vnstat
   ```

2. Configure vnstat:
   ```bash
   sudo vnstat -u -i YOUR_INTERFACE
   sudo systemctl enable vnstat
   sudo systemctl start vnstat
   ```

3. Run with Discord webhook:
   ```bash
   uvx traffic-monitor run --discord <YOUR_DISCORD_WEBHOOK_URL>
   ```

4. Install as system service (auto-start on boot):
   ```bash
   sudo uvx traffic-monitor run --discord <YOUR_DISCORD_WEBHOOK_URL> --install
   ```

### Traditional Installation

1. Clone and install:
   ```bash
   git clone https://github.com/faker2048/traffic-monitor.git
   cd traffic-monitor
   pip install -e .
   ```

2. Run:
   ```bash
   traffic-monitor run --discord <YOUR_DISCORD_WEBHOOK_URL>
   ```

## Usage

### Command Line Options

```bash
# Run with Discord notifications
uvx traffic-monitor run --discord <webhook_url>

# Run with email notifications
uvx traffic-monitor run --email-server smtp.gmail.com --email-user user@gmail.com --email-pass password

# Customize thresholds
uvx traffic-monitor run --discord <webhook_url> --limit 1000 --interval 50 --critical 85

# Install as system service
sudo uvx traffic-monitor run --discord <webhook_url> --install

# Check current status
uvx traffic-monitor status

# View configuration
uvx traffic-monitor config-show
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

## Configuration

Configuration is automatically created when you first run the application. You can also manually edit `~/.config/traffic-monitor/settings.toml`:

```toml
[thresholds]
total_limit = 2000          # Total traffic limit in GB
interval = 100              # Alert interval in GB
critical_percentage = 90    # Critical threshold percentage

[notifiers.email]
enabled = true
smtp_server = "smtp.example.com"
smtp_port = 587
username = "your_username"
password = "your_password"
sender = "traffic-monitor@example.com"
recipients = ["admin@example.com"]
use_tls = true

[notifiers.discord]
enabled = true
webhook_url = ""            # Discord webhook URL
username = "Traffic Monitor"

[monitor]
check_interval = 300        # Check interval in seconds

[monitor.reporting]
enable_startup_notification = true
enable_daily_report = true
daily_report_hour = 8

[action]
delay_seconds = 60
force = false
```

## Getting Discord Webhook URL

1. Go to your Discord server
2. Server Settings → Integrations → Webhooks
3. Create New Webhook
4. Copy the Webhook URL
5. Use it with `--discord <webhook_url>`

## License

MIT 
