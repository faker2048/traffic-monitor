# Traffic Monitor

A Rust application that monitors network traffic usage (using vnstat) for various cloud and data center environments. It helps prevent excessive data transfer costs by sending staged email notifications or discord messages at specified intervals, and automatically shuts down the system when a critical threshold is reached.

## 🚀 Quick Start (One Command Setup)

### Remote one-liner (recommended, x86_64 Linux)

Downloads the latest prebuilt binary from GitHub Releases, installs vnstat if missing,
and (when extra args are passed) registers a systemd service in one shot:

```bash
# Install binary + set up systemd service with 2TB limit + Discord notifications
curl -fsSL https://raw.githubusercontent.com/faker2048/traffic-monitor/master/install.sh \
  | sudo bash -s -- \
      --discord https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN \
      --limit 2048
```

Or just install the binary without configuring the service:

```bash
curl -fsSL https://raw.githubusercontent.com/faker2048/traffic-monitor/master/install.sh | sudo bash
sudo traffic-monitor status
```

### Build from source

```bash
sudo apt install vnstat
git clone https://github.com/faker2048/traffic-monitor.git
cd traffic-monitor
cargo build --release

sudo ./target/release/traffic_monitor run \
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
- Cross-platform support (Linux, Windows with WSL)

## Requirements

- Rust (cargo) to build the binary
- vnstat
- SMTP server (for email) or Discord webhook URL (for Discord notifications)

## Installation & Usage

### 1. Install vnstat (System Dependency)
```bash
# Ubuntu/Debian
sudo apt install vnstat

# CentOS/RHEL
sudo yum install vnstat
```

Ensure the vnstat daemon is enabled and running:
```bash
sudo systemctl enable vnstat
sudo systemctl start vnstat
```

### 2. Build and Run the Traffic Monitor

```bash
# Clone the repository
git clone https://github.com/faker2048/traffic-monitor.git
cd traffic-monitor

# Build the release profile
cargo build --release

# Basic usage: 2TB limit with Discord notifications
./target/release/traffic_monitor run --discord https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN --limit 2048

# AWS Lightsail optimized: 1TB limit, alerts every 50GB, shutdown at 95%
./target/release/traffic_monitor run --discord https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN --limit 1024 --interval 50 --critical 95

# Install as system service for auto-start on boot (requires sudo)
sudo ./target/release/traffic_monitor run --discord https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN --limit 2048 --install

# Run with email notifications instead of Discord
./target/release/traffic_monitor run \
  --email-server smtp.gmail.com \
  --email-user your-email@gmail.com \
  --email-pass your-app-password \
  --email-sender traffic-monitor@yourdomain.com \
  --email-recipients admin@yourdomain.com \
  --limit 2048

# Check current traffic status
./target/release/traffic_monitor status

# View configuration
./target/release/traffic_monitor config-show
```

### Parameter Explanation:
- `--limit 2048`: Total traffic limit of 2048GB (2TB). This counts **both inbound and outbound traffic combined**
- `--interval 100`: Send alert notifications every 100GB of usage
- `--critical 90`: Trigger shutdown when reaching 90% of total limit (1843GB in this example)
- `--no-shutdown`: Disable system shutdown even when the critical limit is exceeded (only sends notifications)
- `--discord`: Discord webhook URL for notifications
- `--install`: Install as systemd service with auto-start on boot
- `--once`: Run the checks once and exit (perfect for cron)

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
sudo ./target/release/traffic_monitor uninstall
```

## Configuration

Configuration is automatically created at `~/.config/traffic-monitor/settings.toml` when you first run the application. You can also manually edit it:

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
disable_shutdown = false
```

## License

MIT
