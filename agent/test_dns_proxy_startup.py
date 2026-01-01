"""
DNS Proxy Component Startup Test
================================
Test từng component của DNS Proxy để tìm lỗi cụ thể.
"""

import os
import sys
import ctypes
import logging

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_startup")

def check_admin():
    """Check if running as administrator."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def test_dns_proxy_imports():
    """Test all DNS Proxy imports."""
    print("\n" + "="*60)
    print("TEST 1: DNS PROXY IMPORTS")
    print("="*60)
    
    try:
        from dns_proxy import (
            DNSProxyOrchestrator,
            OrchestratorConfig,
            OrchestratorMode,
            DNSProxyServer,
            DNSProxyConfig,
            DNSServerConfig,
            NetworkManager,
            SecurityManager,
        )
        print("✅ All DNS Proxy imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_load():
    """Test config loading."""
    print("\n" + "="*60)
    print("TEST 2: CONFIG LOADING")
    print("="*60)
    
    try:
        from config import load_config
        config = load_config()
        
        print(f"✅ Config loaded successfully")
        print(f"   DNS Proxy enabled: {config.get('dns_proxy', {}).get('enabled', 'NOT SET')}")
        print(f"   DNS Proxy mode: {config.get('dns_proxy', {}).get('mode', 'NOT SET')}")
        print(f"   DNS Port: {config.get('dns_proxy', {}).get('port', 'NOT SET')}")
        
        return True, config
    except Exception as e:
        print(f"❌ Config error: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_port_53_available():
    """Test if port 53 is available."""
    print("\n" + "="*60)
    print("TEST 3: PORT 53 AVAILABILITY")
    print("="*60)
    
    import socket
    
    # Check UDP
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 53))
        sock.close()
        print("✅ UDP port 53 is available")
        udp_ok = True
    except OSError as e:
        print(f"❌ UDP port 53 NOT available: {e}")
        udp_ok = False
    
    # Check TCP
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 53))
        sock.close()
        print("✅ TCP port 53 is available")
        tcp_ok = True
    except OSError as e:
        print(f"❌ TCP port 53 NOT available: {e}")
        tcp_ok = False
    
    return udp_ok and tcp_ok


def test_dns_proxy_server_start():
    """Test starting DNS Proxy Server directly."""
    print("\n" + "="*60)
    print("TEST 4: DNS PROXY SERVER START")
    print("="*60)
    
    try:
        from dns_proxy import DNSProxyServer, DNSProxyConfig, DNSServerConfig
        
        server_config = DNSServerConfig(
            bind_address="127.0.0.1",
            port=53,
        )
        
        config = DNSProxyConfig(
            enabled=True,
            server=server_config,
        )
        
        print("Creating DNS Proxy Server...")
        server = DNSProxyServer(config=config)
        
        print("Starting DNS Proxy Server...")
        server.start()
        
        print("✅ DNS Proxy Server started successfully!")
        print("   Listening on 127.0.0.1:53")
        
        # Keep running for a moment
        import time
        time.sleep(2)
        
        print("Stopping DNS Proxy Server...")
        server.stop()
        
        print("✅ DNS Proxy Server stopped successfully")
        return True
        
    except Exception as e:
        print(f"❌ DNS Proxy Server error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_network_manager():
    """Test Network Manager (DNS settings)."""
    print("\n" + "="*60)
    print("TEST 5: NETWORK MANAGER")
    print("="*60)
    
    try:
        from dns_proxy.network import NetworkManager, NetworkConfig, NetworkMode
        
        config = NetworkConfig(
            mode=NetworkMode.ACTIVE,
            auto_configure_dns=True,
            dns_address="127.0.0.1",
        )
        
        print("Creating Network Manager...")
        manager = NetworkManager(config=config)
        
        print("Enabling Network Manager (setting DNS to 127.0.0.1)...")
        result = manager.enable()
        
        if result:
            print("✅ Network Manager enabled - DNS should be set to 127.0.0.1")
            
            # Get status
            status = manager.get_status()
            print(f"   Status: {status}")
            
            return True, manager
        else:
            print("❌ Network Manager failed to enable")
            return False, None
        
    except Exception as e:
        print(f"❌ Network Manager error: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_orchestrator_start():
    """Test Orchestrator start."""
    print("\n" + "="*60)
    print("TEST 6: ORCHESTRATOR FULL START")
    print("="*60)
    
    try:
        from dns_proxy import (
            DNSProxyOrchestrator,
            OrchestratorConfig,
            OrchestratorMode,
        )
        
        config = OrchestratorConfig(
            mode=OrchestratorMode.ACTIVE,
            dns_proxy_enabled=True,
            dns_bind_address="127.0.0.1",
            dns_port=53,
            network_manager_enabled=True,
            auto_configure_dns=True,
            security_enabled=True,
            block_doh=True,
            block_dot=True,
            firewall_sync_enabled=False,  # Disable for test
        )
        
        print("Creating Orchestrator...")
        orchestrator = DNSProxyOrchestrator(config)
        
        # Optional: Connect to whitelist
        try:
            from whitelist.state import WhitelistState
            state = WhitelistState()
            # Add test domain
            state.update({
                'domains': ['google.com', 'microsoft.com'],
                'patterns': [],
                'ips': [],
            })
            orchestrator.set_whitelist_state(state)
            print("   Connected whitelist with test domains: google.com, microsoft.com")
        except Exception as e:
            print(f"   ⚠️ Could not connect whitelist: {e}")
        
        print("Starting Orchestrator...")
        success = orchestrator.start()
        
        if success:
            print("✅ Orchestrator started successfully!")
            
            # Get status
            status = orchestrator.get_status()
            print(f"\n   Component Status:")
            for comp, info in status.items():
                print(f"   - {comp}: {info}")
            
            print("\n   DNS Proxy should now be blocking non-whitelisted domains.")
            print("   Try accessing a domain NOT in whitelist (e.g., facebook.com)")
            
            return True, orchestrator
        else:
            print("❌ Orchestrator failed to start")
            return False, None
        
    except Exception as e:
        print(f"❌ Orchestrator error: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    print("\n" + "="*60)
    print("   DNS PROXY COMPONENT STARTUP TEST")
    print("="*60)
    
    # Check admin
    is_admin = check_admin()
    print(f"\nAdmin privileges: {'✅ YES' if is_admin else '❌ NO'}")
    
    if not is_admin:
        print("\n⚠️  WARNING: DNS Proxy requires Administrator privileges!")
        print("   Please run this script as Administrator.")
        print("   Right-click → Run as Administrator")
        return
    
    # Run tests
    results = {}
    
    # Test 1: Imports
    results['imports'] = test_dns_proxy_imports()
    
    # Test 2: Config
    config_ok, config = test_config_load()
    results['config'] = config_ok
    
    # Test 3: Port 53
    results['port_53'] = test_port_53_available()
    
    if not results['port_53']:
        print("\n⚠️  Port 53 is in use! Another DNS service may be running.")
        print("   Check if another DNS Proxy is already running.")
        
    # Test 4: DNS Proxy Server (only if port available)
    if results['port_53']:
        results['dns_server'] = test_dns_proxy_server_start()
    else:
        print("\n⏭️  Skipping DNS Server test (port not available)")
        results['dns_server'] = False
    
    # Test 5: Network Manager
    if results['dns_server']:
        net_ok, net_manager = test_network_manager()
        results['network_manager'] = net_ok
        
        # Restore DNS if we changed it
        if net_manager:
            try:
                net_manager.disable()
                print("   DNS settings restored")
            except:
                pass
    else:
        results['network_manager'] = False
    
    # Test 6: Full Orchestrator (only if everything else OK)
    if all([results['imports'], results['config'], results['port_53']]):
        orch_ok, orchestrator = test_orchestrator_start()
        results['orchestrator'] = orch_ok
        
        if orchestrator:
            print("\n" + "="*60)
            print("   INTERACTIVE DNS TEST")
            print("="*60)
            print("\nOrchestrator is running. Testing DNS queries...")
            
            # Test DNS queries
            try:
                import dns.resolver
                resolver = dns.resolver.Resolver()
                resolver.nameservers = ['127.0.0.1']
                resolver.timeout = 5
                
                test_domains = [
                    ("google.com", "Should RESOLVE (whitelisted)"),
                    ("microsoft.com", "Should RESOLVE (whitelisted)"),
                    ("facebook.com", "Should BLOCK (not whitelisted)"),
                    ("twitter.com", "Should BLOCK (not whitelisted)"),
                ]
                
                print("\nDNS Query Results:")
                for domain, expected in test_domains:
                    try:
                        answers = resolver.resolve(domain, 'A')
                        ips = [str(r) for r in answers]
                        print(f"  ✓ {domain:20} → {ips[0]:15} | {expected}")
                    except dns.resolver.NXDOMAIN:
                        print(f"  ✗ {domain:20} → BLOCKED (NXDOMAIN) | {expected}")
                    except Exception as e:
                        print(f"  ? {domain:20} → Error: {e}")
                
            except ImportError:
                print("   ⚠️ dnspython not installed for testing")
            
            # Stop orchestrator
            print("\n" + "="*60)
            input("Press Enter to stop orchestrator and restore settings...")
            orchestrator.stop()
            print("Orchestrator stopped.")
    else:
        results['orchestrator'] = False
    
    # Summary
    print("\n" + "="*60)
    print("   TEST SUMMARY")
    print("="*60)
    
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} | {test}")
    
    if all(results.values()):
        print("\n✅ All tests passed! DNS Proxy should work correctly.")
    else:
        print("\n❌ Some tests failed. Check the errors above.")


if __name__ == "__main__":
    main()
