import logging
from flask import Blueprint, request, jsonify, render_template

from services.group_service import GroupService


class GroupController:
    def __init__(self, group_service: GroupService):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.service = group_service
        self.blueprint = Blueprint('groups', __name__)
        self._register_routes()

    def _register_routes(self):
        # API routes
        self.blueprint.add_url_rule('/groups', 'list_groups', self.list_groups, methods=['GET'])
        self.blueprint.add_url_rule('/groups', 'create_group', self.create_group, methods=['POST'])
        self.blueprint.add_url_rule('/groups/<group_id>', 'get_group', self.get_group, methods=['GET'])
        self.blueprint.add_url_rule('/groups/<group_id>', 'update_group', self.update_group, methods=['PATCH'])
        self.blueprint.add_url_rule('/groups/<group_id>', 'delete_group', self.delete_group, methods=['DELETE'])

    def list_groups(self):
        try:
            groups = self.service.list_groups()
            return jsonify({"success": True, "data": groups}), 200
        except Exception as exc:
            self.logger.error(f"Failed to list groups: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 500

    def get_group(self, group_id: str):
        """Get single group details"""
        try:
            group = self.service.get_group(group_id)
            return jsonify({"success": True, "data": group}), 200
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404
        except Exception as exc:
            self.logger.error(f"Failed to get group {group_id}: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 500

    def create_group(self):
        try:
            data = request.get_json() or {}
            name = data.get("name")
            if not name:
                return jsonify({"success": False, "error": "Name is required"}), 400
            description = data.get("description", "")
            whitelist = data.get("whitelist", [])
            group = self.service.create_group(name, description, whitelist)
            return jsonify({"success": True, "data": group}), 201
        except Exception as exc:
            self.logger.error(f"Failed to create group: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 400

    def update_group(self, group_id: str):
        try:
            data = request.get_json() or {}
            updated = self.service.update_group(group_id, data)
            return jsonify({"success": True, "data": updated}), 200
        except Exception as exc:
            self.logger.error(f"Failed to update group {group_id}: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 400

    def delete_group(self, group_id: str):
        try:
            self.service.delete_group(group_id)
            return jsonify({"success": True, "message": "Group deleted"}), 200
        except Exception as exc:
            self.logger.error(f"Failed to delete group {group_id}: {exc}")
            return jsonify({"success": False, "error": str(exc)}), 400