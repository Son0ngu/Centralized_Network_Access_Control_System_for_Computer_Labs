"""
Firewall Controller Agent - Entry Point (Refactored)

Simplified entry point with modular architecture.
UTC ONLY - No timezone confusion.
"""

import logging
import signal
import sys

# Setup logging first
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("agent_main")

# Import modules - use new paths
from config import get_config
from shared.time_utils import now, now_iso, uptime_string, sleep, debug_time_info

# Import from new modular structure
from core import (
    agent_state,
    AGENT_HOSTNAME,
    AGENT_DEVICE_ID,
    get_agent,
    initialize_components,
    cleanup,
    build_lifecycle_log
)
from utils import (
    get_local_ip,
    check_admin_privileges,
    validate_configuration
)


# ========================================
# SIGNAL HANDLERS
# ========================================

def signal_handler(sig, frame):
    """Handle shutdown signals."""
    agent = get_agent()
    logger.info(f"Received signal {sig}, shutting down...")
    agent.stop()


# ========================================
# MAIN FUNCTION
# ========================================

def main():
    """
    Main function with UTC timestamps only.
    """
    agent = get_agent()
    
    try:
        logger.info("Starting Secure Firewall Controller Agent...")
        
        # Debug time info in debug mode
        if logger.isEnabledFor(logging.DEBUG):
            debug_info = debug_time_info()
            logger.debug(f"Time info: {debug_info}")
        
        # Load and validate configuration
        logger.info("Loading configuration...")
        config = get_config()
        
        # Ensure device ID is available
        config["device_id"] = AGENT_DEVICE_ID
        
        if not validate_configuration(config):
            logger.error("Configuration validation failed")
            sys.exit(1)
        
        logger.info("Configuration loaded and validated")
        
        # Auto-adjust firewall configuration based on admin privileges
        admin_status = check_admin_privileges()
        firewall_config = config.get("firewall", {})
        current_mode = firewall_config.get("mode", "monitor")
        
        if admin_status:
            # Has admin privileges - enable firewall enforcement
            if current_mode == "monitor":
                logger.info("Admin privileges detected - switching to 'whitelist_only' mode")
                config["firewall"]["enabled"] = True
                config["firewall"]["mode"] = "whitelist_only"
            else:
                # Already in enforce mode, just ensure enabled
                config["firewall"]["enabled"] = True
                logger.info(f"Admin privileges confirmed - firewall mode: {current_mode}")
        else:
            # No admin privileges - force monitor mode
            if current_mode in ["block", "whitelist_only", "enforce"]:
                logger.warning(f"No admin privileges - switching from '{current_mode}' to 'monitor' mode")
                config["firewall"]["enabled"] = False
                config["firewall"]["mode"] = "monitor"
        
        # Apply startup delay if configured
        startup_delay = config["general"]["startup_delay"]
        if startup_delay > 0:
            logger.info(f"Applying startup delay: {startup_delay} seconds...")
            sleep(startup_delay)
        
        # Initialize all components
        if not initialize_components(config):
            logger.error("Component initialization failed - cannot start agent")
            sys.exit(1)
        
        # Send startup notification
        if agent.log_sender and config.get('agent_id'):
            startup_log = build_lifecycle_log(
                config,
                event_type="agent_startup",
                action="STARTUP",
                message="Agent startup"
            )
            agent.log_sender.queue_log(startup_log)
        
        # Mark startup as completed
        agent_state['startup_completed'] = True
        logger.info(f"Agent startup completed successfully (startup time: {uptime_string()})")
        
        # Main loop with UTC timestamps
        loop_count = 0
        last_status_log = now()
        
        while agent.running:
            sleep(1)
            loop_count += 1
            
            # Log status every 5 minutes
            if now() - last_status_log >= 300:
                logger.info(f"Agent running - Loop: {loop_count}, Uptime: {uptime_string()}")
                last_status_log = now()
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unhandled error in main: {e}", exc_info=True)
    finally:
        cleanup(config if 'config' in dir() else None)


# ========================================
# ENTRY POINT
# ========================================

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check if running as service
    if len(sys.argv) > 1 and sys.argv[1] in ['--service', 'install', 'remove', 'start', 'stop', 'restart', 'status']:
        from services.windows_service import run_as_service
        run_as_service(main, cleanup)
    else:
        main()