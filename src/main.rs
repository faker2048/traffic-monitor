use clap::{Parser, Subcommand};
use log::{info, error, LevelFilter};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::fs;

mod config;
mod data_provider;
mod state_manager;
mod notifier;
mod action;
mod monitor;

use config::{AppConfig, load_settings, save_settings};
use data_provider::VnStatDataProvider;
use state_manager::StateManager;
use notifier::{DiscordNotifier, EmailNotifier, MultiNotifier};

use action::ShutdownAction;
use monitor::TrafficMonitor;

const SERVICE_NAME: &str = "traffic-monitor";
const DEFAULT_CONFIG_DIR_NAME: &str = "traffic-monitor";
const DEFAULT_CONFIG_FILE_NAME: &str = "settings.toml";

#[cfg(unix)]
unsafe extern "C" {
    fn geteuid() -> u32;
}

fn check_root() -> bool {
    #[cfg(unix)]
    unsafe { geteuid() == 0 }
    #[cfg(not(unix))]
    false
}

fn get_default_config_path() -> Option<PathBuf> {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .ok()
        .map(|h| PathBuf::from(h).join(".config").join(DEFAULT_CONFIG_DIR_NAME).join(DEFAULT_CONFIG_FILE_NAME))
}

#[derive(Parser, Debug)]
#[command(name = "traffic-monitor", version, about = "Traffic Monitor - Network traffic monitoring and alerting system")]
struct Cli {
    #[arg(short, long, default_value = "info", global = true)]
    log_level: String,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug, Clone)]
enum Commands {

    /// Run the traffic monitor
    Run {
        #[arg(long)]
        discord: Option<String>,

        #[arg(long)]
        email_server: Option<String>,

        #[arg(long)]
        email_user: Option<String>,

        #[arg(long)]
        email_pass: Option<String>,

        #[arg(long)]
        email_sender: Option<String>,

        #[arg(long)]
        email_recipients: Option<String>,

        #[arg(long)]
        limit: Option<u64>,

        #[arg(long)]
        interval: Option<u64>,

        #[arg(long)]
        critical: Option<u8>,

        #[arg(long)]
        config: Option<PathBuf>,

        #[arg(long)]
        install: bool,

        /// Run the checks once and exit (perfect for cron)
        #[arg(long)]
        once: bool,

        /// Disable system shutdown when critical threshold is exceeded
        #[arg(long)]
        no_shutdown: bool,
    },
    /// Show current traffic status
    Status {
        #[arg(long)]
        config: Option<PathBuf>,
    },
    /// Manage system service commands help
    Service,
    /// Uninstall system service (requires sudo)
    Uninstall,
    /// Show current configuration
    ConfigShow {
        #[arg(long)]
        config: Option<PathBuf>,
    },
    /// Show current notification state
    State,
    /// Reset notification state (useful for testing or new month)
    ResetState,
}

fn setup_logging(log_level: &str) {
    let mut builder = env_logger::Builder::new();
    let level = match log_level.to_lowercase().as_str() {
        "debug" => LevelFilter::Debug,
        "info" => LevelFilter::Info,
        "warning" => LevelFilter::Warn,
        "error" => LevelFilter::Error,
        _ => LevelFilter::Info,
    };
    builder.filter(None, level);
    builder.format_timestamp_secs();
    builder.init();
}

fn install_systemd_service(config_path: &Path) -> Result<(), Box<dyn std::error::Error>> {
    use std::process::Command;

    if !check_root() {
        return Err("Service installation requires sudo privileges. Please run with sudo.".into());
    }

    let current_exe = std::env::current_exe()?;
    let exe_str = current_exe.to_str().ok_or("Cannot convert executable path to string")?;
    let config_str = config_path.to_str().ok_or("Cannot convert config path to string")?;

    let service_content = format!(
        "[Unit]\n\
         Description=Traffic Monitor Service (Rust)\n\
         After=network.target\n\
         Wants=network-online.target\n\n\
         [Service]\n\
         Type=simple\n\
         User=root\n\
         ExecStart={} run --config {}\n\
         Restart=on-failure\n\
         RestartSec=30\n\n\
         [Install]\n\
         WantedBy=multi-user.target\n",
        exe_str, config_str
    );

    let service_file = format!("/etc/systemd/system/{}.service", SERVICE_NAME);
    fs::write(&service_file, service_content)?;

    println!("Reloading systemd...");
    Command::new("systemctl").arg("daemon-reload").status()?;

    println!("Enabling service...");
    Command::new("systemctl").arg("enable").arg(SERVICE_NAME).status()?;

    println!("Starting service...");
    Command::new("systemctl").arg("start").arg(SERVICE_NAME).status()?;

    println!("✅ Service installed and started successfully!");
    println!("   Service file: {}", service_file);
    println!("   Config file: {}", config_str);
    println!("\nService management commands:");
    println!("   sudo systemctl status {}", SERVICE_NAME);
    println!("   sudo systemctl stop {}", SERVICE_NAME);
    println!("   sudo systemctl restart {}", SERVICE_NAME);
    println!("   sudo journalctl -u {} -f", SERVICE_NAME);

    Ok(())
}

fn uninstall_systemd_service() -> Result<(), Box<dyn std::error::Error>> {
    use std::process::Command;

    if !check_root() {
        return Err("Service uninstallation requires sudo privileges. Please run with sudo.".into());
    }

    let service_file = format!("/etc/systemd/system/{}.service", SERVICE_NAME);

    println!("Stopping service...");
    let _ = Command::new("systemctl").arg("stop").arg(SERVICE_NAME).status();

    println!("Disabling service...");
    let _ = Command::new("systemctl").arg("disable").arg(SERVICE_NAME).status();

    if Path::new(&service_file).exists() {
        println!("Removing service file...");
        fs::remove_file(&service_file)?;
    }

    println!("Reloading systemd...");
    Command::new("systemctl").arg("daemon-reload").status()?;

    println!("✅ Service uninstalled successfully!");
    Ok(())
}

fn main() {
    let cli = Cli::parse();
    setup_logging(&cli.log_level);

    if let Err(e) = run_app(cli) {
        error!("Fatal error: {}", e);
        std::process::exit(1);
    }
}

fn run_app(cli: Cli) -> Result<(), Box<dyn std::error::Error>> {
    match cli.command {
        Commands::Run {
            discord,
            email_server,
            email_user,
            email_pass,
            email_sender,
            email_recipients,
            limit,
            interval,
            critical,
            config,
            install,
            once,
            no_shutdown,
        } => {
            let config_path = match config {
                Some(p) => p,
                None => get_default_config_path().ok_or("Cannot determine default config path")?,
            };

            // Create config if not exists or override parameters are passed
            if !config_path.exists()
                || discord.is_some()
                || email_server.is_some()
                || limit.is_some()
                || interval.is_some()
                || critical.is_some()
                || no_shutdown
            {
                info!("Creating configuration file at {:?}", config_path);
                let mut app_config = AppConfig::default();

                if let Some(ref d) = discord {
                    app_config.notifiers.discord.enabled = true;
                    app_config.notifiers.discord.webhook_url = d.clone();
                    app_config.notifiers.email.enabled = false;
                }

                if let Some(ref es) = email_server {
                    app_config.notifiers.email.enabled = true;
                    app_config.notifiers.email.smtp_server = es.clone();
                    if let Some(ref eu) = email_user {
                        app_config.notifiers.email.username = eu.clone();
                    }
                    if let Some(ref ep) = email_pass {
                        app_config.notifiers.email.password = ep.clone();
                    }
                    if let Some(ref s) = email_sender {
                        app_config.notifiers.email.sender = s.clone();
                    }
                    if let Some(ref er) = email_recipients {
                        app_config.notifiers.email.recipients = er.split(',').map(|s| s.trim().to_string()).collect();
                    }
                }

                if let Some(l) = limit {
                    app_config.thresholds.total_limit = l;
                }
                if let Some(i) = interval {
                    app_config.thresholds.interval = i;
                }
                if let Some(c) = critical {
                    app_config.thresholds.critical_percentage = c;
                }
                if no_shutdown {
                    app_config.action.disable_shutdown = true;
                }

                save_settings(&app_config, &config_path)?;
                info!("✅ Configuration saved.");
            }

            if install {
                install_systemd_service(&config_path)?;
                return Ok(());
            }

            // Load settings
            let app_config = load_settings(&config_path)?;

            if !app_config.notifiers.email.enabled && !app_config.notifiers.discord.enabled {
                return Err("No notification methods enabled. Please configure email or Discord.".into());
            }

            // Initialize components
            let mut multi_notifier = MultiNotifier::new();

            if app_config.notifiers.email.enabled {
                info!("Email notifications enabled");
                let email_notifier = EmailNotifier::new(app_config.notifiers.email.clone())?;
                multi_notifier.add_notifier(Box::new(email_notifier));
            }

            if app_config.notifiers.discord.enabled {
                info!("Discord notifications enabled");
                let discord_notifier = DiscordNotifier::new(app_config.notifiers.discord.clone());
                multi_notifier.add_notifier(Box::new(discord_notifier));
            }

            let notifier = Arc::new(multi_notifier);
            let action = Arc::new(ShutdownAction::new(app_config.action.clone()));
            let data_provider = VnStatDataProvider::new(app_config.monitor.interface.clone())?;
            let state_manager = StateManager::new(None)?;

            let mut monitor = TrafficMonitor::new(
                app_config.thresholds.clone(),
                notifier,
                action,
                app_config.monitor.clone(),
                data_provider,
                state_manager,
            );

            if once {
                monitor.run_once()?;
            } else {
                monitor.run_loop()?;
            }
        }
        Commands::Status { config } => {
            let config_path = match config {
                Some(p) => p,
                None => get_default_config_path().ok_or("Cannot determine default config path")?,
            };

            let app_config = load_settings(&config_path)?;
            let data_provider = VnStatDataProvider::new(app_config.monitor.interface.clone())?;
            
            let current_usage = data_provider.get_current_month_usage()?;
            let percentage = (current_usage / app_config.thresholds.total_limit as f64) * 100.0;
            let critical_threshold = (app_config.thresholds.total_limit * app_config.thresholds.critical_percentage as u64) as f64 / 100.0;

            println!("📊 Traffic Monitor Status");
            println!("   Current Usage: {:.2}GB / {}GB ({:.1}%)", current_usage, app_config.thresholds.total_limit, percentage);
            println!("   Critical Threshold: {:.2}GB ({}%)", critical_threshold, app_config.thresholds.critical_percentage);

            if current_usage >= critical_threshold {
                println!("   🔴 Status: CRITICAL - Shutdown threshold exceeded!");
            } else if percentage > 70.0 {
                println!("   🟡 Status: WARNING - High usage");
            } else {
                println!("   🟢 Status: OK");
            }
        }
        Commands::Service => {
            println!("Service management commands:");
            println!("   sudo systemctl status {}", SERVICE_NAME);
            println!("   sudo systemctl stop {}", SERVICE_NAME);
            println!("   sudo systemctl start {}", SERVICE_NAME);
            println!("   sudo systemctl restart {}", SERVICE_NAME);
            println!("   sudo journalctl -u {} -f", SERVICE_NAME);
        }
        Commands::Uninstall => {
            uninstall_systemd_service()?;
        }
        Commands::ConfigShow { config } => {
            let config_path = match config {
                Some(p) => p,
                None => get_default_config_path().ok_or("Cannot determine default config path")?,
            };

            if !config_path.exists() {
                return Err(format!("Configuration file not found: {:?}", config_path).into());
            }

            let content = fs::read_to_string(config_path)?;
            println!("{}", content);
        }
        Commands::State => {
            let state_manager = StateManager::new(None)?;
            let state = state_manager.get_state();
            println!("📊 Traffic Monitor State");
            println!("   State file: {:?}", state_manager.get_state_file_path());
            println!("   Current month: {}", state.current_month);
            println!("   Notified thresholds: {:?}", state.notified_thresholds);
            println!("   Critical notification sent: {}", state.critical_notification_sent);
            println!("   Last daily report: {:?}", state.last_daily_report_date);
            println!("   Last updated: {}", state.last_updated);
        }
        Commands::ResetState => {
            let mut state_manager = StateManager::new(None)?;
            state_manager.reset_monthly_state()?;
            println!("✅ Notification state has been reset.");
        }
    }
    Ok(())
}
