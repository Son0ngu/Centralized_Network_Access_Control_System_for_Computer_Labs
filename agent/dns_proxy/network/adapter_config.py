"""
Network Adapter Configuration
------------------------------
Detects network adapters and their DNS configuration.
Supports IPv4 and IPv6, handles multi-adapter scenarios.
"""

import logging
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("dns_proxy.network.adapter")


class AdapterType(Enum):
    """Network adapter type."""
    ETHERNET = "ethernet"
    WIFI = "wifi"
    VIRTUAL = "virtual"
    VPN = "vpn"
    LOOPBACK = "loopback"
    UNKNOWN = "unknown"


class AdapterStatus(Enum):
    """Adapter connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


@dataclass
class DNSConfig:
    """DNS configuration for an adapter."""
    ipv4_servers: List[str] = field(default_factory=list)
    ipv6_servers: List[str] = field(default_factory=list)
    is_dhcp_v4: bool = True
    is_dhcp_v6: bool = True
    
    @property
    def has_ipv4(self) -> bool:
        return len(self.ipv4_servers) > 0
    
    @property
    def has_ipv6(self) -> bool:
        return len(self.ipv6_servers) > 0
    
    @property
    def is_proxy_configured(self) -> bool:
        """Check if DNS is configured for our proxy."""
        return (
            "127.0.0.1" in self.ipv4_servers or
            "::1" in self.ipv6_servers
        )


@dataclass
class NetworkAdapter:
    """Represents a network adapter with its configuration."""
    name: str
    interface_index: int
    description: str = ""
    adapter_type: AdapterType = AdapterType.UNKNOWN
    status: AdapterStatus = AdapterStatus.UNKNOWN
    
    # IP configuration
    ipv4_addresses: List[str] = field(default_factory=list)
    ipv6_addresses: List[str] = field(default_factory=list)
    ipv4_gateway: Optional[str] = None
    ipv6_gateway: Optional[str] = None
    
    # DNS configuration
    dns_config: DNSConfig = field(default_factory=DNSConfig)
    
    # Routing
    metric: int = 0
    is_default_route: bool = False
    
    @property
    def has_ipv4(self) -> bool:
        return len(self.ipv4_addresses) > 0
    
    @property
    def has_ipv6(self) -> bool:
        return len(self.ipv6_addresses) > 0
    
    @property
    def is_active(self) -> bool:
        return self.status == AdapterStatus.CONNECTED
    
    @property
    def needs_dns_config(self) -> bool:
        """Check if this adapter needs DNS configuration."""
        return (
            self.is_active and
            self.adapter_type not in (AdapterType.LOOPBACK, AdapterType.VIRTUAL) and
            not self.dns_config.is_proxy_configured
        )


@dataclass
class AdapterPriority:
    """Adapter priority for DNS configuration."""
    adapter: NetworkAdapter
    priority: int  # Lower = higher priority
    reason: str


class NetworkAdapterManager:
    """
    Manages network adapter detection and configuration.
    
    Features:
    - Detect all network adapters
    - Get current DNS configuration
    - Prioritize adapters (default route first)
    - Support multi-adapter scenarios
    """
    
    # Known virtual adapter patterns
    VIRTUAL_PATTERNS = [
        r"vmware",
        r"virtualbox",
        r"hyper-v",
        r"docker",
        r"vethernet",
        r"wsl",
        r"loopback",
    ]
    
    # Known VPN adapter patterns
    VPN_PATTERNS = [
        r"vpn",
        r"tap-",
        r"tun-",
        r"wireguard",
        r"openvpn",
        r"nordvpn",
        r"expressvpn",
        r"fortinet",
        r"cisco anyconnect",
        r"pulse secure",
        r"globalprotect",
    ]
    
    def __init__(self):
        self._adapters: Dict[str, NetworkAdapter] = {}
        self._last_scan_time: float = 0
    
    def scan_adapters(self) -> List[NetworkAdapter]:
        """
        Scan all network adapters.
        
        Returns:
            List of NetworkAdapter objects
        """
        self._adapters.clear()
        
        try:
            # Get adapter list from netsh
            adapters = self._get_adapters_netsh()
            
            # Enrich with PowerShell data for more details
            self._enrich_with_powershell(adapters)
            
            # Detect default route adapters
            self._detect_default_routes(adapters)
            
            self._adapters = {a.name: a for a in adapters}
            
            logger.info(f"Scanned {len(adapters)} network adapters")
            return adapters
            
        except Exception as e:
            logger.error(f"Failed to scan adapters: {e}", exc_info=True)
            return []
    
    def _get_adapters_netsh(self) -> List[NetworkAdapter]:
        """Get adapters using netsh interface show interface."""
        adapters = []
        
        try:
            result = subprocess.run(
                ["netsh", "interface", "show", "interface"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode != 0:
                logger.warning(f"netsh interface show failed: {result.stderr}")
                return adapters
            
            # Parse output
            for line in result.stdout.split("\n"):
                line = line.strip()
                if not line or line.startswith("-") or line.startswith("Admin"):
                    continue
                
                # Format: Admin State    State          Type             Interface Name
                parts = line.split()
                if len(parts) >= 4:
                    admin_state = parts[0]
                    state = parts[1]
                    iface_type = parts[2]
                    name = " ".join(parts[3:])
                    
                    adapter = NetworkAdapter(
                        name=name,
                        interface_index=0,  # Will be filled by PowerShell
                        status=AdapterStatus.CONNECTED if state == "Connected" else AdapterStatus.DISCONNECTED,
                        adapter_type=self._classify_adapter(name, iface_type),
                    )
                    
                    adapters.append(adapter)
            
        except subprocess.TimeoutExpired:
            logger.error("netsh interface show timed out")
        except Exception as e:
            logger.error(f"Error getting adapters: {e}")
        
        return adapters
    
    def _enrich_with_powershell(self, adapters: List[NetworkAdapter]) -> None:
        """Enrich adapter data using PowerShell."""
        try:
            # Get detailed adapter info
            ps_script = """
            Get-NetAdapter | ForEach-Object {
                $dns4 = (Get-DnsClientServerAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses -join ','
                $dns6 = (Get-DnsClientServerAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv6 -ErrorAction SilentlyContinue).ServerAddresses -join ','
                $ip4 = (Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.PrefixOrigin -ne 'WellKnown' }).IPAddress -join ','
                $ip6 = (Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv6 -ErrorAction SilentlyContinue | Where-Object { $_.PrefixOrigin -ne 'WellKnown' -and $_.IPAddress -notlike 'fe80::*' }).IPAddress -join ','
                $gw4 = (Get-NetRoute -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).NextHop | Select-Object -First 1
                $gw6 = (Get-NetRoute -InterfaceIndex $_.ifIndex -AddressFamily IPv6 -DestinationPrefix '::/0' -ErrorAction SilentlyContinue).NextHop | Select-Object -First 1
                $metric = (Get-NetRoute -InterfaceIndex $_.ifIndex -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).RouteMetric | Select-Object -First 1
                "$($_.Name)|$($_.ifIndex)|$($_.InterfaceDescription)|$($_.Status)|$dns4|$dns6|$ip4|$ip6|$gw4|$gw6|$metric"
            }
            """
            
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode != 0:
                logger.warning(f"PowerShell adapter query failed: {result.stderr}")
                return
            
            # Create lookup by name
            adapter_map = {a.name.lower(): a for a in adapters}
            
            for line in result.stdout.strip().split("\n"):
                if not line.strip() or "|" not in line:
                    continue
                
                try:
                    parts = line.split("|")
                    if len(parts) < 11:
                        continue
                    
                    name = parts[0].strip()
                    adapter = adapter_map.get(name.lower())
                    
                    if not adapter:
                        continue
                    
                    # Update adapter info
                    adapter.interface_index = int(parts[1]) if parts[1].isdigit() else 0
                    adapter.description = parts[2].strip()
                    
                    # DNS servers
                    dns4 = [s.strip() for s in parts[4].split(",") if s.strip()]
                    dns6 = [s.strip() for s in parts[5].split(",") if s.strip()]
                    adapter.dns_config.ipv4_servers = dns4
                    adapter.dns_config.ipv6_servers = dns6
                    
                    # IP addresses
                    adapter.ipv4_addresses = [s.strip() for s in parts[6].split(",") if s.strip()]
                    adapter.ipv6_addresses = [s.strip() for s in parts[7].split(",") if s.strip()]
                    
                    # Gateways
                    adapter.ipv4_gateway = parts[8].strip() if parts[8].strip() else None
                    adapter.ipv6_gateway = parts[9].strip() if parts[9].strip() else None
                    
                    # Metric
                    adapter.metric = int(parts[10]) if parts[10].strip().isdigit() else 9999
                    
                except Exception as e:
                    logger.debug(f"Error parsing adapter line: {e}")
                    continue
                    
        except subprocess.TimeoutExpired:
            logger.error("PowerShell adapter query timed out")
        except Exception as e:
            logger.error(f"Error enriching adapter data: {e}")
    
    def _detect_default_routes(self, adapters: List[NetworkAdapter]) -> None:
        """Detect which adapters have default routes."""
        # Find lowest metric with gateway
        ipv4_default = None
        ipv6_default = None
        lowest_v4_metric = 9999
        lowest_v6_metric = 9999
        
        for adapter in adapters:
            if adapter.ipv4_gateway and adapter.metric < lowest_v4_metric:
                lowest_v4_metric = adapter.metric
                ipv4_default = adapter
            
            if adapter.ipv6_gateway and adapter.metric < lowest_v6_metric:
                lowest_v6_metric = adapter.metric
                ipv6_default = adapter
        
        if ipv4_default:
            ipv4_default.is_default_route = True
            logger.debug(f"IPv4 default route: {ipv4_default.name}")
        
        if ipv6_default and ipv6_default != ipv4_default:
            ipv6_default.is_default_route = True
            logger.debug(f"IPv6 default route: {ipv6_default.name}")
    
    def _classify_adapter(self, name: str, iface_type: str = "") -> AdapterType:
        """Classify adapter type based on name and type."""
        name_lower = name.lower()
        
        # Check loopback
        if "loopback" in name_lower:
            return AdapterType.LOOPBACK
        
        # Check virtual patterns
        for pattern in self.VIRTUAL_PATTERNS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return AdapterType.VIRTUAL
        
        # Check VPN patterns
        for pattern in self.VPN_PATTERNS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return AdapterType.VPN
        
        # Check interface type
        if iface_type:
            type_lower = iface_type.lower()
            if "dedicated" in type_lower:
                if "wi-fi" in name_lower or "wireless" in name_lower:
                    return AdapterType.WIFI
                return AdapterType.ETHERNET
        
        # Fallback based on name
        if any(w in name_lower for w in ["wi-fi", "wireless", "wlan"]):
            return AdapterType.WIFI
        
        if any(w in name_lower for w in ["ethernet", "local area"]):
            return AdapterType.ETHERNET
        
        return AdapterType.UNKNOWN
    
    def get_adapters_for_dns_config(self) -> List[AdapterPriority]:
        """
        Get prioritized list of adapters that need DNS configuration.
        
        Priority order:
        1. Default route adapter (lowest metric)
        2. Other connected adapters with gateway
        3. Connected adapters without gateway (secondary)
        
        Returns:
            List of AdapterPriority sorted by priority
        """
        if not self._adapters:
            self.scan_adapters()
        
        priorities = []
        
        for adapter in self._adapters.values():
            if not adapter.is_active:
                continue
            
            if adapter.adapter_type in (AdapterType.LOOPBACK,):
                continue
            
            # Skip virtual adapters unless they have a gateway
            if adapter.adapter_type == AdapterType.VIRTUAL:
                if not adapter.ipv4_gateway and not adapter.ipv6_gateway:
                    continue
            
            # Calculate priority
            if adapter.is_default_route:
                priority = 10  # Highest priority
                reason = "Default route"
            elif adapter.ipv4_gateway or adapter.ipv6_gateway:
                priority = 20 + adapter.metric // 100
                reason = "Has gateway"
            elif adapter.adapter_type == AdapterType.VPN:
                priority = 15  # VPN should be configured
                reason = "VPN adapter"
            else:
                priority = 50
                reason = "Secondary adapter"
            
            priorities.append(AdapterPriority(
                adapter=adapter,
                priority=priority,
                reason=reason
            ))
        
        # Sort by priority (lower = higher priority)
        priorities.sort(key=lambda p: p.priority)
        
        return priorities
    
    def get_adapter(self, name: str) -> Optional[NetworkAdapter]:
        """Get adapter by name."""
        return self._adapters.get(name)
    
    def get_active_adapters(self) -> List[NetworkAdapter]:
        """Get all active (connected) adapters."""
        return [a for a in self._adapters.values() if a.is_active]
    
    def get_default_route_adapter(self) -> Optional[NetworkAdapter]:
        """Get the primary default route adapter."""
        for adapter in self._adapters.values():
            if adapter.is_default_route:
                return adapter
        return None
    
    def get_adapters_with_ipv6(self) -> List[NetworkAdapter]:
        """Get adapters that have IPv6 configuration."""
        return [a for a in self._adapters.values() if a.has_ipv6 and a.is_active]
    
    def refresh(self) -> None:
        """Refresh adapter information."""
        self.scan_adapters()
    
    def get_summary(self) -> Dict:
        """Get summary of network adapters."""
        adapters = list(self._adapters.values())
        active = [a for a in adapters if a.is_active]
        
        return {
            "total_adapters": len(adapters),
            "active_adapters": len(active),
            "ipv6_enabled": len([a for a in active if a.has_ipv6]),
            "default_route": self.get_default_route_adapter().name if self.get_default_route_adapter() else None,
            "proxy_configured": len([a for a in active if a.dns_config.is_proxy_configured]),
            "needs_config": len([a for a in active if a.needs_dns_config]),
        }
