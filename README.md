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

1. Clone and install:
   ```
   git clone https://github.com/faker2048/traffic-monitor.git
   cd traffic-monitor
   pip install -r requirements.txt
   ```

2. Install vnstat:
   - Ubuntu/Debian: `sudo apt install vnstat`
   - CentOS/RHEL: `sudo yum install vnstat`
   - macOS: `brew install vnstat`
   - Windows: Requires WSL

3. Configure vnstat:
   ```
   sudo vnstat -u -i YOUR_INTERFACE
   sudo systemctl enable vnstat
   sudo systemctl start vnstat
   ```

## Configuration

Edit `config/settings.toml`:

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
interface = ""              # Network interface (empty = default)

[monitor.reporting]
enable_startup_notification = true
enable_daily_report = true
daily_report_hour = 8

[action]
delay_seconds = 60
force = false
```

## Usage

Run the monitor:

```
python main.py [--config PATH] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
```

## Service Setup (Linux)

Create `/etc/systemd/system/traffic-monitor.service`:

```
[Unit]
Description=Traffic Monitor Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/traffic-monitor
ExecStart=/usr/bin/python3 /path/to/traffic-monitor/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:
```
sudo systemctl enable traffic-monitor
sudo systemctl start traffic-monitor
```

## License

MIT 
