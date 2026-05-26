"""Error handler registration."""

from flask import jsonify, render_template, request

from time_utils import now_iso


def register_error_handlers(app) -> None:
    """Register HTML and JSON error handlers."""

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found", "timestamp": now_iso()}), 404
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        app.logger.error(f"Server error: {str(error)}")
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "Internal server error",
                "timestamp": now_iso(),
            }), 500
        return render_template("500.html"), 500
