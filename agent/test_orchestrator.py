"""
Full DNS Proxy Orchestrator Test
================================
Test with whitelist connected.
Run as Administrator!
"""

import os
import sys
import ctypes
import socket
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test")

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def main():
    results = []
    results.append("=" * 60)
    results.append("DNS PROXY ORCHESTRATOR TEST")
    results.append("=" * 60)
    
    # Admin check
    admin = is_admin()
    results.append(f"\n1. Admin: {'YES' if admin else 'NO'}")
    
    if not admin:
        results.append("ERROR: Run as Administrator!")
        with open("test_orchestrator_results.txt", "w") as f:
            f.write("\n".join(results))
        print("\n".join(results))
        return
    
    orchestrator = None
    
    try:
        from dns_proxy import (
            DNSProxyOrchestrator,
            OrchestratorConfig,
            OrchestratorMode,
        )
        # Import WhitelistState directly to avoid circular import
        from dns_proxy.handler import DNSQueryHandler
        
        results.append("\n2. Creating whitelist state...")
        
        # Create a simple mock whitelist state
        class MockWhitelistState:
            """Mock whitelist state for testing."""
            def __init__(self):
                self._domains = {'google.com', 'microsoft.com', 'github.com', 'googleapis.com', 'gstatic.com'}
                self._patterns = {'*.google.com', '*.microsoft.com', '*.github.com'}
                self._ips = set()
            
            def is_domain_allowed(self, domain: str) -> bool:
                # Check exact match
                if domain in self._domains:
                    return True
                # Check patterns
                for pattern in self._patterns:
                    if pattern.startswith('*.'):
                        suffix = pattern[2:]
                        if domain.endswith(suffix) or domain == suffix[1:] if suffix.startswith('.') else domain.endswith('.' + suffix):
                            return True
                return False
            
            def is_ip_allowed(self, ip: str) -> bool:
                return ip in self._ips
            
            def get_stats(self):
                return {
                    'domains_count': len(self._domains),
                    'patterns_count': len(self._patterns),
                    'ips_count': len(self._ips),
                }
            
            def get_all_domains(self):
                return self._domains
            
            def get_all_patterns(self):
                return self._patterns
        
        state = MockWhitelistState()
        
        stats = state.get_stats()
        results.append(f"   Whitelist: {stats.get('domains_count', 0)} domains, {stats.get('patterns_count', 0)} patterns")
        
        results.append("\n3. Creating orchestrator config...")
        
        config = OrchestratorConfig(
            mode=OrchestratorMode.ACTIVE,
            dns_proxy_enabled=True,
            dns_bind_address="127.0.0.1",
            dns_port=53,
            network_manager_enabled=True,
            auto_configure_dns=True,
            security_enabled=False,  # Disable for simpler test
            firewall_sync_enabled=False,
        )
        
        results.append("\n4. Creating orchestrator...")
        orchestrator = DNSProxyOrchestrator(config)
        
        results.append("\n5. Connecting whitelist to orchestrator...")
        orchestrator.set_whitelist_state(state)
        
        results.append("\n6. Starting orchestrator...")
        success = orchestrator.start()
        
        if success:
            results.append("   ORCHESTRATOR STARTED SUCCESSFULLY!")
        else:
            results.append("   ERROR: Orchestrator failed to start!")
            
        # Wait a bit
        time.sleep(2)
        
        # Test DNS queries
        results.append("\n7. Testing DNS queries...")
        
        try:
            import dns.resolver
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['127.0.0.1']
            resolver.timeout = 10
            resolver.lifetime = 10
            
            test_domains = [
                ("google.com", "WHITELISTED - should resolve"),
                ("microsoft.com", "WHITELISTED - should resolve"),
                ("facebook.com", "NOT WHITELISTED - should block/NXDOMAIN"),
                ("twitter.com", "NOT WHITELISTED - should block/NXDOMAIN"),
            ]
            
            for domain, expected in test_domains:
                try:
                    answers = resolver.resolve(domain, 'A')
                    ips = [str(r) for r in answers]
                    results.append(f"   ✓ {domain:20} → {ips[0]:15} | {expected}")
                except dns.resolver.NXDOMAIN:
                    results.append(f"   ✗ {domain:20} → NXDOMAIN (blocked) | {expected}")
                except dns.resolver.Timeout:
                    results.append(f"   ? {domain:20} → TIMEOUT | {expected}")
                except Exception as e:
                    results.append(f"   ! {domain:20} → ERROR: {e}")
                    
        except ImportError:
            results.append("   dnspython not installed - using socket")
            
            for domain, expected in [("google.com", "should resolve"), ("facebook.com", "should block")]:
                try:
                    ip = socket.gethostbyname(domain)
                    results.append(f"   ✓ {domain:20} → {ip}")
                except socket.gaierror as e:
                    results.append(f"   ✗ {domain:20} → BLOCKED: {e}")
        
        # Get status
        results.append("\n8. Orchestrator status:")
        try:
            status = orchestrator.get_status()
            for key, value in status.items():
                results.append(f"   {key}: {value}")
        except Exception as e:
            results.append(f"   Error getting status: {e}")
            
    except Exception as e:
        import traceback
        results.append(f"\nERROR: {e}")
        results.append(traceback.format_exc())
    
    finally:
        # Cleanup
        if orchestrator:
            results.append("\n9. Stopping orchestrator...")
            try:
                orchestrator.stop()
                results.append("   Orchestrator stopped.")
            except Exception as e:
                results.append(f"   Error stopping: {e}")
    
    results.append("\n" + "=" * 60)
    results.append("TEST COMPLETED")
    results.append("=" * 60)
    
    # Save to file
    with open("test_orchestrator_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    
    print("\n".join(results))
    print("\nResults saved to test_orchestrator_results.txt")
    
    # Keep window open
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
