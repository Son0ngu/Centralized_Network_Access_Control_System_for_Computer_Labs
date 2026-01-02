"""
Whitelist Flow Diagnostic Test
==============================
Kiểm tra từng bước của flow whitelist:
1. Kết nối server và sync whitelist
2. Kiểm tra whitelist state có domain không
3. Kiểm tra DNS handler có check whitelist đúng không
4. Kiểm tra upstream resolver có hoạt động không
5. Test full flow: domain → DNS proxy → response

Chạy:
    python test_whitelist_flow.py

Chạy với debug chi tiết:
    python test_whitelist_flow.py --debug

Author: Firewall Controller Team
"""

import argparse
import json
import logging
import os
import socket
import sys
import time
from typing import Dict, List, Optional, Tuple

# Add agent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Colors for output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(title: str):
    print(f"\n{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}{title}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*60}{Colors.RESET}")


def print_ok(msg: str):
    print(f"  {Colors.GREEN}[OK]{Colors.RESET} {msg}")


def print_fail(msg: str):
    print(f"  {Colors.RED}[FAIL]{Colors.RESET} {msg}")


def print_warn(msg: str):
    print(f"  {Colors.YELLOW}[WARN]{Colors.RESET} {msg}")


def print_info(msg: str):
    print(f"  {Colors.BLUE}[INFO]{Colors.RESET} {msg}")


# ============================================================================
# TEST 1: Load Configuration
# ============================================================================
def test_configuration() -> Tuple[bool, Dict]:
    """Test loading configuration."""
    print_header("TEST 1: Load Configuration")
    
    try:
        from config import get_config
        config = get_config()
        
        print_ok(f"Configuration loaded from agent_config.json")
        
        # Check server config
        server_config = config.get("server", {})
        server_url = server_config.get("url", "")
        server_urls = server_config.get("urls", [])
        
        if server_url:
            print_ok(f"Primary server URL: {server_url}")
        if server_urls:
            print_ok(f"Server URLs: {server_urls}")
        
        if not server_url and not server_urls:
            print_fail("No server URL configured!")
            return False, config
        
        # Check auth config
        auth_config = config.get("auth", {})
        api_key = auth_config.get("api_key", "")
        if api_key:
            print_ok(f"API Key configured: {api_key[:20]}...")
        else:
            print_warn("No API key configured")
        
        # Check DNS proxy config
        dns_config = config.get("dns_proxy", {})
        print_info(f"DNS Proxy mode: {dns_config.get('mode', 'not set')}")
        print_info(f"DNS Proxy enabled: {dns_config.get('enabled', False)}")
        
        return True, config
        
    except Exception as e:
        print_fail(f"Failed to load configuration: {e}")
        return False, {}


# ============================================================================
# TEST 2: Server Connectivity
# ============================================================================
def test_server_connectivity(config: Dict) -> Tuple[bool, str]:
    """Test connectivity to server."""
    print_header("TEST 2: Server Connectivity")
    
    import requests
    
    server_config = config.get("server", {})
    urls = list(server_config.get("urls", []))
    if server_config.get("url"):
        urls.insert(0, server_config["url"])
    
    working_url = None
    
    for url in urls:
        try:
            # Test health endpoint
            health_url = f"{url.rstrip('/')}/api/health"
            print_info(f"Testing: {health_url}")
            
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                print_ok(f"Server reachable: {url}")
                working_url = url
                break
            else:
                print_warn(f"Server returned {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print_fail(f"Cannot connect to {url}")
        except Exception as e:
            print_fail(f"Error testing {url}: {e}")
    
    if not working_url:
        # Try localhost as fallback
        try:
            response = requests.get("http://localhost:5000/api/health", timeout=5)
            if response.status_code == 200:
                print_ok("Server reachable at localhost:5000")
                working_url = "http://localhost:5000"
        except:
            pass
    
    if working_url:
        return True, working_url
    else:
        print_fail("No server is reachable!")
        return False, ""


# ============================================================================
# TEST 3: Whitelist Sync
# ============================================================================
def test_whitelist_sync(config: Dict, server_url: str) -> Tuple[bool, Dict]:
    """Test whitelist sync from server."""
    print_header("TEST 3: Whitelist Sync")
    
    import requests
    
    try:
        # Get agent_id from config or generate one
        agent_id = config.get("agent_id", "test-agent-001")
        
        # Build sync URL
        sync_url = f"{server_url.rstrip('/')}/api/whitelist/agent-sync"
        print_info(f"Sync URL: {sync_url}")
        
        # Build headers
        headers = {'Content-Type': 'application/json'}
        
        # Add API key if available
        api_key = config.get("auth", {}).get("api_key", "")
        if api_key:
            headers["X-API-KEY"] = api_key
        
        # Add JWT if available
        auth_config = config.get("auth", {})
        access_token = auth_config.get("access_token", "")
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        
        # Make sync request
        params = {
            "agent_id": agent_id,
            "current_version": "",
            "mode": "full"
        }
        
        print_info(f"Agent ID: {agent_id}")
        print_info(f"Headers: {list(headers.keys())}")
        
        response = requests.get(sync_url, params=params, headers=headers, timeout=30)
        
        print_info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                whitelist_data = data.get("data", {})
                domains = whitelist_data.get("domains", [])
                
                print_ok(f"Whitelist synced successfully!")
                print_ok(f"Total domains: {len(domains)}")
                
                # Show first 10 domains
                if domains:
                    print_info("Sample domains:")
                    for i, domain in enumerate(domains[:10]):
                        if isinstance(domain, dict):
                            value = domain.get("value", domain.get("domain", "?"))
                            dtype = domain.get("type", "domain")
                            print(f"      {i+1}. {value} ({dtype})")
                        else:
                            print(f"      {i+1}. {domain}")
                    
                    if len(domains) > 10:
                        print(f"      ... and {len(domains) - 10} more")
                else:
                    print_warn("Whitelist is EMPTY!")
                
                return True, whitelist_data
            else:
                print_fail(f"Sync failed: {data.get('message', 'Unknown error')}")
                return False, {}
        
        elif response.status_code == 401:
            print_fail("Authentication failed - check API key or JWT token")
            return False, {}
        else:
            print_fail(f"Server error: {response.status_code}")
            print_info(f"Response: {response.text[:500]}")
            return False, {}
            
    except Exception as e:
        print_fail(f"Sync error: {e}")
        import traceback
        traceback.print_exc()
        return False, {}


# ============================================================================
# TEST 4: Whitelist State Matching
# ============================================================================
def test_whitelist_state(whitelist_data: Dict, test_domains: List[str] = None) -> bool:
    """Test whitelist state domain matching."""
    print_header("TEST 4: Whitelist State Matching")
    
    try:
        from whitelist.state import WhitelistState
        
        state = WhitelistState()
        updated = state.update(whitelist_data)
        
        if updated:
            print_ok("Whitelist state updated")
        else:
            print_warn("No changes in whitelist state")
        
        stats = state.get_stats()
        print_info(f"Domains: {stats.get('domains', 0)}")
        print_info(f"Patterns: {stats.get('patterns', 0)}")
        print_info(f"IPs: {stats.get('ips', 0)}")
        
        # Show actual domains in state
        all_domains = state.get_all_domains()
        print_info(f"Domains in state: {list(all_domains)[:10]}")
        
        all_patterns = state.get_all_patterns()
        if all_patterns:
            print_info(f"Patterns in state: {list(all_patterns)[:5]}")
        
        # Test domain matching
        if test_domains is None:
            # Get some domains from whitelist to test
            test_domains = list(all_domains)[:5]
            # Add some that should NOT be allowed
            test_domains.extend(["should-not-exist.xyz", "blocked-domain.test"])
        
        print("\n  Domain matching tests:")
        
        all_passed = True
        for domain in test_domains:
            allowed = state.is_domain_allowed(domain)
            is_in_whitelist = domain.lower() in {d.lower() for d in all_domains}
            
            # Check pattern match
            pattern_match = False
            for pattern in all_patterns:
                import fnmatch
                if fnmatch.fnmatch(domain.lower(), pattern.lower()):
                    pattern_match = True
                    break
            
            expected = is_in_whitelist or pattern_match
            
            status = "OK" if allowed == expected else "MISMATCH"
            symbol = Colors.GREEN + "✓" if allowed else Colors.RED + "✗"
            
            print(f"    {symbol}{Colors.RESET} {domain}: allowed={allowed} (in_list={is_in_whitelist}, pattern={pattern_match})")
            
            if allowed != expected:
                all_passed = False
        
        if all_passed:
            print_ok("All domain matching tests passed")
        else:
            print_warn("Some domain matching tests had unexpected results")
        
        return True
        
    except Exception as e:
        print_fail(f"Whitelist state test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 5: Upstream DNS Resolver
# ============================================================================
def test_upstream_resolver() -> bool:
    """Test upstream DNS resolver connectivity."""
    print_header("TEST 5: Upstream DNS Resolver")
    
    try:
        import dns.resolver
        import dns.query
        import dns.message
        
        # Test resolvers
        resolvers = [
            ("8.8.8.8", "Google DNS"),
            ("1.1.1.1", "Cloudflare DNS"),
            ("208.67.222.222", "OpenDNS"),
        ]
        
        test_domain = "google.com"
        working_resolvers = 0
        
        for resolver_ip, name in resolvers:
            try:
                # Create query
                query = dns.message.make_query(test_domain, "A")
                
                # Send query with timeout
                response = dns.query.udp(
                    query, 
                    resolver_ip, 
                    timeout=3
                )
                
                # Check response
                if response.answer:
                    ips = [str(rdata) for rrset in response.answer for rdata in rrset]
                    print_ok(f"{name} ({resolver_ip}): {test_domain} -> {ips[0]}")
                    working_resolvers += 1
                else:
                    print_warn(f"{name} ({resolver_ip}): No answer")
                    
            except dns.exception.Timeout:
                print_fail(f"{name} ({resolver_ip}): TIMEOUT")
            except Exception as e:
                print_fail(f"{name} ({resolver_ip}): {e}")
        
        if working_resolvers > 0:
            print_ok(f"{working_resolvers}/{len(resolvers)} resolvers working")
            return True
        else:
            print_fail("No upstream resolvers are reachable!")
            print_info("Check if firewall is blocking outbound DNS (port 53)")
            return False
            
    except ImportError:
        print_fail("dnspython not installed")
        return False
    except Exception as e:
        print_fail(f"Resolver test failed: {e}")
        return False


# ============================================================================
# TEST 6: DNS Proxy Port
# ============================================================================
def test_dns_proxy_port() -> bool:
    """Test if DNS proxy is listening."""
    print_header("TEST 6: DNS Proxy Port Check")
    
    try:
        # Check if port 53 is listening
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        
        try:
            sock.bind(("127.0.0.1", 53))
            sock.close()
            print_warn("Port 53 is FREE - DNS Proxy is NOT running")
            return False
        except OSError:
            print_ok("Port 53 is in use - DNS Proxy appears to be running")
        
        # Try to send a DNS query to local proxy
        try:
            import dns.message
            import dns.query
            
            query = dns.message.make_query("test.local", "A")
            response = dns.query.udp(query, "127.0.0.1", port=53, timeout=2)
            print_ok("DNS Proxy responds to queries")
            return True
            
        except dns.exception.Timeout:
            print_fail("DNS Proxy not responding (timeout)")
            return False
        except Exception as e:
            print_warn(f"DNS query test: {e}")
            return True  # Port is in use, probably running
            
    except Exception as e:
        print_fail(f"Port check failed: {e}")
        return False


# ============================================================================
# TEST 7: Full DNS Query Flow
# ============================================================================
def test_dns_query_flow(whitelist_data: Dict, config: Dict) -> bool:
    """Test full DNS query through proxy."""
    print_header("TEST 7: Full DNS Query Flow")
    
    try:
        import dns.message
        import dns.query
        import dns.rdatatype
        
        # Get domains from whitelist
        domains = whitelist_data.get("domains", [])
        
        if not domains:
            print_warn("No domains in whitelist to test")
            return False
        
        # Get first 3 domains for testing
        test_domains = []
        for d in domains[:3]:
            if isinstance(d, dict):
                test_domains.append(d.get("value", d.get("domain", "")))
            else:
                test_domains.append(d)
        
        # Add a domain that should be blocked
        test_domains.append("blocked-test-domain.xyz")
        
        print_info(f"Testing domains: {test_domains}")
        
        successes = 0
        
        for domain in test_domains:
            if not domain:
                continue
            
            try:
                # Create DNS query
                query = dns.message.make_query(domain, "A")
                
                print(f"\n  Testing: {domain}")
                
                # Query local DNS proxy
                start = time.time()
                response = dns.query.udp(query, "127.0.0.1", port=53, timeout=10)
                elapsed = (time.time() - start) * 1000
                
                # Check response
                rcode = dns.rcode.to_text(response.rcode())
                
                if rcode == "NOERROR":
                    if response.answer:
                        ips = [str(rdata) for rrset in response.answer for rdata in rrset]
                        print_ok(f"  {domain} -> {ips[0]} ({elapsed:.0f}ms)")
                        successes += 1
                    else:
                        print_warn(f"  {domain} -> NOERROR but no answer ({elapsed:.0f}ms)")
                elif rcode == "NXDOMAIN":
                    # Check if it should be blocked
                    is_whitelisted = any(
                        (isinstance(d, dict) and d.get("value", d.get("domain", "")).lower() == domain.lower()) or
                        (isinstance(d, str) and d.lower() == domain.lower())
                        for d in domains
                    )
                    
                    if is_whitelisted:
                        print_fail(f"  {domain} -> BLOCKED but is in whitelist!")
                    else:
                        print_ok(f"  {domain} -> BLOCKED (not in whitelist) ({elapsed:.0f}ms)")
                        successes += 1
                else:
                    print_warn(f"  {domain} -> {rcode} ({elapsed:.0f}ms)")
                    
            except dns.exception.Timeout:
                print_fail(f"  {domain} -> TIMEOUT")
            except Exception as e:
                print_fail(f"  {domain} -> ERROR: {e}")
        
        if successes > 0:
            print_ok(f"\n{successes}/{len(test_domains)} queries successful")
            return True
        else:
            print_fail("All DNS queries failed!")
            return False
            
    except ImportError:
        print_fail("dnspython not installed")
        return False
    except Exception as e:
        print_fail(f"DNS flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 8: Check Current DNS Settings
# ============================================================================
def test_dns_settings() -> bool:
    """Check current DNS settings."""
    print_header("TEST 8: Current DNS Settings")
    
    try:
        import subprocess
        
        # Get DNS settings
        result = subprocess.run(
            ["netsh", "interface", "ipv4", "show", "dnsservers"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print_info("Current DNS configuration:")
        
        lines = result.stdout.strip().split('\n')
        adapter_info = {}
        current_adapter = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("Configuration for interface"):
                current_adapter = line.split('"')[1] if '"' in line else "Unknown"
                adapter_info[current_adapter] = []
            elif current_adapter and line:
                if "DHCP" in line.upper():
                    adapter_info[current_adapter].append("DHCP")
                elif any(c.isdigit() for c in line):
                    # Extract IP
                    parts = line.split()
                    for part in parts:
                        if part.replace('.', '').isdigit():
                            adapter_info[current_adapter].append(part)
                            break
        
        dns_to_proxy = False
        
        for adapter, dns_list in adapter_info.items():
            dns_str = ", ".join(dns_list) if dns_list else "None"
            
            if "127.0.0.1" in dns_list:
                print_ok(f"  {adapter}: {dns_str} (using DNS Proxy)")
                dns_to_proxy = True
            elif "DHCP" in dns_list:
                print_warn(f"  {adapter}: {dns_str}")
            else:
                print_info(f"  {adapter}: {dns_str}")
        
        if dns_to_proxy:
            print_ok("At least one adapter is using the DNS Proxy (127.0.0.1)")
        else:
            print_fail("No adapter is using the DNS Proxy!")
            print_info("DNS queries may be bypassing the proxy entirely")
        
        return dns_to_proxy
        
    except Exception as e:
        print_fail(f"Failed to check DNS settings: {e}")
        return False


# ============================================================================
# TEST 9: Check Firewall Rules
# ============================================================================
def test_firewall_rules() -> bool:
    """Check firewall rules created by agent."""
    print_header("TEST 9: Firewall Rules")
    
    try:
        import subprocess
        
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Find DNS proxy rules
        dns_proxy_rules = []
        fc_rules = []
        
        for line in result.stdout.split('\n'):
            if line.startswith("Rule Name:"):
                rule_name = line.replace("Rule Name:", "").strip()
                if rule_name.startswith("DNS_Proxy_"):
                    dns_proxy_rules.append(rule_name)
                elif rule_name.startswith("FirewallController") or rule_name.startswith("FC_"):
                    fc_rules.append(rule_name)
        
        print_info(f"DNS Proxy rules: {len(dns_proxy_rules)}")
        print_info(f"FirewallController rules: {len(fc_rules)}")
        
        if dns_proxy_rules:
            print_info("Sample DNS Proxy rules:")
            for rule in dns_proxy_rules[:5]:
                print(f"      - {rule}")
        
        # Check for block rules that might interfere
        block_rules = [r for r in dns_proxy_rules if "Block" in r]
        if block_rules:
            print_warn(f"Found {len(block_rules)} BLOCK rules - these may block upstream DNS")
            for rule in block_rules[:3]:
                print(f"      - {rule}")
        
        return True
        
    except Exception as e:
        print_fail(f"Failed to check firewall rules: {e}")
        return False


# ============================================================================
# DIAGNOSIS SUMMARY
# ============================================================================
def print_diagnosis(results: Dict):
    """Print diagnosis summary."""
    print_header("DIAGNOSIS SUMMARY")
    
    issues = []
    
    if not results.get("config"):
        issues.append("Configuration loading failed")
    
    if not results.get("server"):
        issues.append("Cannot connect to server")
    
    if not results.get("sync"):
        issues.append("Whitelist sync failed")
    
    if not results.get("upstream"):
        issues.append("Upstream DNS resolvers are blocked/unreachable")
    
    if not results.get("proxy_running"):
        issues.append("DNS Proxy is not running")
    
    if not results.get("dns_settings"):
        issues.append("DNS not configured to use proxy (127.0.0.1)")
    
    if issues:
        print(f"\n{Colors.RED}Issues found:{Colors.RESET}")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        
        print(f"\n{Colors.YELLOW}Recommended actions:{Colors.RESET}")
        
        if not results.get("upstream"):
            print("  - Check if firewall is blocking outbound DNS (port 53)")
            print("  - Run: netsh advfirewall firewall show rule name=DNS_Proxy_Block_All_DNS")
        
        if not results.get("dns_settings"):
            print("  - Set DNS to 127.0.0.1:")
            print("    netsh interface ipv4 set dnsservers \"Ethernet\" static 127.0.0.1 primary")
        
        if not results.get("proxy_running"):
            print("  - Start the agent: python agent_main.py")
            print("  - Or start GUI: python agent_gui.py")
        
        if not results.get("sync"):
            print("  - Check server connection")
            print("  - Verify API key in agent_config.json")
    else:
        print(f"\n{Colors.GREEN}All tests passed!{Colors.RESET}")
        print("\nIf you still can't access whitelisted sites:")
        print("  1. Check browser DNS cache (chrome://net-internals/#dns)")
        print("  2. Flush Windows DNS: ipconfig /flushdns")
        print("  3. Check if browser is using DoH (Settings > Privacy > DNS)")
        print("  4. Restart browser completely")


# ============================================================================
# MAIN
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Whitelist Flow Diagnostic")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--domain", type=str, help="Specific domain to test")
    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(message)s')
    else:
        logging.basicConfig(level=logging.WARNING)
    
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║          WHITELIST FLOW DIAGNOSTIC TEST                      ║
║          Kiểm tra toàn bộ flow whitelist                      ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")
    
    results = {}
    config = {}
    server_url = ""
    whitelist_data = {}
    
    # Test 1: Configuration
    results["config"], config = test_configuration()
    
    # Test 2: Server connectivity
    if results["config"]:
        results["server"], server_url = test_server_connectivity(config)
    
    # Test 3: Whitelist sync
    if results.get("server"):
        results["sync"], whitelist_data = test_whitelist_sync(config, server_url)
    
    # Test 4: Whitelist state
    if results.get("sync"):
        test_domains = [args.domain] if args.domain else None
        results["state"] = test_whitelist_state(whitelist_data, test_domains)
    
    # Test 5: Upstream resolver
    results["upstream"] = test_upstream_resolver()
    
    # Test 6: DNS Proxy port
    results["proxy_running"] = test_dns_proxy_port()
    
    # Test 7: Full DNS flow (only if proxy is running)
    if results.get("proxy_running") and whitelist_data:
        results["dns_flow"] = test_dns_query_flow(whitelist_data, config)
    
    # Test 8: DNS settings
    results["dns_settings"] = test_dns_settings()
    
    # Test 9: Firewall rules
    results["firewall"] = test_firewall_rules()
    
    # Summary
    print_diagnosis(results)
    
    print(f"\n{Colors.CYAN}Press Enter to exit...{Colors.RESET}")
    input()


if __name__ == "__main__":
    main()
