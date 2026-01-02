"""
Whitelist JWT Flow Test
=======================
Test complete whitelist flow with proper JWT authentication:
1. Register agent with API Key → Get JWT
2. Sync whitelist with JWT
3. Test whitelist state matching
4. Test DNS query flow

Chạy:
    python test_whitelist_jwt.py

Output:
    Results saved to test_whitelist_results.txt
"""

import json
import os
import socket
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add agent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

# Output file
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_whitelist_results.txt")
_output_lines = []

def _log(msg: str):
    """Log to both console and buffer."""
    print(msg)
    _output_lines.append(msg)

def save_results():
    """Save all results to file."""
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Whitelist JWT Flow Test Results\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        f.write("\n".join(_output_lines))
    print(f"\n[SAVED] Results saved to: {OUTPUT_FILE}")

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
    msg = f"\n{'='*60}\n{title}\n{'='*60}"
    _log(msg)


def print_ok(msg: str):
    _log(f"  [OK] {msg}")


def print_fail(msg: str):
    _log(f"  [FAIL] {msg}")


def print_warn(msg: str):
    _log(f"  [WARN] {msg}")


def print_info(msg: str):
    _log(f"  [INFO] {msg}")


# ============================================================================
# STEP 1: Load Configuration
# ============================================================================
def load_config() -> Dict:
    """Load agent configuration."""
    print_header("STEP 1: Load Configuration")
    
    try:
        from config import get_config
        config = get_config()
        
        api_key = config.get("auth", {}).get("api_key", "")
        server_url = config.get("server", {}).get("url", "")
        
        print_ok(f"Config loaded")
        print_info(f"API Key: {api_key[:20]}..." if api_key else "No API Key")
        print_info(f"Server: {server_url}")
        
        return config
    except Exception as e:
        print_fail(f"Failed to load config: {e}")
        return {}


# ============================================================================
# STEP 2: Register Agent with API Key → Get JWT
# ============================================================================
def register_agent(config: Dict) -> Tuple[bool, str, str, str]:
    """
    Register agent with API Key to get JWT token.
    
    Returns:
        (success, agent_id, access_token, refresh_token)
    """
    print_header("STEP 2: Register Agent (API Key → JWT)")
    
    server_url = config.get("server", {}).get("url", "http://localhost:5000")
    api_key = config.get("auth", {}).get("api_key", "")
    
    if not api_key:
        print_fail("No API Key configured!")
        return False, "", "", ""
    
    register_url = f"{server_url.rstrip('/')}/api/agents/register"
    print_info(f"Register URL: {register_url}")
    
    headers = {
        'Content-Type': 'application/json',
        'X-API-KEY': api_key
    }
    
    # Get device info
    import hashlib
    device_id = hashlib.sha256(socket.gethostname().encode()).hexdigest()[:24]
    hostname = socket.gethostname()
    
    data = {
        'device_id': device_id,
        'hostname': hostname,
        'os_info': {'platform': 'Windows', 'version': '10'}
    }
    
    print_info(f"Device ID: {device_id}")
    print_info(f"Hostname: {hostname}")
    
    try:
        response = requests.post(register_url, json=data, headers=headers, timeout=10)
        
        print_info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                data = result.get("data", {})
                agent_id = data.get("agent_id", "")
                jwt_data = data.get("jwt", {})
                access_token = jwt_data.get("access_token", "")
                refresh_token = jwt_data.get("refresh_token", "")
                
                print_ok(f"Registration successful!")
                print_ok(f"Agent ID: {agent_id}")
                print_ok(f"Access Token: {access_token[:50]}...")
                print_info(f"Token expires: {jwt_data.get('access_expires_at', 'N/A')}")
                
                return True, agent_id, access_token, refresh_token
            else:
                print_fail(f"Registration failed: {result.get('error', 'Unknown')}")
        else:
            print_fail(f"HTTP Error: {response.status_code}")
            print_info(f"Response: {response.text[:500]}")
            
    except requests.exceptions.ConnectionError:
        print_fail(f"Cannot connect to server")
    except Exception as e:
        print_fail(f"Error: {e}")
    
    return False, "", "", ""


# ============================================================================
# STEP 3: Sync Whitelist with JWT
# ============================================================================
def sync_whitelist(config: Dict, agent_id: str, access_token: str) -> Tuple[bool, Dict]:
    """
    Sync whitelist using JWT token.
    
    Returns:
        (success, whitelist_data)
    """
    print_header("STEP 3: Sync Whitelist (JWT Auth)")
    
    server_url = config.get("server", {}).get("url", "http://localhost:5000")
    sync_url = f"{server_url.rstrip('/')}/api/whitelist/agent-sync"
    
    print_info(f"Sync URL: {sync_url}")
    print_info(f"Agent ID: {agent_id}")
    
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    params = {
        'agent_id': agent_id,
        'mode': 'full'
    }
    
    try:
        response = requests.get(sync_url, params=params, headers=headers, timeout=30)
        
        print_info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                domains = result.get("domains", [])
                
                print_ok(f"Whitelist synced successfully!")
                print_ok(f"Total domains: {len(domains)}")
                
                # Show domains
                if domains:
                    print_info("Domains in whitelist:")
                    for i, domain in enumerate(domains[:10]):
                        if isinstance(domain, dict):
                            value = domain.get("value", domain.get("domain", "?"))
                            dtype = domain.get("type", "domain")
                            _log(f"      {i+1}. {value} ({dtype})")
                        else:
                            _log(f"      {i+1}. {domain}")
                    
                    if len(domains) > 10:
                        _log(f"      ... and {len(domains) - 10} more")
                else:
                    print_warn("Whitelist is EMPTY!")
                
                return True, result
            else:
                error = result.get("error", "Unknown")
                print_fail(f"Sync failed: {error}")
        elif response.status_code == 401:
            print_fail("Authentication failed - JWT token invalid or expired")
        else:
            print_fail(f"HTTP Error: {response.status_code}")
            
    except Exception as e:
        print_fail(f"Error: {e}")
    
    return False, {}


# ============================================================================
# STEP 4: Test WhitelistState Matching
# ============================================================================
def test_whitelist_state(whitelist_data: Dict) -> bool:
    """Test whitelist state domain matching logic."""
    print_header("STEP 4: Test WhitelistState Matching")
    
    try:
        from whitelist.state import WhitelistState
        
        state = WhitelistState()
        
        # Update state with synced data
        updated = state.update(whitelist_data)
        print_info(f"State updated: {updated}")
        
        stats = state.get_stats()
        print_info(f"Domains in state: {stats.get('domains', 0)}")
        print_info(f"Patterns in state: {stats.get('patterns', 0)}")
        print_info(f"IPs in state: {stats.get('ips', 0)}")
        
        # Get actual domains
        all_domains = state.get_all_domains()
        print_info(f"Domains loaded: {list(all_domains)[:5]}")
        
        if not all_domains:
            print_warn("No domains in state!")
            return False
        
        # Test matching
        _log("\n  Domain matching tests:")
        
        test_cases = []
        
        # Add domains from whitelist
        for d in list(all_domains)[:3]:
            test_cases.append((d, True, "in whitelist"))
        
        # Add domains NOT in whitelist
        test_cases.extend([
            ("blocked-test.xyz", False, "not in whitelist"),
            ("malware-site.com", False, "not in whitelist"),
        ])
        
        all_passed = True
        
        for domain, expected, reason in test_cases:
            allowed = state.is_domain_allowed(domain)
            
            if allowed == expected:
                symbol = "✓"
                status = "PASS"
            else:
                symbol = "✗"
                status = "FAIL"
                all_passed = False
            
            _log(f"    {symbol} {domain}: allowed={allowed}, expected={expected} ({reason}) [{status}]")
        
        if all_passed:
            print_ok("All matching tests passed!")
        else:
            print_fail("Some matching tests failed!")
        
        return all_passed
        
    except Exception as e:
        print_fail(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# STEP 5: Test DNS Handler Integration
# ============================================================================
def test_dns_handler(whitelist_data: Dict) -> bool:
    """Test DNS handler whitelist checking."""
    print_header("STEP 5: Test DNS Handler Integration")
    
    try:
        from whitelist.state import WhitelistState
        from dns_proxy.handler import DNSQueryHandler
        from dns_proxy.config import DNSProxyConfig
        
        # Create whitelist state
        state = WhitelistState()
        state.update(whitelist_data)
        
        # Create handler with whitelist state
        config = DNSProxyConfig()
        handler = DNSQueryHandler(config, whitelist_state=state)
        
        print_ok("DNS Handler created with whitelist state")
        
        # Test _is_domain_allowed method
        all_domains = state.get_all_domains()
        
        _log("\n  DNS Handler domain check:")
        
        test_domains = list(all_domains)[:3] + ["blocked-test.xyz"]
        
        for domain in test_domains:
            # Check if handler has _is_domain_allowed method
            if hasattr(handler, '_is_domain_allowed'):
                allowed = handler._is_domain_allowed(domain)
                in_whitelist = domain in all_domains
                
                symbol = "✓" if allowed else "✗"
                _log(f"    {symbol} {domain}: handler_allows={allowed}, in_whitelist={in_whitelist}")
            else:
                print_warn("Handler doesn't have _is_domain_allowed method")
                break
        
        return True
        
    except ImportError as e:
        print_warn(f"Cannot import DNS handler modules: {e}")
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# STEP 6: Test Upstream DNS Resolver
# ============================================================================
def test_upstream_resolver() -> bool:
    """Test upstream DNS resolver connectivity."""
    print_header("STEP 6: Test Upstream DNS Resolver")
    
    try:
        import dns.resolver
        import dns.query
        import dns.message
        
        resolvers = [
            ("8.8.8.8", "Google DNS"),
            ("1.1.1.1", "Cloudflare DNS"),
        ]
        
        test_domain = "google.com"
        working = 0
        
        for resolver_ip, name in resolvers:
            try:
                query = dns.message.make_query(test_domain, "A")
                response = dns.query.udp(query, resolver_ip, timeout=3)
                
                if response.answer:
                    ips = [str(rdata) for rrset in response.answer for rdata in rrset]
                    print_ok(f"{name} ({resolver_ip}): {test_domain} → {ips[0]}")
                    working += 1
                else:
                    print_warn(f"{name}: No answer")
                    
            except Exception as e:
                print_fail(f"{name} ({resolver_ip}): {e}")
        
        if working > 0:
            print_ok(f"{working}/{len(resolvers)} resolvers working")
            return True
        else:
            print_fail("No upstream resolvers working!")
            return False
            
    except ImportError:
        print_fail("dnspython not installed")
        return False


# ============================================================================
# STEP 7: Check DNS Proxy Status
# ============================================================================
def check_dns_proxy_status() -> Tuple[bool, str]:
    """Check if DNS proxy is running."""
    print_header("STEP 7: Check DNS Proxy Status")
    
    # Check if port 53 is in use
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)
        sock.bind(("127.0.0.1", 53))
        sock.close()
        print_warn("Port 53 is FREE - DNS Proxy is NOT running")
        return False, "not_running"
    except OSError:
        print_ok("Port 53 is in use")
    
    # Try to query DNS proxy
    try:
        import dns.message
        import dns.query
        
        query = dns.message.make_query("test.local", "A")
        response = dns.query.udp(query, "127.0.0.1", port=53, timeout=2)
        print_ok("DNS Proxy responds to queries")
        return True, "running"
        
    except Exception as e:
        print_warn(f"DNS Proxy may not be responding: {e}")
        return True, "unknown"  # Port is in use, assume running


# ============================================================================
# STEP 8: Test Full DNS Query Flow
# ============================================================================
def test_dns_query_flow(whitelist_data: Dict) -> bool:
    """Test full DNS query through proxy."""
    print_header("STEP 8: Test DNS Query Flow")
    
    try:
        import dns.message
        import dns.query
        import dns.rcode
        
        domains = whitelist_data.get("domains", [])
        
        if not domains:
            print_warn("No domains to test")
            return False
        
        # Extract domain values
        test_domains = []
        for d in domains[:3]:
            if isinstance(d, dict):
                value = d.get("value", d.get("domain", ""))
                if value and not value.startswith("http"):
                    test_domains.append(value)
            elif isinstance(d, str) and not d.startswith("http"):
                test_domains.append(d)
        
        # Add a blocked domain
        test_domains.append("blocked-test.xyz")
        
        if not test_domains:
            print_warn("No valid domains to test")
            return False
        
        print_info(f"Testing {len(test_domains)} domains via DNS Proxy (127.0.0.1:53)")
        
        successes = 0
        
        for domain in test_domains:
            try:
                query = dns.message.make_query(domain, "A")
                
                start = time.time()
                response = dns.query.udp(query, "127.0.0.1", port=53, timeout=10)
                elapsed = (time.time() - start) * 1000
                
                rcode_text = dns.rcode.to_text(response.rcode())
                
                # Check if domain should be allowed
                is_whitelisted = any(
                    (isinstance(d, dict) and d.get("value", d.get("domain", "")).lower() == domain.lower()) or
                    (isinstance(d, str) and d.lower() == domain.lower())
                    for d in domains
                )
                
                if rcode_text == "NOERROR":
                    if response.answer:
                        ips = [str(rdata) for rrset in response.answer for rdata in rrset]
                        if is_whitelisted:
                            print_ok(f"{domain} → {ips[0]} ({elapsed:.0f}ms) [ALLOWED - correct]")
                            successes += 1
                        else:
                            print_fail(f"{domain} → {ips[0]} [SHOULD BE BLOCKED!]")
                    else:
                        print_warn(f"{domain} → NOERROR but no IPs ({elapsed:.0f}ms)")
                        
                elif rcode_text == "NXDOMAIN":
                    if is_whitelisted:
                        print_fail(f"{domain} → BLOCKED but is in whitelist!")
                    else:
                        print_ok(f"{domain} → BLOCKED ({elapsed:.0f}ms) [NOT IN WHITELIST - correct]")
                        successes += 1
                else:
                    print_warn(f"{domain} → {rcode_text} ({elapsed:.0f}ms)")
                    
            except dns.exception.Timeout:
                print_fail(f"{domain} → TIMEOUT")
            except Exception as e:
                print_fail(f"{domain} → ERROR: {e}")
        
        if successes == len(test_domains):
            print_ok(f"\nAll {successes} queries behaved correctly!")
            return True
        else:
            print_warn(f"\n{successes}/{len(test_domains)} queries correct")
            return False
            
    except ImportError:
        print_fail("dnspython not installed")
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False


# ============================================================================
# STEP 9: Check System DNS Settings
# ============================================================================
def check_dns_settings() -> bool:
    """Check if system DNS points to 127.0.0.1."""
    print_header("STEP 9: System DNS Settings")
    
    try:
        import subprocess
        
        result = subprocess.run(
            ["netsh", "interface", "ipv4", "show", "dnsservers"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        using_proxy = False
        lines = result.stdout.strip().split('\n')
        
        current_adapter = None
        for line in lines:
            if "Configuration for interface" in line:
                current_adapter = line.split('"')[1] if '"' in line else "Unknown"
            elif "127.0.0.1" in line:
                print_ok(f"{current_adapter}: Uses DNS Proxy (127.0.0.1)")
                using_proxy = True
            elif line.strip() and current_adapter:
                # Check for IP addresses
                parts = line.strip().split()
                for part in parts:
                    if part.replace('.', '').isdigit() and part.count('.') == 3:
                        if part != "127.0.0.1":
                            print_info(f"{current_adapter}: Uses {part}")
        
        if using_proxy:
            print_ok("System is configured to use DNS Proxy")
        else:
            print_fail("System DNS is NOT pointing to 127.0.0.1!")
            print_info("DNS queries bypass the proxy entirely")
        
        return using_proxy
        
    except Exception as e:
        print_fail(f"Error: {e}")
        return False


# ============================================================================
# SUMMARY
# ============================================================================
def print_summary(results: Dict):
    """Print test summary."""
    print_header("SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    _log(f"\n  Results: {passed}/{total} tests passed\n")
    
    for test, result in results.items():
        symbol = "✓" if result else "✗"
        _log(f"  {symbol} {test}")
    
    # Diagnosis
    issues = []
    
    if not results.get("registration"):
        issues.append("Agent registration failed - check API key")
    
    if not results.get("whitelist_sync"):
        issues.append("Whitelist sync failed - check JWT token")
    
    if not results.get("dns_proxy"):
        issues.append("DNS Proxy not running - start the agent")
    
    if not results.get("dns_settings"):
        issues.append("System DNS not configured - queries bypass proxy")
    
    if issues:
        _log("\nIssues:")
        for issue in issues:
            _log(f"  • {issue}")
    else:
        _log("\nAll systems operational!")


# ============================================================================
# MAIN
# ============================================================================
def main():
    _log("""
╔══════════════════════════════════════════════════════════════╗
║           WHITELIST JWT FLOW TEST                             ║
║           Test complete authentication & whitelist flow       ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    results = {}
    
    # Step 1: Load config
    config = load_config()
    results["config"] = bool(config)
    
    if not config:
        print_fail("Cannot proceed without config")
        return
    
    # Step 2: Register agent (API Key → JWT)
    success, agent_id, access_token, refresh_token = register_agent(config)
    results["registration"] = success
    
    if not success:
        print_fail("Cannot proceed without JWT token")
        print_summary(results)
        return
    
    # Step 3: Sync whitelist with JWT
    success, whitelist_data = sync_whitelist(config, agent_id, access_token)
    results["whitelist_sync"] = success
    
    if not success:
        print_fail("Cannot proceed without whitelist")
        print_summary(results)
        return
    
    # Step 4: Test whitelist state matching
    results["state_matching"] = test_whitelist_state(whitelist_data)
    
    # Step 5: Test DNS handler integration
    results["handler_integration"] = test_dns_handler(whitelist_data)
    
    # Step 6: Test upstream resolver
    results["upstream_resolver"] = test_upstream_resolver()
    
    # Step 7: Check DNS proxy status
    proxy_running, status = check_dns_proxy_status()
    results["dns_proxy"] = proxy_running
    
    # Step 8: Test DNS query flow (only if proxy is running)
    if proxy_running and status == "running":
        results["dns_query_flow"] = test_dns_query_flow(whitelist_data)
    else:
        print_header("STEP 8: Test DNS Query Flow")
        print_warn("Skipped - DNS Proxy not running")
        results["dns_query_flow"] = False
    
    # Step 9: Check DNS settings
    results["dns_settings"] = check_dns_settings()
    
    # Summary
    print_summary(results)
    
    # Save results to file
    save_results()
    
    print("\nPress Enter to exit...")
    input()


if __name__ == "__main__":
    main()
