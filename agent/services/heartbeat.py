"""
Heartbeat Sender - Send periodic heartbeats to server.
Vietnam ONLY - Clean implementation.
"""

import logging
import platform
import threading
from typing import Dict, Optional

import psutil
import requests

from shared.time_utils import now, now_iso, sleep
from shared.os_info import get_os_details

logger = logging.getLogger("services.heartbeat")


class HeartbeatSender:
    """Sends periodic heartbeats to server."""
    
    def __init__(self, config: Dict):
        """
        Initialize heartbeat sender.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.heartbeat_config = config.get("heartbeat", {})
        self.server_config = config.get("server", {})
        
        # Settings
        self.enabled = self.heartbeat_config.get("enabled", True)
        self.interval = self.heartbeat_config.get("interval", 20)
        self.timeout = self.heartbeat_config.get("timeout", 10)
        self.retry_interval = self.heartbeat_config.get("retry_interval", 5)
        self.max_failures = self.heartbeat_config.get("max_failures", 3)
        
        # Credentials
        self.agent_id: Optional[str] = None
        self.agent_token: Optional[str] = None
        self.server_urls = self._get_server_urls()
        
        # State
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._consecutive_failures = 0
        self._last_successful_heartbeat: Optional[float] = None
    
    def _get_server_urls(self) -> list:
        """Get list of server URLs."""
        urls = []
        
        if isinstance(self.server_config.get("urls"), list):
            urls.extend(self.server_config["urls"])
        
        if self.server_config.get("url"):
            main_url = self.server_config["url"]
            if main_url not in urls:
                urls.append(main_url)
        
        return urls or ["http://localhost:5000"]
    
    def set_agent_credentials(self, agent_id: str, token: str) -> None:
        """Set agent credentials for heartbeat."""
        self.agent_id = agent_id
        self.agent_token = token
    
    def start(self) -> None:
        """Start heartbeat sender."""
        if not self.enabled:
            logger.info("Heartbeat sender disabled")
            return
        
        if not self.agent_id or not self.agent_token:
            logger.warning("Cannot start heartbeat - missing agent credentials")
            return
        
        if self._running:
            logger.warning("Heartbeat sender already running")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="HeartbeatSender"
        )
        self._thread.start()
        logger.info(f"Heartbeat sender started (interval: {self.interval}s)")
    
    def stop(self) -> None:
        """Stop heartbeat sender."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Heartbeat sender stopped")
    
    def _heartbeat_loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                success = self._send_heartbeat()
                
                if success:
                    self._consecutive_failures = 0
                    self._last_successful_heartbeat = now()
                    sleep_time = self.interval
                else:
                    self._consecutive_failures += 1
                    if self._consecutive_failures >= self.max_failures:
                        logger.error(
                            f"Too many consecutive heartbeat failures "
                            f"({self._consecutive_failures})"
                        )
                    sleep_time = self.retry_interval
                
                # Interruptible sleep
                for _ in range(int(sleep_time)):
                    if not self._running:
                        break
                    sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                sleep(self.retry_interval)
    
    def _send_heartbeat(self) -> bool:
        """Send heartbeat to server."""
        metrics = self._collect_metrics()
        os_details = get_os_details()
        
        heartbeat_data = {
            "agent_id": self.agent_id,
            "token": self.agent_token,
            "device_id": self.config.get("device_id"),
            "timestamp": now_iso(),
            "metrics": metrics,
            "status": "active",
            "platform": os_details["platform"],
            "os_info": f"{os_details['name']} {os_details['version']}",
            "agent_version": "1.0.0"
        }
        
        for server_url in self.server_urls:
            try:
                url = f"{server_url.rstrip('/')}/api/agents/heartbeat"
                
                response = requests.post(
                    url,
                    json=heartbeat_data,
                    timeout=self.timeout,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        logger.debug(f"Heartbeat sent successfully to {server_url}")
                        return True
                    else:
                        logger.warning(
                            f"Server rejected heartbeat: {data.get('error', 'Unknown')}"
                        )
                else:
                    logger.warning(f"Heartbeat failed: HTTP {response.status_code}")
                    
            except requests.exceptions.ConnectTimeout:
                logger.debug(f"Connection timeout to {server_url}")
            except requests.exceptions.ConnectionError:
                logger.debug(f"Connection error to {server_url}")
            except Exception as e:
                logger.warning(f"Error sending heartbeat to {server_url}: {e}")
        
        return False
    
    def _collect_metrics(self) -> Dict:
        """Collect system metrics (simplified, avoids PDH errors on Windows)."""
        metrics = {
            "memory_percent": 0,
            "disk_percent": 0,
            "uptime_seconds": 0,
            "timestamp": now_iso()
        }
        
        try:
            mem = psutil.virtual_memory()
            metrics["memory_percent"] = round(mem.percent, 2)
        except Exception:
            pass
        
        try:
            disk_path = "C:\\" if platform.system() == "Windows" else "/"
            disk = psutil.disk_usage(disk_path)
            metrics["disk_percent"] = round(disk.percent, 2)
        except Exception:
            pass
        
        try:
            metrics["uptime_seconds"] = int(now() - psutil.boot_time())
        except Exception:
            pass
        
        return metrics
    
    def get_status(self) -> Dict:
        """Get heartbeat sender status."""
        return {
            "enabled": self.enabled,
            "running": self._running,
            "agent_id": self.agent_id,
            "consecutive_failures": self._consecutive_failures,
            "last_successful_heartbeat": self._last_successful_heartbeat,
            "interval": self.interval,
            "timestamp": now_iso()
        }