try:
    import gevent.monkey

    gevent.monkey.patch_all()
except ImportError:
    pass

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bootstrap.app_factory import create_app
from database.config import close_mongo_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    try:
        app, socketio = create_app()
        config = app.config_instance

        logger.info(" Starting MVC Firewall Controller")
        logger.info(f" Server: {config.HOST}:{config.PORT}")
        logger.info(" Architecture: Model-View-Controller")
        logger.info(f" Database: {config.MONGO_DBNAME}")
        logger.info(" Timezone: vietnam")

        run_options = {
            "host": config.HOST,
            "port": config.PORT,
            "debug": config.DEBUG,
            "use_reloader": False,
        }
        async_mode = app.config.get(
            "SOCKETIO_ASYNC_MODE",
            getattr(config, "SOCKETIO_ASYNC_MODE", None),
        )
        if async_mode == "threading" and config.DEBUG:
            run_options["allow_unsafe_werkzeug"] = True

        socketio.run(app, **run_options)
    except KeyboardInterrupt:
        logger.info(" Server stopped by user")
        close_mongo_client()
    except Exception as exc:
        logger.error(f" Server error: {str(exc)}")
        import traceback

        traceback.print_exc()
        close_mongo_client()
        raise
