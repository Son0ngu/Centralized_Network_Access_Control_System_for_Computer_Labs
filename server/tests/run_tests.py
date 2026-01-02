"""
Test Runner Script
------------------
Runs all Phase 7 tests and generates report.
"""

import subprocess
import sys
import os
from datetime import datetime

# Add server to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_tests():
    """Run all test suites."""
    print("=" * 70)
    print("PHASE 7: TESTING & SECURITY AUDIT")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    test_files = [
        "test_authorization.py",
        "test_security.py",
        "test_multi_tenancy.py",
        "test_impersonation.py",
    ]
    
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    results = {}
    
    for test_file in test_files:
        test_path = os.path.join(tests_dir, test_file)
        if not os.path.exists(test_path):
            print(f"⚠️  {test_file}: NOT FOUND")
            results[test_file] = "NOT FOUND"
            continue
        
        print(f"\n{'─' * 70}")
        print(f"Running: {test_file}")
        print('─' * 70)
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
            
            if result.returncode == 0:
                results[test_file] = "PASSED"
            else:
                results[test_file] = "FAILED"
                
        except subprocess.TimeoutExpired:
            print(f"❌ {test_file}: TIMEOUT")
            results[test_file] = "TIMEOUT"
        except Exception as e:
            print(f"❌ {test_file}: ERROR - {e}")
            results[test_file] = f"ERROR: {e}"
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results.values() if r == "PASSED")
    failed = sum(1 for r in results.values() if r == "FAILED")
    errors = sum(1 for r in results.values() if r not in ["PASSED", "FAILED", "NOT FOUND"])
    
    for test_file, result in results.items():
        status_icon = "✅" if result == "PASSED" else "❌"
        print(f"  {status_icon} {test_file}: {result}")
    
    print()
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed} | Errors: {errors}")
    print("=" * 70)
    
    # Run security audit
    print("\n")
    print("=" * 70)
    print("RUNNING SECURITY AUDIT")
    print("=" * 70)
    
    audit_path = os.path.join(tests_dir, "security_audit.py")
    if os.path.exists(audit_path):
        try:
            subprocess.run([sys.executable, audit_path], timeout=60)
        except Exception as e:
            print(f"Audit error: {e}")
    else:
        print("Security audit script not found")
    
    return passed == len(results)


def main():
    """Main entry point."""
    success = run_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
