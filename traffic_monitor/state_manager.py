#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class StateManager:
    """
    Manages persistent state for the traffic monitor to avoid duplicate notifications
    after service restarts.
    """
    
    def __init__(self, state_file: Optional[str] = None):
        """
        Initialize the state manager.
        
        Args:
            state_file: Path to the state file. If None, uses default location.
        """
        self.logger = logging.getLogger(__name__)
        
        # Default state file location
        if state_file is None:
            state_dir = Path.home() / ".config" / "traffic-monitor"
            state_dir.mkdir(parents=True, exist_ok=True)
            self.state_file = state_dir / "state.json"
        else:
            self.state_file = Path(state_file)
            
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize state
        self.state = self._load_state()
        
    def _load_state(self) -> Dict[str, Any]:
        """Load state from file."""
        if not self.state_file.exists():
            self.logger.debug(f"State file not found, creating new state: {self.state_file}")
            return self._create_default_state()
            
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            self.logger.debug(f"Loaded state from {self.state_file}")
            return self._validate_state(state)
            
        except Exception as e:
            self.logger.error(f"Error loading state file {self.state_file}: {e}")
            self.logger.info("Creating new state file")
            return self._create_default_state()
    
    def _create_default_state(self) -> Dict[str, Any]:
        """Create default state structure."""
        return {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "current_month": datetime.now().strftime("%Y-%m"),
            "notified_thresholds": [],
            "critical_notification_sent": False,
            "last_daily_report_date": None
        }
    
    def _validate_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and migrate state if necessary."""
        current_month = datetime.now().strftime("%Y-%m")
        
        # If it's a new month, reset notification states
        if state.get("current_month") != current_month:
            self.logger.info(f"New month detected ({current_month}), resetting notification states")
            state["current_month"] = current_month
            state["notified_thresholds"] = []
            state["critical_notification_sent"] = False
            state["last_daily_report_date"] = None
            
        # Ensure all required fields exist
        default_state = self._create_default_state()
        for key, default_value in default_state.items():
            if key not in state:
                state[key] = default_value
                
        return state
    
    def _save_state(self) -> None:
        """Save current state to file."""
        try:
            self.state["last_updated"] = datetime.now().isoformat()
            
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
                
            self.logger.debug(f"Saved state to {self.state_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving state to {self.state_file}: {e}")
    
    def get_notified_thresholds(self) -> List[int]:
        """Get list of thresholds that have already been notified."""
        return self.state.get("notified_thresholds", [])
    
    def add_notified_threshold(self, threshold: int) -> None:
        """Add a threshold to the notified list."""
        thresholds = self.state.get("notified_thresholds", [])
        if threshold not in thresholds:
            thresholds.append(threshold)
            thresholds.sort()  # Keep sorted for easier debugging
            self.state["notified_thresholds"] = thresholds
            self._save_state()
            self.logger.debug(f"Added threshold {threshold}GB to notified list")
    
    def is_critical_notification_sent(self) -> bool:
        """Check if critical notification has been sent."""
        return self.state.get("critical_notification_sent", False)
    
    def set_critical_notification_sent(self, sent: bool = True) -> None:
        """Set critical notification sent status."""
        self.state["critical_notification_sent"] = sent
        self._save_state()
        self.logger.debug(f"Set critical notification sent: {sent}")
    
    def get_last_daily_report_date(self) -> Optional[str]:
        """Get the date of the last daily report sent."""
        return self.state.get("last_daily_report_date")
    
    def set_last_daily_report_date(self, date_str: str) -> None:
        """Set the date of the last daily report sent."""
        self.state["last_daily_report_date"] = date_str
        self._save_state()
        self.logger.debug(f"Set last daily report date: {date_str}")
    
    def reset_monthly_state(self) -> None:
        """Reset state for a new month (useful for testing or manual reset)."""
        current_month = datetime.now().strftime("%Y-%m")
        self.state["current_month"] = current_month
        self.state["notified_thresholds"] = []
        self.state["critical_notification_sent"] = False
        self.state["last_daily_report_date"] = None
        self._save_state()
        self.logger.info("Reset monthly notification state")
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of current state for debugging."""
        return {
            "state_file": str(self.state_file),
            "current_month": self.state.get("current_month"),
            "notified_thresholds": self.state.get("notified_thresholds", []),
            "critical_notification_sent": self.state.get("critical_notification_sent", False),
            "last_daily_report_date": self.state.get("last_daily_report_date"),
            "last_updated": self.state.get("last_updated")
        }