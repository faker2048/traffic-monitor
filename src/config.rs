use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DiscordConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_discord_webhook")]
    pub webhook_url: String,
    #[serde(default = "default_discord_username")]
    pub username: String,
    #[serde(default = "default_discord_avatar")]
    pub avatar_url: String,
    #[serde(default = "default_discord_template")]
    pub message_template: String,
}

fn default_discord_webhook() -> String {
    "https://discord.com/api/webhooks/your-webhook-url".to_string()
}
fn default_discord_username() -> String {
    "Traffic Monitor".to_string()
}
fn default_discord_avatar() -> String {
    "https://example.com/traffic-monitor-icon.png".to_string()
}
fn default_discord_template() -> String {
    "**Traffic Alert**: {message}".to_string()
}

impl Default for DiscordConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            webhook_url: default_discord_webhook(),
            username: default_discord_username(),
            avatar_url: default_discord_avatar(),
            message_template: default_discord_template(),
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct EmailConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_email_server")]
    pub smtp_server: String,
    #[serde(default = "default_email_port")]
    pub smtp_port: u16,
    #[serde(default = "default_email_user")]
    pub username: String,
    #[serde(default = "default_email_pass")]
    pub password: String,
    #[serde(default = "default_email_sender")]
    pub sender: String,
    #[serde(default = "default_email_recipients")]
    pub recipients: Vec<String>,
    #[serde(default = "default_true")]
    pub use_tls: bool,
}

fn default_true() -> bool {
    true
}
fn default_email_server() -> String {
    "smtp.example.com".to_string()
}
fn default_email_port() -> u16 {
    587
}
fn default_email_user() -> String {
    "your_username".to_string()
}
fn default_email_pass() -> String {
    "your_password".to_string()
}
fn default_email_sender() -> String {
    "traffic-monitor@example.com".to_string()
}
fn default_email_recipients() -> Vec<String> {
    vec!["admin@example.com".to_string()]
}

impl Default for EmailConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            smtp_server: default_email_server(),
            smtp_port: default_email_port(),
            username: default_email_user(),
            password: default_email_pass(),
            sender: default_email_sender(),
            recipients: default_email_recipients(),
            use_tls: true,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct NotifiersConfig {
    #[serde(default)]
    pub email: EmailConfig,
    #[serde(default)]
    pub discord: DiscordConfig,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ThresholdConfig {
    #[serde(default = "default_total_limit")]
    pub total_limit: u64, // GB
    #[serde(default = "default_interval")]
    pub interval: u64, // GB
    #[serde(default = "default_critical_percentage")]
    pub critical_percentage: u8,
}

fn default_total_limit() -> u64 {
    2000
}
fn default_interval() -> u64 {
    100
}
fn default_critical_percentage() -> u8 {
    90
}

impl Default for ThresholdConfig {
    fn default() -> Self {
        Self {
            total_limit: default_total_limit(),
            interval: default_interval(),
            critical_percentage: default_critical_percentage(),
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ActionConfig {
    #[serde(default = "default_delay_seconds")]
    pub delay_seconds: u64,
    #[serde(default)]
    pub force: bool,
    #[serde(default)]
    pub disable_shutdown: bool,
}

fn default_delay_seconds() -> u64 {
    60
}

impl Default for ActionConfig {
    fn default() -> Self {
        Self {
            delay_seconds: default_delay_seconds(),
            force: false,
            disable_shutdown: false,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ReportConfig {
    #[serde(default = "default_true")]
    pub enable_startup_notification: bool,
    #[serde(default = "default_true")]
    pub enable_daily_report: bool,
    #[serde(default = "default_daily_report_hour")]
    pub daily_report_hour: u32,
    #[serde(default = "default_true")]
    pub include_traffic_trend: bool,
    #[serde(default = "default_true")]
    pub include_daily_breakdown: bool,
}

fn default_daily_report_hour() -> u32 {
    8
}

impl Default for ReportConfig {
    fn default() -> Self {
        Self {
            enable_startup_notification: true,
            enable_daily_report: true,
            daily_report_hour: default_daily_report_hour(),
            include_traffic_trend: true,
            include_daily_breakdown: true,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MonitorConfig {
    #[serde(default = "default_check_interval")]
    pub check_interval: u64,
    #[serde(default)]
    pub interface: Option<String>,
    #[serde(default)]
    pub reporting: ReportConfig,
}

fn default_check_interval() -> u64 {
    300
}

impl Default for MonitorConfig {
    fn default() -> Self {
        Self {
            check_interval: default_check_interval(),
            interface: None,
            reporting: ReportConfig::default(),
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct AppConfig {
    #[serde(default)]
    pub thresholds: ThresholdConfig,
    #[serde(default)]
    pub notifiers: NotifiersConfig,
    #[serde(default)]
    pub monitor: MonitorConfig,
    #[serde(default)]
    pub action: ActionConfig,
}

pub fn load_settings<P: AsRef<Path>>(config_path: P) -> Result<AppConfig, Box<dyn std::error::Error>> {
    let content = fs::read_to_string(config_path)?;
    let config: AppConfig = toml::from_str(&content)?;
    Ok(config)
}

pub fn save_settings<P: AsRef<Path>>(config: &AppConfig, output_path: P) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(parent) = output_path.as_ref().parent() {
        fs::create_dir_all(parent)?;
    }
    let content = toml::to_string_pretty(config)?;
    fs::write(output_path, content)?;
    Ok(())
}

#[allow(dead_code)]
pub fn create_default_config<P: AsRef<Path>>(output_path: P) -> Result<(), Box<dyn std::error::Error>> {
    let config = AppConfig::default();
    save_settings(&config, output_path)?;
    Ok(())
}

