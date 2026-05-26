"""Startup tasks that are intentionally run when the app boots."""

import logging

logger = logging.getLogger(__name__)


def run_startup_tasks(user_service, api_key_service) -> None:
    """Run safe startup tasks that existed in the old app factory."""
    user_service.ensure_default_admin()
    logger.info(" RBAC defaults seeded")

    default_key = api_key_service.create_default_key_if_none()
    if default_key:
        logger.warning("=" * 60)
        logger.warning("SAVE THIS API KEY - IT WON'T BE SHOWN AGAIN!")
        logger.warning(f"API Key: {default_key.get('api_key')}")
        logger.warning("=" * 60)
