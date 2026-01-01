"""
Password Validator
------------------
Validates password strength and compliance with security policy.
"""

import re
import math
from typing import Dict, List, Tuple
from config.security_config import PASSWORD_CONFIG


class PasswordValidator:
    """Validates passwords against security policy."""
    
    def __init__(self, config: Dict = None):
        self.config = config or PASSWORD_CONFIG
    
    def validate(self, password: str, username: str = None) -> Tuple[bool, List[str]]:
        """
        Validate password against all rules.
        
        Returns:
            (is_valid, errors_list)
        """
        errors = []
        
        # Length check
        if len(password) < self.config["min_length"]:
            errors.append(f"Password must be at least {self.config['min_length']} characters")
        
        if len(password) > self.config["max_length"]:
            errors.append(f"Password must not exceed {self.config['max_length']} characters")
        
        # Character requirements
        if self.config["require_uppercase"] and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.config["require_lowercase"] and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.config["require_digits"] and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if self.config["require_special"]:
            special_chars = re.escape(self.config["special_chars"])
            if not re.search(f'[{special_chars}]', password):
                errors.append(f"Password must contain at least one special character: {self.config['special_chars']}")
        
        # Entropy check
        entropy = self.calculate_entropy(password)
        if entropy < self.config["min_entropy"]:
            errors.append(f"Password is too weak (entropy: {entropy:.1f} bits, required: {self.config['min_entropy']})")
        
        # Blacklist check (optional)
        password_lower = password.lower()
        blacklist = self.config.get("blacklist", [])
        for blacklisted in blacklist:
            if blacklisted in password_lower:
                errors.append(f"Password contains common word: {blacklisted}")
        
        # Username check
        if username and username.lower() in password_lower:
            errors.append("Password must not contain username")
        
        return len(errors) == 0, errors
    
    def calculate_entropy(self, password: str) -> float:
        """
        Calculate password entropy in bits.
        
        Shannon entropy: -Σ(p(x) * log2(p(x)))
        """
        if not password:
            return 0.0
        
        # Character frequency
        freq = {}
        for char in password:
            freq[char] = freq.get(char, 0) + 1
        
        # Calculate entropy
        entropy = 0.0
        length = len(password)
        
        for count in freq.values():
            probability = count / length
            entropy -= probability * math.log2(probability)
        
        # Scale by length
        return entropy * length
    
    def check_password_history(self, new_password: str, password_history: List[str]) -> bool:
        """
        Check if password was used recently.
        
        Args:
            new_password: The new password to check
            password_history: List of hashed previous passwords
            
        Returns:
            True if password is acceptable (not in recent history)
        """
        # This would compare against hashed passwords
        # Implementation depends on hashing method used
        return True  # Placeholder
    
    def generate_strong_password(self, length: int = 16) -> str:
        """Generate a cryptographically strong password."""
        import secrets
        import string
        
        # Character sets
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        special = self.config["special_chars"]
        
        # Ensure at least one of each required type
        password = [
            secrets.choice(uppercase) if self.config["require_uppercase"] else "",
            secrets.choice(lowercase) if self.config["require_lowercase"] else "",
            secrets.choice(digits) if self.config["require_digits"] else "",
            secrets.choice(special) if self.config["require_special"] else "",
        ]
        
        # Fill the rest
        all_chars = ""
        if self.config["require_uppercase"]:
            all_chars += uppercase
        if self.config["require_lowercase"]:
            all_chars += lowercase
        if self.config["require_digits"]:
            all_chars += digits
        if self.config["require_special"]:
            all_chars += special
        
        password += [secrets.choice(all_chars) for _ in range(length - len(password))]
        
        # Shuffle
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)


def validate_password(password: str, username: str = None) -> Tuple[bool, List[str]]:
    """Convenience function for password validation."""
    validator = PasswordValidator()
    return validator.validate(password, username)
