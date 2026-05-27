"""Model/service/controller composition for the Flask application."""

import logging
import traceback

from controllers.agent_controller import AgentController
from controllers.api_key_controller import APIKeyController
from controllers.audit_controller import AuditController
from controllers.auth_controller import AgentAuthController
from controllers.group_controller import GroupController
from controllers.log_controller import LogController
from controllers.user_controller import UserController
from controllers.web_auth_controller import WebAuthController
from controllers.whitelist_controller import WhitelistController
from controllers.whitelist_profile_controller import WhitelistProfileController
from middleware.auth import init_auth_middleware
from middleware.rbac import init_rbac_middleware
from models.agent_model import AgentModel
from models.agent_policy_model import AgentPolicyModel
from models.api_key_model import APIKeyModel
from models.audit_model import AuditModel
from models.group_model import GroupModel
from models.log_model import LogModel
from models.session_model import SessionModel
from models.user_model import UserModel
from models.whitelist_model import WhitelistModel
from models.whitelist_entry_model import WhitelistEntryModel
from models.whitelist_profile_model import WhitelistProfileModel
from services.admin_auth_service import AdminAuthService
from services.agent_policy_service import AgentPolicyService
from services.agent_service import AgentService
from services.api_key_service import APIKeyService
from services.audit_service import AuditService
from services.group_service import GroupService
from services.jwt_service import init_jwt_service
from services.log_service import LogService
from services.rbac_service import RBACService
from services.user_service import UserService
from services.whitelist_profile_service import WhitelistProfileService
from services.whitelist_service import WhitelistService

from bootstrap.startup_tasks import run_startup_tasks

logger = logging.getLogger(__name__)


def initialize_database_indexes(app, db) -> None:
    """Initialize database indexes safely with proper parameters."""
    try:
        app.logger.info(" Initializing database indexes...")
        WhitelistModel(db)
        WhitelistEntryModel(db)
        LogModel(db)
        AgentModel(db)
        GroupModel(db)
        app.logger.info(" Database indexes initialized successfully")
    except Exception as exc:
        app.logger.warning(f"Index initialization had issues: {exc}")
        app.logger.debug(f"Index initialization traceback: {traceback.format_exc()}")


def initialize_container(app, socketio, db):
    """Create models, services and controllers, then register blueprints."""
    logger.info(" Initializing MVC components...")

    whitelist_model = WhitelistModel(db)
    whitelist_entry_model = WhitelistEntryModel(db)
    agent_model = AgentModel(db)
    log_model = LogModel(db)
    group_model = GroupModel(db)
    api_key_model = APIKeyModel(db)
    agent_policy_model = AgentPolicyModel(db)
    user_model = UserModel(db)
    whitelist_profile_model = WhitelistProfileModel(db)
    session_model = SessionModel(db)
    audit_model = AuditModel(db)
    logger.info(" Models initialized")

    jwt_service = init_jwt_service(db)
    logger.info(" JWT service initialized")

    group_service = GroupService(group_model, agent_model, user_model)
    agent_policy_service = AgentPolicyService(agent_policy_model, agent_model, socketio)
    whitelist_profile_service = WhitelistProfileService(
        whitelist_profile_model, group_model, socketio
    )
    whitelist_service = WhitelistService(
        whitelist_model,
        agent_model,
        group_model,
        socketio,
        entry_model=whitelist_entry_model,
        policy_service=agent_policy_service,
        profile_service=whitelist_profile_service,
    )
    agent_service = AgentService(agent_model, group_model, socketio, jwt_service)
    log_service = LogService(log_model, agent_model=agent_model, socketio=socketio)
    api_key_service = APIKeyService(api_key_model, socketio)
    audit_service = AuditService(audit_model)
    rbac_service = RBACService(group_model, agent_model)
    admin_auth_service = AdminAuthService(
        user_model, jwt_service, session_model, audit_service, socketio
    )
    user_service = UserService(user_model, audit_service, socketio)
    logger.info(" Services initialized (including RBAC)")

    init_auth_middleware(api_key_service, jwt_service)
    init_rbac_middleware(admin_auth_service, rbac_service, jwt_service, user_model)
    logger.info(" Auth + RBAC middleware initialized")

    run_startup_tasks(user_service, api_key_service)

    whitelist_controller = WhitelistController(
        whitelist_model, whitelist_service, rbac_service, socketio
    )
    agent_controller = AgentController(
        agent_model,
        agent_service,
        rbac_service,
        socketio,
        policy_service=agent_policy_service,
    )
    log_controller = LogController(log_model, log_service, rbac_service, socketio)
    group_controller = GroupController(group_service, rbac_service)
    api_key_controller = APIKeyController(api_key_model, api_key_service, socketio)
    auth_controller = AgentAuthController(jwt_service, agent_model, socketio)
    whitelist_profile_controller = WhitelistProfileController(
        whitelist_profile_service, rbac_service
    )
    web_auth_controller = WebAuthController(admin_auth_service, jwt_service, socketio)
    user_controller = UserController(user_service, socketio)
    audit_controller = AuditController(audit_service, socketio)
    logger.info(" Controllers initialized (including RBAC)")

    for controller in (
        whitelist_controller,
        agent_controller,
        log_controller,
        group_controller,
        api_key_controller,
        auth_controller,
        whitelist_profile_controller,
        web_auth_controller,
        user_controller,
        audit_controller,
    ):
        app.register_blueprint(controller.blueprint, url_prefix="/api")

    logger.info(" All controllers registered successfully")
    logger.info(" Registered API routes:")
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/api/"):
            methods = ", ".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
            logger.info(f"  {methods:15} {rule.rule}")

    app.log_service = log_service
    app.agent_service = agent_service
    app.group_service = group_service
    app.api_key_service = api_key_service
    app.user_service = user_service

    return {
        "log_service": log_service,
        "agent_service": agent_service,
        "group_service": group_service,
        "api_key_service": api_key_service,
        "user_service": user_service,
    }
