"""
Agent Cleanup Script
====================
Script khôi phục hệ thống về trạng thái ban đầu sau khi agent thay đổi:
1. Khôi phục DNS về DHCP (tự động)
2. Xóa firewall rules do agent tạo
3. Xóa DoH/DoT blocking rules

Chạy với quyền Administrator:
    python cleanup_agent.py

Author: Firewall Controller Team
"""

import ctypes
import subprocess
import sys
import os
import time
from typing import List, Tuple

# Colors for terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header():
    """Print script header."""
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║          FIREWALL AGENT - CLEANUP SCRIPT                      ║
║          Khôi phục hệ thống về trạng thái ban đầu             ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def run_command(cmd: List[str], description: str = "") -> Tuple[bool, str]:
    """
    Run a command and return success status and output.
    
    Args:
        cmd: Command to run as list
        description: Description for logging
        
    Returns:
        Tuple of (success, output)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        output = result.stdout.strip() or result.stderr.strip()
        success = result.returncode == 0
        
        return success, output
        
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def get_network_adapters() -> List[str]:
    """Get list of network adapter names."""
    adapters = []
    
    try:
        # Use netsh to list interfaces
        result = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines[2:]:  # Skip header
                parts = line.split()
                if len(parts) >= 4:
                    # Get adapter name (last part, may contain spaces)
                    # Format: Admin State    State          Type             Interface Name
                    name_start = line.find(parts[3])
                    if name_start > 0:
                        adapter_name = line[name_start:].strip()
                        # Skip loopback
                        if 'loopback' not in adapter_name.lower():
                            adapters.append(adapter_name)
    except Exception as e:
        print(f"{Colors.RED}Error getting adapters: {e}{Colors.RESET}")
    
    return adapters


def reset_dns_to_dhcp(adapter_name: str) -> Tuple[bool, bool]:
    """
    Reset DNS settings to DHCP for an adapter.
    
    Args:
        adapter_name: Name of the network adapter
        
    Returns:
        Tuple of (ipv4_success, ipv6_success)
    """
    # Reset IPv4 DNS to DHCP
    cmd_v4 = [
        "netsh", "interface", "ipv4", "set", "dnsservers",
        f"name={adapter_name}",
        "source=dhcp"
    ]
    
    # Reset IPv6 DNS to DHCP
    cmd_v6 = [
        "netsh", "interface", "ipv6", "set", "dnsservers",
        f"name={adapter_name}",
        "source=dhcp"
    ]
    
    v4_success, _ = run_command(cmd_v4, f"Reset IPv4 DNS for {adapter_name}")
    v6_success, _ = run_command(cmd_v6, f"Reset IPv6 DNS for {adapter_name}")
    
    return v4_success, v6_success


def cleanup_dns() -> int:
    """
    Reset DNS on all network adapters to DHCP.
    
    Returns:
        Number of adapters successfully reset
    """
    print(f"\n{Colors.BLUE}[1/3] Khôi phục DNS về DHCP...{Colors.RESET}")
    print("-" * 50)
    
    adapters = get_network_adapters()
    
    if not adapters:
        print(f"{Colors.YELLOW}⚠ Không tìm thấy network adapter nào{Colors.RESET}")
        return 0
    
    success_count = 0
    
    for adapter in adapters:
        v4_ok, v6_ok = reset_dns_to_dhcp(adapter)
        
        if v4_ok or v6_ok:
            status = []
            if v4_ok:
                status.append("IPv4")
            if v6_ok:
                status.append("IPv6")
            print(f"  {Colors.GREEN}✓{Colors.RESET} {adapter}: {', '.join(status)} → DHCP")
            success_count += 1
        else:
            print(f"  {Colors.YELLOW}○{Colors.RESET} {adapter}: Không thể reset (có thể đã là DHCP)")
    
    print(f"\n  → Đã reset {success_count}/{len(adapters)} adapters")
    
    return success_count


def cleanup_firewall_rules() -> int:
    """
    Remove all firewall rules created by the agent.
    
    Returns:
        Number of rules removed
    """
    print(f"\n{Colors.BLUE}[2/3] Xóa Firewall Rules do Agent tạo...{Colors.RESET}")
    print("-" * 50)
    
    # Firewall rule prefixes used by the agent
    rule_prefixes = [
        "FirewallController",
        "DNS_Proxy_Block_",
        "FC_",
    ]
    
    removed_count = 0
    
    # First, list all rules to find matches
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0:
            rules_to_delete = []
            current_rule = None
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith("Rule Name:"):
                    rule_name = line.replace("Rule Name:", "").strip()
                    for prefix in rule_prefixes:
                        if rule_name.startswith(prefix):
                            rules_to_delete.append(rule_name)
                            break
            
            # Remove duplicates
            rules_to_delete = list(set(rules_to_delete))
            
            if not rules_to_delete:
                print(f"  {Colors.GREEN}✓{Colors.RESET} Không có firewall rules nào cần xóa")
                return 0
            
            print(f"  Tìm thấy {len(rules_to_delete)} rules cần xóa:")
            
            for rule_name in rules_to_delete:
                cmd = [
                    "netsh", "advfirewall", "firewall", "delete", "rule",
                    f"name={rule_name}"
                ]
                success, output = run_command(cmd, f"Delete rule: {rule_name}")
                
                if success:
                    print(f"  {Colors.GREEN}✓{Colors.RESET} Đã xóa: {rule_name}")
                    removed_count += 1
                else:
                    print(f"  {Colors.RED}✗{Colors.RESET} Lỗi xóa: {rule_name}")
    
    except Exception as e:
        print(f"{Colors.RED}Error listing firewall rules: {e}{Colors.RESET}")
    
    print(f"\n  → Đã xóa {removed_count} firewall rules")
    
    return removed_count


def cleanup_doh_dot_rules() -> int:
    """
    Remove DoH/DoT blocking rules specifically.
    
    Returns:
        Number of rules removed
    """
    print(f"\n{Colors.BLUE}[3/3] Xóa DoH/DoT Blocking Rules...{Colors.RESET}")
    print("-" * 50)
    
    # Specific DoH/DoT rule names
    doh_rules = [
        "DNS_Proxy_Block_DoH_IPv4",
        "DNS_Proxy_Block_DoH_IPv6",
        "DNS_Proxy_Block_DoT_IPv4",
        "DNS_Proxy_Block_DoT_IPv6",
        "DNS_Proxy_Block_DoT_All",
    ]
    
    removed_count = 0
    
    for rule_name in doh_rules:
        cmd = [
            "netsh", "advfirewall", "firewall", "delete", "rule",
            f"name={rule_name}"
        ]
        success, output = run_command(cmd, f"Delete DoH rule: {rule_name}")
        
        if success:
            print(f"  {Colors.GREEN}✓{Colors.RESET} Đã xóa: {rule_name}")
            removed_count += 1
        else:
            # Rule không tồn tại - không phải lỗi
            print(f"  {Colors.YELLOW}○{Colors.RESET} Không tồn tại: {rule_name}")
    
    print(f"\n  → Đã xóa {removed_count} DoH/DoT rules")
    
    return removed_count


def flush_dns_cache():
    """Flush the DNS resolver cache."""
    print(f"\n{Colors.BLUE}[Bonus] Xóa DNS Cache...{Colors.RESET}")
    print("-" * 50)
    
    success, output = run_command(
        ["ipconfig", "/flushdns"],
        "Flush DNS cache"
    )
    
    if success:
        print(f"  {Colors.GREEN}✓{Colors.RESET} Đã xóa DNS cache")
    else:
        print(f"  {Colors.YELLOW}⚠{Colors.RESET} Không thể xóa DNS cache: {output}")


def reset_winsock():
    """Reset Winsock catalog (optional, requires restart)."""
    print(f"\n{Colors.BLUE}[Optional] Reset Winsock Catalog...{Colors.RESET}")
    print("-" * 50)
    
    response = input("  Bạn có muốn reset Winsock? (cần restart máy) [y/N]: ").strip().lower()
    
    if response == 'y':
        success, output = run_command(
            ["netsh", "winsock", "reset"],
            "Reset Winsock"
        )
        
        if success:
            print(f"  {Colors.GREEN}✓{Colors.RESET} Đã reset Winsock - Cần RESTART máy để áp dụng")
        else:
            print(f"  {Colors.RED}✗{Colors.RESET} Lỗi reset Winsock: {output}")
    else:
        print(f"  {Colors.YELLOW}○{Colors.RESET} Bỏ qua reset Winsock")


def verify_cleanup():
    """Verify that cleanup was successful."""
    print(f"\n{Colors.BLUE}[Verify] Kiểm tra kết quả...{Colors.RESET}")
    print("-" * 50)
    
    issues = []
    
    # Check DNS settings
    adapters = get_network_adapters()
    for adapter in adapters[:3]:  # Check first 3 adapters
        try:
            result = subprocess.run(
                ["netsh", "interface", "ipv4", "show", "dnsservers", f"name={adapter}"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                if "127.0.0.1" in output:
                    issues.append(f"DNS của {adapter} vẫn đang trỏ về 127.0.0.1")
                elif "dhcp" in output or "configured through dhcp" in output:
                    print(f"  {Colors.GREEN}✓{Colors.RESET} {adapter}: DNS = DHCP")
                else:
                    print(f"  {Colors.CYAN}○{Colors.RESET} {adapter}: DNS = Static (không phải agent)")
        except:
            pass
    
    # Check for remaining firewall rules
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0:
            remaining_rules = []
            for line in result.stdout.split('\n'):
                if "Rule Name:" in line:
                    rule_name = line.replace("Rule Name:", "").strip()
                    if rule_name.startswith("FirewallController") or rule_name.startswith("DNS_Proxy_Block_"):
                        remaining_rules.append(rule_name)
            
            if remaining_rules:
                issues.append(f"Còn {len(remaining_rules)} firewall rules chưa xóa được")
            else:
                print(f"  {Colors.GREEN}✓{Colors.RESET} Không còn firewall rules của agent")
    except:
        pass
    
    if issues:
        print(f"\n{Colors.YELLOW}⚠ Một số vấn đề chưa được giải quyết:{Colors.RESET}")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"\n{Colors.GREEN}✓ Cleanup hoàn tất thành công!{Colors.RESET}")


def main():
    """Main cleanup function."""
    print_header()
    
    # Check admin privileges
    if not is_admin():
        print(f"{Colors.RED}╔══════════════════════════════════════════════════════════════╗")
        print(f"║  ⚠ CẢNH BÁO: Cần chạy với quyền Administrator!               ║")
        print(f"║                                                              ║")
        print(f"║  Cách chạy:                                                  ║")
        print(f"║  1. Click phải vào Command Prompt → Run as Administrator    ║")
        print(f"║  2. Chạy lệnh: python cleanup_agent.py                       ║")
        print(f"╚══════════════════════════════════════════════════════════════╝{Colors.RESET}")
        
        input("\nNhấn Enter để thoát...")
        sys.exit(1)
    
    print(f"{Colors.GREEN}✓ Đang chạy với quyền Administrator{Colors.RESET}")
    
    # Confirmation
    print(f"\n{Colors.YELLOW}⚠ Script này sẽ:{Colors.RESET}")
    print("  1. Reset DNS của tất cả network adapters về DHCP")
    print("  2. Xóa tất cả Firewall Rules do Agent tạo")
    print("  3. Xóa DoH/DoT Blocking Rules")
    print("  4. Flush DNS Cache")
    
    response = input(f"\n{Colors.BOLD}Bạn có muốn tiếp tục? [y/N]: {Colors.RESET}").strip().lower()
    
    if response != 'y':
        print(f"\n{Colors.YELLOW}Đã hủy cleanup.{Colors.RESET}")
        sys.exit(0)
    
    print(f"\n{Colors.CYAN}Bắt đầu cleanup...{Colors.RESET}")
    start_time = time.time()
    
    # Run cleanup steps
    dns_count = cleanup_dns()
    fw_count = cleanup_firewall_rules()
    doh_count = cleanup_doh_dot_rules()
    flush_dns_cache()
    
    # Optional: Reset Winsock
    # reset_winsock()
    
    # Verify
    verify_cleanup()
    
    # Summary
    elapsed = time.time() - start_time
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                        CLEANUP SUMMARY                        ║
╠══════════════════════════════════════════════════════════════╣
║  DNS Adapters reset:        {dns_count:>3}                               ║
║  Firewall Rules removed:    {fw_count:>3}                               ║
║  DoH/DoT Rules removed:     {doh_count:>3}                               ║
║  Time elapsed:              {elapsed:.1f}s                              ║
╠══════════════════════════════════════════════════════════════╣
║  {Colors.GREEN}✓ Hệ thống đã được khôi phục về trạng thái ban đầu{Colors.RESET}        {Colors.CYAN}║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")
    
    input("Nhấn Enter để thoát...")


if __name__ == "__main__":
    main()
