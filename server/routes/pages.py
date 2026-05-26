"""Page and simple API route registration."""

import os

from flask import jsonify, redirect, render_template, url_for

from time_utils import now_iso


def register_page_routes(app) -> None:
    """Register web pages and simple app metadata endpoints."""

    @app.route("/")
    def index():
        try:
            stats = {
                "total_logs": 0,
                "allowed_count": 0,
                "blocked_count": 0,
                "active_agents": 0,
            }
            recent_logs = []
            return render_template(
                "dashboard.html",
                page_title="Dashboard",
                stats=stats,
                recent_logs=recent_logs,
            )
        except Exception as exc:
            app.logger.error(f"Dashboard error: {exc}")
            return render_template(
                "dashboard.html",
                page_title="Dashboard",
                stats={
                    "total_logs": 0,
                    "allowed_count": 0,
                    "blocked_count": 0,
                    "active_agents": 0,
                },
                recent_logs=[],
            )

    @app.route("/agents")
    def agents_page():
        return render_template("agents.html", page_title="Agent Management")

    @app.route("/groups")
    def groups_page():
        return render_template("groups.html", page_title="Group Management")

    @app.route("/groups/<group_id>")
    def group_detail(group_id):
        try:
            group = app.group_service.get_group(group_id)
            if not group:
                return render_template("404.html", message="Group not found"), 404
            return render_template(
                "group_detail.html",
                group=group,
                page_title=f"Group: {group.get('name', 'Unknown')}",
            )
        except ValueError as exc:
            app.logger.warning(f"Group not found: {group_id} - {exc}")
            return render_template("404.html", message="Group not found"), 404
        except Exception as exc:
            app.logger.error(f"Error loading group {group_id}: {exc}")
            return render_template("500.html", message=str(exc)), 500

    @app.route("/whitelist")
    def whitelist_page():
        return render_template("whitelist.html", page_title="Whitelist Management")

    @app.route("/logs")
    def logs_page():
        return render_template("logs.html", page_title="System Logs")

    @app.route("/api-keys")
    def api_keys_page():
        return render_template("api_keys.html", page_title="API Keys Management")

    @app.route("/login")
    def login_page():
        return render_template("login.html")

    @app.route("/admin/users")
    def admin_users_page():
        return render_template("admin_users.html", page_title="User Management")

    @app.route("/admin/audit")
    def admin_audit_page():
        return render_template("admin_audit.html", page_title="Audit Logs")

    @app.route("/profile")
    def profile_page():
        return render_template("profile.html", page_title="My Profile")

    @app.route("/admin/change-password")
    def change_password_page():
        return redirect(url_for("profile_page"))

    @app.route("/api/health")
    def health_check():
        return jsonify({
            "status": "healthy",
            "version": "1.0.0",
            "architecture": "MVC",
            "timestamp": now_iso(),
        }), 200

    @app.route("/api/config")
    def get_client_config():
        return jsonify({
            "socketio_enabled": True,
            "version": "1.0.0",
            "architecture": "MVC",
            "environment": os.environ.get("FLASK_ENV", "production"),
            "timezone": "vietnam",
            "server_time": now_iso(),
        }), 200
