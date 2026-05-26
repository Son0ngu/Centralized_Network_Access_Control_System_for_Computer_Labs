"""Flask application factory."""

import logging

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from bootstrap.container import initialize_container, initialize_database_indexes
from database.config import get_config, get_database, validate_config
from routes.errors import register_error_handlers
from routes.pages import register_page_routes
from routes.socketio_events import register_socketio_events
from time_utils import format_datetime, parse_agent_timestamp

logger = logging.getLogger(__name__)


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

    CORS(app, resources={
        r"/api/*": {
            "origins": ["*"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "X-API-Key",
                "X-Agent-ID",
                "X-Access-Token",
            ],
        }
    })

    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode=getattr(config, "SOCKETIO_ASYNC_MODE", "gevent"),
        logger=False,
        engineio_logger=False,
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

    register_page_routes(app)
    register_error_handlers(app)
    register_socketio_events(socketio)

    app.config_instance = config
    app.socketio = socketio

    app.logger.info(" MVC Application initialized successfully")
    return app, socketio
