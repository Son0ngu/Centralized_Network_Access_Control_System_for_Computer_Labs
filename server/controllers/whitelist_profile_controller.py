"""
Whitelist Profile Controller - Per-teacher whitelist profiles within groups.
"""

import logging
from flask import Blueprint, request, jsonify, g

from services.whitelist_profile_service import WhitelistProfileService
from services.rbac_service import RBACService
from middleware.rbac import require_login, require_permission


class WhitelistProfileController:
    def __init__(self, profile_service: WhitelistProfileService, rbac_service: RBACService):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.service = profile_service
        self.rbac_service = rbac_service
        self.blueprint = Blueprint('whitelist_profiles', __name__)
        self._register_routes()

    def _register_routes(self):
        bp = self.blueprint
        # Teacher's own profiles across all groups (for /whitelist page dropdown)
        bp.add_url_rule(
            '/my-profiles', 'my_profiles',
            require_login(self.my_profiles), methods=['GET'])
        bp.add_url_rule(
            '/groups/<group_id>/profiles', 'list_profiles',
            require_login(self.list_profiles), methods=['GET'])
        bp.add_url_rule(
            '/groups/<group_id>/profiles', 'create_profile',
            require_login(require_permission("whitelist_profile:create")(self.create_profile)),
            methods=['POST'])
        bp.add_url_rule(
            '/groups/<group_id>/profiles/<profile_id>', 'update_profile',
            require_login(require_permission("whitelist_profile:update")(self.update_profile)),
            methods=['PATCH'])
        bp.add_url_rule(
            '/groups/<group_id>/profiles/<profile_id>', 'delete_profile',
            require_login(require_permission("whitelist_profile:delete")(self.delete_profile)),
            methods=['DELETE'])
        bp.add_url_rule(
            '/groups/<group_id>/profiles/<profile_id>/activate', 'activate_profile',
            require_login(require_permission("whitelist_profile:activate")(self.activate_profile)),
            methods=['POST'])
        bp.add_url_rule(
            '/groups/<group_id>/profiles/<profile_id>/deactivate', 'deactivate_profile',
            require_login(require_permission("whitelist_profile:activate")(self.deactivate_profile)),
            methods=['POST'])

    def _get_user(self):
        return getattr(g, 'current_user', None)

    def _check_group_access(self, group_id):
        """Verify user can access this group. Returns (group, error_response)."""
        user = self._get_user()
        if not user:
            return None, (jsonify({"success": False, "error": "Auth required"}), 401)

        group_model = self.rbac_service.group_model
        group = group_model.find_by_id(group_id) if group_model else None
        if not group:
            return None, (jsonify({"success": False, "error": "Group not found"}), 404)

        if not self.rbac_service.can_access_group(user, group):
            return None, (jsonify({"success": False, "error": "No permission for this Group"}), 403)

        return group, None

    def my_profiles(self):
        """GET /api/my-profiles - Return all profiles owned by current teacher."""
        try:
            user = self._get_user()
            if not user:
                return jsonify({"success": False, "error": "Auth required"}), 401

            # Get groups this teacher has access to
            teacher_group_ids = self.rbac_service.get_teacher_group_ids(user)
            if teacher_group_ids is None:
                # Admin - return empty (admin doesn't use profile selector)
                return jsonify({"success": True, "data": []}), 200
            if not teacher_group_ids:
                return jsonify({"success": True, "data": []}), 200

            profiles = self.service.get_teacher_profiles(
                teacher_id=user["_id"],
                group_ids=teacher_group_ids,
            )
            return jsonify({"success": True, "data": profiles}), 200
        except Exception as exc:
            self.logger.error(f"Failed to get my profiles: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 500

    def list_profiles(self, group_id):
        try:
            group, err = self._check_group_access(group_id)
            if err:
                return err

            # All users see all profiles in group (to see who's active)
            # Edit/delete is restricted by ownership in service layer
            profiles = self.service.list_profiles(group_id)
            return jsonify({"success": True, "data": profiles}), 200
        except Exception as exc:
            self.logger.error(f"Failed to list profiles: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 500

    def create_profile(self, group_id):
        try:
            group, err = self._check_group_access(group_id)
            if err:
                return err

            user = self._get_user()
            data = request.get_json() or {}
            name = data.get("name")
            if not name:
                return jsonify({"success": False, "error": "Name is required"}), 400

            domains = data.get("domains", [])
            profile = self.service.create_profile(
                group_id=group_id,
                teacher_id=user["_id"],
                teacher_username=user.get("username", ""),
                name=name,
                domains=domains,
            )
            return jsonify({"success": True, "data": profile}), 201
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        except Exception as exc:
            self.logger.error(f"Failed to create profile: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 500

    def update_profile(self, group_id, profile_id):
        try:
            group, err = self._check_group_access(group_id)
            if err:
                return err

            user = self._get_user()
            data = request.get_json() or {}
            updated = self.service.update_profile(profile_id, data, user=user)
            return jsonify({"success": True, "data": updated}), 200
        except PermissionError as exc:
            return jsonify({"success": False, "error": str(exc)}), 403
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        except Exception as exc:
            self.logger.error(f"Failed to update profile: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 500

    def delete_profile(self, group_id, profile_id):
        try:
            group, err = self._check_group_access(group_id)
            if err:
                return err

            user = self._get_user()
            self.service.delete_profile(profile_id, user=user)
            return jsonify({"success": True, "message": "Profile deleted"}), 200
        except PermissionError as exc:
            return jsonify({"success": False, "error": str(exc)}), 403
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        except Exception as exc:
            self.logger.error(f"Failed to delete profile: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 500

    def activate_profile(self, group_id, profile_id):
        try:
            group, err = self._check_group_access(group_id)
            if err:
                return err

            user = self._get_user()
            result = self.service.activate_profile(profile_id, user=user)
            return jsonify({"success": True, "data": result}), 200
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        except Exception as exc:
            self.logger.error(f"Failed to activate profile: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 500

    def deactivate_profile(self, group_id, profile_id):
        try:
            group, err = self._check_group_access(group_id)
            if err:
                return err

            user = self._get_user()
            result = self.service.deactivate_profile(profile_id, user=user)
            return jsonify({"success": True, "data": result}), 200
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        except Exception as exc:
            self.logger.error(f"Failed to deactivate profile: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 500
