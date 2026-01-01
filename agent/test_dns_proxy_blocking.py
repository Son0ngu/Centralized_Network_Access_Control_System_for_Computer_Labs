"""
DNS Proxy Blocking Diagnostic Test
===================================
Test để xác định tại sao DNS Proxy không chặn được domain không có trong whitelist.
"""

import os
import sys
import socket
import ctypes
import subprocess

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_result(test: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} | {test}")
    if detail:
        print(f"         └─ {detail}")

def check_admin():
    """Check if running as administrator."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def get_system_dns():
    """Get current system DNS settings."""
    try:
        result = subprocess.run(
            ['netsh', 'interface', 'ip', 'show', 'dns'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout
    except Exception as e:
        return f"Error: {e}"

def check_port_53_listening():
    """Check if something is listening on port 53."""
    try:
        result = subprocess.run(
            ['netstat', '-an'],
            capture_output=True,
            text=True,
            timeout=10
        )
        lines = result.stdout.split('\n')
        port_53_entries = [l for l in lines if ':53 ' in l or ':53\t' in l]
        return port_53_entries
    except Exception as e:
        return [f"Error: {e}"]

def test_dns_query(domain: str, dns_server: str = "127.0.0.1"):
    """Test DNS query to specific server."""
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [dns_server]
        resolver.timeout = 5
        resolver.lifetime = 5
        
        answers = resolver.resolve(domain, 'A')
        ips = [str(rdata) for rdata in answers]
        return True, ips
    except dns.resolver.NXDOMAIN:
        return False, "NXDOMAIN (blocked)"
    except dns.resolver.NoAnswer:
        return False, "No Answer"
    except dns.resolver.Timeout:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def test_direct_socket_dns(domain: str):
    """Test DNS resolution using system default."""
    try:
        ip = socket.gethostbyname(domain)
        return True, ip
    except socket.gaierror as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def check_dns_proxy_process():
    """Check if DNS Proxy process is running."""
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/V'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout
    except Exception as e:
        return f"Error: {e}"

def get_whitelist_status():
    """Try to get whitelist status from agent."""
    try:
        from whitelist.state import WhitelistState
        from config.loader import load_config
        
        config = load_config()
        state = WhitelistState()
        
        return {
            'domains_count': len(state.get_all_domains()),
            'patterns_count': len(state.get_all_patterns()),
            'domains_sample': list(state.get_all_domains())[:5]
        }
    except Exception as e:
        return {'error': str(e)}

def check_doh_dot_blocking():
    """Check if DoH/DoT ports are blocked in firewall."""
    try:
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        doh_rules = []
        lines = result.stdout.split('\n')
        for i, line in enumerate(lines):
            if 'DoH' in line or 'DoT' in line or '853' in line or '443' in line:
                # Get context
                start = max(0, i-2)
                end = min(len(lines), i+3)
                doh_rules.append('\n'.join(lines[start:end]))
        
        return doh_rules if doh_rules else ["No DoH/DoT blocking rules found"]
    except Exception as e:
        return [f"Error: {e}"]

def test_browser_dns_bypass():
    """Check common DoH endpoints."""
    doh_endpoints = [
        ("dns.google", "8.8.8.8"),
        ("cloudflare-dns.com", "1.1.1.1"),
        ("dns.quad9.net", "9.9.9.9"),
    ]
    
    results = []
    for domain, expected_ip in doh_endpoints:
        resolved, result = test_direct_socket_dns(domain)
        results.append((domain, resolved, result))
    
    return results


def main():
    print("\n" + "="*60)
    print("   DNS PROXY BLOCKING DIAGNOSTIC TEST")
    print("="*60)
    
    # 1. Admin Check
    print_header("1. ADMIN PRIVILEGES")
    is_admin = check_admin()
    print_result("Running as Administrator", is_admin)
    if not is_admin:
        print("\n⚠️  CRITICAL: DNS Proxy requires admin privileges!")
        print("   Please run this script as Administrator.")
    
    # 2. System DNS Settings
    print_header("2. SYSTEM DNS SETTINGS")
    dns_output = get_system_dns()
    print(dns_output)
    
    is_dns_local = "127.0.0.1" in dns_output
    print_result("DNS set to 127.0.0.1", is_dns_local)
    if not is_dns_local:
        print("\n⚠️  CRITICAL: System DNS is NOT set to 127.0.0.1!")
        print("   DNS Proxy cannot intercept queries if DNS is not redirected.")
    
    # 3. Port 53 Check
    print_header("3. PORT 53 STATUS")
    port_53_entries = check_port_53_listening()
    if port_53_entries:
        for entry in port_53_entries[:5]:
            print(f"   {entry.strip()}")
        
        listening_on_53 = any('LISTENING' in e or 'UDP' in e for e in port_53_entries)
        print_result("DNS Proxy listening on port 53", listening_on_53)
    else:
        print("   No entries found for port 53")
        print_result("DNS Proxy listening on port 53", False, "Nothing on port 53!")
    
    # 4. DNS Query Tests
    print_header("4. DNS QUERY TESTS")
    
    # Test domains
    test_domains = [
        ("google.com", "Usually in whitelist"),
        ("facebook.com", "May or may not be whitelisted"),
        ("malware-test-domain.com", "Should be blocked"),
        ("randomsite123456.com", "Random - should be blocked"),
    ]
    
    print("\n  Testing via 127.0.0.1 (DNS Proxy):")
    print("  " + "-"*50)
    
    try:
        import dns.resolver
        for domain, note in test_domains:
            resolved, result = test_dns_query(domain, "127.0.0.1")
            status = "RESOLVED" if resolved else "BLOCKED"
            print(f"   {status:10} | {domain:30} | {result}")
    except ImportError:
        print("   ⚠️  dnspython not installed, using socket instead")
        for domain, note in test_domains:
            resolved, result = test_direct_socket_dns(domain)
            status = "RESOLVED" if resolved else "BLOCKED"
            print(f"   {status:10} | {domain:30} | {result}")
    
    print("\n  Testing via 8.8.8.8 (Google DNS - bypass test):")
    print("  " + "-"*50)
    try:
        import dns.resolver
        for domain, note in test_domains[:2]:
            resolved, result = test_dns_query(domain, "8.8.8.8")
            status = "RESOLVED" if resolved else "BLOCKED"
            print(f"   {status:10} | {domain:30} | {result}")
    except ImportError:
        print("   ⚠️  dnspython not installed")
    
    # 5. Whitelist Status
    print_header("5. WHITELIST STATUS")
    whitelist_info = get_whitelist_status()
    if 'error' in whitelist_info:
        print(f"   ⚠️  Could not load whitelist: {whitelist_info['error']}")
    else:
        print(f"   Domains in whitelist: {whitelist_info['domains_count']}")
        print(f"   Patterns in whitelist: {whitelist_info['patterns_count']}")
        if whitelist_info['domains_sample']:
            print(f"   Sample domains: {whitelist_info['domains_sample']}")
    
    # 6. DoH/DoT Bypass Check
    print_header("6. DOH/DOT BYPASS CHECK")
    doh_results = test_browser_dns_bypass()
    print("\n  Testing DoH provider domains:")
    for domain, resolved, result in doh_results:
        status = "⚠️ REACHABLE" if resolved else "✅ BLOCKED"
        print(f"   {status:15} | {domain:25} | {result}")
    
    if any(r[1] for r in doh_results):
        print("\n  ⚠️  WARNING: DoH providers are reachable!")
        print("     Browsers may bypass DNS Proxy using DoH/DoT!")
        print("     Consider blocking ports 443 to DoH servers in firewall.")
    
    # 7. Summary
    print_header("7. DIAGNOSIS SUMMARY")
    
    issues = []
    if not is_admin:
        issues.append("❌ Not running as Administrator")
    if not is_dns_local:
        issues.append("❌ System DNS not set to 127.0.0.1")
    if not port_53_entries or not any('LISTENING' in e or 'UDP' in e for e in port_53_entries):
        issues.append("❌ DNS Proxy not listening on port 53")
    if any(r[1] for r in doh_results):
        issues.append("⚠️ DoH bypass possible - browsers may use encrypted DNS")
    
    if issues:
        print("\n  ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
        
        print("\n  RECOMMENDED ACTIONS:")
        if not is_admin:
            print("   1. Run Agent GUI as Administrator")
        if not is_dns_local:
            print("   2. Check if DNS Proxy is starting correctly")
            print("      - The agent should set DNS to 127.0.0.1 automatically")
        if any(r[1] for r in doh_results):
            print("   3. Disable DoH in browser settings:")
            print("      - Chrome: Settings > Privacy > Use secure DNS > OFF")
            print("      - Firefox: Settings > Network > Enable DNS over HTTPS > OFF")
            print("      - Edge: Settings > Privacy > Use secure DNS > OFF")
    else:
        print("\n  ✅ No major issues detected")
        print("     DNS Proxy should be blocking correctly.")
    
    print("\n" + "="*60)
    print("   TEST COMPLETED")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
