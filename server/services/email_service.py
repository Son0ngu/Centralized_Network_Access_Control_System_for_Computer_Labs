"""
Email Service
-------------
Sends emails for 2FA, password reset, notifications.
"""

import logging
import smtplib
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
from datetime import datetime, timedelta

from time_utils import now_vietnam

logger = logging.getLogger(__name__)

# Simple 2FA config (hardcoded, no external dependency)
_2FA_CODE_LENGTH = 6
_2FA_CODE_EXPIRY = 300  # 5 minutes
_2FA_MAX_ATTEMPTS = 3

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails."""
    
    def __init__(self, smtp_config: Dict):
        """
        Initialize email service.
        
        Args:
            smtp_config: {
                "host": "smtp.gmail.com",
                "port": 587,
                "username": "your-email@gmail.com",
                "password": "your-app-password",
                "from_email": "noreply@yourapp.com",
                "from_name": "Your App"
            }
        """
        self.config = smtp_config
        self.logger = logging.getLogger(__name__)
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> bool:
        """
        Send email.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            body_text: Plain text body
            body_html: HTML body (optional)
        
        Returns:
            True if sent successfully
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.config['from_name']} <{self.config['from_email']}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add plain text
            msg.attach(MIMEText(body_text, 'plain'))
            
            # Add HTML if provided
            if body_html:
                msg.attach(MIMEText(body_html, 'html'))
            
            # Connect and send
            with smtplib.SMTP(self.config['host'], self.config['port']) as server:
                server.starttls()
                server.login(self.config['username'], self.config['password'])
                server.send_message(msg)
            
            self.logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def send_2fa_code(self, to_email: str, code: str, expires_in: int = 300) -> bool:
        """
        Send 2FA verification code.
        
        Args:
            to_email: Recipient email
            code: 6-digit verification code
            expires_in: Expiry time in seconds
        
        Returns:
            True if sent successfully
        """
        subject = "Your Verification Code"
        
        body_text = f"""
Your verification code is: {code}

This code will expire in {expires_in // 60} minutes.

If you didn't request this code, please ignore this email.
"""
        
        body_html = f"""
<html>
<body>
    <h2>Verification Code</h2>
    <p>Your verification code is:</p>
    <h1 style="font-size: 32px; letter-spacing: 5px; color: #007bff;">{code}</h1>
    <p>This code will expire in <strong>{expires_in // 60} minutes</strong>.</p>
    <p>If you didn't request this code, please ignore this email.</p>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, body_text, body_html)
    
    def send_password_reset(self, to_email: str, reset_token: str, reset_url: str) -> bool:
        """Send password reset email."""
        subject = "Password Reset Request"
        
        body_text = f"""
You have requested to reset your password.

Click the link below to reset your password:
{reset_url}?token={reset_token}

This link will expire in 1 hour.

If you didn't request this, please ignore this email.
"""
        
        body_html = f"""
<html>
<body>
    <h2>Password Reset Request</h2>
    <p>You have requested to reset your password.</p>
    <p>
        <a href="{reset_url}?token={reset_token}" 
           style="display: inline-block; padding: 10px 20px; background-color: #007bff; 
                  color: white; text-decoration: none; border-radius: 5px;">
            Reset Password
        </a>
    </p>
    <p>Or copy and paste this link:</p>
    <p>{reset_url}?token={reset_token}</p>
    <p>This link will expire in <strong>1 hour</strong>.</p>
    <p>If you didn't request this, please ignore this email.</p>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, body_text, body_html)
    
    def send_welcome_email(self, to_email: str, username: str) -> bool:
        """Send welcome email to new user."""
        subject = "Welcome to Firewall Controller!"
        
        body_text = f"""
Welcome {username}!

Thank you for joining Firewall Controller.

You can now log in and start managing your firewall agents.

If you have any questions, please contact our support team.
"""
        
        body_html = f"""
<html>
<body>
    <h2>Welcome {username}!</h2>
    <p>Thank you for joining <strong>Firewall Controller</strong>.</p>
    <p>You can now log in and start managing your firewall agents.</p>
    <p>If you have any questions, please contact our support team.</p>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, body_text, body_html)
    
    def send_security_alert(self, to_email: str, alert_type: str, details: str) -> bool:
        """Send security alert email."""
        subject = f"Security Alert: {alert_type}"
        
        body_text = f"""
SECURITY ALERT

Type: {alert_type}
Time: {now_vietnam().strftime('%Y-%m-%d %H:%M:%S')} (Vietnam Time)

Details:
{details}

If this was you, no action is needed. Otherwise, please secure your account immediately.
"""
        
        body_html = f"""
<html>
<body>
    <h2 style="color: #dc3545;">Security Alert</h2>
    <p><strong>Type:</strong> {alert_type}</p>
    <p><strong>Time:</strong> {now_vietnam().strftime('%Y-%m-%d %H:%M:%S')} (Vietnam Time)</p>
    <h3>Details:</h3>
    <p>{details}</p>
    <p>If this was you, no action is needed. Otherwise, please secure your account immediately.</p>
</body>
</html>
"""
        
        return self.send_email(to_email, subject, body_text, body_html)


class TwoFactorAuthService:
    """2FA code generation and verification."""
    
    def __init__(self, email_service: EmailService):
        self.email_service = email_service
        self.codes = {}  # In-memory storage (use Redis in production)
    
    def generate_code(self, user_id: str) -> str:
        """Generate 6-digit code."""
        code = ''.join([str(secrets.randbelow(10)) for _ in range(_2FA_CODE_LENGTH)])
        
        # Store code with expiry
        expiry = now_vietnam() + timedelta(seconds=_2FA_CODE_EXPIRY)
        self.codes[user_id] = {
            "code": code,
            "expires": expiry,
            "attempts": 0
        }
        
        return code
    
    def send_code(self, user_id: str, email: str) -> bool:
        """Generate and send 2FA code."""
        code = self.generate_code(user_id)
        return self.email_service.send_2fa_code(
            email, 
            code, 
            _2FA_CODE_EXPIRY
        )
    
    def verify_code(self, user_id: str, code: str) -> bool:
        """Verify 2FA code."""
        if user_id not in self.codes:
            return False
        
        stored = self.codes[user_id]
        
        # Check expiry
        if now_vietnam() > stored["expires"]:
            del self.codes[user_id]
            return False
        
        # Check attempts
        if stored["attempts"] >= _2FA_MAX_ATTEMPTS:
            del self.codes[user_id]
            return False
        
        # Increment attempts
        stored["attempts"] += 1
        
        # Verify code
        if stored["code"] == code:
            del self.codes[user_id]
            return True
        
        return False
    
    def generate_backup_codes(self, count: int = 10) -> list:
        """Generate backup codes for 2FA."""
        return [
            '-'.join([
                ''.join([str(secrets.randbelow(10)) for _ in range(4)])
                for _ in range(2)
            ])
            for _ in range(count)
        ]


# Global email service instance
_email_service = None
_2fa_service = None


def init_email_service(smtp_config: Dict):
    """Initialize global email service."""
    global _email_service, _2fa_service
    _email_service = EmailService(smtp_config)
    _2fa_service = TwoFactorAuthService(_email_service)
    logger.info("Email service initialized")


def get_email_service() -> EmailService:
    """Get email service instance."""
    return _email_service


def get_2fa_service() -> TwoFactorAuthService:
    """Get 2FA service instance."""
    return _2fa_service
