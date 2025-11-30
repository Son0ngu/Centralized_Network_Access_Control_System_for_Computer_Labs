"""
System information utilities for accurate OS detection.
Fixes Windows 11 mislabeling in Registry for builds >= 22000.
"""

import logging
import platform
import sys
from typing import Dict

logger = logging.getLogger("shared.os_info")

# Windows-specific imports
if sys.platform == "win32":
    import winreg


def _detect_windows_info() -> Dict[str, str]:
    """
    Collect Windows version details.
    
    Corrects the 'Windows 10' mislabeling in Registry for Windows 11 builds.
    Windows 11 has build numbers >= 22000.
    
    Returns:
        dict: Windows version information with 'name' and 'version' keys
    """
    info = {"name": "Windows", "version": platform.version()}

    try:
        key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            product_name, _ = winreg.QueryValueEx(key, "ProductName")
            current_build, _ = winreg.QueryValueEx(key, "CurrentBuild")

            try:
                display_version, _ = winreg.QueryValueEx(key, "DisplayVersion")
            except FileNotFoundError:
                display_version = None

            # Windows 11 detection based on build number
            build_num = int(current_build)
            if build_num >= 22000:
                product_name = product_name.replace("Windows 10", "Windows 11")

            info["name"] = product_name

            if display_version:
                info["version"] = f"{display_version} (Build {current_build})"
            else:
                info["version"] = f"Build {current_build}"

    except Exception as e:
        logger.debug(f"Registry read failed, using fallback: {e}")
        
        # Fallback: check build number from platform.version()
        version_str = platform.version()
        try:
            build_number = int(version_str.split(".")[-1])
            if build_number >= 22000:
                info["name"] = "Windows 11"
        except Exception:
            pass

    return info


def get_os_details() -> Dict[str, str]:
    """
    Get operating system details.
    
    Returns:
        dict: OS information with keys:
            - platform: OS platform (Windows, Linux, Darwin)
            - name: OS name (e.g., "Windows 11 Pro")
            - version: OS version string
            - arch: System architecture (AMD64, x86_64, etc.)
    """
    system = platform.system() or "Unknown"
    arch = platform.machine() or "Unknown"

    os_info: Dict[str, str] = {
        "platform": system,
        "name": system,
        "version": platform.version() or "Unknown",
        "arch": arch,
    }

    if system == "Windows":
        os_info.update(_detect_windows_info())
    elif system == "Linux":
        try:
            import distro
            os_info["name"] = distro.name(pretty=True)
            os_info["version"] = distro.version()
        except ImportError:
            pass
    elif system == "Darwin":
        os_info["name"] = "macOS"
        os_info["version"] = platform.mac_ver()[0]

    return os_info