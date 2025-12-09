import logging
import sys

from shared.time_utils import sleep

logger = logging.getLogger("services.windows")


def run_as_service(main_func, cleanup_func):
    try:
        import servicemanager
        import win32event
        import win32service
        import win32serviceutil
        
        class AgentService(win32serviceutil.ServiceFramework):
            _svc_name_ = "FirewallControllerAgent"
            _svc_display_name_ = "Firewall Controller Agent"
            _svc_description_ = "Network traffic monitoring and domain whitelist enforcement"
            
            def __init__(self, args):
                win32serviceutil.ServiceFramework.__init__(self, args)
                self.stop_event = win32event.CreateEvent(None, 0, 0, None)
                self.running = True
            
            def SvcStop(self):
                """Stop the service."""
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                win32event.SetEvent(self.stop_event)
                self.running = False
                
                # Cleanup components
                try:
                    cleanup_func()
                except Exception as e:
                    servicemanager.LogErrorMsg(f"Error during service cleanup: {e}")
            
            def SvcDoRun(self):
                """Main service execution."""
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, '')
                )
                
                try:
                    main_func()
                except Exception as e:
                    servicemanager.LogErrorMsg(f"Service error: {e}")
                    self.SvcStop()
                
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STOPPED,
                    (self._svc_name_, '')
                )
        
        # Command line handling
        if len(sys.argv) == 1:
            # No arguments - run as service
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(AgentService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            _handle_service_command(AgentService, win32service, win32serviceutil)
            
    except ImportError as e:
        logger.error("Windows service modules not available. Install pywin32:")
        logger.error("pip install pywin32")
        logger.error("python Scripts/pywin32_postinstall.py -install")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Service error: {e}")
        sys.exit(1)


def _handle_service_command(AgentService, win32service, win32serviceutil):
    """Handle service command line arguments."""
    command = sys.argv[1]
    
    if command == 'install':
        win32serviceutil.InstallService(
            pythonClassString=f"{__name__}.AgentService",
            serviceName=AgentService._svc_name_,
            displayName=AgentService._svc_display_name_,
            description=AgentService._svc_description_,
            startType=win32service.SERVICE_AUTO_START
        )
        print(f"Service '{AgentService._svc_display_name_}' installed successfully")
        
    elif command == 'remove':
        win32serviceutil.RemoveService(AgentService._svc_name_)
        print(f"Service '{AgentService._svc_display_name_}' removed successfully")
        
    elif command == 'start':
        win32serviceutil.StartService(AgentService._svc_name_)
        print(f"Service '{AgentService._svc_display_name_}' started")
        
    elif command == 'stop':
        win32serviceutil.StopService(AgentService._svc_name_)
        print(f"Service '{AgentService._svc_display_name_}' stopped")
        
    elif command == 'restart':
        try:
            win32serviceutil.StopService(AgentService._svc_name_)
            sleep(2)
            win32serviceutil.StartService(AgentService._svc_name_)
            print(f"Service '{AgentService._svc_display_name_}' restarted")
        except Exception as e:
            print(f"Error restarting service: {e}")
            
    elif command == 'status':
        try:
            status = win32serviceutil.QueryServiceStatus(AgentService._svc_name_)
            status_map = {
                win32service.SERVICE_STOPPED: "STOPPED",
                win32service.SERVICE_START_PENDING: "START_PENDING",
                win32service.SERVICE_STOP_PENDING: "STOP_PENDING",
                win32service.SERVICE_RUNNING: "RUNNING",
                win32service.SERVICE_CONTINUE_PENDING: "CONTINUE_PENDING",
                win32service.SERVICE_PAUSE_PENDING: "PAUSE_PENDING",
                win32service.SERVICE_PAUSED: "PAUSED"
            }
            print(f"Service Status: {status_map.get(status[1], 'UNKNOWN')}")
        except Exception as e:
            print(f"Error checking service status: {e}")
    else:
        win32serviceutil.HandleCommandLine(AgentService)