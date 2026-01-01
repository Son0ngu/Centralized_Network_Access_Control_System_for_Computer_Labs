"""
DoH Provider Updater
--------------------
Fetches and updates DoH/DoT provider blocklists from remote sources.

Sources:
1. GitHub-hosted blocklists (community maintained)
2. Official DNS provider announcements
3. Custom enterprise lists

Update Strategy:
- Periodic updates (default: daily)
- On-demand updates
- Fallback to local cache if remote fails
- Merge with built-in providers
"""

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from urllib.request import urlopen, Request
from urllib.error import URLError

from .doh_blocker_enhanced import DoHProviderEntry

logger = logging.getLogger("dns_proxy.security.provider_updater")


@dataclass
class RemoteSource:
    """Remote blocklist source configuration."""
    name: str
    url: str
    format: str  # "json", "hosts", "ips", "domains"
    enabled: bool = True
    priority: int = 2
    last_updated: Optional[datetime] = None
    last_hash: Optional[str] = None
    update_interval_hours: int = 24


@dataclass
class UpdaterConfig:
    """Provider updater configuration."""
    # Cache directory
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".dns_proxy" / "blocklists")
    
    # Update settings
    auto_update: bool = True
    update_interval_hours: int = 24
    retry_interval_minutes: int = 60
    max_retries: int = 3
    
    # Network settings
    timeout_seconds: int = 30
    user_agent: str = "DNS-Proxy-Updater/1.0"
    
    # Merge settings
    merge_with_builtin: bool = True
    deduplicate: bool = True


# Default remote sources
DEFAULT_SOURCES: List[RemoteSource] = [
    # Removed curl-doh-servers - 404 Not Found
    RemoteSource(
        name="hagezi-doh",
        url="https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/doh.txt",
        format="domains",
        priority=1,
    ),
    RemoteSource(
        name="hagezi-doh-ips",
        url="https://raw.githubusercontent.com/hagezi/dns-blocklists/main/ips/doh.txt",
        format="ips",
        priority=1,
    ),
    # Removed nextdns-doh - 404 Not Found
    # Using AdGuard list instead
    RemoteSource(
        name="adguard-doh-providers",
        url="https://raw.githubusercontent.com/nickspaargaren/no-google/master/categories/dns.txt",
        format="domains",
        priority=2,
        enabled=False,  # Optional - enable if needed
    ),
]


@dataclass
class UpdateResult:
    """Result of an update operation."""
    success: bool
    source: str
    new_entries: int = 0
    updated_entries: int = 0
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class ProviderUpdater:
    """
    Updates DoH/DoT provider blocklists from remote sources.
    
    Features:
    - Multiple source support
    - Automatic periodic updates
    - Caching with hash verification
    - Graceful fallback on errors
    
    Usage:
        updater = ProviderUpdater()
        
        # Manual update
        results = updater.update_all()
        
        # Start auto-update
        updater.start_auto_update()
        
        # Get merged providers
        providers = updater.get_providers()
    """
    
    CACHE_FILE = "providers_cache.json"
    STATE_FILE = "updater_state.json"
    
    def __init__(
        self,
        config: UpdaterConfig = None,
        sources: List[RemoteSource] = None,
        builtin_providers: List[DoHProviderEntry] = None
    ):
        self._config = config or UpdaterConfig()
        self._sources = sources or DEFAULT_SOURCES.copy()
        self._builtin_providers = builtin_providers or []
        
        # Ensure cache directory exists
        self._config.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # State
        self._providers: List[DoHProviderEntry] = []
        self._last_update: Optional[datetime] = None
        self._update_errors: List[str] = []
        
        # Auto-update
        self._running = False
        self._update_thread: Optional[threading.Thread] = None
        self._on_update_callbacks: List[Callable[[List[DoHProviderEntry]], None]] = []
        
        # Load cached data
        self._load_cache()
        self._load_state()
        
        logger.info(
            f"Provider Updater initialized with {len(self._sources)} sources, "
            f"{len(self._providers)} cached providers"
        )
    
    def update_all(self) -> List[UpdateResult]:
        """
        Update from all enabled sources.
        
        Returns:
            List of UpdateResult for each source
        """
        results = []
        new_entries: Set[str] = set()  # Track by domain
        
        for source in self._sources:
            if not source.enabled:
                continue
            
            try:
                result = self._update_from_source(source)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Failed to update from {source.name}: {e}")
                results.append(UpdateResult(
                    success=False,
                    source=source.name,
                    errors=[str(e)]
                ))
        
        # Merge with builtin
        if self._config.merge_with_builtin:
            self._merge_providers()
        
        # Save cache
        self._save_cache()
        self._save_state()
        
        self._last_update = datetime.now()
        
        # Notify callbacks
        for callback in self._on_update_callbacks:
            try:
                callback(self._providers)
            except Exception as e:
                logger.error(f"Update callback error: {e}")
        
        return results
    
    def _update_from_source(self, source: RemoteSource) -> UpdateResult:
        """Update from a single source."""
        result = UpdateResult(success=True, source=source.name)
        
        logger.info(f"Updating from source: {source.name}")
        
        try:
            # Fetch data
            data = self._fetch_url(source.url)
            
            if not data:
                result.success = False
                result.errors.append("Empty response")
                return result
            
            # Check hash for changes
            data_hash = hashlib.md5(data.encode()).hexdigest()
            if source.last_hash == data_hash:
                logger.debug(f"No changes from {source.name}")
                return result
            
            # Parse based on format
            entries = self._parse_data(data, source.format)
            
            if not entries:
                result.errors.append("No entries parsed")
                return result
            
            # Add to providers
            for entry in entries:
                entry.last_updated = datetime.now().isoformat()
                self._add_or_update_provider(entry)
                result.new_entries += 1
            
            # Update source state
            source.last_hash = data_hash
            source.last_updated = datetime.now()
            
            logger.info(f"Updated {result.new_entries} entries from {source.name}")
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error(f"Error updating from {source.name}: {e}")
        
        return result
    
    def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch content from URL."""
        try:
            request = Request(
                url,
                headers={"User-Agent": self._config.user_agent}
            )
            
            with urlopen(request, timeout=self._config.timeout_seconds) as response:
                return response.read().decode("utf-8", errors="ignore")
                
        except URLError as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _parse_data(self, data: str, format: str) -> List[DoHProviderEntry]:
        """Parse data based on format."""
        entries = []
        
        if format == "json":
            entries = self._parse_json(data)
        elif format == "domains":
            entries = self._parse_domains(data)
        elif format == "ips":
            entries = self._parse_ips(data)
        elif format == "hosts":
            entries = self._parse_hosts(data)
        elif format == "markdown":
            entries = self._parse_markdown(data)
        else:
            logger.warning(f"Unknown format: {format}")
        
        return entries
    
    def _parse_json(self, data: str) -> List[DoHProviderEntry]:
        """Parse JSON format blocklist."""
        entries = []
        try:
            parsed = json.loads(data)
            
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        entry = DoHProviderEntry(
                            name=item.get("name", "Unknown"),
                            domains=item.get("domains", []),
                            ipv4_addresses=item.get("ipv4", item.get("ips", [])),
                            ipv6_addresses=item.get("ipv6", []),
                            category="remote",
                        )
                        if entry.domains or entry.ipv4_addresses:
                            entries.append(entry)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
        
        return entries
    
    def _parse_domains(self, data: str) -> List[DoHProviderEntry]:
        """Parse domain list format."""
        domains = []
        
        for line in data.split("\n"):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            
            # Handle hosts format
            if " " in line:
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[1]
                else:
                    continue
            else:
                domain = line
            
            # Validate domain
            if self._is_valid_domain(domain):
                domains.append(domain)
        
        if domains:
            return [DoHProviderEntry(
                name="Remote Domains",
                domains=domains,
                category="remote",
            )]
        return []
    
    def _parse_ips(self, data: str) -> List[DoHProviderEntry]:
        """Parse IP list format."""
        ipv4 = []
        ipv6 = []
        
        for line in data.split("\n"):
            line = line.strip()
            
            if not line or line.startswith("#"):
                continue
            
            # Remove CIDR notation if present
            ip = line.split("/")[0]
            
            if ":" in ip:
                ipv6.append(ip)
            elif self._is_valid_ip(ip):
                ipv4.append(ip)
        
        if ipv4 or ipv6:
            return [DoHProviderEntry(
                name="Remote IPs",
                ipv4_addresses=ipv4,
                ipv6_addresses=ipv6,
                category="remote",
            )]
        return []
    
    def _parse_hosts(self, data: str) -> List[DoHProviderEntry]:
        """Parse hosts file format."""
        return self._parse_domains(data)  # Same logic
    
    def _parse_markdown(self, data: str) -> List[DoHProviderEntry]:
        """Parse markdown format (extract domains/IPs from text)."""
        import re
        
        domains = set()
        ips = set()
        
        # Extract domains
        domain_pattern = r'\b([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}\b'
        for match in re.finditer(domain_pattern, data):
            domain = match.group(0).lower()
            if "dns" in domain or "doh" in domain:
                domains.add(domain)
        
        # Extract IPs
        ip_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
        for match in re.finditer(ip_pattern, data):
            ip = match.group(0)
            if self._is_valid_ip(ip):
                ips.add(ip)
        
        entries = []
        if domains:
            entries.append(DoHProviderEntry(
                name="Markdown Domains",
                domains=list(domains),
                category="remote",
            ))
        if ips:
            entries.append(DoHProviderEntry(
                name="Markdown IPs",
                ipv4_addresses=list(ips),
                category="remote",
            ))
        
        return entries
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Check if domain is valid."""
        if not domain or len(domain) > 253:
            return False
        if domain.startswith(".") or domain.endswith("."):
            return False
        labels = domain.split(".")
        return len(labels) >= 2 and all(len(l) <= 63 for l in labels)
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Check if IP is valid."""
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False
    
    def _add_or_update_provider(self, entry: DoHProviderEntry) -> None:
        """Add or update a provider entry."""
        # Check for existing by domains
        for existing in self._providers:
            if set(existing.domains) & set(entry.domains):
                # Merge
                existing.domains = list(set(existing.domains) | set(entry.domains))
                existing.ipv4_addresses = list(set(existing.ipv4_addresses) | set(entry.ipv4_addresses))
                existing.ipv6_addresses = list(set(existing.ipv6_addresses) | set(entry.ipv6_addresses))
                return
        
        self._providers.append(entry)
    
    def _merge_providers(self) -> None:
        """Merge builtin providers with remote providers."""
        for builtin in self._builtin_providers:
            self._add_or_update_provider(builtin)
    
    def _load_cache(self) -> None:
        """Load cached providers."""
        cache_file = self._config.cache_dir / self.CACHE_FILE
        
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                
                for item in data.get("providers", []):
                    self._providers.append(DoHProviderEntry(**item))
                    
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
    
    def _save_cache(self) -> None:
        """Save providers to cache."""
        cache_file = self._config.cache_dir / self.CACHE_FILE
        
        try:
            data = {
                "updated": datetime.now().isoformat(),
                "providers": [
                    {
                        "name": p.name,
                        "domains": p.domains,
                        "ipv4_addresses": p.ipv4_addresses,
                        "ipv6_addresses": p.ipv6_addresses,
                        "sni_patterns": p.sni_patterns,
                        "category": p.category,
                        "priority": p.priority,
                        "last_updated": p.last_updated,
                    }
                    for p in self._providers
                ],
            }
            
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _load_state(self) -> None:
        """Load updater state."""
        state_file = self._config.cache_dir / self.STATE_FILE
        
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
                
                if data.get("last_update"):
                    self._last_update = datetime.fromisoformat(data["last_update"])
                    
            except Exception as e:
                logger.debug(f"Failed to load state: {e}")
    
    def _save_state(self) -> None:
        """Save updater state."""
        state_file = self._config.cache_dir / self.STATE_FILE
        
        try:
            data = {
                "last_update": self._last_update.isoformat() if self._last_update else None,
                "sources": [
                    {
                        "name": s.name,
                        "last_hash": s.last_hash,
                        "last_updated": s.last_updated.isoformat() if s.last_updated else None,
                    }
                    for s in self._sources
                ],
            }
            
            with open(state_file, "w") as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def start_auto_update(self) -> None:
        """Start automatic periodic updates."""
        if self._running:
            return
        
        self._running = True
        self._update_thread = threading.Thread(
            target=self._auto_update_loop,
            name="ProviderUpdater",
            daemon=True
        )
        self._update_thread.start()
        
        logger.info(
            f"Auto-update started (interval: {self._config.update_interval_hours}h)"
        )
    
    def stop_auto_update(self) -> None:
        """Stop automatic updates."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=5)
        logger.info("Auto-update stopped")
    
    def _auto_update_loop(self) -> None:
        """Automatic update loop."""
        while self._running:
            try:
                # Check if update needed
                if self._should_update():
                    logger.info("Running scheduled provider update")
                    self.update_all()
                
            except Exception as e:
                logger.error(f"Auto-update error: {e}")
            
            # Sleep with periodic wake-ups
            sleep_time = self._config.update_interval_hours * 3600
            while sleep_time > 0 and self._running:
                time.sleep(min(60, sleep_time))
                sleep_time -= 60
    
    def _should_update(self) -> bool:
        """Check if an update is needed."""
        if not self._last_update:
            return True
        
        interval = timedelta(hours=self._config.update_interval_hours)
        return datetime.now() - self._last_update > interval
    
    def on_update(self, callback: Callable[[List[DoHProviderEntry]], None]) -> None:
        """Register callback for update events."""
        self._on_update_callbacks.append(callback)
    
    def get_providers(self) -> List[DoHProviderEntry]:
        """Get all providers (builtin + remote)."""
        return self._providers.copy()
    
    def get_all_domains(self) -> Set[str]:
        """Get all domains from all providers."""
        domains = set()
        for p in self._providers:
            domains.update(p.domains)
        return domains
    
    def get_all_ips(self) -> Set[str]:
        """Get all IPs from all providers."""
        ips = set()
        for p in self._providers:
            ips.update(p.ipv4_addresses)
            ips.update(p.ipv6_addresses)
        return ips
    
    def add_source(self, source: RemoteSource) -> None:
        """Add a custom remote source."""
        self._sources.append(source)
    
    def get_stats(self) -> Dict:
        """Get updater statistics."""
        return {
            "sources_count": len(self._sources),
            "providers_count": len(self._providers),
            "total_domains": len(self.get_all_domains()),
            "total_ips": len(self.get_all_ips()),
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "auto_update_running": self._running,
            "update_interval_hours": self._config.update_interval_hours,
        }
