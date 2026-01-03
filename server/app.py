"""
Main Flask application with MVC architecture
- Clean and simple
"""

#  QUAN TRỌNG: Monkey patch PHẢI ở đầu tiên, trước tất cả imports khác
import eventlet

eventlet.monkey_patch()

import os
import sys
import logging

#  Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request, redirect, session, url_for
from flask_socketio import SocketIO
from flask_cors import CORS
from functools import wraps

#  Import từ config.py (không phải database/config.py)
from database.config import get_config, get_mongo_client, get_database, validate_config, close_mongo_client

# Import time utilities - vietnam ONLY
from time_utils import now_iso, format_datetime, parse_agent_timestamp

#  Import MVC components với absolute imports
from models.whitelist_model import WhitelistModel
from models.agent_model import AgentModel
from models.log_model import LogModel
from models.group_model import GroupModel

from services.whitelist_service import WhitelistService
from services.agent_service import AgentService
from services.log_service import LogService
from services.group_service import GroupService

from controllers.whitelist_controller import WhitelistController
from controllers.agent_controller import AgentController
from controllers.log_controller import LogController
from controllers.group_controller import GroupController
from controllers.api_key_controller import APIKeyController
from controllers.auth_controller import AuthController
from controllers.admin_controller import AdminController

# API Key components
from models.api_key_model import APIKeyModel
from services.api_key_service import APIKeyService

# JWT components
from services.jwt_service import JWTService, init_jwt_service

# Auth middleware
from middleware.auth import init_auth_middleware, require_api_key, require_jwt

# Admin & Tenant components
from models.admin_model import AdminModel
from models.tenant_model import TenantModel
from services.admin_service import AdminService

# Super Admin components
from models.broadcast_model import BroadcastModel
from models.impersonation_log_model import ImpersonationLogModel
from services.super_admin_service import SuperAdminService
from controllers.super_admin_controller import SuperAdminController

# Broadcast components
from services.broadcast_service import BroadcastService
from controllers.broadcast_controller import BroadcastController

# Authorization middleware
from middleware.authorization import init_authorization_middleware

# Impersonation middleware and scheduler
from middleware.impersonation import init_impersonation_middleware
from services.impersonation_scheduler import init_impersonation_scheduler

# Security middleware
from middleware.security import init_security_middleware

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add global flag để prevent multiple initialization
_app_initialized = False

def create_app():
    """Create Flask application with MVC architecture - Singleton pattern"""
    global _app_initialized
    
    #  FIX: Prevent multiple initialization
    if _app_initialized:
        logger.info(" App already initialized, skipping...")
        # Return minimal app for reloader
        app = Flask(__name__, 
                    static_folder='views/static',
                    template_folder='views/templates')
        config = get_config()
        app.config.from_object(config)
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
        return app, socketio
    
    logger.info(" Creating new Flask application...")
    
    # Create Flask app
    app = Flask(__name__, 
                static_folder='views/static',
                template_folder='views/templates')
    
    # Load configuration
    config = get_config()
    app.config.from_object(config)
    
    # Set secret key for session (use from config or generate)
    if not app.config.get('SECRET_KEY'):
        import secrets
        app.config['SECRET_KEY'] = secrets.token_hex(32)
        logger.warning("⚠️ SECRET_KEY not set, using random key. Sessions will be lost on restart!")
    
    #  Add template filters using time_utils - vietnam ONLY
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
        async_mode='eventlet',
        logger=False,
        engineio_logger=False
    )
    
    #  FIX: Initialize database BEFORE using it
    try:
        db = get_database(config)
        app.logger.info(f" MongoDB connected: {config.MONGO_DBNAME}")
        
        #  FIX: Initialize indexes safely with proper parameters
        initialize_database_indexes(app, db)
        
    except Exception as e:
        app.logger.error(f" MongoDB connection failed: {e}")
        raise RuntimeError("Database connection failed")
    
    #  FIX: Initialize MVC components and get services
    try:
        log_service, agent_service, group_service, api_key_service = register_controllers(app, socketio, db)

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
    app.api_key_service = api_key_service  # NEW: Store API key service
    
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
    """Register all controllers với proper parameters"""
    try:
        logger.info(" Initializing MVC components...")
        
        #  FIX: Initialize models với db parameter
        whitelist_model = WhitelistModel(db)
        agent_model = AgentModel(db)
        log_model = LogModel(db)
        group_model = GroupModel(db)
        api_key_model = APIKeyModel(db)  # NEW: API Key model
        admin_model = AdminModel(db)  # NEW: Admin model
        tenant_model = TenantModel(db)  # NEW: Tenant model
        broadcast_model = BroadcastModel(db)  # NEW: Broadcast model
        impersonation_log_model = ImpersonationLogModel(db)  # NEW: Impersonation log model

        logger.info(" Models initialized")
        
        # Initialize JWT service first (needed by agent_service)
        jwt_service = init_jwt_service(db)
        logger.info(" JWT service initialized")
        
        # Initialize email service for 2FA and notifications
        from services.email_service import init_email_service
        smtp_config = {
            "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "port": int(os.getenv("SMTP_PORT", 587)),
            "username": os.getenv("SMTP_USERNAME", ""),
            "password": os.getenv("SMTP_PASSWORD", ""),
            "from_email": os.getenv("SMTP_FROM_EMAIL", "noreply@yourapp.com"),
            "from_name": os.getenv("SMTP_FROM_NAME", "Firewall Controller")
        }
        init_email_service(smtp_config)
        logger.info(" Email service initialized")
        
        #  Initialize services
        group_service = GroupService(group_model, agent_model)
        whitelist_service = WhitelistService(whitelist_model, agent_model, group_model, socketio)
        agent_service = AgentService(agent_model, group_model, socketio, jwt_service)  # Pass JWT service
        log_service = LogService(log_model, agent_model=agent_model, socketio=socketio)
        api_key_service = APIKeyService(api_key_model, socketio)  # API Key service
        admin_service = AdminService(admin_model, tenant_model, jwt_service, socketio)  # NEW: Admin service
        super_admin_service = SuperAdminService(
            tenant_model, admin_model, agent_model, log_model,
            broadcast_model, impersonation_log_model, jwt_service
        )  # NEW: Super Admin service
        
        # Broadcast service
        broadcast_service = BroadcastService(broadcast_model, admin_model, tenant_model)
        
        logger.info(" Services initialized")
        
        # Initialize auth middleware with both API Key and JWT services
        init_auth_middleware(api_key_service, jwt_service)
        logger.info(" Auth middleware initialized")
        
        # Initialize authorization middleware for role-based access
        init_authorization_middleware(admin_model)
        logger.info(" Authorization middleware initialized")
        
        # Initialize impersonation middleware and scheduler
        init_impersonation_middleware(impersonation_log_model, admin_model)
        init_impersonation_scheduler(impersonation_log_model, interval_seconds=60)
        logger.info(" Impersonation middleware and scheduler initialized")
        
        # Initialize security middleware (sanitization, rate limiting)
        init_security_middleware(app)
        logger.info(" Security middleware initialized")
        
        # Create default API key if none exist
        default_key = api_key_service.create_default_key_if_none()
        if default_key:
            logger.warning("=" * 60)
            logger.warning("SAVE THIS API KEY - IT WON'T BE SHOWN AGAIN!")
            logger.warning(f"API Key: {default_key.get('api_key')}")
            logger.warning("=" * 60)
        
        #  Initialize controllers
        whitelist_controller = WhitelistController(whitelist_model, whitelist_service, socketio)
        agent_controller = AgentController(agent_model, agent_service, socketio)
        log_controller = LogController(log_model, log_service, socketio)
        group_controller = GroupController(group_service)
        api_key_controller = APIKeyController(api_key_model, api_key_service, socketio)
        auth_controller = AuthController(jwt_service, agent_model, socketio)  # NEW: Auth controller
        admin_controller = AdminController(admin_model, tenant_model, admin_service, socketio)  # NEW: Admin controller
        super_admin_controller = SuperAdminController(super_admin_service)  # NEW: Super Admin controller
        broadcast_controller = BroadcastController(broadcast_service, socketio)  # Broadcast controller

        logger.info(" Controllers initialized")
        
        #  Register blueprints with proper URL prefixes
        app.register_blueprint(whitelist_controller.blueprint, url_prefix='/api')
        app.register_blueprint(agent_controller.blueprint, url_prefix='/api')
        app.register_blueprint(log_controller.blueprint, url_prefix='/api')
        app.register_blueprint(group_controller.blueprint, url_prefix='/api')
        app.register_blueprint(api_key_controller.blueprint, url_prefix='/api')
        app.register_blueprint(auth_controller.blueprint, url_prefix='/api')  # NEW: Auth routes
        app.register_blueprint(admin_controller.blueprint, url_prefix='/api/admin')  # FIX: Admin routes at /api/admin/*
        app.register_blueprint(super_admin_controller.blueprint)  # Super Admin API routes (/api/super/*)
        app.register_blueprint(super_admin_controller.view_blueprint)  # Super Admin view routes (/super-admin/*)
        app.register_blueprint(broadcast_controller.blueprint, url_prefix='/api/broadcasts')  # Broadcast routes

        logger.info(" All controllers registered successfully")
        
        #  Debug: Log registered routes
        logger.info(" Registered API routes:")
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith('/api/'):
                methods = ', '.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
                logger.info(f"  {methods:15} {rule.rule}")
        
        #  FIX: Return services để dùng trong main routes
        return log_service, agent_service, group_service, api_key_service
        
    except Exception as e:
        logger.error(f" Error registering controllers: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None
def login_required(f):
    """Decorator to require login for web routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in (has admin_id in session)
        if 'admin_id' not in session:
            # Redirect to admin login page
            return redirect(url_for('admin_page') + '?redirect=' + request.path)
        return f(*args, **kwargs)
    return decorated_function


def register_main_routes(app, log_service, agent_service):
    """Register main web routes - vietnam ONLY"""

    def _collect_dashboard_stats(tenant_id=None):
        """Collect dashboard statistics from services, filtered by tenant_id if provided."""
        stats = {
            'total_logs': 0,
            'allowed_count': 0,
            'blocked_count': 0,
            'active_agents': 0
        }
        recent_logs = []

        try:
            # Pass tenant_id to filter logs by tenant
            filters = {'tenant_id': tenant_id} if tenant_id else {}
            log_stats = log_service.get_comprehensive_statistics(filters)
            stats['total_logs'] = log_stats.get('total', 0)
            stats['allowed_count'] = log_stats.get('allowed', 0)
            stats['blocked_count'] = log_stats.get('blocked', 0)
            recent_logs = log_service.get_recent_logs(limit=10, tenant_id=tenant_id)
        except Exception as e:
            app.logger.warning(f"Could not fetch log stats: {e}")

        try:
            # Pass tenant_id to filter agents by tenant
            agent_stats = agent_service.calculate_statistics(tenant_id=tenant_id)
            stats['active_agents'] = agent_stats.get('active', 0)
            stats['agent_stats'] = agent_stats
        except Exception as e:
            app.logger.warning(f"Could not fetch agent stats: {e}")
            stats['agent_stats'] = {}

        return stats, recent_logs
    
    @app.route('/')
    @app.route('/dashboard')
    @login_required
    def index():
        """Dashboard route with statistics - vietnam ONLY"""
        try:
            # Get tenant_id from session for data isolation
            # Super admin (no tenant_id) sees all data, tenant admin sees only their data
            tenant_id = session.get('tenant_id')
            role = session.get('role')
            
            # Super admin sees all data (tenant_id=None), tenant admin sees only their tenant's data
            filter_tenant_id = None if role == 'super_admin' else tenant_id
            
            stats, recent_logs = _collect_dashboard_stats(tenant_id=filter_tenant_id)
            
            return render_template('dashboard.html', 
                                 page_title="Dashboard", 
                                 stats=stats,
                                 recent_logs=recent_logs,
                                 current_role=role,
                                 current_tenant_id=tenant_id)
                                 
        except Exception as e:
            app.logger.error(f"Dashboard error: {e}")
            return render_template('dashboard.html', 
                                 page_title="Dashboard", 
                                 stats={'total_logs': 0, 'allowed_count': 0, 'blocked_count': 0, 'active_agents': 0},
                                 recent_logs=[])
    
    @app.route('/api/dashboard/stats')
    @login_required
    def dashboard_stats_api():
        """API endpoint to provide real dashboard statistics"""
        try:
            # Get tenant_id from session for data isolation
            tenant_id = session.get('tenant_id')
            role = session.get('role')
            
            # Super admin sees all data, tenant admin sees only their tenant's data
            filter_tenant_id = None if role == 'super_admin' else tenant_id
            
            stats, recent_logs = _collect_dashboard_stats(tenant_id=filter_tenant_id)
            return jsonify({
                "success": True,
                "data": {
                    "logs": {
                        "total": stats.get("total_logs", 0),
                        "allowed": stats.get("allowed_count", 0),
                        "blocked": stats.get("blocked_count", 0),
                    },
                    "agents": stats.get("agent_stats", {}),
                    "active_agents": stats.get("active_agents", 0),
                    "recent_logs": recent_logs
                },
                "timestamp": now_iso()
            })
        except Exception as e:
            app.logger.error(f"Dashboard stats API error: {e}")
            return jsonify({
                "success": False,
                "error": "Failed to load dashboard stats",
                "timestamp": now_iso()
            }), 500
    
    @app.route('/agents')
    @login_required
    def agents_page():
        return render_template('agents.html', page_title="Agent Management")
    
    # ADD: Groups page route
    @app.route('/groups')
    @login_required
    def groups_page():
        """Groups management page"""
        return render_template('groups.html', page_title="Group Management")
    
    @app.route('/admin')
    def admin_page():
        """Admin management page (login page)"""
        return render_template('admin.html', page_title="Admin Management")
    
    # ADD: Group detail page route
    @app.route('/groups/<group_id>')
    @login_required
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
    @login_required
    def whitelist_page():
        return render_template('whitelist.html', page_title="Whitelist Management")
    
    @app.route('/logs')
    @login_required
    def logs_page():
        return render_template('logs.html', page_title="System Logs")
    
    @app.route('/api-keys')
    @login_required
    def api_keys_page():
        """API Keys management page - Admin only"""
        return render_template('api_keys.html', page_title="API Keys Management")
    
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
    
    # Admin namespace for broadcasts and real-time updates
    @socketio.on('connect', namespace='/admin')
    def handle_admin_connect():
        """Handle admin WebSocket connection"""
        logger.info(f"Admin connected: {request.sid} at {now_iso()}")
        socketio.emit('admin_connected', {
            'message': 'Connected to admin namespace',
            'timestamp': now_iso()
        }, room=request.sid, namespace='/admin')
    
    @socketio.on('join_tenant', namespace='/admin')
    def handle_join_tenant(data):
        """Join tenant-specific room for targeted broadcasts"""
        from flask_socketio import join_room
        tenant_id = data.get('tenant_id')
        if tenant_id:
            room = f"tenant_{tenant_id}"
            join_room(room)
            logger.info(f"Admin {request.sid} joined room {room}")
    
    @socketio.on('disconnect', namespace='/admin')
    def handle_admin_disconnect():
        logger.info(f"Admin disconnected: {request.sid} at {now_iso()}")

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
        
        #  FIX: Disable reloader để tránh double initialization
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