import json
import logging
import queue
import socket
import threading
import uuid
from typing import Any, Dict, List, Optional

import requests

from shared.time_utils import now, now_iso, sleep
from core.token_manager import get_auth_headers

logger = logging.getLogger("logging.sender")


class LogSender:
    
    def __init__(self, config: Dict):

        self.config = config 
        
        # Server configuration
        self.server_urls = self._get_server_urls(config)
        
        # Queue configuration
        self.max_queue_size = config.get("max_queue_size", 1000)
        self.batch_size = config.get("batch_size", 100)
        self.send_interval = config.get("send_interval", 2)
        
        self.log_queue: queue.Queue = queue.Queue(maxsize=self.max_queue_size)
        self.running = False
        self._sender_thread: Optional[threading.Thread] = None
        
        self.agent_id = config.get("agent_id") or self._generate_agent_id()
        
        self.last_send_time = now()
        self._send_lock = threading.Lock()
        
        logger.info(f"LogSender initialized with agent_id: {self.agent_id}")
        logger.info(f"Will send logs to: {', '.join(self.server_urls)}")
    
    def _get_server_urls(self, config: Dict) -> List[str]:
        server_config = config.get("server", {})
        
        if "urls" in server_config and server_config["urls"]:
            return server_config["urls"]
        
        primary_url = (
            config.get("server_url") or
            server_config.get("url", "https://firewall-controller.onrender.com")
        )
        
        return [primary_url, "http://localhost:5000"]
    
    def start(self) -> None:
        if self.running:
            return
        
        self.running = True
        self._sender_thread = threading.Thread(
            target=self._sender_loop,
            daemon=True,
            name="LogSender"
        )
        self._sender_thread.start()
        logger.info("Log sender started")
    
    def stop(self) -> None:
        """Stop sender and flush remaining logs."""
        if not self.running:
            return
        
        self.running = False
        
        if self._sender_thread:
            try:
                self._flush_queue()
            except Exception as e:
                logger.error(f"Error flushing logs: {e}")
            
            self._sender_thread.join(timeout=2)  # Reduced for faster shutdown
        
        logger.info("Log sender stopped")
    
    def queue_log(self, log_data: Dict) -> bool:
        try:
            serialized_log = self._serialize_log(log_data.copy())
            
            if "agent_id" not in serialized_log:
                serialized_log["agent_id"] = self.agent_id
            
            if "timestamp" not in serialized_log:
                serialized_log["timestamp"] = now_iso()
            
            self.log_queue.put_nowait(serialized_log)
            return True
            
        except queue.Full:
            logger.warning("Log queue is full, dropping log")
            return False
        except Exception as e:
            logger.error(f"Error queueing log: {e}")
            return False
    
    def _serialize_log(self, log_data: Dict) -> Dict:
        """Serialize log data for JSON transmission."""
        serialized = {}
        
        for key, value in log_data.items():
            if hasattr(value, 'isoformat'):
                serialized[key] = value.isoformat()
            elif isinstance(value, dict):
                serialized[key] = self._serialize_log(value)
            elif isinstance(value, list):
                serialized[key] = [
                    item.isoformat() if hasattr(item, 'isoformat')
                    else (self._serialize_log(item) if isinstance(item, dict) else item)
                    for item in value
                ]
            elif value is None:
                serialized[key] = "unknown"
            else:
                serialized[key] = value
        
        # Check if this is a lifecycle event (startup/shutdown)
        is_lifecycle = serialized.get("is_lifecycle_event", False)
        
        # Ensure essential fields
        essential_fields = {
            "timestamp": now_iso(),
            "agent_id": self.agent_id,
            "level": "INFO",
            "action": "UNKNOWN",
            "message": "Log entry"
        }
        
        # Network-related fields - only set defaults for non-lifecycle events
        if not is_lifecycle:
            network_fields = {
                "domain": "unknown",
                "destination": "unknown",
                "source_ip": "unknown",
                "dest_ip": "unknown",
                "protocol": "unknown",
                "port": "unknown"
            }
            essential_fields.update(network_fields)
        
        for field, default in essential_fields.items():
            if field not in serialized or not serialized[field]:
                serialized[field] = default
        
        return serialized
    
    def _sender_loop(self) -> None:
        """Main sender loop."""
        while self.running:
            try:
                current_time = now()
                queue_size = self.log_queue.qsize()
                
                should_send = (
                    queue_size >= self.batch_size or
                    (queue_size > 0 and (current_time - self.last_send_time) >= self.send_interval)
                )
                
                if should_send:
                    self._send_logs()
                    self.last_send_time = current_time
                
                sleep(1)
                
            except Exception as e:
                logger.error(f"Error in sender loop: {e}")
                sleep(5)
    
    def _flush_queue(self) -> None:
        logs = []
        try:
            while not self.log_queue.empty():
                logs.append(self.log_queue.get_nowait())
                self.log_queue.task_done()
        except queue.Empty:
            pass
        
        if logs:
            self._send_batch(logs)
    
    def _send_logs(self) -> None:
        logs = []
        batch_size = min(self.batch_size, self.log_queue.qsize())
        
        for _ in range(batch_size):
            try:
                log = self.log_queue.get_nowait()
                logs.append(log)
                self.log_queue.task_done()
            except queue.Empty:
                break
        
        if logs:
            self._send_batch(logs)
    
    def _send_batch(self, logs: List[Dict]) -> bool:
        if not self.server_urls:
            logger.error("Server URL not configured")
            return False
        
        serialized_logs = []
        for log in logs:
            try:
                clean_log = self._ensure_serializable(log)
                serialized_logs.append(clean_log)
            except Exception as e:
                logger.error(f"Failed to serialize log: {e}")
                serialized_logs.append({
                    "message": f"Serialization failed: {e}",
                    "level": "error",
                    "timestamp": now_iso(),
                    "agent_id": self.agent_id
                })
        
        try:
            url = f"{self.server_urls[0].rstrip('/')}/api/logs"
            payload = {"logs": serialized_logs}
            
            # Build headers with JWT authentication
            headers = {"Content-Type": "application/json"}
            auth_headers = get_auth_headers(self.config)
            headers.update(auth_headers)
            
            response = requests.post(
                url=url,
                json=payload,
                headers=headers,
                timeout=15
            )
            
            if response.status_code in (200, 201, 202):
                logger.info(f"Sent {len(serialized_logs)} logs to server")
                return True
            elif response.status_code == 401:
                logger.warning("Log send authentication failed - token may be expired")
                return False
            else:
                logger.error(f"Failed to send logs: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Timeout sending logs")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Connection error sending logs")
            return False
        except Exception as e:
            logger.error(f"Error sending logs: {e}")
            return False
    
    def _ensure_serializable(self, obj: Any) -> Any:
        """Ensure object is JSON serializable."""
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._ensure_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._ensure_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        else:
            return str(obj)
    
    def _generate_agent_id(self) -> str:
        """Generate unique agent identifier."""
        import platform
        
        hostname = socket.gethostname()
        system_info = platform.system() + platform.release()
        mac = ':'.join([
            f'{(uuid.getnode() >> elements) & 0xff:02x}'
            for elements in range(0, 12, 2)
        ][::-1])
        
        return f"{hostname}-{mac}"
    
    def get_status(self) -> Dict:
        """Get sender status."""
        return {
            "running": self.running,
            "agent_id": self.agent_id,
            "queue_size": self.log_queue.qsize(),
            "max_queue_size": self.max_queue_size,
            "batch_size": self.batch_size,
            "send_interval": self.send_interval,
            "last_send_time": self.last_send_time,
            "server_urls": self.server_urls,
            "status_timestamp": now_iso()
        }