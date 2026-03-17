"""
User Controller - Admin manages teacher/admin accounts.
- CRUD: list, create, update, delete users
- Reset password, toggle active
- Admin-only operations
"""

import logging
import bcrypt
from flask import Blueprint, request, jsonify, g
from typing import Tuple

from time_utils import now_iso
from middleware.rbac import require_login, require_admin


class UserController:
    """Controller for user management (admin only)"""

    def __init__(self, user_model, audit_service=None, socketio=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.user_model = user_model
        self.audit_service = audit_service
        self.socketio = socketio
        self.blueprint = Blueprint('users', __name__)
        self._register_routes()

    def _register_routes(self):
        """Register all user management routes — admin only"""
        rl = require_login  # shortcut
        ra = require_admin

        # List users
        self.blueprint.add_url_rule(
            '/users', 'list_users',
            rl(ra(self.list_users)), methods=['GET']
        )
        # Create user
        self.blueprint.add_url_rule(
            '/users', 'create_user',
            rl(ra(self.create_user)), methods=['POST']
        )
        # Get single user
        self.blueprint.add_url_rule(
            '/users/<user_id>', 'get_user',
            rl(ra(self.get_user)), methods=['GET']
        )
        # Update user
        self.blueprint.add_url_rule(
            '/users/<user_id>', 'update_user',
            rl(ra(self.update_user)), methods=['PATCH']
        )
        # Delete user
        self.blueprint.add_url_rule(
            '/users/<user_id>', 'delete_user',
            rl(ra(self.delete_user)), methods=['DELETE']
        )
        # Reset password
        self.blueprint.add_url_rule(
            '/users/<user_id>/reset-password', 'reset_password',
            rl(ra(self.reset_password)), methods=['POST']
        )
        # Statistics
        self.blueprint.add_url_rule(
            '/users/statistics', 'user_statistics',
            rl(ra(self.get_statistics)), methods=['GET']
        )

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------
    def list_users(self):
        try:
            role = request.args.get('role', '').strip()
            search = request.args.get('search', '').strip()
            limit = min(int(request.args.get('limit', 100)), 500)
            offset = int(request.args.get('offset', 0))

            query = {}
            if role in ('admin', 'teacher'):
                query['role'] = role
            if search:
                query['$or'] = [
                    {'username': {'$regex': search, '$options': 'i'}},
                    {'email': {'$regex': search, '$options': 'i'}},
                ]

            users = self.user_model.get_all_users(query, limit, offset)
            total = self.user_model.count_users(query)

            # Sanitize — never return password_hash
            sanitized = [self._sanitize(u) for u in users]

            return jsonify({
                'success': True,
                'users': sanitized,
                'total': total,
                'limit': limit,
                'offset': offset,
                'timestamp': now_iso(),
            }), 200

        except Exception as e:
            self.logger.error(f'list_users error: {e}')
            return self._err('Lỗi tải danh sách user', 500)

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------
    def get_user(self, user_id):
        try:
            user = self.user_model.find_by_id(user_id)
            if not user:
                return self._err('User không tồn tại', 404)
            return jsonify({'success': True, 'user': self._sanitize(user)}), 200
        except Exception as e:
            self.logger.error(f'get_user error: {e}')
            return self._err('Lỗi', 500)

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------
    def create_user(self):
        try:
            data = request.get_json() or {}
            username = data.get('username', '').strip().lower()
            password = data.get('password', '').strip()
            role = data.get('role', 'teacher').strip().lower()
            email = data.get('email', '').strip().lower() or None

            # Validate
            if not username or len(username) < 3:
                return self._err('Username tối thiểu 3 ký tự', 400)
            if not password or len(password) < 6:
                return self._err('Password tối thiểu 6 ký tự', 400)
            if role not in ('admin', 'teacher'):
                return self._err('Role phải là admin hoặc teacher', 400)

            # Check duplicate
            if self.user_model.find_by_username(username):
                return self._err(f'Username "{username}" đã tồn tại', 409)
            if email and self.user_model.find_by_email(email):
                return self._err(f'Email "{email}" đã được sử dụng', 409)

            # Hash password
            password_hash = bcrypt.hashpw(
                password.encode('utf-8'), bcrypt.gensalt(rounds=12)
            ).decode('utf-8')

            user = self.user_model.create({
                'username': username,
                'password_hash': password_hash,
                'role': role,
                'email': email,
                'is_active': True,
                'created_by': str(g.current_user.get('_id', '')) if hasattr(g, 'current_user') and g.current_user else None,
            })

            # Audit
            self._audit('user.create', f'Created {role} user: {username}')

            return jsonify({
                'success': True,
                'user': self._sanitize(user),
                'message': f'Tạo tài khoản {username} thành công',
            }), 201

        except Exception as e:
            self.logger.error(f'create_user error: {e}')
            return self._err('Lỗi tạo user', 500)

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------
    def update_user(self, user_id):
        try:
            user = self.user_model.find_by_id(user_id)
            if not user:
                return self._err('User không tồn tại', 404)

            data = request.get_json() or {}
            update = {}

            # Role change
            if 'role' in data and data['role'] in ('admin', 'teacher'):
                update['role'] = data['role']

            # Email change
            if 'email' in data:
                new_email = (data['email'] or '').strip().lower() or None
                if new_email:
                    existing = self.user_model.find_by_email(new_email)
                    if existing and str(existing['_id']) != user_id:
                        return self._err('Email đã được sử dụng', 409)
                update['email'] = new_email

            # Active toggle
            if 'is_active' in data:
                update['is_active'] = bool(data['is_active'])

            if not update:
                return self._err('Không có gì thay đổi', 400)

            self.user_model.update(user_id, update)
            self._audit('user.update', f'Updated user {user.get("username")}: {list(update.keys())}')

            updated = self.user_model.find_by_id(user_id)
            return jsonify({
                'success': True,
                'user': self._sanitize(updated),
                'message': 'Cập nhật thành công',
            }), 200

        except Exception as e:
            self.logger.error(f'update_user error: {e}')
            return self._err('Lỗi cập nhật', 500)

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------
    def delete_user(self, user_id):
        try:
            user = self.user_model.find_by_id(user_id)
            if not user:
                return self._err('User không tồn tại', 404)

            # Prevent self-delete
            current_id = str(g.current_user.get('_id', '')) if hasattr(g, 'current_user') and g.current_user else ''
            if current_id == user_id:
                return self._err('Không thể xoá chính mình', 400)

            # Prevent deleting last admin
            if user.get('role') == 'admin':
                admin_count = self.user_model.count_users({'role': 'admin'})
                if admin_count <= 1:
                    return self._err('Không thể xoá admin cuối cùng', 400)

            self.user_model.delete(user_id)
            self._audit('user.delete', f'Deleted user: {user.get("username")}')

            return jsonify({
                'success': True,
                'message': f'Đã xoá tài khoản {user.get("username")}',
            }), 200

        except Exception as e:
            self.logger.error(f'delete_user error: {e}')
            return self._err('Lỗi xoá user', 500)

    # ------------------------------------------------------------------
    # RESET PASSWORD
    # ------------------------------------------------------------------
    def reset_password(self, user_id):
        try:
            user = self.user_model.find_by_id(user_id)
            if not user:
                return self._err('User không tồn tại', 404)

            data = request.get_json() or {}
            new_password = data.get('new_password', '').strip()
            if not new_password or len(new_password) < 6:
                return self._err('Password tối thiểu 6 ký tự', 400)

            password_hash = bcrypt.hashpw(
                new_password.encode('utf-8'), bcrypt.gensalt(rounds=12)
            ).decode('utf-8')

            self.user_model.update(user_id, {
                'password_hash': password_hash,
                'failed_login_attempts': 0,
                'locked_until': None,
            })
            self._audit('user.reset_password', f'Reset password for {user.get("username")}')

            return jsonify({
                'success': True,
                'message': f'Đã đặt lại mật khẩu cho {user.get("username")}',
            }), 200

        except Exception as e:
            self.logger.error(f'reset_password error: {e}')
            return self._err('Lỗi đặt lại mật khẩu', 500)

    # ------------------------------------------------------------------
    # STATISTICS
    # ------------------------------------------------------------------
    def get_statistics(self):
        try:
            stats = self.user_model.get_user_statistics()
            return jsonify({'success': True, **stats, 'timestamp': now_iso()}), 200
        except Exception as e:
            self.logger.error(f'get_statistics error: {e}')
            return self._err('Lỗi', 500)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    @staticmethod
    def _sanitize(user: dict) -> dict:
        """Remove sensitive fields before returning to client"""
        if not user:
            return {}
        return {
            '_id': str(user.get('_id', '')),
            'username': user.get('username', ''),
            'email': user.get('email', ''),
            'role': user.get('role', ''),
            'is_active': user.get('is_active', True),
            'created_at': str(user.get('created_at', '')),
            'updated_at': str(user.get('updated_at', '')),
            'last_login': str(user.get('last_login', '')) if user.get('last_login') else None,
            'created_by': str(user.get('created_by', '')) if user.get('created_by') else None,
        }

    @staticmethod
    def _err(message: str, code: int):
        return jsonify({'success': False, 'error': message, 'timestamp': now_iso()}), code

    def _audit(self, action: str, detail: str):
        if self.audit_service:
            try:
                user = getattr(g, 'current_user', None)
                self.audit_service.log(
                    action=action,
                    user_id=str(user.get('_id', '')) if user else None,
                    username=user.get('username', '') if user else 'system',
                    role=getattr(g, 'current_role', ''),
                    ip_address=request.remote_addr,
                    details=detail,
                )
            except Exception:
                pass
