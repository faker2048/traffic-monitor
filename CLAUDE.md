# CLAUDE.md

This file provides guidance when working with code in this repository.

## Commands

### Build & Run
```bash
# Build the project
cargo build

# Run in development mode
cargo run -- run --limit 2048 --once

# Run the release binary directly
./target/release/traffic_monitor run --limit 2048 --discord <webhook_url> --once
```

### Installation
```bash
# Build release binary
cargo build --release

# Install as systemd service (requires sudo)
sudo ./target/release/traffic_monitor run --limit 2048 --discord <webhook_url> --install
```

### Testing
```bash
# Run all tests
cargo test

# Run a specific test
cargo test data_provider::tests::test_parse_monthly_usage
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

# Uninstall service (requires sudo)
sudo ./target/release/traffic_monitor uninstall
```

### CLI Commands
```bash
# Show current traffic status
./target/release/traffic_monitor status

# Show configuration
./target/release/traffic_monitor config-show

# Show notification state (what thresholds have been notified)
./target/release/traffic_monitor state

# Reset notification state (for testing or new month)
./target/release/traffic_monitor reset-state

# Service management help
./target/release/traffic_monitor service
```

## Architecture

### Core Components (Rust)

**Main Application** (`src/main.rs`):
- CLI parsing using `clap` and main coordination.
- Handles service install/uninstall and configuration loading/saving.
- Sets up logging and initializes the monitor loop.

**Traffic Monitor** (`src/monitor.rs`):
- Core monitoring logic with warning interval checks and critical threshold checks.
- Manages startup notifications, daily reports, and system actions.
- Keeps track of state to prevent redundant notifications.

**Data Provider** (`src/data_provider.rs`):
- Interacts with the `vnstat` CLI tool.
- Parses monthly and daily network traffic statistics from the output.
- Converts units (GiB, MiB, KiB, TiB) consistently to GB.

**Configuration** (`src/config.rs`):
- Hierarchical configuration structure mapped from `settings.toml` via `serde` and `toml`.
- Includes thresholds, notifier options (email/discord), monitoring parameters, and action parameters.

**Notification System** (`src/notifier.rs`):
- Discord webhook integration using `ureq` and `serde_json`.
- SMTP email notifications via the `lettre` crate.
- `MultiNotifier` composite allowing multiple channels to be notified simultaneously.

**Action System** (`src/action.rs`):
- Executes system shutdown when the critical threshold is exceeded.
- Configurable delay and force options.

**State Manager** (`src/state_manager.rs`):
- Manages persistent storage of notification states in `~/.config/traffic-monitor/state.json`.
- Resets month-specific counters and flags on month transitions.