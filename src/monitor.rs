use std::sync::Arc;
use std::thread;
use std::time::Duration;
use chrono::{Local, Datelike, NaiveDate, Duration as ChronoDuration, Timelike};
use log::{info, debug, error};


use crate::config::{ThresholdConfig, MonitorConfig};
use crate::data_provider::VnStatDataProvider;
use crate::state_manager::StateManager;
use crate::notifier::Notifier;
use crate::action::Action;

pub struct TrafficMonitor {
    threshold_config: ThresholdConfig,
    notifier: Arc<dyn Notifier>,
    action: Arc<dyn Action>,
    monitor_config: MonitorConfig,
    data_provider: VnStatDataProvider,
    state_manager: StateManager,
    
    total_limit: f64, // GB
    interval: f64,    // GB
    critical_threshold: f64, // GB
}

impl TrafficMonitor {
    pub fn new(
        threshold_config: ThresholdConfig,
        notifier: Arc<dyn Notifier>,
        action: Arc<dyn Action>,
        monitor_config: MonitorConfig,
        data_provider: VnStatDataProvider,
        state_manager: StateManager,
    ) -> Self {
        let total_limit = threshold_config.total_limit as f64;
        let interval = threshold_config.interval as f64;
        let critical_percentage = threshold_config.critical_percentage as f64;
        let critical_threshold = (total_limit * critical_percentage) / 100.0;

        info!(
            "Initialized TrafficMonitor with total limit: {}GB, interval: {}GB, critical threshold: {}GB ({}%)",
            total_limit, interval, critical_threshold, threshold_config.critical_percentage
        );

        Self {
            threshold_config,
            notifier,
            action,
            monitor_config,
            data_provider,
            state_manager,
            total_limit,
            interval,
            critical_threshold,
        }
    }

    fn should_notify(&self, current_usage: f64) -> Option<u64> {
        let notified = self.state_manager.get_notified_thresholds();
        let max_steps = (self.total_limit / self.interval) as u64;

        for i in 1..=max_steps {
            let threshold = i * (self.interval as u64);
            if current_usage >= (threshold as f64) && !notified.contains(&threshold) {
                return Some(threshold);
            }
        }
        None
    }

    fn is_critical(&self, current_usage: f64) -> bool {
        current_usage >= self.critical_threshold
    }

    fn get_status_summary(&self, current_usage: f64) -> String {
        let percentage = (current_usage / self.total_limit) * 100.0;
        let now = Local::now();

        // Calculate next threshold
        let mut next_threshold = 0.0;
        let max_steps = (self.total_limit / self.interval) as u64;
        for i in 1..=max_steps {
            let threshold = (i * (self.interval as u64)) as f64;
            if current_usage < threshold {
                next_threshold = threshold;
                break;
            }
        }

        // Calculate remaining to critical
        let remaining_to_critical = if current_usage < self.critical_threshold {
            self.critical_threshold - current_usage
        } else {
            0.0
        };

        // Remaining days in month
        let current_year = now.year();
        let current_month = now.month();
        let next_month = if current_month == 12 { 1 } else { current_month + 1 };
        let next_year = if current_month == 12 { current_year + 1 } else { current_year };
        
        let next_month_date = NaiveDate::from_ymd_opt(next_year, next_month, 1).unwrap_or_default();
        let today_date = now.date_naive();
        let remaining_days = (next_month_date - today_date).num_days();

        // Estimate daily average
        let daily_average = if now.day() > 0 { current_usage / (now.day() as f64) } else { current_usage };
        let estimated_end_of_month = current_usage + (daily_average * (remaining_days as f64));

        let mut summary = format!(
            "Traffic Monitoring System Status Report\n\n\
             Current Traffic Usage Summary:\n\
             ----------------------\n\
             Current Date: {}\n\
             Current Month Usage: {:.2}GB / {}GB ({:.1}%)\n",
            now.format("%Y-%m-%d %H:%M:%S"),
            current_usage,
            self.total_limit,
            percentage
        );

        if current_usage >= self.critical_threshold {
            summary.push_str("⚠️ Warning: Shutdown threshold exceeded!\n");
        }

        summary.push_str(&format!(
            "\nDaily Average Usage: {:.2}GB/day\n\
             Remaining Days in Month: {} days\n\
             Estimated Month-End Total: {:.2}GB\n",
            daily_average, remaining_days, estimated_end_of_month
        ));

        if next_threshold > 0.0 {
            summary.push_str(&format!(
                "\nTraffic until next threshold ({:.0}GB): {:.2}GB",
                next_threshold,
                next_threshold - current_usage
            ));
        }

        if remaining_to_critical > 0.0 {
            summary.push_str(&format!(
                "\nTraffic until shutdown threshold ({:.2}GB): {:.2}GB",
                self.critical_threshold, remaining_to_critical
            ));
        }

        if self.monitor_config.reporting.include_traffic_trend {
            if let Ok(daily_usage) = self.data_provider.get_daily_usage(7) {
                if !daily_usage.is_empty() {
                    summary.push_str("\n\nLast 7 Days Traffic Trend:");
                    for i in (1..=7).rev() {
                        let date = (now - ChronoDuration::days(i)).format("%Y-%m-%d").to_string();
                        let usage = daily_usage.get(&date).copied().unwrap_or(0.0);
                        summary.push_str(&format!("\n- {}: {:.2}GB", date, usage));
                    }
                }
            }
        }

        summary.push_str(&format!(
            "\n\nTraffic Monitor Settings:\n\
             ----------------------\n\
             Total Traffic Limit: {}GB\n\
             Warning Threshold Interval: Warning sent every {}GB\n\
             Shutdown Threshold: {:.2}GB ({}%)\n\
             Check Interval: {} seconds\n\n\
             This is an automated notification email, please do not reply.\n",
            self.total_limit,
            self.interval,
            self.critical_threshold,
            self.threshold_config.critical_percentage,
            self.monitor_config.check_interval
        ));

        summary
    }

    fn get_daily_report(&self) -> String {
        let now = Local::now();
        let current_usage = self.data_provider.get_current_month_usage().unwrap_or(0.0);
        let yesterday = now - ChronoDuration::days(1);
        let yesterday_str = yesterday.format("%Y-%m-%d").to_string();

        let daily_usage = self.data_provider.get_daily_usage(30).unwrap_or_default();
        let yesterday_usage = daily_usage.get(&yesterday_str).copied().unwrap_or(0.0);

        let daily_average = if now.day() > 0 { current_usage / (now.day() as f64) } else { current_usage };
        
        let current_year = now.year();
        let current_month = now.month();
        let next_month = if current_month == 12 { 1 } else { current_month + 1 };
        let next_year = if current_month == 12 { current_year + 1 } else { current_year };
        let next_month_date = NaiveDate::from_ymd_opt(next_year, next_month, 1).unwrap_or_default();
        let today_date = now.date_naive();
        let remaining_days = (next_month_date - today_date).num_days();

        let estimated_end_of_month = current_usage + (daily_average * (remaining_days as f64));
        let percentage = (current_usage / self.total_limit) * 100.0;

        let mut report = format!(
            "Traffic Monitoring System - Daily Traffic Report\n\n\
             Date: {}\n\n\
             Yesterday's Traffic Usage:\n\
             ----------------------\n\
             Yesterday's Total Usage: {:.2}GB\n",
            now.format("%Y-%m-%d"),
            yesterday_usage
        );

        if yesterday_usage > daily_average * 1.5 {
            report.push_str("⚠️ Yesterday's traffic was high!\n");
        }

        report.push_str(&format!(
            "\nCurrent Month Cumulative Traffic Usage:\n\
             ----------------------\n\
             Current Month Total: {:.2}GB / {}GB ({:.1}%)\n\
             Daily Average Usage: {:.2}GB/day\n\
             Remaining Days: {} days\n\
             Month-End Estimate: {:.2}GB\n",
            current_usage, self.total_limit, percentage, daily_average, remaining_days, estimated_end_of_month
        ));

        if self.monitor_config.reporting.include_traffic_trend && !daily_usage.is_empty() {
            report.push_str("\nTraffic Trend:\n----------------------\nLast 7 Days Traffic Trend:\n");
            for i in (1..=7).rev() {
                let date = (now - ChronoDuration::days(i)).format("%Y-%m-%d").to_string();
                let usage = daily_usage.get(&date).copied().unwrap_or(0.0);
                report.push_str(&format!("- {}: {:.2}GB\n", date, usage));
            }
        }

        if percentage > 70.0 {
            report.push_str(&format!("\n⚠️ Warning: Current traffic has used {:.1}% of monthly quota!\n", percentage));
        }

        if estimated_end_of_month > self.total_limit {
            report.push_str("\n⚠️ Warning: At current usage rate, you will exceed your total traffic limit this month!\n");
        }

        if current_usage >= self.critical_threshold {
            report.push_str(&format!(
                "\n🔴 Critical Warning: Shutdown threshold reached ({}%)! System may shut down at any time.\n",
                self.threshold_config.critical_percentage
            ));
        }

        report.push_str("\nThis is an automated traffic report, please do not reply.");
        report
    }

    pub fn send_startup_notification(&self) {
        if !self.monitor_config.reporting.enable_startup_notification {
            info!("Startup notification disabled in configuration");
            return;
        }

        match self.data_provider.get_current_month_usage() {
            Ok(current_usage) => {
                let summary = self.get_status_summary(current_usage);
                let mut level = "info";
                if current_usage >= self.critical_threshold {
                    level = "critical";
                } else if current_usage >= self.total_limit * 0.7 {
                    level = "warning";
                }

                let percentage = (current_usage / self.total_limit) * 100.0;
                let subject = format!(
                    "Traffic Monitoring System Started - Current Usage: {:.2}GB ({:.1}%)",
                    current_usage, percentage
                );

                self.notifier.notify(&subject, &summary, level);
                info!("System startup notification sent");
            }
            Err(e) => {
                error!("Error sending startup notification: {}", e);
            }
        }
    }

    pub fn send_daily_report(&mut self) {
        if !self.monitor_config.reporting.enable_daily_report {
            return;
        }

        let now = Local::now();
        let today_str = now.format("%Y-%m-%d").to_string();

        if let Some(last_report) = self.state_manager.get_last_daily_report_date() {
            if last_report == today_str {
                return; // Already sent today
            }
        }

        if now.hour() == self.monitor_config.reporting.daily_report_hour {
            match self.data_provider.get_current_month_usage() {
                Ok(current_usage) => {
                    let report_body = self.get_daily_report();
                    let mut level = "info";
                    if current_usage >= self.critical_threshold {
                        level = "critical";
                    } else if current_usage >= self.total_limit * 0.7 {
                        level = "warning";
                    }

                    let percentage = (current_usage / self.total_limit) * 100.0;
                    let subject = format!(
                        "Traffic Daily Report - {} - Usage: {:.2}GB ({:.1}%)",
                        today_str, current_usage, percentage
                    );

                    if self.notifier.notify(&subject, &report_body, level) {
                        if let Err(e) = self.state_manager.set_last_daily_report_date(today_str) {
                            error!("Failed to save daily report date to state: {}", e);
                        }
                        info!("Daily traffic report sent");
                    }
                }
                Err(e) => {
                    error!("Error sending daily report: {}", e);
                }
            }
        }
    }

    pub fn check_traffic(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        let current_usage = self.data_provider.get_current_month_usage()?;
        debug!("Current month usage: {}GB", current_usage);

        // Check if we need to send daily report
        self.send_daily_report();

        // Check warning interval thresholds
        while let Some(threshold) = self.should_notify(current_usage) {
            info!("Threshold reached: {}GB", threshold);
            let subject = format!("Traffic Alert: {}GB threshold reached", threshold);
            let message = format!(
                "Your network traffic has reached {}GB out of your {}GB limit. Current usage: {:.2}GB.",
                threshold, self.total_limit, current_usage
            );

            self.notifier.notify(&subject, &message, "warning");
            self.state_manager.add_notified_threshold(threshold)?;
        }

        // Check critical threshold
        if self.is_critical(current_usage) && !self.state_manager.is_critical_notification_sent() {
            error!("Critical threshold reached: {:.2}GB exceeds {}GB", current_usage, self.critical_threshold);
            let subject = "CRITICAL: Traffic Limit Nearly Exceeded - System Shutdown Imminent";
            let message = format!(
                "CRITICAL WARNING: Your network traffic has reached {:.2}GB, \
                 which exceeds the critical threshold of {:.2}GB ({}% of your {}GB limit). \
                 The system will now shutdown to prevent exceeding your limit.",
                current_usage,
                self.critical_threshold,
                self.threshold_config.critical_percentage,
                self.total_limit
            );

            self.notifier.notify(subject, &message, "critical");
            self.state_manager.set_critical_notification_sent(true)?;

            error!("Executing shutdown action");
            self.action.execute();
        }

        Ok(())
    }

    pub fn run_once(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        info!("Running traffic monitor single check...");
        self.check_traffic()?;
        Ok(())
    }

    pub fn run_loop(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        info!("Starting traffic monitoring with {}s interval", self.monitor_config.check_interval);

        self.send_startup_notification();

        let sleep_duration = Duration::from_secs(self.monitor_config.check_interval);
        loop {
            if let Err(e) = self.check_traffic() {
                error!("Error during traffic check: {}", e);
            }
            thread::sleep(sleep_duration);
        }
    }
}
