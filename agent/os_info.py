"""
System information utilities for accurate OS detection.
Fixed: Forces 'Windows 11' label if Build Number >= 22000.
"""

import platform
import sys
from typing import Dict

if sys.platform == "win32":
    import winreg

def _detect_windows_info() -> Dict[str, str]:
    """
    Collect Windows version details.
    Corrects the 'Windows 10' mislabeling in Registry for Windows 11 builds (>=22000).
    """
    info = {"name": "Windows", "version": platform.version()}

    try:
        key_path = r"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion"

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            product_name, _ = winreg.QueryValueEx(key, "ProductName")
            current_build, _ = winreg.QueryValueEx(key, "CurrentBuild")

            try:
                display_version, _ = winreg.QueryValueEx(key, "DisplayVersion")
            except FileNotFoundError:
                display_version = None

            build_num = int(current_build)
            if build_num >= 22000:
                product_name = product_name.replace("Windows 10", "Windows 11")

            info["name"] = product_name

            if display_version:
                info["version"] = f"{display_version} (Build {current_build})"
            else:
                info["version"] = f"Build {current_build}"

    except Exception:
        version_str = platform.version()
        try:
            build_number = int(version_str.split(".")[-1])
            if build_number >= 22000:
                info["name"] = "Windows 11"
        except Exception:
            pass

    return info

def get_os_details() -> Dict[str, str]:
    system = platform.system() or "Unknown"
    arch = platform.machine() or "Unknown"

    os_info: Dict[str, str] = {
        "platform": system,
        "name": system,
        "version": None,
        "arch": arch,
    }

    if system == "Windows":
        os_info.update(_detect_windows_info())

    return os_info