"""
Admin Auth Controller - Login, logout, refresh, profile, change password.
- Blueprint prefix: /admin/auth/*
- Separate from Agent auth (/api/auth/*)
- Token stored in httpOnly cookie
"""

import logging
from flask import Blueprint, request, jsonify, g, make_response
from typing import Tuple

from services.admin_auth_service import AdminAuthService
from services.jwt_service import JWTService
from middleware.rbac import require_login
from time_utils import now_iso

logger = logging.getLogger(__name__)

# Cookie config
COOKIE_ACCESS_NAME = "access_token"
COOKIE_REFRESH_NAME = "refresh_token"
COOKIE_HTTPONLY = True
COOKIE_SECURE = False        # Set True in production (HTTPS)
COOKIE_SAMESITE = "Lax"
COOKIE_PATH = "/"


class AdminAuthController:
    """Controller for admin/teacher authentication"""

    def __init__(self, admin_auth_service: AdminAuthService,
                 jwt_service: JWTService, socketio=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.auth_service = admin_auth_service
        self.jwt_service = jwt_service
        self.socketio = socketio
        self.blueprint = Blueprint('admin_auth', __name__)
        self._register_routes()

    def _register_routes(self):
        """Register routes"""
        # Public
        self.blueprint.add_url_rule(
            '/admin/auth/login', 'login', self.login, methods=['POST']
        )
        # Protected
        self.blueprint.add_url_rule(
            '/admin/auth/me', 'me', self.get_profile, methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/admin/auth/refresh', 'refresh', self.refresh_token, methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/admin/auth/logout', 'logout', self.logout, methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/admin/auth/change-password', 'change_password',
            self.change_password, methods=['PUT']
        )
        self.blueprint.add_url_rule(
            '/admin/auth/profile', 'update_profile',
            self.update_profile, methods=['PUT']
        )

    def _success(self, data=None, message="Success", status_code=200) -> Tuple:
        response = {"success": True, "message": message}
        if data is not None:
            response["data"] = data
        return jsonify(response), status_code

    def _error(self, message: str, status_code=400, code=None) -> Tuple:
        response = {"success": False, "error": message}
        if code:
            response["code"] = code
        return jsonify(response), status_code

    # ========================================================================
    # PUBLIC
    # ========================================================================

    def login(self):
        """
        POST /api/admin/auth/login
        Body: {"username": "admin", "password": "admin123456"}
        Response: Set httpOnly cookies + return user info
        """
        try:
            if not request.is_json:
                return self._error("Request must be JSON", 400)

            data = request.get_json()
            username = data.get("username", "").strip()
            password = data.get("password", "")

            if not username or not password:
                return self._error("Username and password are required", 400)

            success, result, error = self.auth_service.login(
                username=username,
                password=password,
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )

            if not success:
                return self._error(error or "Login failed", 401)

            # Build response with httpOnly cookies
            tokens = result["tokens"]
            resp = make_response(jsonify({
                "success": True,
                "message": "Login successful",
                "data": {
                    "user": result["user"],
                    "tokens": tokens,  # Also return in body for API clients
                },
            }))

            # Set httpOnly cookies
            resp.set_cookie(
                COOKIE_ACCESS_NAME,
                tokens["access_token"],
                httponly=COOKIE_HTTPONLY,
                secure=COOKIE_SECURE,
                samesite=COOKIE_SAMESITE,
                path=COOKIE_PATH,
                max_age=tokens.get("access_expires_in", 86400),
            )
            resp.set_cookie(
                COOKIE_REFRESH_NAME,
                tokens["refresh_token"],
                httponly=COOKIE_HTTPONLY,
                secure=COOKIE_SECURE,
                samesite=COOKIE_SAMESITE,
                path=COOKIE_PATH,
                max_age=tokens.get("refresh_expires_in", 604800),
            )

            return resp

        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return self._error("Login failed", 500)

    # ========================================================================
    # PROTECTED
    # ========================================================================

    @require_login
    def get_profile(self):
        """
        GET /api/admin/auth/me
        Returns current user profile
        """
        try:
            user = g.current_user
            safe_user = {
                "_id": str(user["_id"]),
                "username": user.get("username"),
                "email": user.get("email"),
                "role": user.get("role"),
                "is_active": user.get("is_active"),
                "last_login": user.get("last_login"),
                "created_at": user.get("created_at"),
            }
            return self._success(safe_user)
        except Exception as e:
            self.logger.error(f"Get profile error: {e}")
            return self._error("Failed to get info", 500)

    @require_login
    def refresh_token(self):
        """
        POST /api/admin/auth/refresh
        Body: {"refresh_token": "..."} or from cookie
        """
        try:
            # Get refresh token from body or cookie
            refresh_token = None
            if request.is_json:
                data = request.get_json()
                refresh_token = data.get("refresh_token")
            if not refresh_token:
                refresh_token = request.cookies.get(COOKIE_REFRESH_NAME)

            if not refresh_token:
                return self._error("Refresh token required", 400)

            success, result, error = self.auth_service.refresh_token(refresh_token)

            if not success:
                if "expired" in (error or "").lower():
                    return self._error(error, 401, "REFRESH_TOKEN_EXPIRED")
                return self._error(error or "Refresh failed", 401)

            # Update access_token cookie
            resp = make_response(jsonify({
                "success": True,
                "message": "Token refreshed",
                "data": result,
            }))
            resp.set_cookie(
                COOKIE_ACCESS_NAME,
                result["access_token"],
                httponly=COOKIE_HTTPONLY,
                secure=COOKIE_SECURE,
                samesite=COOKIE_SAMESITE,
                path=COOKIE_PATH,
                max_age=result.get("expires_in", 86400),
            )
            return resp

        except Exception as e:
            self.logger.error(f"Refresh error: {e}")
            return self._error("Refresh failed", 500)

    @require_login
    def logout(self):
        """
        POST /api/admin/auth/logout
        Revoke tokens + clear cookies
        """
        try:
            access_token = request.cookies.get(COOKIE_ACCESS_NAME)
            refresh_token = None
            if request.is_json:
                data = request.get_json()
                refresh_token = data.get("refresh_token")
            if not refresh_token:
                refresh_token = request.cookies.get(COOKIE_REFRESH_NAME)

            self.auth_service.logout(access_token, refresh_token)

            # Clear cookies
            resp = make_response(jsonify({
                "success": True,
                "message": "Logout successful",
            }))
            resp.delete_cookie(COOKIE_ACCESS_NAME, path=COOKIE_PATH)
            resp.delete_cookie(COOKIE_REFRESH_NAME, path=COOKIE_PATH)

            return resp

        except Exception as e:
            self.logger.error(f"Logout error: {e}")
            return self._error("Logout failed", 500)

    @require_login
    def change_password(self):
        """
        PUT /api/admin/auth/change-password
        Body: {"old_password": "...", "new_password": "..."}
        """
        try:
            if not request.is_json:
                return self._error("Request must be JSON", 400)

            data = request.get_json()
            old_password = data.get("old_password", "")
            new_password = data.get("new_password", "")

            if not old_password or not new_password:
                return self._error("old_password and new_password are required", 400)

            success, error = self.auth_service.change_password(
                g.current_user_id, old_password, new_password
            )

            if not success:
                return self._error(error, 400)

            return self._success(None, "Password changed successfully")

        except Exception as e:
            self.logger.error(f"Change password error: {e}")
            return self._error("Password change failed", 500)

    @require_login
    def update_profile(self):
        """
        PUT /api/admin/auth/profile
        Body: {"email": "..."}
        """
        try:
            if not request.is_json:
                return self._error("Request must be JSON", 400)

            data = request.get_json()
            email = data.get("email", "").strip()

            update_data = {}
            if email:
                # Check email duplicate
                existing = self.auth_service.user_model.find_by_email(email)
                if existing and str(existing.get("_id")) != str(g.current_user_id):
                    return self._error("Email already in use by another user", 400)
                update_data["email"] = email

            if update_data:
                success = self.auth_service.user_model.update(g.current_user_id, update_data)
                if success:
                    # Log audit if needed
                    try:
                        if hasattr(self.auth_service, 'audit_service'):
                            self.auth_service.audit_service.log(
                                action="profile.update",
                                username=g.current_user.get("username"),
                                role=g.current_role,
                                ip_address=request.remote_addr,
                                details={"updated_fields": list(update_data.keys())}
                            )
                    except Exception as e:
                        self.logger.error(f"Failed to log profile update: {e}")
                        
                    return self._success(None, "Profile updated successfully")
                return self._error("Cannot update profile", 500)

            return self._success(None, "No changes")

        except Exception as e:
            self.logger.error(f"Update profile error: {e}")
            return self._error("Profile update failed", 500)
