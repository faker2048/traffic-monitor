#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import subprocess
import platform
import time
from typing import Optional, List

from ..config.settings import ActionConfig


class ShutdownAction:
    """
    Action to shutdown the system when traffic limits are reached.
    
    This class implements a cross-platform shutdown mechanism that works
    on Linux, Windows, and macOS.
    """
    
    def __init__(self, config: Optional[ActionConfig] = None, delay_seconds: int = 60, force: bool = False) -> None:
        """
        Initialize the shutdown action.
        
        Args:
            config: Configuration for shutdown action
            delay_seconds: Delay in seconds before shutdown is executed (used if config is None)
            force: Whether to force the shutdown (used if config is None)
        """
        self.logger = logging.getLogger(__name__)
        
        # Use config if provided, otherwise use parameters
        if config is not None:
            self.delay_seconds = config.delay_seconds
            self.force = config.force
        else:
            self.delay_seconds = delay_seconds
            self.force = force
            
        self.system = platform.system().lower()
        
        self.logger.info(
            f"Initialized ShutdownAction for {self.system} with "
            f"{self.delay_seconds}s delay, force={self.force}"
        )
    
    def _get_shutdown_command(self) -> List[str]:
        """
        Get the appropriate shutdown command for the current operating system.
        
        Returns:
            List containing the shutdown command and arguments
        """
        if self.system == "linux":
            cmd = ["shutdown"]
            if self.force:
                cmd.append("-f")
            cmd.extend(["-h", f"+{self.delay_seconds // 60}"])
            
        elif self.system == "windows":
            cmd = ["shutdown", "/s"]
            if self.force:
                cmd.append("/f")
            cmd.extend(["/t", str(self.delay_seconds)])
            
        elif self.system == "darwin":  # macOS
            cmd = ["shutdown", "-h"]
            delay_mins = max(1, self.delay_seconds // 60)  # At least 1 minute
            cmd.append(f"+{delay_mins}")
            
        else:
            self.logger.error(f"Unsupported operating system: {self.system}")
            raise NotImplementedError(f"Shutdown not implemented for {self.system}")
            
        return cmd
    
    def execute(self) -> bool:
        """
        Execute the shutdown action.
        
        Returns:
            True if the shutdown command was executed successfully, False otherwise
        """
        try:
            cmd = self._get_shutdown_command()
            self.logger.critical(f"Executing shutdown command: {' '.join(cmd)}")
            
            # Log countdown message
            self.logger.warning(
                f"System will shutdown in {self.delay_seconds} seconds due to "
                "traffic limit being reached"
            )
            
            # Execute the shutdown command
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False  # Don't raise an exception on non-zero exit code
            )
            
            if result.returncode != 0:
                self.logger.error(
                    f"Shutdown command failed with code {result.returncode}: {result.stderr}"
                )
                return False
            
            self.logger.info("Shutdown command executed successfully")
            return True
            
        except Exception as e:
            self.logger.exception(f"Failed to execute shutdown action: {e}")
            return False


class MockShutdownAction(ShutdownAction):
    """
    Mock implementation of ShutdownAction for testing purposes.
    
    This class logs the shutdown action but doesn't actually shut down the system.
    """
    
    def execute(self) -> bool:
        """
        Simulate a shutdown action without actually shutting down.
        
        Returns:
            True to indicate successful simulation
        """
        try:
            cmd = self._get_shutdown_command()
            self.logger.warning(
                f"[MOCK] Would execute shutdown command: {' '.join(cmd)}"
            )
            
            self.logger.warning(
                f"[MOCK] System would shutdown in {self.delay_seconds} seconds "
                "due to traffic limit being reached"
            )
            
            # Simulate a delay
            self.logger.info("[MOCK] Simulating shutdown in 5 seconds...")
            for i in range(5, 0, -1):
                self.logger.info(f"[MOCK] Shutdown in {i}...")
                time.sleep(1)
                
            self.logger.critical("[MOCK] Shutdown action completed (system not actually shutdown)")
            return True
            
        except Exception as e:
            self.logger.exception(f"Failed to execute mock shutdown action: {e}")
            return False 