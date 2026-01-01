import logging
import threading
from typing import Callable, Dict, Optional

from shared.time_utils import now_iso, sleep

from .scapy_config import configure_scapy, ensure_pcap_driver, apply_scapy_config

configure_scapy()
ensure_pcap_driver()

from scapy.all import sniff
from scapy.layers.inet import IP, TCP, UDP
from scapy.packet import Packet

# Apply configuration after import
apply_scapy_config()

from .extractors import DomainExtractor

logger = logging.getLogger("capture.sniffer")


class PacketSniffer:
    """
    Packet Sniffer for network traffic monitoring.
    
    MODES:
    - "bypass_detection_only": Only detect bypass attempts (DNS Proxy handles blocking)
    - "full": Full packet capture with domain detection (legacy mode)
    
    In DNS Proxy Architecture (Phase 1):
    - PacketSniffer is SECONDARY/OPTIONAL
    - Primary whitelist enforcement is done by DNS Proxy
    - This module only detects bypass attempts (direct IP, DoH, etc.)
    """
    
    def __init__(self, callback: Callable[[Dict], None], mode: str = "bypass_detection_only"):
        """
        Initialize packet sniffer.
        
        Args:
            callback: Function to call with captured packet info
            mode: Operating mode - "bypass_detection_only" or "full"
        """
        self.callback = callback
        self.mode = mode
        self.running = False
        self._capture_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._extractor = DomainExtractor()
        
        # Stats
        self.packet_count = 0
        self.domain_count = 0
        self.bypass_attempts = 0
        self._stats_lock = threading.Lock()
        
        logger.info(f"PacketSniffer initialized (mode: {mode})")
    
    def start(self) -> None:
       
        if self.running:
            logger.warning("Packet sniffer is already running")
            return
        
        self.running = True
        self._stop_event.clear()
        
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="PacketSniffer"
        )
        self._capture_thread.start()
        
        logger.info("Packet sniffer started")
    
    def stop(self) -> None:
        if not self.running:
            logger.warning("Packet sniffer is not running")
            return
        
        logger.info("Stopping packet sniffer...")
        self.running = False
        self._stop_event.set()
        
        if self._capture_thread:
            self._capture_thread.join(timeout=5)
            
            if self._capture_thread.is_alive():
                logger.warning("Packet capture thread did not terminate gracefully")
            else:
                logger.info("Packet capture thread terminated")
        
        logger.info("Packet sniffer stopped")
    
    def _capture_loop(self) -> None:
        max_retries = 3
        retry_count = 0
        
        # Filter based on mode
        if self.mode == "bypass_detection_only":
            # Only capture HTTPS traffic (to detect direct IP or DoH attempts)
            # DNS should go through DNS Proxy, so we don't need to capture port 53
            filter_str = "tcp and dst port 443"
            logger.info("Bypass detection mode: monitoring HTTPS traffic only")
        else:
            # Full mode - capture all relevant traffic
            filter_str = (
                "tcp and (dst port 80 or dst port 443 or dst port 53) "
                "or udp and dst port 53"
            )
        
        while self.running and retry_count < max_retries:
            try:
                logger.info(f"Starting packet capture with filter: {filter_str}")
                
                while self.running and not self._stop_event.is_set():
                    try:
                        sniff(
                            filter=filter_str,
                            prn=self._process_packet,
                            store=0,
                            timeout=2,
                            stop_filter=lambda _: self._stop_event.is_set()
                        )
                    except Exception as e:
                        if self.running:
                            logger.debug(f"Sniff iteration error: {e}")
                        break
                    
                    if self._stop_event.is_set():
                        break
                
                break  # Normal exit
                
            except PermissionError as e:
                logger.error(f"Permission error - need admin/root: {e}")
                break
                
            except OSError as e:
                if "No suitable" in str(e) or "wpcap" in str(e).lower():
                    logger.error(f"Network driver issue: {e}")
                    logger.error("Ensure WinPcap or Npcap is installed")
                    break
                else:
                    retry_count += 1
                    logger.error(f"OS error (attempt {retry_count}/{max_retries}): {e}")
                    
            except Exception as e:
                retry_count += 1
                logger.error(f"Capture error (attempt {retry_count}/{max_retries}): {e}")
                
                if retry_count < max_retries and self.running:
                    logger.info("Retrying capture in 5 seconds...")
                    if self._stop_event.wait(timeout=5):
                        break
        
        logger.debug("Packet capture thread exiting")
    
    def _process_packet(self, packet: Packet) -> None:
        """
        Process captured packet and extract domain info.
        
        In bypass_detection_only mode:
        - Detects direct IP connections (no SNI/Host header)
        - Detects connections to known DoH providers
        - Logs as potential bypass attempts
        """
        try:
            if not packet.haslayer(IP):
                return
            
            # Increment packet counter
            with self._stats_lock:
                self.packet_count += 1
            
            ip_layer = packet[IP]
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            
            domain: Optional[str] = None
            protocol = "unknown"
            dst_port: Optional[int] = None
            src_port: Optional[int] = None
            is_bypass_attempt = False
            bypass_reason = None
            
            if packet.haslayer(TCP):
                tcp_layer = packet[TCP]
                src_port = tcp_layer.sport
                dst_port = tcp_layer.dport
                
                if dst_port == 80:
                    protocol = "HTTP"
                    domain = self._extractor.extract_http_host(packet)
                elif dst_port == 443:
                    protocol = "HTTPS"
                    domain = self._extractor.extract_https_sni(packet)
                    
                    # Bypass detection for HTTPS
                    if self.mode == "bypass_detection_only":
                        if not domain:
                            # Direct IP connection without SNI - potential bypass
                            is_bypass_attempt = True
                            bypass_reason = "direct_ip_connection"
                        elif self._is_doh_provider(dst_ip, domain):
                            # Connection to known DoH provider
                            is_bypass_attempt = True
                            bypass_reason = "doh_provider"
                else:
                    protocol = f"TCP/{dst_port}"
                    
                    # Port 853 is DNS over TLS (DoT)
                    if dst_port == 853:
                        is_bypass_attempt = True
                        bypass_reason = "dot_connection"
                        protocol = "DoT"
                    
            elif packet.haslayer(UDP):
                udp_layer = packet[UDP]
                src_port = udp_layer.sport
                dst_port = udp_layer.dport
                
                if dst_port == 53:
                    protocol = "DNS"
                    domain = self._extractor.extract_dns_query(packet)
                    
                    # In bypass detection mode, external DNS is suspicious
                    # (should go through DNS Proxy at 127.0.0.1)
                    if self.mode == "bypass_detection_only" and dst_ip != "127.0.0.1":
                        is_bypass_attempt = True
                        bypass_reason = "external_dns_query"
                else:
                    protocol = f"UDP/{dst_port}"
            
            # Track bypass attempts
            if is_bypass_attempt:
                with self._stats_lock:
                    self.bypass_attempts += 1
            
            # Build record
            if domain or dst_port in [80, 443, 53, 853] or is_bypass_attempt:
                if domain:
                    with self._stats_lock:
                        self.domain_count += 1
                
                record = {
                    "timestamp": now_iso(),
                    "domain": domain,
                    "src_ip": src_ip,
                    "dest_ip": dst_ip,
                    "src_port": src_port,
                    "port": dst_port,
                    "dest_port": dst_port,
                    "protocol": protocol,
                    "packet_size": len(packet),
                    "connection_direction": "outbound",
                    # Bypass detection fields
                    "is_bypass_attempt": is_bypass_attempt,
                    "bypass_reason": bypass_reason,
                    "capture_mode": self.mode,
                }
                
                self.callback(record)
    
        except Exception as e:
            logger.error(f"Error processing packet: {e}")
    
    def _is_doh_provider(self, ip: str, domain: Optional[str]) -> bool:
        """Check if IP/domain belongs to known DoH providers."""
        # Known DoH provider IPs
        DOH_IPS = {
            # Google DNS
            "8.8.8.8", "8.8.4.4",
            # Cloudflare DNS  
            "1.1.1.1", "1.0.0.1",
            # Quad9
            "9.9.9.9", "149.112.112.112",
            # OpenDNS
            "208.67.222.222", "208.67.220.220",
        }
        
        # Known DoH domains
        DOH_DOMAINS = {
            "dns.google", "dns.google.com",
            "cloudflare-dns.com", "one.one.one.one",
            "dns.quad9.net",
            "doh.opendns.com",
            "dns.nextdns.io",
            "dns.adguard.com",
            "doh.cleanbrowsing.org",
        }
        
        if ip in DOH_IPS:
            return True
        
        if domain:
            domain_lower = domain.lower()
            for doh_domain in DOH_DOMAINS:
                if domain_lower == doh_domain or domain_lower.endswith("." + doh_domain):
                    return True
        
        return False
    
    def get_stats(self) -> Dict:
        """Get sniffer statistics."""
        with self._stats_lock:
            return {
                "packet_count": self.packet_count,
                "domain_count": self.domain_count,
                "bypass_attempts": self.bypass_attempts,
                "mode": self.mode,
                "running": self.running,
            }