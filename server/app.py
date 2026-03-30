import gevent.monkey

gevent.monkey.patch_all()

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_socketio import SocketIO
from flask_cors import CORS

from database.config import get_config, get_database, validate_config, close_mongo_client

from time_utils import now_iso, format_datetime, parse_agent_timestamp

from models.whitelist_model import WhitelistModel
from models.agent_model import AgentModel
from models.log_model import LogModel
from models.group_model import GroupModel
from models.agent_policy_model import AgentPolicyModel

from services.whitelist_service import WhitelistService
from services.agent_service import AgentService
from services.log_service import LogService
from services.group_service import GroupService
from services.agent_policy_service import AgentPolicyService

from controllers.whitelist_controller import WhitelistController
from controllers.agent_controller import AgentController
from controllers.log_controller import LogController
from controllers.group_controller import GroupController
from controllers.api_key_controller import APIKeyController
from controllers.auth_controller import AuthController

from models.user_model import UserModel
from models.session_model import SessionModel
from models.audit_model import AuditModel
from models.whitelist_profile_model import WhitelistProfileModel
from services.admin_auth_service import AdminAuthService
from services.rbac_service import RBACService
from services.audit_service import AuditService
from services.user_service import UserService
from services.whitelist_profile_service import WhitelistProfileService
from controllers.admin_auth_controller import AdminAuthController
from controllers.user_controller import UserController
from controllers.audit_controller import AuditController
from controllers.whitelist_profile_controller import WhitelistProfileController

from models.api_key_model import APIKeyModel
from services.api_key_service import APIKeyService

from services.jwt_service import JWTService, init_jwt_service

from middleware.auth import init_auth_middleware
from middleware.rbac import init_rbac_middleware

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_app_initialized = False

def create_app():
    global _app_initialized
    
    if _app_initialized:
        logger.info(" App already initialized, skipping...")
        # Return minimal app for reloader
        app = Flask(__name__, 
                    static_folder='views/static',
                    template_folder='views/templates')
        config = get_config()
        app.config.from_object(config)
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')
        return app, socketio
    
    logger.info(" Creating new Flask application...")
    
    # Create Flask app
    app = Flask(__name__, 
                static_folder='views/static',
                template_folder='views/templates')
    
    config = get_config()
    app.config.from_object(config)
    
    @app.template_filter('format_datetime')
    def format_datetime_filter(dt, format='%Y-%m-%d %H:%M:%S vietnam'):
        """Format datetime for template using time_utils - vietnam ONLY"""
        if dt is None:
            return 'N/A'
        if isinstance(dt, str):
            try:
                # Parse ISO string using vietnam parsing
                dt = parse_agent_timestamp(dt)  # vietnam parsing
            except:
                return dt
        return format_datetime(dt, format)
    
    # Validate configuration
    if not validate_config(config):
        raise RuntimeError("Invalid configuration")
    
    # Setup CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["*"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Initialize SocketIO
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='gevent',
        logger=False,
        engineio_logger=False
    )

    try:
        db = get_database(config)
        app.logger.info(f" MongoDB connected: {config.MONGO_DBNAME}")
        
        initialize_database_indexes(app, db)
        
    except Exception as e:
        app.logger.error(f" MongoDB connection failed: {e}")
        raise RuntimeError("Database connection failed")
    
    try:
        log_service, agent_service, group_service, api_key_service, user_service = register_controllers(app, socketio, db)

        if log_service is None or agent_service is None or group_service is None or api_key_service is None:
            raise RuntimeError("Failed to initialize services")
            
        app.logger.info(" MVC components initialized successfully")
        
    except Exception as e:
        app.logger.error(f" Failed to initialize MVC components: {e}")
        raise
    
    # Register application routes
    register_main_routes(app, log_service, agent_service)
    register_error_handlers(app)
    register_socketio_events(socketio)
    
    # Store instances
    app.config_instance = config
    app.socketio = socketio
    app.log_service = log_service
    app.agent_service = agent_service
    app.group_service = group_service
    app.api_key_service = api_key_service
    app.user_service = user_service  # RBAC: Store user service
    
    #  Mark as initialized
    _app_initialized = True
    
    app.logger.info(" MVC Application initialized successfully")
    return app, socketio

def initialize_database_indexes(app, db):
    """Initialize database indexes safely with proper parameters"""
    try:
        app.logger.info(" Initializing database indexes...")
        
        # Initialize all model indexes with proper db parameter
        from models.whitelist_model import WhitelistModel
        from models.log_model import LogModel
        from models.agent_model import AgentModel
        
        #  FIX: Pass db parameter properly
        whitelist_model = WhitelistModel(db)
        log_model = LogModel(db) 
        agent_model = AgentModel(db)
        group_model = GroupModel(db)

        app.logger.info(" Database indexes initialized successfully")
        
    except Exception as e:
        #  FIX: Use app.logger properly
        app.logger.warning(f"Index initialization had issues: {e}")
        # Continue anyway - not critical for startup
        import traceback
        app.logger.debug(f"Index initialization traceback: {traceback.format_exc()}")

def register_controllers(app, socketio, db):
    """Register all controllers with proper parameters"""
    try:
        logger.info(" Initializing MVC components...")
        
        #  FIX: Initialize models with db parameter
        whitelist_model = WhitelistModel(db)
        agent_model = AgentModel(db)
        log_model = LogModel(db)
        group_model = GroupModel(db)
        api_key_model = APIKeyModel(db)  # NEW: API Key model
        agent_policy_model = AgentPolicyModel(db)

        logger.info(" Models initialized")

        # Initialize JWT service first (needed by agent_service)
        jwt_service = init_jwt_service(db)
        logger.info(" JWT service initialized")

        #  Initialize services
        user_model = UserModel(db)
        whitelist_profile_model = WhitelistProfileModel(db)
        group_service = GroupService(group_model, agent_model, user_model)
        agent_policy_service = AgentPolicyService(agent_policy_model, agent_model, socketio)
        whitelist_profile_service = WhitelistProfileService(whitelist_profile_model, group_model, socketio)
        whitelist_service = WhitelistService(whitelist_model, agent_model, group_model, socketio,
                                             policy_service=agent_policy_service,
                                             profile_service=whitelist_profile_service)
        agent_service = AgentService(agent_model, group_model, socketio, jwt_service)  # Pass JWT service
        log_service = LogService(log_model, agent_model=agent_model, socketio=socketio)
        api_key_service = APIKeyService(api_key_model, socketio)  # API Key service

        # RBAC: Initialize models
        session_model = SessionModel(db)
        audit_model = AuditModel(db)

        # RBAC: Initialize services
        audit_service = AuditService(audit_model)
        rbac_service = RBACService(group_model, agent_model)
        admin_auth_service = AdminAuthService(
            user_model, jwt_service, session_model, audit_service, socketio
        )
        user_service = UserService(user_model, audit_service, socketio)

        logger.info(" Services initialized (including RBAC)")

        # Initialize auth middleware with both API Key and JWT services
        init_auth_middleware(api_key_service, jwt_service)

        # Initialize RBAC middleware
        init_rbac_middleware(admin_auth_service, rbac_service, jwt_service, user_model)
        logger.info(" Auth + RBAC middleware initialized")

        # RBAC: Seed default admin on startup
        user_service.ensure_default_admin()
        logger.info(" RBAC defaults seeded")
        
        # Create default API key if none exist
        default_key = api_key_service.create_default_key_if_none()
        if default_key:
            logger.warning("=" * 60)
            logger.warning("SAVE THIS API KEY - IT WON'T BE SHOWN AGAIN!")
            logger.warning(f"API Key: {default_key.get('api_key')}")
            logger.warning("=" * 60)
        
        #  Initialize controllers (with rbac_service for teacher data filtering)
        whitelist_controller = WhitelistController(whitelist_model, whitelist_service, rbac_service, socketio)
        agent_controller = AgentController(agent_model, agent_service, rbac_service, socketio, policy_service=agent_policy_service)
        log_controller = LogController(log_model, log_service, rbac_service, socketio)
        group_controller = GroupController(group_service, rbac_service)
        api_key_controller = APIKeyController(api_key_model, api_key_service, socketio)
        auth_controller = AuthController(jwt_service, agent_model, socketio)

        # Whitelist profile controller
        whitelist_profile_controller = WhitelistProfileController(whitelist_profile_service, rbac_service)

        # RBAC controllers
        admin_auth_controller = AdminAuthController(admin_auth_service, jwt_service, socketio)
        user_controller = UserController(user_service, socketio)
        audit_controller = AuditController(audit_service, socketio)

        logger.info(" Controllers initialized (including RBAC)")

        # Cleanup legacy Default Profiles (replaced by group.whitelist)
        try:
            deleted = whitelist_profile_model.collection.delete_many({"is_default": True})
            if deleted.deleted_count:
                logger.info(f" Cleaned up {deleted.deleted_count} legacy Default Profile(s)")
        except Exception as e:
            logger.warning(f" Default Profile cleanup warning: {e}")

        #  Register blueprints with proper URL prefixes
        app.register_blueprint(whitelist_controller.blueprint, url_prefix='/api')
        app.register_blueprint(agent_controller.blueprint, url_prefix='/api')
        app.register_blueprint(log_controller.blueprint, url_prefix='/api')
        app.register_blueprint(group_controller.blueprint, url_prefix='/api')
        app.register_blueprint(api_key_controller.blueprint, url_prefix='/api')
        app.register_blueprint(auth_controller.blueprint, url_prefix='/api')

        # Whitelist profile blueprint
        app.register_blueprint(whitelist_profile_controller.blueprint, url_prefix='/api')

        # RBAC blueprints
        app.register_blueprint(admin_auth_controller.blueprint, url_prefix='/api')
        app.register_blueprint(user_controller.blueprint, url_prefix='/api')
        app.register_blueprint(audit_controller.blueprint, url_prefix='/api')

        logger.info(" All controllers registered successfully")
        
        #  Debug: Log registered routes
        logger.info(" Registered API routes:")
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith('/api/'):
                methods = ', '.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
                logger.info(f"  {methods:15} {rule.rule}")
        
        #  FIX: Return services for use in main routes
        return log_service, agent_service, group_service, api_key_service, user_service
        
    except Exception as e:
        logger.error(f" Error registering controllers: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None, None
def register_main_routes(app, log_service, agent_service):
    """Register main web routes - vietnam ONLY"""
    
    @app.route('/')
    def index():
        """Dashboard route with statistics - vietnam ONLY"""
        try:
            # Get dashboard statistics
            stats = {
                'total_logs': 0,
                'allowed_count': 0,
                'blocked_count': 0,
                'active_agents': 0
            }
            
            # Stats are loaded via JS (/api/logs/stats + /api/agents/statistics)
            # which applies RBAC filtering for teacher accounts.
            # Server-side template always renders 0 to avoid leaking global stats
            # before JS updates with the correct filtered values.
            recent_logs = []
            
            return render_template('dashboard.html', 
                                 page_title="Dashboard", 
                                 stats=stats,
                                 recent_logs=recent_logs)
                                 
        except Exception as e:
            app.logger.error(f"Dashboard error: {e}")
            return render_template('dashboard.html', 
                                 page_title="Dashboard", 
                                 stats={'total_logs': 0, 'allowed_count': 0, 'blocked_count': 0, 'active_agents': 0},
                                 recent_logs=[])
    
    @app.route('/agents')
    def agents_page():
        return render_template('agents.html', page_title="Agent Management")
    
    # ADD: Groups page route
    @app.route('/groups')
    def groups_page():
        """Groups management page"""
        return render_template('groups.html', page_title="Group Management")
    
    # ADD: Group detail page route
    @app.route('/groups/<group_id>')
    def group_detail(group_id):
        """Group detail page - view agents in group, add/remove agents"""
        try:
            group_service = app.group_service
            group = group_service.get_group(group_id)
            
            if not group:
                return render_template('404.html', message="Group not found"), 404
                
            return render_template('group_detail.html', group=group, page_title=f"Group: {group.get('name', 'Unknown')}")
            
        except ValueError as e:
            app.logger.warning(f"Group not found: {group_id} - {e}")
            return render_template('404.html', message="Group not found"), 404
        except Exception as e:
            app.logger.error(f"Error loading group {group_id}: {e}")
            return render_template('500.html', message=str(e)), 500
    
    @app.route('/whitelist')
    def whitelist_page():
        return render_template('whitelist.html', page_title="Whitelist Management")
    
    @app.route('/logs')
    def logs_page():
        return render_template('logs.html', page_title="System Logs")
    
    @app.route('/api-keys')
    def api_keys_page():
        """API Keys management page - Admin only"""
        return render_template('api_keys.html', page_title="API Keys Management")

    # ========================================================================
    # RBAC: Login & Admin page routes
    # ========================================================================

    @app.route('/login')
    def login_page():
        """Login page for Admin/Teacher"""
        return render_template('login.html')

    @app.route('/admin/users')
    def admin_users_page():
        """User management page - Admin only (auth checked by JS + API)"""
        return render_template('admin_users.html', page_title="User Management")

    @app.route('/admin/audit')
    def admin_audit_page():
        """Audit logs page - Admin only"""
        return render_template('admin_audit.html', page_title="Audit Logs")

    @app.route('/profile')
    def profile_page():
        """User profile edit page"""
        return render_template('profile.html', page_title="My Profile")

    @app.route('/admin/change-password')
    def change_password_page():
        """Redirect to profile page (password change is now integrated)"""
        return redirect(url_for('profile_page'))

    # ========================================================================

    @app.route('/api/health')
    def health_check():
        """Health check endpoint - vietnam ONLY"""
        return jsonify({
            "status": "healthy",
            "version": "1.0.0",
            "architecture": "MVC",
            "timestamp": now_iso()  # vietnam ISO
        }), 200
    
    @app.route('/api/config')
    def get_client_config():
        """Client configuration endpoint - vietnam ONLY"""
        return jsonify({
            "socketio_enabled": True,
            "version": "1.0.0",
            "architecture": "MVC",
            "environment": os.environ.get('FLASK_ENV', 'production'),
            "timezone": "vietnam",
            "server_time": now_iso()  # vietnam ISO
        }), 200

def register_error_handlers(app):
    """Register error handlers - vietnam ONLY"""
    
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({
                "error": "Not found",
                "timestamp": now_iso()  # vietnam ISO
            }), 404
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f"Server error: {str(e)}")
        if request.path.startswith('/api/'):
            return jsonify({
                "error": "Internal server error",
                "timestamp": now_iso()  # vietnam ISO
            }), 500
        return render_template('500.html'), 500

def register_socketio_events(socketio):
    """Register Socket.IO events - vietnam ONLY"""
    
    @socketio.on('connect')
    def handle_connect():
        logger.info(f"Client connected: {request.sid} at {now_iso()}")
        # Send welcome message with vietnam timestamp
        socketio.emit('server_message', {
            'type': 'welcome',
            'message': 'Connected to Firewall Controller',
            'timestamp': now_iso()  # vietnam ISO
        }, room=request.sid)
    
    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info(f"Client disconnected: {request.sid} at {now_iso()}")
    
    @socketio.on('ping')
    def handle_ping(data):
        """Handle ping from client - vietnam ONLY"""
        logger.debug(f"Ping received from {request.sid}")
        socketio.emit('pong', {
            'timestamp': now_iso(),  # vietnam ISO
            'client_data': data
        }, room=request.sid)

if __name__ == "__main__":
    try:
        # Create MVC application
        app, socketio = create_app()
        
        # Get configuration
        config = app.config_instance
        
        logger.info(f" Starting MVC Firewall Controller")
        logger.info(f" Server: {config.HOST}:{config.PORT}")
        logger.info(f" Architecture: Model-View-Controller")
        logger.info(f" Database: {config.MONGO_DBNAME}")
        logger.info(f" Timezone: vietnam (Clean & Simple)")
        
        #  FIX: Disable reloader to avoid double initialization
        socketio.run(
            app, 
            host=config.HOST, 
            port=config.PORT, 
            debug=config.DEBUG,
            use_reloader=False  #  CHANGE: Disable reloader
        )
        
    except KeyboardInterrupt:
        logger.info(" Server stopped by user")
        close_mongo_client()
    except Exception as e:
        logger.error(f" Server error: {str(e)}")
        import traceback
        traceback.print_exc()
        close_mongo_client()
        raise