import atexit
import ctypes
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("capture.winpcap_installer")

WINPCAP_DOWNLOAD_URL = "https://www.winpcap.org/install/bin/WinPcap_4_1_3.exe"
WINPCAP_INSTALLER_NAME = "WinPcap_4_1_3.exe"

WINPCAP_MIRROR_URLS = [
    "https://www.winpcap.org/install/bin/WinPcap_4_1_3.exe",
]

# Installation tracking
_winpcap_installed_by_us = False
_installer_path: Optional[str] = None
_install_lock = threading.Lock()


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def is_winpcap_installed() -> bool:
    if os.name != "nt":
        return True  # Not Windows, assume OK
    # Check for wpcap.dll in common locations
    search_paths = [
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wpcap.dll",
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "Npcap" / "wpcap.dll",
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "SysWOW64" / "wpcap.dll",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WinPcap" / "rpcapd.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Npcap" / "NPFInstall.exe",
    ]
    
    for path in search_paths:
        if path.exists():
            logger.debug(f"Found pcap driver at: {path}")
            return True
    
    # Also check registry
    try:
        import winreg
        
        # Check WinPcap
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WinPcap"
            )
            winreg.CloseKey(key)
            logger.debug("WinPcap found in registry")
            return True
        except FileNotFoundError:
            pass
        
        # Check Npcap
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Npcap"
            )
            winreg.CloseKey(key)
            logger.debug("Npcap found in registry")
            return True
        except FileNotFoundError:
            pass
            
    except Exception as e:
        logger.debug(f"Registry check failed: {e}")
    
    return False


def download_winpcap(target_dir: Optional[str] = None) -> Optional[str]:

    global _installer_path
    
    if target_dir is None:
        target_dir = tempfile.gettempdir()
    
    installer_path = os.path.join(target_dir, WINPCAP_INSTALLER_NAME)
    
    # Check if already downloaded
    if os.path.exists(installer_path):
        logger.info(f"WinPcap installer already exists: {installer_path}")
        _installer_path = installer_path
        return installer_path
    
    logger.info("Downloading WinPcap installer...")
    
    urls_to_try = [WINPCAP_DOWNLOAD_URL] + WINPCAP_MIRROR_URLS
    
    for url in urls_to_try:
        try:
            logger.debug(f"Trying to download from: {url}")
            
            # Create request with user agent
            request = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) FirewallAgent/1.0'
                }
            )
            
            # Download with progress
            with urllib.request.urlopen(request, timeout=60) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                chunk_size = 8192
                
                with open(installer_path, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            if downloaded % (chunk_size * 10) == 0:  # Log every ~80KB
                                logger.debug(f"Download progress: {percent:.1f}%")
            
            # Verify file was downloaded
            if os.path.exists(installer_path) and os.path.getsize(installer_path) > 100000:
                logger.info(f"WinPcap downloaded successfully: {installer_path}")
                _installer_path = installer_path
                return installer_path
            else:
                logger.warning("Downloaded file is too small, may be corrupted")
                if os.path.exists(installer_path):
                    os.remove(installer_path)
                    
        except urllib.error.URLError as e:
            logger.warning(f"Failed to download from {url}: {e}")
        except Exception as e:
            logger.warning(f"Download error from {url}: {e}")
    
    logger.error("Failed to download WinPcap from all sources")
    return None


def install_winpcap_silent(installer_path: str) -> bool:

    global _winpcap_installed_by_us
    
    if not is_admin():
        logger.error("Admin privileges required to install WinPcap")
        return False
    
    if not os.path.exists(installer_path):
        logger.error(f"Installer not found: {installer_path}")
        return False
    
    logger.info("Installing WinPcap silently...")
    
    try:
        # WinPcap silent install command
        # /S = Silent mode
        # /D = Installation directory (optional)
        result = subprocess.run(
            [installer_path, "/S"],
            capture_output=True,
            timeout=120,  # 2 minutes timeout
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        time.sleep(3)
        
        if is_winpcap_installed():
            logger.info("WinPcap installed successfully")
            _winpcap_installed_by_us = True
            
            atexit.register(cleanup_winpcap)
            
            return True
        else:
            logger.error("WinPcap installation verification failed")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("WinPcap installation timed out")
        return False
    except Exception as e:
        logger.error(f"WinPcap installation failed: {e}")
        return False


def uninstall_winpcap_silent() -> bool:

    if not is_admin():
        logger.warning("Admin privileges required to uninstall WinPcap")
        return False
    
    logger.info("Uninstalling WinPcap...")
    
    # Find uninstaller
    uninstaller_paths = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WinPcap" / "Uninstall.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "WinPcap" / "Uninstall.exe",
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WinPcap" / "Uninstall.exe",
    ]
    
    uninstaller = None
    for path in uninstaller_paths:
        if path.exists():
            uninstaller = str(path)
            break
    
    if not uninstaller:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\WinPcapInst"
            )
            uninstall_string, _ = winreg.QueryValueEx(key, "UninstallString")
            winreg.CloseKey(key)
            uninstaller = uninstall_string.strip('"')
        except Exception:
            pass
    
    if not uninstaller or not os.path.exists(uninstaller):
        logger.warning("WinPcap uninstaller not found")
        return False
    
    try:
        logger.debug(f"Running uninstaller: {uninstaller}")
        
        result = subprocess.run(
            [uninstaller, "/S"],
            capture_output=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        time.sleep(2)
        
        if not is_winpcap_installed():
            logger.info("WinPcap uninstalled successfully")
            return True
        else:
            logger.warning("WinPcap may still be installed")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("WinPcap uninstallation timed out")
        return False
    except Exception as e:
        logger.error(f"WinPcap uninstallation failed: {e}")
        return False


def cleanup_winpcap() -> None:

    global _winpcap_installed_by_us, _installer_path
    
    with _install_lock:
        if _winpcap_installed_by_us:
            logger.info("Cleaning up WinPcap (installed by agent)...")
            try:
                uninstall_winpcap_silent()
            except Exception as e:
                logger.warning(f"Failed to uninstall WinPcap: {e}")
            finally:
                _winpcap_installed_by_us = False
        
        if _installer_path and os.path.exists(_installer_path):
            try:
                os.remove(_installer_path)
                logger.debug(f"Removed installer: {_installer_path}")
            except Exception as e:
                logger.warning(f"Failed to remove installer: {e}")
            finally:
                _installer_path = None


def ensure_winpcap_available() -> Tuple[bool, str]:

    global _winpcap_installed_by_us
    
    with _install_lock:
        # Check if already installed
        if is_winpcap_installed():
            return True, "WinPcap/Npcap already installed"
        
        # Need to install - check admin
        if not is_admin():
            return False, "Admin privileges required to install WinPcap"
        
        logger.info("WinPcap not found - attempting auto-installation...")
        
        # Download
        installer_path = download_winpcap()
        if not installer_path:
            return False, "Failed to download WinPcap"
        
        # Install
        if install_winpcap_silent(installer_path):
            return True, "WinPcap installed successfully (will be removed on exit)"
        else:
            return False, "Failed to install WinPcap"


def was_installed_by_us() -> bool:
    """Check if WinPcap was installed by this agent session."""
    return _winpcap_installed_by_us


# Module-level initialization
def init_winpcap_manager() -> None:
    """Initialize the WinPcap manager - call this at startup."""
    if os.name != "nt":
        return
    
    logger.debug("WinPcap manager initialized")
