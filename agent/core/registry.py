import logging
import platform
import socket
from typing import Dict

import requests

from shared.time_utils import now, now_iso
from shared.os_info import get_os_details

from .agent import agent_state, AGENT_DEVICE_ID
from utils.ip_detector import get_local_ip, check_admin_privileges
from utils.error_handler import CriticalErrorHandler

logger = logging.getLogger("core.registry")

@CriticalErrorHandler.critical_operation("Agent Registration")
def register_agent(config: Dict) -> bool:
    try:
        # Collect agent information
        local_ip = get_local_ip()
        admin_status = check_admin_privileges()
        os_details = get_os_details()
        
        agent_info = {
            "hostname": socket.gethostname(),
            "device_id": AGENT_DEVICE_ID,
            "ip_address": local_ip,
            "platform": os_details["platform"],
            "os_info": f"{os_details['name']} {os_details['version']}",
            "agent_version": "1.0.0",
            "python_version": platform.python_version(),
            "admin_privileges": admin_status,
            "capabilities": {
                "packet_capture": True,
                "firewall_management": False,
                "whitelist_sync": True
            },
            "registration_time": now_iso(),
            "registration_timestamp": now()
        }
        
        server_urls = config['server'].get('urls', [config['server']['url']])
        
        for server_url in server_urls:
            if try_register_with_server(server_url, agent_info, config):
                return True
        
        logger.error("Failed to register with any server")
        return False
        
    except Exception as e:
        logger.error(f"Error in agent registration: {e}")
        return False


def try_register_with_server(server_url: str, agent_info: Dict, config: Dict) -> bool:
    try:
        register_url = f"{server_url.rstrip('/')}/api/agents/register"
        logger.info(f"Attempting registration with: {register_url}")
        
        # Build headers with API key for authentication
        headers = {'Content-Type': 'application/json'}
        
        # Add API key if configured (required for secure registration)
        api_key = config.get('auth', {}).get('api_key', '')
        if api_key:
            headers['X-API-Key'] = api_key
            logger.debug("API key included in registration request")
        else:
            logger.warning("No API key configured - registration may fail if server requires authentication")
        
        response = requests.post(
            register_url,
            json=agent_info,
            timeout=config['server'].get('connect_timeout', 15),
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                agent_data = data.get('data', {})
                
                # Save credentials globally
                config['agent_id'] = agent_data.get('agent_id')
                config['agent_token'] = agent_data.get('token')  # Legacy token
                config['user_id'] = agent_data.get('user_id')
                config['server_url'] = server_url
                
                # NEW: Save JWT tokens if provided (Phase 2)
                jwt_data = agent_data.get('jwt', {})
                if jwt_data:
                    config['jwt'] = {
                        'access_token': jwt_data.get('access_token'),
                        'refresh_token': jwt_data.get('refresh_token'),
                        'token_type': jwt_data.get('token_type', 'Bearer'),
                        'access_expires_at': jwt_data.get('access_expires_at'),
                        'refresh_expires_at': jwt_data.get('refresh_expires_at'),
                    }
                    logger.info("JWT tokens received and stored")
                else:
                    logger.warning("No JWT tokens in registration response - using legacy auth")
                
                # Update agent state
                agent_state['agent_id'] = config['agent_id']
                agent_state['registration_completed'] = True
                
                logger.info(f"Registration successful - Agent ID: {config['agent_id']}")
                return True
            else:
                logger.warning(f"Registration rejected: {data.get('error')}")
                return False
        else:
            logger.warning(f"Registration failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection failed to {server_url}")
        return False
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout connecting to {server_url}")
        return False
    except Exception as e:
        logger.error(f"Error registering with {server_url}: {e}")
        return False