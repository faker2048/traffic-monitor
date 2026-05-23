use std::collections::HashMap;
use log::{debug, error, info, warn};
use chrono::Local;
use serde_json::json;

use crate::config::{DiscordConfig, EmailConfig};

pub trait Notifier: Send + Sync {
    fn notify(&self, subject: &str, message: &str, level: &str) -> bool;
}

pub struct DiscordNotifier {
    config: DiscordConfig,
}

impl DiscordNotifier {
    pub fn new(config: DiscordConfig) -> Self {
        Self { config }
    }

    fn get_level_emoji(&self, level: &str) -> &'static str {
        match level.to_lowercase().as_str() {
            "info" => "📊",
            "warning" => "⚠️",
            "critical" => "🚨",
            _ => "📢",
        }
    }

    fn get_additional_emojis(&self, level: &str, message: &str) -> HashMap<&'static str, &'static str> {
        let mut emojis = HashMap::new();

        if message.to_lowercase().contains("traffic") {
            emojis.insert("traffic", "🚦");
        }
        if message.to_lowercase().contains("limit") {
            emojis.insert("limit", "🔄");
        }
        if message.to_lowercase().contains("threshold") {
            emojis.insert("threshold", "📈");
        }

        match level.to_lowercase().as_str() {
            "info" => {
                emojis.insert("status", "✅");
            }
            "warning" => {
                emojis.insert("status", "⚠️");
            }
            "critical" => {
                emojis.insert("status", "❌");
            }
            _ => {}
        }

        emojis.insert("time", "⏰");
        emojis
    }
}

impl Notifier for DiscordNotifier {
    fn notify(&self, subject: &str, message: &str, level: &str) -> bool {
        if !self.config.enabled {
            debug!("Discord notifications are disabled, skipping");
            return false;
        }

        if self.config.webhook_url.contains("your-webhook-url") {
            warn!("Using example webhook URL. This will likely fail to send notifications.");
        }

        let colors = {
            let mut m = HashMap::new();
            m.insert("info", 3447003);     // Blue
            m.insert("warning", 16098851); // Orange/Yellow
            m.insert("critical", 15746887); // Red
            m
        };
        let color = colors.get(level.to_lowercase().as_str()).copied().unwrap_or(3447003);
        let level_emoji = self.get_level_emoji(level);
        let emojis = self.get_additional_emojis(level, message);

        let time_emoji = emojis.get("time").copied().unwrap_or("⏰");
        let time_str = format!("{} {}", time_emoji, Local::now().format("%Y-%m-%d %H:%M:%S"));

        let mut formatted_message = message.replace("\n\n", "\n");
        let emoji_subject = format!("{} {}", level_emoji, subject);

        if !self.config.message_template.is_empty() {
            let traffic_emoji = emojis.get("traffic").copied().unwrap_or("");
            let status_emoji = emojis.get("status").copied().unwrap_or("");

            formatted_message = self.config.message_template
                .replace("{message}", &formatted_message)
                .replace("{level_emoji}", level_emoji)
                .replace("{traffic_emoji}", traffic_emoji)
                .replace("{time}", &time_str)
                .replace("{status_emoji}", status_emoji);
        } else {
            let status_emoji = emojis.get("status").copied().unwrap_or("");
            formatted_message = format!("{}\n\n{} Status as of {}", formatted_message, status_emoji, time_str);
        }

        let traffic_icon = emojis.get("traffic").copied().unwrap_or("🚦");
        let payload = json!({
            "username": self.config.username,
            "avatar_url": if self.config.avatar_url.trim().is_empty() { None } else { Some(&self.config.avatar_url) },
            "embeds": [{
                "title": emoji_subject,
                "description": formatted_message,
                "color": color,
                "footer": {
                    "text": format!("Traffic Monitor {} | {} {}", traffic_icon, level.to_uppercase(), level_emoji)
                },
                "timestamp": Local::now().to_rfc3339()
            }]
        });

        debug!("Sending Discord webhook payload...");
        match ureq::post(&self.config.webhook_url)
            .set("Content-Type", "application/json")
            .timeout(std::time::Duration::from_secs(10))
            .send_json(payload)
        {
            Ok(resp) => {
                if resp.status() == 200 || resp.status() == 204 {
                    info!("Sent {} Discord notification with subject '{}'", level, subject);
                    true
                } else {
                    error!("Failed to send Discord notification: HTTP {} - {}", resp.status(), resp.into_string().unwrap_or_default());
                    false
                }
            }
            Err(e) => {
                error!("Network error sending Discord notification: {}", e);
                false
            }
        }
    }
}

pub struct EmailNotifier {
    config: EmailConfig,
}

impl EmailNotifier {
    pub fn new(config: EmailConfig) -> Result<Self, Box<dyn std::error::Error>> {
        if config.smtp_server.is_empty() || config.smtp_port == 0 || config.sender.is_empty() || config.recipients.is_empty() {
            return Err("Missing required email configuration".into());
        }
        Ok(Self { config })
    }
}

impl Notifier for EmailNotifier {
    fn notify(&self, subject: &str, message: &str, level: &str) -> bool {
        if !self.config.enabled {
            debug!("Email notifications are disabled, skipping");
            return false;
        }

        if self.config.recipients.is_empty() {
            warn!("No recipients configured, skipping email notification");
            return false;
        }

        let color = match level.to_lowercase().as_str() {
            "info" => "#2196F3",
            "warning" => "#FF9800",
            "critical" => "#F44336",
            _ => "#2196F3",
        };

        let formatted_message = message.replace("\n", "<br>");
        let html_content = format!(
            r#"<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .message {{ padding: 20px; border-left: 4px solid {}; background-color: #f8f8f8; }}
        .footer {{ font-size: 12px; color: #666; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="message">
        {}
    </div>
    <div class="footer">
        This is an automated message from the Traffic Monitor system.
    </div>
</body>
</html>"#,
            color, formatted_message
        );

        use lettre::message::{MultiPart, SinglePart, Mailbox};
        use lettre::{Message, SmtpTransport, Transport};
        use lettre::transport::smtp::authentication::Credentials;

        let parsed_sender = match self.config.sender.parse::<Mailbox>() {
            Ok(s) => s,
            Err(e) => {
                error!("Invalid email sender format: {}", e);
                return false;
            }
        };

        let mut builder = Message::builder().from(parsed_sender);
        for rec in &self.config.recipients {
            match rec.parse::<Mailbox>() {
                Ok(r) => {
                    builder = builder.to(r);
                }
                Err(e) => {
                    error!("Invalid email recipient format '{}': {}", rec, e);
                    return false;
                }
            }
        }

        let email_msg = match builder
            .subject(subject)
            .multipart(
                MultiPart::alternative()
                    .singlepart(SinglePart::plain(message.to_string()))
                    .singlepart(SinglePart::html(html_content))
            )
        {
            Ok(msg) => msg,
            Err(e) => {
                error!("Failed to build email message: {}", e);
                return false;
            }
        };

        let creds = Credentials::new(self.config.username.clone(), self.config.password.clone());

        // Connect and send
        let transport_res = if self.config.use_tls {
            // Port 465 SSL/TLS connection
            SmtpTransport::relay(&self.config.smtp_server)
                .map(|t| t.port(self.config.smtp_port).credentials(creds).build())
        } else {
            // Port 587 STARTTLS or unencrypted connection
            SmtpTransport::starttls_relay(&self.config.smtp_server)
                .map(|t| t.port(self.config.smtp_port).credentials(creds).build())
        };

        let transport = match transport_res {
            Ok(t) => t,
            Err(e) => {
                error!("Failed to construct SMTP transport: {}", e);
                return false;
            }
        };

        match transport.send(&email_msg) {
            Ok(_) => {
                info!("Sent {} email notification with subject '{}' to {} recipients", level, subject, self.config.recipients.len());
                true
            }
            Err(e) => {
                error!("Failed to send email via SMTP: {}", e);
                false
            }
        }
    }
}

pub struct MultiNotifier {
    notifiers: Vec<Box<dyn Notifier>>,
}

impl MultiNotifier {
    pub fn new() -> Self {
        Self { notifiers: Vec::new() }
    }

    pub fn add_notifier(&mut self, notifier: Box<dyn Notifier>) {
        self.notifiers.push(notifier);
    }
}

impl Notifier for MultiNotifier {
    fn notify(&self, subject: &str, message: &str, level: &str) -> bool {
        if self.notifiers.is_empty() {
            warn!("No notifiers configured, skipping notification");
            return false;
        }

        let mut success = false;
        for notifier in &self.notifiers {
            if notifier.notify(subject, message, level) {
                success = true;
            }
        }
        success
    }
}
