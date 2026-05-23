use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use chrono::Local;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct State {
    pub version: String,
    pub last_updated: String,
    pub current_month: String,
    pub notified_thresholds: Vec<u64>,
    pub critical_notification_sent: bool,
    pub last_daily_report_date: Option<String>,
}

impl Default for State {
    fn default() -> Self {
        let now = Local::now();
        Self {
            version: "1.0".to_string(),
            last_updated: now.to_rfc3339(),
            current_month: now.format("%Y-%m").to_string(),
            notified_thresholds: Vec::new(),
            critical_notification_sent: false,
            last_daily_report_date: None,
        }
    }
}

pub struct StateManager {
    state_file: PathBuf,
    state: State,
}

fn get_home_dir() -> Option<PathBuf> {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .ok()
        .map(PathBuf::from)
}

impl StateManager {
    pub fn new(state_file: Option<PathBuf>) -> Result<Self, Box<dyn std::error::Error>> {
        let path = match state_file {
            Some(p) => p,
            None => {
                let home = get_home_dir().ok_or("Cannot find home directory")?;
                home.join(".config").join("traffic-monitor").join("state.json")
            }
        };

        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let mut manager = Self {
            state_file: path,
            state: State::default(),
        };

        manager.load_state()?;
        Ok(manager)
    }

    fn load_state(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        if !self.state_file.exists() {
            self.state = State::default();
            self.save_state()?;
            return Ok(());
        }

        let content = fs::read_to_string(&self.state_file)?;
        match serde_json::from_str::<State>(&content) {
            Ok(loaded_state) => {
                self.state = self.validate_state(loaded_state);
            }
            Err(_) => {
                self.state = State::default();
                self.save_state()?;
            }
        }
        Ok(())
    }

    fn validate_state(&self, mut state: State) -> State {
        let now = Local::now();
        let current_month = now.format("%Y-%m").to_string();

        if state.current_month != current_month {
            state.current_month = current_month;
            state.notified_thresholds.clear();
            state.critical_notification_sent = false;
            state.last_daily_report_date = None;
        }

        state
    }

    fn save_state(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        self.state.last_updated = Local::now().to_rfc3339();
        let content = serde_json::to_string_pretty(&self.state)?;
        fs::write(&self.state_file, content)?;
        Ok(())
    }

    pub fn get_notified_thresholds(&self) -> &[u64] {
        &self.state.notified_thresholds
    }

    pub fn add_notified_threshold(&mut self, threshold: u64) -> Result<(), Box<dyn std::error::Error>> {
        if !self.state.notified_thresholds.contains(&threshold) {
            self.state.notified_thresholds.push(threshold);
            self.state.notified_thresholds.sort();
            self.save_state()?;
        }
        Ok(())
    }

    pub fn is_critical_notification_sent(&self) -> bool {
        self.state.critical_notification_sent
    }

    pub fn set_critical_notification_sent(&mut self, sent: bool) -> Result<(), Box<dyn std::error::Error>> {
        self.state.critical_notification_sent = sent;
        self.save_state()?;
        Ok(())
    }

    pub fn get_last_daily_report_date(&self) -> Option<&str> {
        self.state.last_daily_report_date.as_deref()
    }

    pub fn set_last_daily_report_date(&mut self, date_str: String) -> Result<(), Box<dyn std::error::Error>> {
        self.state.last_daily_report_date = Some(date_str);
        self.save_state()?;
        Ok(())
    }

    pub fn reset_monthly_state(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        let now = Local::now();
        self.state.current_month = now.format("%Y-%m").to_string();
        self.state.notified_thresholds.clear();
        self.state.critical_notification_sent = false;
        self.state.last_daily_report_date = None;
        self.save_state()?;
        Ok(())
    }

    pub fn get_state(&self) -> &State {
        &self.state
    }

    pub fn get_state_file_path(&self) -> &Path {
        &self.state_file
    }
}
