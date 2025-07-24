# Traffic Monitor

A Python application that monitors network traffic usage (using vnstat) for various cloud and data center environments. It helps prevent excessive data transfer costs by sending staged email notifications or discord messages at specified intervals, and automatically shuts down the system when a critical threshold is reached.

## 🚀 Quick Start (One Command Setup)

```bash
# Install vnstat (one-time setup)
sudo apt install vnstat && sudo vnstat -u -i $(ip route | grep default | awk '{print $5}' | head -1)

# Run with 2TB limit and Discord notifications (replace YOUR_WEBHOOK_URL)
uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor run \
  --discord https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN \
  --limit 2048 \
  --install
```

Perfect for:
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

#### Direct from GitHub (No local installation needed)

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

3. Run directly from GitHub with complete example:
   ```bash
   # Run with Discord webhook and 2TB limit (2048GB total inbound+outbound traffic)
   # Perfect for AWS Lightsail which counts both incoming and outgoing traffic
   uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor run \
     --discord https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN \
     --limit 2048 \
     --interval 100 \
     --critical 90
   ```

4. Install as system service (auto-start on boot):
   ```bash
   # Install service that automatically starts on system boot
   sudo uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor run \
     --discord https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN \
     --limit 2048 \
     --install
   ```

#### Parameter Explanation:
- `--limit 2048`: Total traffic limit of 2048GB (2TB). This counts **both inbound and outbound traffic combined**
- `--interval 100`: Send alert notifications every 100GB of usage
- `--critical 90`: Trigger shutdown when reaching 90% of total limit (1843GB in this example)
- `--discord`: Discord webhook URL for notifications
- `--install`: Install as systemd service with auto-start on boot

### Cloud Provider Specific Setup

#### AWS Lightsail (Recommended settings)
```bash
# Lightsail counts both inbound and outbound traffic
# 1TB plan with 5% safety margin and frequent alerts
sudo uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor run \
  --discord https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN \
  --limit 1024 \
  --interval 50 \
  --critical 95 \
  --install
```

#### AWS EC2 (Data Transfer Out focus)
```bash
# EC2 typically charges for outbound traffic only
# 2TB conservative limit with standard intervals
sudo uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor run \
  --discord https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN \
  --limit 2048 \
  --interval 100 \
  --critical 90 \
  --install
```

#### Other Cloud Providers
- **Alibaba Cloud/Tencent Cloud**: Usually count both inbound and outbound
- **DigitalOcean**: Check your specific plan's bandwidth limits
- **Vultr/Linode**: Most plans include generous bandwidth allowances

**Important Notes:**
- `--limit 2048` = 2048GB total bandwidth (inbound + outbound combined)
- Lightsail plans typically count ALL traffic toward your monthly allowance
- EC2 free tier includes 1GB outbound per month, paid plans vary by region

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

### Remote Usage Examples (Recommended)

```bash
# Basic usage: 2TB limit with Discord notifications
uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor run \
  --discord https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN \
  --limit 2048

# AWS Lightsail optimized: 1TB limit, alerts every 50GB, shutdown at 95%
uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor run \
  --discord https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN \
  --limit 1024 \
  --interval 50 \
  --critical 95

# Install as system service for AWS EC2/Lightsail
sudo uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor run \
  --discord https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN \
  --limit 2048 \
  --interval 100 \
  --install

# Run with email notifications instead of Discord
uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor run \
  --email-server smtp.gmail.com \
  --email-user your-email@gmail.com \
  --email-pass your-app-password \
  --email-sender traffic-monitor@yourdomain.com \
  --email-recipients admin@yourdomain.com,ops@yourdomain.com \
  --limit 2048

# Check current traffic status (after installation)
uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor status

# View current configuration
uvx --from git+https://github.com/faker2048/traffic-monitor traffic-monitor config-show
```

### Local Installation Usage

```bash
# If you have installed locally
traffic-monitor run --discord <webhook_url> --limit 2048

# Install as service locally
sudo traffic-monitor run --discord <webhook_url> --limit 2048 --install

# Check status locally
traffic-monitor status
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
