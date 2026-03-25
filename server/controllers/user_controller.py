"""
User Controller - Admin manages teacher/admin accounts.
- CRUD: list, create, update, delete users
- Reset password, toggle active
- Admin-only operations
- Delegates to UserService for business logic
"""

import logging
from flask import Blueprint, request, jsonify, g
from typing import Tuple

from time_utils import now_iso
from middleware.rbac import require_login, require_admin


class UserController:
    """Controller for user management (admin only)"""

    def __init__(self, user_service, socketio=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.user_service = user_service
        self.socketio = socketio
        self.blueprint = Blueprint('users', __name__)
        self._register_routes()

    def _register_routes(self):
        """Register all user management routes - admin only"""
        rl = require_login  # shortcut
        ra = require_admin

        # List users
        self.blueprint.add_url_rule(
            '/admin/users', 'list_users',
            rl(ra(self.list_users)), methods=['GET']
        )
        # Create user
        self.blueprint.add_url_rule(
            '/admin/users', 'create_user',
            rl(ra(self.create_user)), methods=['POST']
        )
        # Get single user
        self.blueprint.add_url_rule(
            '/admin/users/<user_id>', 'get_user',
            rl(ra(self.get_user)), methods=['GET']
        )
        # Update user
        self.blueprint.add_url_rule(
            '/admin/users/<user_id>', 'update_user',
            rl(ra(self.update_user)), methods=['PATCH']
        )
        # Delete user
        self.blueprint.add_url_rule(
            '/admin/users/<user_id>', 'delete_user',
            rl(ra(self.delete_user)), methods=['DELETE']
        )
        # Reset password
        self.blueprint.add_url_rule(
            '/admin/users/<user_id>/reset-password', 'reset_password',
            rl(ra(self.reset_password)), methods=['POST']
        )
        # Statistics
        self.blueprint.add_url_rule(
            '/admin/users/statistics', 'user_statistics',
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

            users = self.user_service.get_all_users(query, limit, offset)
            total = self.user_service.user_model.count_users(query)

            return jsonify({
                'success': True,
                'data': {
                    'users': users,
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                },
                'timestamp': now_iso(),
            }), 200

        except Exception as e:
            self.logger.error(f'list_users error: {e}')
            return self._err('Error loading user list', 500)

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------
    def get_user(self, user_id):
        try:
            user = self.user_service.get_user_by_id(user_id)
            if not user:
                return self._err('User does not exist', 404)
            return jsonify({'success': True, 'user': user}), 200
        except Exception as e:
            self.logger.error(f'get_user error: {e}')
            return self._err('Error', 500)

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------
    def create_user(self):
        try:
            data = request.get_json() or {}
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            role = data.get('role', 'teacher').strip().lower()
            email = data.get('email', '').strip().lower() or None

            current_user = getattr(g, 'current_user', None)

            success, user, error = self.user_service.create_user(
                username=username,
                password=password,
                role=role,
                email=email,
                created_by_user=current_user,
            )

            if not success:
                return self._err(error or 'Error creating user', 400)

            return jsonify({
                'success': True,
                'user': user,
                'message': f'Account {username} created successfully',
            }), 201

        except Exception as e:
            self.logger.error(f'create_user error: {e}')
            return self._err('Error creating user', 500)

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------
    def update_user(self, user_id):
        try:
            data = request.get_json() or {}
            current_user = getattr(g, 'current_user', None)

            # Handle is_active toggle separately
            if 'is_active' in data and len(data) == 1:
                success, error = self.user_service.toggle_active(
                    user_id, bool(data['is_active']), current_user
                )
            else:
                update_data = {}
                if 'role' in data:
                    update_data['role'] = data['role']
                if 'email' in data:
                    update_data['email'] = data['email']
                if 'is_active' in data:
                    update_data['is_active'] = bool(data['is_active'])

                if not update_data:
                    return self._err('No changes made', 400)

                success, error = self.user_service.update_user(
                    user_id, update_data, current_user
                )

            if not success:
                return self._err(error or 'Update error', 400)

            updated = self.user_service.get_user_by_id(user_id)
            return jsonify({
                'success': True,
                'user': updated,
                'message': 'Updated successfully',
            }), 200

        except Exception as e:
            self.logger.error(f'update_user error: {e}')
            return self._err('Update error', 500)

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------
    def delete_user(self, user_id):
        try:
            current_user = getattr(g, 'current_user', None)

            # Self-delete check
            current_id = str(current_user.get('_id', '')) if current_user else ''
            if current_id == user_id:
                return self._err('Cannot delete yourself', 400)

            success, error = self.user_service.delete_user(user_id, current_user)

            if not success:
                return self._err(error or 'Error deleting user', 400)

            return jsonify({
                'success': True,
                'message': 'Account deleted successfully',
            }), 200

        except Exception as e:
            self.logger.error(f'delete_user error: {e}')
            return self._err('Error deleting user', 500)

    # ------------------------------------------------------------------
    # RESET PASSWORD
    # ------------------------------------------------------------------
    def reset_password(self, user_id):
        try:
            data = request.get_json() or {}
            new_password = data.get('new_password', '').strip()
            if not new_password:
                return self._err('Password cannot be empty', 400)

            current_user = getattr(g, 'current_user', None)

            success, error = self.user_service.reset_password(
                user_id, new_password, current_user
            )

            if not success:
                return self._err(error or 'Error resetting password', 400)

            return jsonify({
                'success': True,
                'message': 'Password reset successfully',
            }), 200

        except Exception as e:
            self.logger.error(f'reset_password error: {e}')
            return self._err('Error resetting password', 500)

    # ------------------------------------------------------------------
    # STATISTICS
    # ------------------------------------------------------------------
    def get_statistics(self):
        try:
            stats = self.user_service.user_model.get_user_statistics()
            return jsonify({'success': True, 'data': stats, 'timestamp': now_iso()}), 200
        except Exception as e:
            self.logger.error(f'get_statistics error: {e}')
            return self._err('Error', 500)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    @staticmethod
    def _err(message: str, code: int):
        return jsonify({'success': False, 'error': message, 'timestamp': now_iso()}), code
