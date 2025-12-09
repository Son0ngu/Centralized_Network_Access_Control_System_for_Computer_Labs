import logging
import re
from typing import Optional

from scapy.layers.dns import DNS
from scapy.layers.inet import TCP
from scapy.packet import Packet

try:
    from scapy.layers.http import HTTPRequest
except ImportError:
    HTTPRequest = None

try:
    from scapy.layers.tls.extensions import ServerName
    from scapy.layers.tls.handshake import TLSClientHello
except ImportError:
    ServerName = None
    TLSClientHello = None

logger = logging.getLogger("capture.extractors")


class DomainExtractor:
    """Extracts domain names from various packet types."""
    
    @staticmethod
    def extract_http_host(packet: Packet) -> Optional[str]:
        """
        Extract Host header from HTTP packet.
        
        Args:
            packet: Scapy packet with HTTP layer
            
        Returns:
            Domain name or None
        """
        try:
            # Method 1: Use Scapy's HTTPRequest layer (if available)
            if HTTPRequest is not None and packet.haslayer(HTTPRequest):
                if hasattr(packet[HTTPRequest], 'Host'):
                    return packet[HTTPRequest].Host.decode('utf-8', errors='ignore')
            
            # Method 2: Manual extraction from payload
            if packet.haslayer(TCP) and packet[TCP].payload:
                payload = bytes(packet[TCP].payload)
                
                if b"Host: " in payload:
                    host_idx = payload.find(b"Host: ") + 6
                    end_idx = payload.find(b"\r\n", host_idx)
                    
                    if end_idx > host_idx:
                        host = payload[host_idx:end_idx].decode('utf-8', errors='ignore')
                        return host.strip()
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting HTTP host: {e}")
            return None
    
    @staticmethod
    def extract_https_sni(packet: Packet) -> Optional[str]:
        """
        Extract SNI from TLS ClientHello.
        
        Args:
            packet: Scapy packet with TLS layer
            
        Returns:
            Domain name or None
        """
        try:
            # Method 1: Use Scapy's TLS layer (if available)
            if TLSClientHello is not None and packet.haslayer(TLSClientHello):
                client_hello = packet[TLSClientHello]
                
                if hasattr(client_hello, 'ext') and client_hello.ext:
                    for extension in client_hello.ext:
                        if ServerName is not None and isinstance(extension, ServerName):
                            if hasattr(extension, 'servernames') and extension.servernames:
                                servername = extension.servernames[0].servername
                                hostname = servername.decode('utf-8', errors='ignore')
                                if DomainExtractor._is_valid_hostname(hostname):
                                    return hostname
            
            # Method 2: Manual extraction from payload
            if packet.haslayer(TCP) and packet[TCP].payload:
                payload = bytes(packet[TCP].payload)
                return DomainExtractor._extract_sni_manual(payload)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting HTTPS SNI: {e}")
            return None
    
    @staticmethod
    def _extract_sni_manual(payload: bytes) -> Optional[str]:
        """Manual SNI extraction from TLS payload."""
        try:
            # Check minimum length and TLS handshake type
            if len(payload) < 43 or payload[0] != 0x16:
                return None
            
            # Check ClientHello type
            if len(payload) <= 5 or payload[5] != 0x01:
                return None

            # Parse TLS structure
            pos = 9  # Skip record header (5) + handshake header (4)
            pos += 2  # Skip client version
            pos += 32  # Skip client random
            
            if pos >= len(payload):
                return None
            
            # Skip session ID
            session_id_length = payload[pos]
            pos += 1 + session_id_length
            
            # Skip cipher suites
            if pos + 2 > len(payload):
                return None
            cipher_suites_length = (payload[pos] << 8) | payload[pos + 1]
            pos += 2 + cipher_suites_length
            
            # Skip compression methods
            if pos >= len(payload):
                return None
            compression_methods_length = payload[pos]
            pos += 1 + compression_methods_length
            
            # Parse extensions
            if pos + 2 > len(payload):
                return None
            extensions_length = (payload[pos] << 8) | payload[pos + 1]
            pos += 2
            extensions_end = pos + extensions_length
            
            if extensions_end > len(payload):
                return None
            
            # Find SNI extension
            while pos + 4 <= extensions_end:
                ext_type = (payload[pos] << 8) | payload[pos + 1]
                pos += 2
                ext_length = (payload[pos] << 8) | payload[pos + 1]
                pos += 2
                
                if pos + ext_length > extensions_end:
                    break
                
                # SNI extension type is 0
                if ext_type == 0 and ext_length > 2:
                    if pos + 2 > extensions_end:
                        break
                    
                    pos += 2  # Skip SNI list length
                    
                    if pos < extensions_end and payload[pos] == 0:
                        pos += 1
                        
                        if pos + 2 > extensions_end:
                            break
                        
                        name_length = (payload[pos] << 8) | payload[pos + 1]
                        pos += 2
                        
                        if pos + name_length <= extensions_end:
                            hostname = payload[pos:pos + name_length].decode('utf-8', errors='ignore')
                            if DomainExtractor._is_valid_hostname(hostname):
                                return hostname
                
                pos += ext_length
            
            return None
            
        except (IndexError, Exception):
            return None
    
    @staticmethod
    def extract_dns_query(packet: Packet) -> Optional[str]:
        """
        Extract domain from DNS query.
        
        Args:
            packet: Scapy packet with DNS layer
            
        Returns:
            Queried domain or None
        """
        try:
            if packet.haslayer(DNS):
                dns_layer = packet[DNS]
                
                if hasattr(dns_layer, 'qd') and dns_layer.qd:
                    domain = dns_layer.qd.qname.decode('utf-8', errors='ignore').rstrip('.')
                    if DomainExtractor._is_valid_hostname(domain):
                        return domain
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting DNS query: {e}")
            return None
    
    @staticmethod
    def _is_valid_hostname(hostname: str) -> bool:
        """Validate hostname format."""
        if not hostname or len(hostname) > 253:
            return False
        
        if not re.match(r'^[a-zA-Z0-9.-]+$', hostname):
            return False
        
        if '.' not in hostname:
            return False
        
        parts = hostname.split('.')
        for part in parts:
            if not part or part.startswith('-') or part.endswith('-'):
                return False
        
        return True