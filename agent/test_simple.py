"""
Simple DNS Proxy Test - Saves results to file
Run as Administrator!
"""

import os
import sys
import ctypes
import socket
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def main():
    results = []
    results.append("=" * 60)
    results.append("DNS PROXY SIMPLE TEST")
    results.append("=" * 60)
    
    # Admin check
    admin = is_admin()
    results.append(f"\n1. Admin: {'YES' if admin else 'NO'}")
    
    if not admin:
        results.append("ERROR: Run as Administrator!")
        with open("test_results.txt", "w") as f:
            f.write("\n".join(results))
        return
    
    # Port 53 check
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 53))
        sock.close()
        results.append("2. Port 53 UDP: AVAILABLE")
    except OSError as e:
        results.append(f"2. Port 53 UDP: IN USE - {e}")
    
    # Try to start DNS Proxy
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
        
        results.append("3. Creating DNS Proxy Server...")
        server = DNSProxyServer(config=config)
        
        results.append("4. Starting DNS Proxy Server...")
        server.start()
        
        results.append("5. DNS Proxy Server STARTED!")
        
        # Test DNS queries
        import time
        time.sleep(1)
        
        try:
            import dns.resolver
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['127.0.0.1']
            resolver.timeout = 5
            
            # Test a domain
            try:
                answers = resolver.resolve('google.com', 'A')
                ips = [str(r) for r in answers]
                results.append(f"6. DNS query google.com: {ips[0]}")
            except Exception as e:
                results.append(f"6. DNS query google.com: ERROR - {e}")
        except ImportError:
            results.append("6. dnspython not installed")
        
        # Stop server
        server.stop()
        results.append("7. DNS Proxy Server STOPPED")
        
    except Exception as e:
        import traceback
        results.append(f"ERROR: {e}")
        results.append(traceback.format_exc())
    
    results.append("\n" + "=" * 60)
    results.append("TEST COMPLETED")
    results.append("=" * 60)
    
    # Save to file
    with open("test_results.txt", "w") as f:
        f.write("\n".join(results))
    
    print("\n".join(results))
    print("\nResults saved to test_results.txt")

if __name__ == "__main__":
    main()
