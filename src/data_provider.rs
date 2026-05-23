use std::process::Command;
use std::collections::HashMap;
use log::{debug, error, warn};
use regex::Regex;
use chrono::Local;
use serde::Deserialize;

#[derive(Deserialize, Debug)]
struct VnStatOutput {
    interfaces: Vec<Interface>,
}

#[derive(Deserialize, Debug)]
struct Interface {
    name: String,
    traffic: Traffic,
}

#[derive(Deserialize, Debug)]
struct Traffic {
    #[serde(default)]
    month: Vec<MonthData>,
    #[serde(default)]
    day: Vec<DayData>,
}

#[derive(Deserialize, Debug)]
struct MonthData {
    date: MonthDate,
    rx: u64,
    tx: u64,
}

#[derive(Deserialize, Debug)]
struct MonthDate {
    year: i32,
    month: u32,
}

#[derive(Deserialize, Debug)]
struct DayData {
    date: DayDate,
    rx: u64,
    tx: u64,
}

#[derive(Deserialize, Debug)]
struct DayDate {
    year: i32,
    month: u32,
    day: u32,
}

pub struct VnStatDataProvider {
    interface: Option<String>,
}

fn is_safe_interface(iface: &str) -> bool {
    if iface.is_empty() {
        return false;
    }
    // Limit to safe characters to prevent argument/command injection
    iface.chars().all(|c| c.is_ascii_alphanumeric() || c == '.' || c == '-' || c == '_')
}

impl VnStatDataProvider {
    pub fn new(interface: Option<String>) -> Result<Self, Box<dyn std::error::Error>> {
        let provider = Self { interface };
        provider.verify_vnstat()?;
        Ok(provider)
    }

    fn verify_vnstat(&self) -> Result<(), Box<dyn std::error::Error>> {
        let output = Command::new("vnstat")
            .arg("--version")
            .output();
        match output {
            Ok(out) if out.status.success() => Ok(()),
            _ => {
                error!("vnstat is not installed or not in PATH");
                Err("vnstat not installed or not in PATH".into())
            }
        }
    }

    fn run_vnstat_command(&self, args: &[&str]) -> Result<String, Box<dyn std::error::Error>> {
        let mut cmd = Command::new("vnstat");
        if let Some(ref iface) = self.interface {
            if !is_safe_interface(iface) {
                return Err(format!("Unsafe interface name configured: {}", iface).into());
            }
            cmd.arg("-i").arg(iface);
        }
        cmd.args(args);

        debug!("Running command: vnstat {:?}", args);
        let output = cmd.output()?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            error!("vnstat command failed: {}", stderr);
            return Err(format!("vnstat command failed: {}", stderr).into());
        }

        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }

    #[allow(dead_code)]
    pub fn parse_size_to_gb(&self, size_str: &str) -> f64 {
        // Parse size string e.g. "10.5 GiB" or "800 MiB"
        let re = match Regex::new(r"([\d.]+)\s+(\w+)") {
            Ok(r) => r,
            Err(e) => {
                error!("Failed to compile regex: {}", e);
                return 0.0;
            }
        };

        if let Some(caps) = re.captures(size_str) {
            let val_str = caps.get(1).map_or("0.0", |m| m.as_str());
            let unit = caps.get(2).map_or("", |m| m.as_str()).to_lowercase();

            let val: f64 = val_str.parse().unwrap_or(0.0);
            if unit.contains("gib") {
                val
            } else if unit.contains("mib") {
                val / 1024.0
            } else if unit.contains("kib") {
                val / (1024.0 * 1024.0)
            } else if unit.contains("tib") {
                val * 1024.0
            } else {
                warn!("Unknown unit in size string: {}", size_str);
                val
            }
        } else {
            warn!("Failed to parse size string: {}", size_str);
            0.0
        }
    }

    pub fn get_current_month_usage(&self) -> Result<f64, Box<dyn std::error::Error>> {
        let output = self.run_vnstat_command(&["--json", "m"])?;
        debug!("vnstat --json m output:\n{}", output);

        let now = Local::now();
        let current_month = now.format("%Y-%m").to_string();
        self.parse_monthly_usage_from_output(&output, &current_month)
    }

    pub fn parse_monthly_usage_from_output(&self, output: &str, current_month: &str) -> Result<f64, Box<dyn std::error::Error>> {
        let parts: Vec<&str> = current_month.split('-').collect();
        if parts.len() != 2 {
            return Err("Invalid current_month format".into());
        }
        let target_year: i32 = parts[0].parse()?;
        let target_month: u32 = parts[1].parse()?;

        let data: VnStatOutput = match serde_json::from_str(output) {
            Ok(d) => d,
            Err(e) => {
                if output.contains("No data") {
                    debug!("vnstat database has no data yet.");
                    return Ok(0.0);
                }
                return Err(e.into());
            }
        };

        let interface = if let Some(ref iface) = self.interface {
            data.interfaces.iter().find(|i| &i.name == iface)
        } else {
            data.interfaces.first()
        };

        let interface = match interface {
            Some(i) => i,
            None => {
                debug!("No matching interface found in vnstat output.");
                return Ok(0.0);
            }
        };

        let month_data = interface.traffic.month.iter().find(|m| {
            m.date.year == target_year && m.date.month == target_month
        });

        match month_data {
            Some(m) => {
                let total_bytes = m.rx + m.tx;
                let total_gb = total_bytes as f64 / (1024.0 * 1024.0 * 1024.0);
                debug!("Found current month ({}) usage: {} GB", current_month, total_gb);
                Ok(total_gb)
            }
            None => {
                debug!("No usage data found for month {} in vnstat output.", current_month);
                Ok(0.0)
            }
        }
    }

    pub fn get_daily_usage(&self, _days: u32) -> Result<HashMap<String, f64>, Box<dyn std::error::Error>> {
        let output = self.run_vnstat_command(&["--json", "d"])?;
        self.parse_daily_usage_from_output(&output)
    }

    pub fn parse_daily_usage_from_output(&self, output: &str) -> Result<HashMap<String, f64>, Box<dyn std::error::Error>> {
        let data: VnStatOutput = match serde_json::from_str(output) {
            Ok(d) => d,
            Err(e) => {
                if output.contains("No data") {
                    debug!("vnstat database has no data yet.");
                    return Ok(HashMap::new());
                }
                return Err(e.into());
            }
        };

        let interface = if let Some(ref iface) = self.interface {
            data.interfaces.iter().find(|i| &i.name == iface)
        } else {
            data.interfaces.first()
        };

        let interface = match interface {
            Some(i) => i,
            None => {
                debug!("No matching interface found in vnstat output.");
                return Ok(HashMap::new());
            }
        };

        let mut daily_usage = HashMap::new();
        for d in &interface.traffic.day {
            let date_str = format!("{:04}-{:02}-{:02}", d.date.year, d.date.month, d.date.day);
            let total_bytes = d.rx + d.tx;
            let total_gb = total_bytes as f64 / (1024.0 * 1024.0 * 1024.0);
            daily_usage.insert(date_str, total_gb);
        }

        Ok(daily_usage)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_size_to_gb() {
        let provider = VnStatDataProvider { interface: None };
        assert_eq!(provider.parse_size_to_gb("10.5 GiB"), 10.5);
        assert_eq!(provider.parse_size_to_gb("800 MiB"), 800.0 / 1024.0);
        assert_eq!(provider.parse_size_to_gb("1024 KiB"), 1024.0 / (1024.0 * 1024.0));
        assert_eq!(provider.parse_size_to_gb("2.5 TiB"), 2.5 * 1024.0);
        assert_eq!(provider.parse_size_to_gb("0 GiB"), 0.0);
    }

    #[test]
    fn test_parse_monthly_usage() {
        let provider = VnStatDataProvider { interface: None };
        let sample = r#"{
            "interfaces": [
                {
                    "name": "ens5",
                    "traffic": {
                        "month": [
                            {
                                "date": { "year": 2025, "month": 4 },
                                "rx": 55268207206,
                                "tx": 54468207207
                            }
                        ]
                    }
                }
            ]
        }"#;

        let usage = provider.parse_monthly_usage_from_output(sample, "2025-04").unwrap();
        assert!((usage - 102.20).abs() < 1e-5);
    }

    #[test]
    fn test_parse_daily_usage() {
        let provider = VnStatDataProvider { interface: None };
        let sample = r#"{
            "interfaces": [
                {
                    "name": "ens5",
                    "traffic": {
                        "day": [
                            {
                                "date": { "year": 2025, "month": 4, "day": 11 },
                                "rx": 5148592046,
                                "tx": 5148592046
                            },
                            {
                                "date": { "year": 2025, "month": 4, "day": 12 },
                                "rx": 4445291151,
                                "tx": 4445291152
                            }
                        ]
                    }
                }
            ]
        }"#;

        let daily = provider.parse_daily_usage_from_output(sample).unwrap();
        assert!((daily.get("2025-04-11").unwrap() - 9.59).abs() < 1e-5);
        assert!((daily.get("2025-04-12").unwrap() - 8.28).abs() < 1e-5);
    }

    #[test]
    fn test_parse_monthly_usage_no_data() {
        let provider = VnStatDataProvider { interface: None };
        let sample = " eth0: No data. Timestamp of last update is same 2026-05-24 00:32:18 as of database creation.";
        let usage = provider.parse_monthly_usage_from_output(sample, "2026-05").unwrap();
        assert_eq!(usage, 0.0);
    }

    #[test]
    fn test_parse_daily_usage_no_data() {
        let provider = VnStatDataProvider { interface: None };
        let sample = " eth0: No data. Timestamp of last update is same 2026-05-24 00:32:18 as of database creation.";
        let daily = provider.parse_daily_usage_from_output(sample).unwrap();
        assert!(daily.is_empty());
    }
}

