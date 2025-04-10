# Traffic Monitor

A Python application that monitors network traffic usage (using vnstat), sends staged email notifications at specified intervals, and automatically shuts down the system when a critical threshold is reached.

## Features

- Monitors network traffic using vnstat
- Sends email notifications at configurable traffic thresholds
- Automatically shuts down the system when critical traffic threshold is reached
- Modular design for easy extension and customization
- Cross-platform support (Linux, Windows, macOS)

## Requirements

- Python 3.6+
- vnstat installed and properly configured
- SMTP server for email notifications

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/faker2048/traffic-monitor.git
   cd traffic-monitor
   ```

2. Install required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Make sure vnstat is installed and working on your system:
   - Ubuntu/Debian: `sudo apt install vnstat`
   - CentOS/RHEL: `sudo yum install vnstat`
   - macOS (via Homebrew): `brew install vnstat`
   - Windows: Unsupported natively (requires WSL)

4. Configure vnstat for your network interface:
   ```
   sudo vnstat -u -i YOUR_INTERFACE
   sudo systemctl enable vnstat
   sudo systemctl start vnstat
   ```

## Configuration

Edit the `config/settings.yaml` file to match your requirements:

```yaml
thresholds:
  total_limit: 2000       # Total traffic limit in GB (2TB)
  interval: 100           # Alert interval in GB
  critical_percentage: 90 # Critical threshold percentage

email:
  smtp_server: smtp.example.com
  smtp_port: 587
  username: your_username
  password: your_password
  sender: traffic-monitor@example.com
  recipients:
    - admin@example.com
```

## Usage

Run the traffic monitor:

```
python main.py
```

Options:
- `--config`: Path to the configuration file (default: `config/settings.yaml`)
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

Example:
```
python main.py --config /path/to/config.yaml --log-level DEBUG
```

## Service Setup (Linux)

To run as a systemd service on Linux:

1. Create a systemd service file:
   ```
   sudo nano /etc/systemd/system/traffic-monitor.service
   ```

2. Add the following content:
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

3. Enable and start the service:
   ```
   sudo systemctl enable traffic-monitor
   sudo systemctl start traffic-monitor
   ```

## Extending the Application

The application follows a modular design that makes it easy to extend:

- **Data Providers**: Implement a custom data provider by creating a new class in the `data_providers` directory.
- **Notifiers**: Create custom notification methods by implementing a new notifier in the `notifiers` directory.
- **Actions**: Define custom actions by implementing a new action class in the `actions` directory.

## License

MIT 
