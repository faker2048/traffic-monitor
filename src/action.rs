use log::{error, info, warn};
use std::process::Command;
use crate::config::ActionConfig;

pub trait Action: Send + Sync {
    fn execute(&self) -> bool;
}

pub struct ShutdownAction {
    config: ActionConfig,
    os: &'static str,
}

impl ShutdownAction {
    pub fn new(config: ActionConfig) -> Self {
        Self {
            config,
            os: std::env::consts::OS,
        }
    }

    fn get_shutdown_command(&self) -> Result<Vec<String>, Box<dyn std::error::Error>> {
        let mut cmd = Vec::new();
        match self.os {
            "linux" => {
                cmd.push("shutdown".to_string());
                if self.config.force {
                    cmd.push("-f".to_string());
                }
                cmd.push("-h".to_string());
                cmd.push(format!("+{}", self.config.delay_seconds / 60));
            }
            "windows" => {
                cmd.push("shutdown".to_string());
                cmd.push("/s".to_string());
                if self.config.force {
                    cmd.push("/f".to_string());
                }
                cmd.push("/t".to_string());
                cmd.push(self.config.delay_seconds.to_string());
            }
            "macos" => {
                cmd.push("shutdown".to_string());
                cmd.push("-h".to_string());
                let delay_mins = std::cmp::max(1, self.config.delay_seconds / 60);
                cmd.push(format!("+{}", delay_mins));
            }
            _ => {
                error!("Unsupported operating system: {}", self.os);
                return Err(format!("Shutdown not implemented for {}", self.os).into());
            }
        }
        Ok(cmd)
    }
}

impl Action for ShutdownAction {
    fn execute(&self) -> bool {
        if self.config.disable_shutdown {
            warn!("Traffic limit reached critical threshold, but shutdown action is disabled in configuration. Skipping shutdown.");
            return true;
        }

        let cmd_args = match self.get_shutdown_command() {
            Ok(c) => c,
            Err(e) => {
                error!("Failed to generate shutdown command: {}", e);
                return false;
            }
        };

        if cmd_args.is_empty() {
            error!("Generated shutdown command is empty");
            return false;
        }

        let cmd_name = &cmd_args[0];
        let args = &cmd_args[1..];

        error!("Executing shutdown command: {} {}", cmd_name, args.join(" "));
        warn!(
            "System will shutdown in {} seconds due to traffic limit being reached",
            self.config.delay_seconds
        );


        let output = Command::new(cmd_name)
            .args(args)
            .output();

        match output {
            Ok(out) => {
                if out.status.success() {
                    info!("Shutdown command executed successfully");
                    true
                } else {
                    let stderr = String::from_utf8_lossy(&out.stderr);
                    error!("Shutdown command failed with exit code: {:?}", out.status.code());
                    error!("Stderr: {}", stderr);
                    false
                }
            }
            Err(e) => {
                error!("Failed to execute shutdown process: {}", e);
                false
            }
        }
    }
}
