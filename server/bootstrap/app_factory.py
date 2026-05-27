"""Flask application factory."""

import logging

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from bootstrap.container import initialize_container, initialize_database_indexes
from database.config import get_config, get_database, validate_config
from middleware.csrf import register_csrf
from routes.errors import register_error_handlers
from routes.pages import register_page_routes
from routes.socketio_events import register_socketio_events
from time_utils import format_datetime, parse_agent_timestamp

logger = logging.getLogger(__name__)

API_CORS_OPTIONS = {
    "origins": ["*"],
    "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": [
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-Agent-ID",
        "X-Access-Token",
        "X-CSRF-Token",
    ],
}


def _configure_cors(app) -> None:
    """Configure CORS for API routes."""
    CORS(app, resources={r"/api/*": API_CORS_OPTIONS})


def _create_socketio(app, async_mode: str):
    """Create Socket.IO and fall back when the configured backend is missing."""
    try:
        return SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode=async_mode,
            logger=False,
            engineio_logger=False,
        )
    except ValueError as exc:
        if "Invalid async_mode" not in str(exc) or async_mode == "threading":
            raise
        app.logger.warning(
            "Socket.IO async_mode '%s' is unavailable; falling back to 'threading'",
            async_mode,
        )
        app.config["SOCKETIO_ASYNC_MODE"] = "threading"
        return SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode="threading",
            logger=False,
            engineio_logger=False,
        )


def create_app():
    """Create and fully initialize the MVC Flask application."""
    logger.info(" Creating new Flask application...")

    app = Flask(
        __name__,
        static_folder="../views/static",
        template_folder="../views/templates",
    )

    config = get_config()
    app.config.from_object(config)

    @app.template_filter("format_datetime")
    def format_datetime_filter(dt, format="%Y-%m-%d %H:%M:%S vietnam"):
        if dt is None:
            return "N/A"
        if isinstance(dt, str):
            try:
                dt = parse_agent_timestamp(dt)
            except Exception:
                return dt
        return format_datetime(dt, format)

    if not validate_config(config):
        raise RuntimeError("Invalid configuration")

    _configure_cors(app)

    socketio = _create_socketio(
        app,
        getattr(config, "SOCKETIO_ASYNC_MODE", "gevent"),
    )

    try:
        db = get_database(config)
        app.logger.info(f" MongoDB connected: {config.MONGO_DBNAME}")
        initialize_database_indexes(app, db)
    except Exception as exc:
        app.logger.error(f" MongoDB connection failed: {exc}")
        raise RuntimeError("Database connection failed") from exc

    try:
        initialize_container(app, socketio, db)
        app.logger.info(" MVC components initialized successfully")
    except Exception as exc:
        app.logger.error(f" Failed to initialize MVC components: {exc}")
        raise

    # CSRF check must be registered before route handlers run. It hooks
    # before_request, so order vs. blueprint registration doesn't affect
    # correctness, but keeping it near the top makes the security posture
    # obvious to readers.
    register_csrf(app)

    register_page_routes(app)
    register_error_handlers(app)
    register_socketio_events(socketio)

    app.config_instance = config
    app.socketio = socketio

    app.logger.info(" MVC Application initialized successfully")
    return app, socketio
