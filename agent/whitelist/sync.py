import logging
from typing import Dict, List, Optional

import requests

from shared.time_utils import sleep
from core.token_manager import get_auth_headers

logger = logging.getLogger("whitelist.sync")


class WhitelistSyncer:

    def __init__(
        self,
        server_urls: List[str],
        agent_id: str,
        config: Dict = None,
        connect_timeout: int = 10,
        read_timeout: int = 30,
        max_retries: int = 3
    ):
        self.server_urls = server_urls
        self.agent_id = agent_id
        self.config = config or {}
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_retries = max_retries
        self.current_server_index = 0
    
    @property
    def current_url(self) -> str:
        if self.server_urls:
            return self._build_sync_url(self.server_urls[self.current_server_index])
        return ""
    
    def _build_sync_url(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/api/whitelist/agent-sync"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {'User-Agent': 'FirewallController-Agent/2.2-Modular'}
        auth_headers = get_auth_headers(self.config)
        headers.update(auth_headers)
        return headers
    
    def sync_with_server(self, params: Dict) -> Dict:
        """Sync with server, trying fallback servers if needed."""
        last_error = None
        headers = self._get_headers()
        
        # Whitelist sync endpoint is JWT-protected; fail fast if no auth is available
        if not any(k in headers for k in ("Authorization", "X-Agent-Token")):
            error_msg = (
                "Authentication required for whitelist sync - "
                "configure JWT credentials or agent_token"
            )
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Try current server first
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    self.current_url,
                    params=params,
                    timeout=(self.connect_timeout, self.read_timeout),
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {"success": True, "data": data}
                elif response.status_code == 401:
                    # Authentication failed - might need token refresh
                    last_error = "Authentication failed - token may be expired"
                    logger.warning(f"Sync authentication failed: {response.text[:200]}")
                    break  # Don't retry auth failures
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(f"Sync attempt {attempt + 1} failed: {last_error}")
                    
            except requests.exceptions.Timeout as e:
                last_error = f"Timeout: {e}"
                logger.warning(f"Sync attempt {attempt + 1} timed out")
                
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e}"
                logger.warning(f"Sync attempt {attempt + 1} connection failed")
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Sync attempt {attempt + 1} failed: {e}")
            
            if attempt < self.max_retries - 1:
                sleep(2 ** attempt)  # Exponential backoff
        
        # Try fallback servers
        if len(self.server_urls) > 1:
            logger.info("Trying fallback servers...")
            for i, fallback_url in enumerate(self.server_urls):
                if i == self.current_server_index:
                    continue
                    
                try:
                    sync_url = self._build_sync_url(fallback_url)
                    logger.info(f"Trying fallback server: {fallback_url}")
                    
                    response = requests.get(
                        sync_url,
                        params=params,
                        timeout=(self.connect_timeout, self.read_timeout),
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Update current server index to successful fallback
                        self.current_server_index = i
                        logger.info(f"Switched to fallback server: {fallback_url}")
                        return {"success": True, "data": data}
                        
                except Exception as e:
                    logger.warning(f"Fallback server {fallback_url} failed: {e}")
        
        return {"success": False, "error": str(last_error)}
    
    def extract_domain_value(self, domain_data) -> Optional[str]:
        """Extract domain value from server response."""
        if isinstance(domain_data, dict):
            return domain_data.get('value', '').strip().lower()
        elif isinstance(domain_data, str):
            return domain_data.strip().lower()
        else:
            logger.warning(f"Invalid domain data format: {domain_data}")
            return None