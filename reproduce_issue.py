
import sys
import os
import time
import threading

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent"))

from agent.network.dns_resolver import OptimizedDNSResolver

def main():
    print("="*60)
    print("FINAL VERIFICATION: DNS Resolver System Fallback")
    print("="*60)
    
    domains_to_resolve = [
        "google.com",
        "baomoi.com",
        "login.microsoftonline.com"
    ]
    
    print(f"Resolving {len(domains_to_resolve)} domains using OptimizedDNSResolver...")
    print("(This should now respect system DNS and not rely solely on 8.8.8.8)")
    
    resolver = OptimizedDNSResolver(max_workers=5, timeout=5.0)
    
    start = time.time()
    try:
        results = resolver.resolve_multiple_parallel(domains_to_resolve)
        duration = time.time() - start
        
        print(f"\nResolution complete in {duration:.2f}s")
        
        success_count = 0
        for domain in domains_to_resolve:
            record = results.get(domain)
            if record:
                ips = list(record.ipv4) + list(record.ipv6)
                if ips:
                    print(f"  [OK] {domain:<30} -> {ips[0]} (+{len(ips)-1} others)")
                    success_count += 1
                else:
                    print(f"  [FAIL] {domain:<30} -> Record found but NO IPs")
            else:
                print(f"  [NULL] {domain:<30} -> No result returned")
        
        if success_count == len(domains_to_resolve):
            print("\n✅ SUCCESS: All domains resolved correctly.")
        else:
            print(f"\n❌ FAILURE: Only {success_count}/{len(domains_to_resolve)} resolved.")
            
    except Exception as e:
        print(f"\n❌ CRASH: {e}")
    finally:
        resolver.shutdown()

if __name__ == "__main__":
    main()
