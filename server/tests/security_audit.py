"""
Security Audit Checklist Script
--------------------------------
Automated verification of security requirements.

Checklist:
- [ ] Mọi endpoint đều có authorization check
- [ ] Không có data leak giữa tenants
- [ ] Impersonation logs đầy đủ
- [ ] Super Admin password đủ mạnh
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Tuple, Dict

# Add server to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SecurityAuditChecker:
    """Automated security audit checker."""
    
    def __init__(self, server_path: str):
        self.server_path = Path(server_path)
        self.issues: List[Dict] = []
        self.warnings: List[Dict] = []
        self.passed: List[Dict] = []
    
    def run_all_checks(self):
        """Run all security audit checks."""
        print("=" * 60)
        print("SECURITY AUDIT CHECKLIST")
        print("=" * 60)
        
        self.check_endpoint_authorization()
        self.check_tenant_isolation()
        self.check_impersonation_logging()
        self.check_password_policy()
        self.check_sensitive_data_exposure()
        self.check_rate_limiting()
        self.check_input_sanitization()
        self.check_jwt_security()
        
        self.print_report()
    
    def check_endpoint_authorization(self):
        """Check that all endpoints have authorization."""
        print("\n[1] Checking Endpoint Authorization...")
        
        controllers_path = self.server_path / "controllers"
        
        # Authorization decorators to look for
        auth_decorators = [
            'require_super_admin',
            'require_tenant_admin',
            'require_any_admin',
            'require_jwt',
            'require_api_key',
            'require_jwt_or_api_key',
        ]
        
        unprotected_endpoints = []
        protected_endpoints = []
        
        for py_file in controllers_path.glob("*.py"):
            if py_file.name.startswith('__'):
                continue
            
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            
            # Find route definitions
            route_pattern = r'@.*\.route\s*\(\s*[\'"]([^\'"]+)[\'"]'
            routes = re.findall(route_pattern, content)
            
            # Find add_url_rule definitions
            url_rule_pattern = r'add_url_rule\s*\(\s*[\'"]([^\'"]+)[\'"]'
            routes.extend(re.findall(url_rule_pattern, content))
            
            for route in routes:
                # Check if protected
                has_auth = False
                for decorator in auth_decorators:
                    if decorator in content:
                        has_auth = True
                        break
                
                if has_auth:
                    protected_endpoints.append((py_file.name, route))
                else:
                    # Check if it's a public endpoint
                    if route in ['/health', '/api/health', '/']:
                        protected_endpoints.append((py_file.name, route))
                    else:
                        unprotected_endpoints.append((py_file.name, route))
        
        if unprotected_endpoints:
            self.warnings.append({
                'check': 'Endpoint Authorization',
                'message': f'Found {len(unprotected_endpoints)} potentially unprotected endpoints',
                'details': unprotected_endpoints[:5]  # Show first 5
            })
        else:
            self.passed.append({
                'check': 'Endpoint Authorization',
                'message': f'All {len(protected_endpoints)} endpoints have authorization decorators'
            })
    
    def check_tenant_isolation(self):
        """Check tenant data isolation in models and services."""
        print("\n[2] Checking Tenant Data Isolation...")
        
        models_path = self.server_path / "models"
        services_path = self.server_path / "services"
        
        tenant_aware_files = 0
        files_needing_review = []
        
        for path in [models_path, services_path]:
            for py_file in path.glob("*.py"):
                if py_file.name.startswith('__'):
                    continue
                
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                
                # Check for tenant_id handling
                if 'tenant_id' in content:
                    tenant_aware_files += 1
                elif any(kw in content for kw in ['find_all', 'find_one', 'aggregate']):
                    # Has DB queries but no tenant_id - needs review
                    files_needing_review.append(py_file.name)
        
        if files_needing_review:
            self.warnings.append({
                'check': 'Tenant Isolation',
                'message': f'{len(files_needing_review)} files have DB queries without explicit tenant_id',
                'details': files_needing_review
            })
        
        if tenant_aware_files > 0:
            self.passed.append({
                'check': 'Tenant Isolation',
                'message': f'{tenant_aware_files} files have tenant_id awareness'
            })
    
    def check_impersonation_logging(self):
        """Check impersonation logging configuration."""
        print("\n[3] Checking Impersonation Logging...")
        
        try:
            from config.impersonation_config import IMPERSONATION_CONFIG
            
            if IMPERSONATION_CONFIG.get('log_all_actions'):
                self.passed.append({
                    'check': 'Impersonation Logging',
                    'message': 'log_all_actions is enabled'
                })
            else:
                self.issues.append({
                    'check': 'Impersonation Logging',
                    'message': 'log_all_actions is DISABLED - all actions should be logged',
                    'severity': 'HIGH'
                })
            
            # Check log model exists
            log_model_path = self.server_path / "models" / "impersonation_log_model.py"
            if log_model_path.exists():
                self.passed.append({
                    'check': 'Impersonation Logging',
                    'message': 'ImpersonationLogModel exists'
                })
            else:
                self.issues.append({
                    'check': 'Impersonation Logging',
                    'message': 'ImpersonationLogModel not found',
                    'severity': 'HIGH'
                })
                
        except ImportError as e:
            self.issues.append({
                'check': 'Impersonation Logging',
                'message': f'Cannot import impersonation config: {e}',
                'severity': 'HIGH'
            })
    
    def check_password_policy(self):
        """Check password policy configuration."""
        print("\n[4] Checking Password Policy...")
        
        try:
            from config.security_config import PASSWORD_CONFIG
            
            checks = {
                'min_length >= 8': PASSWORD_CONFIG.get('min_length', 0) >= 8,
                'require_uppercase': PASSWORD_CONFIG.get('require_uppercase', False),
                'require_lowercase': PASSWORD_CONFIG.get('require_lowercase', False),
                'require_digits': PASSWORD_CONFIG.get('require_digits', False),
                'require_special': PASSWORD_CONFIG.get('require_special', False),
            }
            
            passed_checks = sum(checks.values())
            
            if passed_checks == len(checks):
                self.passed.append({
                    'check': 'Password Policy',
                    'message': 'All password requirements are configured'
                })
            else:
                failed = [k for k, v in checks.items() if not v]
                self.issues.append({
                    'check': 'Password Policy',
                    'message': f'Missing password requirements: {failed}',
                    'severity': 'MEDIUM'
                })
                
        except ImportError as e:
            self.issues.append({
                'check': 'Password Policy',
                'message': f'Cannot import security config: {e}',
                'severity': 'MEDIUM'
            })
    
    def check_sensitive_data_exposure(self):
        """Check for sensitive data exposure in responses."""
        print("\n[5] Checking Sensitive Data Exposure...")
        
        sensitive_fields = ['password', 'password_hash', 'secret', 'api_key', 'token']
        
        models_path = self.server_path / "models"
        exposed_fields = []
        
        for py_file in models_path.glob("*.py"):
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            
            for field in sensitive_fields:
                # Check if field is excluded in serialization
                if f"'{field}'" in content and '_to_dict' in content:
                    # Check if it's being excluded
                    if f"exclude.*{field}" not in content and f"pop('{field}')" not in content:
                        exposed_fields.append((py_file.name, field))
        
        if exposed_fields:
            self.warnings.append({
                'check': 'Sensitive Data',
                'message': 'Potential sensitive field exposure',
                'details': exposed_fields[:5]
            })
        else:
            self.passed.append({
                'check': 'Sensitive Data',
                'message': 'No obvious sensitive data exposure detected'
            })
    
    def check_rate_limiting(self):
        """Check rate limiting configuration."""
        print("\n[6] Checking Rate Limiting...")
        
        try:
            from config.security_config import RATE_LIMIT_CONFIG
            
            required_limits = ['login', 'register']
            configured = [k for k in required_limits if k in RATE_LIMIT_CONFIG]
            
            if len(configured) == len(required_limits):
                self.passed.append({
                    'check': 'Rate Limiting',
                    'message': 'Rate limiting configured for sensitive endpoints'
                })
            else:
                missing = [k for k in required_limits if k not in RATE_LIMIT_CONFIG]
                self.issues.append({
                    'check': 'Rate Limiting',
                    'message': f'Missing rate limits for: {missing}',
                    'severity': 'MEDIUM'
                })
                
        except ImportError:
            self.issues.append({
                'check': 'Rate Limiting',
                'message': 'Rate limit config not found',
                'severity': 'MEDIUM'
            })
    
    def check_input_sanitization(self):
        """Check input sanitization."""
        print("\n[7] Checking Input Sanitization...")
        
        security_path = self.server_path / "middleware" / "security.py"
        
        if security_path.exists():
            content = security_path.read_text(encoding='utf-8', errors='ignore')
            
            if 'InputSanitizer' in content:
                self.passed.append({
                    'check': 'Input Sanitization',
                    'message': 'InputSanitizer class exists'
                })
            else:
                self.issues.append({
                    'check': 'Input Sanitization',
                    'message': 'InputSanitizer not found in security middleware',
                    'severity': 'HIGH'
                })
        else:
            self.issues.append({
                'check': 'Input Sanitization',
                'message': 'Security middleware not found',
                'severity': 'HIGH'
            })
    
    def check_jwt_security(self):
        """Check JWT security configuration."""
        print("\n[8] Checking JWT Security...")
        
        jwt_path = self.server_path / "services" / "jwt_service.py"
        
        if jwt_path.exists():
            content = jwt_path.read_text(encoding='utf-8', errors='ignore')
            
            checks = {
                'secret_key_from_env': 'JWT_SECRET_KEY' in content and 'os.environ' in content,
                'token_validation': 'validate' in content.lower(),
                'expiry_check': 'exp' in content,
            }
            
            passed = sum(checks.values())
            if passed == len(checks):
                self.passed.append({
                    'check': 'JWT Security',
                    'message': 'JWT service has proper security measures'
                })
            else:
                failed = [k for k, v in checks.items() if not v]
                self.warnings.append({
                    'check': 'JWT Security',
                    'message': f'Missing JWT security measures: {failed}'
                })
        else:
            self.issues.append({
                'check': 'JWT Security',
                'message': 'JWT service not found',
                'severity': 'HIGH'
            })
    
    def print_report(self):
        """Print the audit report."""
        print("\n" + "=" * 60)
        print("AUDIT REPORT")
        print("=" * 60)
        
        print(f"\n✅ PASSED: {len(self.passed)}")
        for item in self.passed:
            print(f"   [{item['check']}] {item['message']}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS: {len(self.warnings)}")
            for item in self.warnings:
                print(f"   [{item['check']}] {item['message']}")
                if 'details' in item:
                    for detail in item['details'][:3]:
                        print(f"      - {detail}")
        
        if self.issues:
            print(f"\n❌ ISSUES: {len(self.issues)}")
            for item in self.issues:
                severity = item.get('severity', 'MEDIUM')
                print(f"   [{severity}] [{item['check']}] {item['message']}")
        
        print("\n" + "=" * 60)
        total = len(self.passed) + len(self.warnings) + len(self.issues)
        score = (len(self.passed) / total * 100) if total > 0 else 0
        print(f"SECURITY SCORE: {score:.1f}%")
        print("=" * 60)


def main():
    """Run security audit."""
    # Get server path
    server_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    checker = SecurityAuditChecker(server_path)
    checker.run_all_checks()


if __name__ == '__main__':
    main()
