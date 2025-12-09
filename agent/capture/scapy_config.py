import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("capture.scapy_config")

_SCAPY_CACHE_DIR: Optional[str] = None


def configure_scapy() -> Optional[str]:
    """
    Configure Scapy cache directory to avoid permission errors.
    
    On some Windows systems, writing to %USERPROFILE%\\.cache is blocked.
    This function redirects Scapy cache to system temp directory.
    
    Returns:
        str: Path to cache directory, or None on failure
    """
    global _SCAPY_CACHE_DIR
    
    if _SCAPY_CACHE_DIR is not None:
        return _SCAPY_CACHE_DIR
    
    try:
        # Prefer Windows TEMP/TMP, fallback to Python tempdir
        temp_root = (
            os.environ.get("TEMP") or
            os.environ.get("TMP") or
            tempfile.gettempdir()
        )

        cache_dir = os.path.join(temp_root, "scapy-cache")
        os.makedirs(cache_dir, exist_ok=True)

        # Set environment variables for Scapy
        os.environ["SCAPY_CACHE_DIR"] = cache_dir
        os.environ["SCAPY_CONFIG_DIR"] = cache_dir
        os.environ["SCAPY_DATA_DIR"] = cache_dir
        os.environ.setdefault("XDG_CACHE_HOME", cache_dir)
        os.environ.setdefault("SCAPY_HOME", cache_dir)

        _SCAPY_CACHE_DIR = cache_dir
        logger.debug(f"Scapy cache configured at {cache_dir}")
        return cache_dir
        
    except Exception as e:
        logger.warning(f"Failed to configure Scapy cache: {e}")
        return None


def ensure_pcap_driver() -> bool:
    """
    Ensure Scapy can find WinPcap or Npcap on Windows.
    
    Scapy needs wpcap.dll in PATH to function. This function searches
    common installation locations and adds them to PATH if needed.
    
    Returns:
        bool: True if driver found, False otherwise
    """
    if os.name != "nt":
        return True

    candidate_dirs = []

    # Environment variables from installers
    for env_var in ["NPCAP_DIR", "WINPCAP_DIR"]:
        env_path = os.environ.get(env_var)
        if env_path:
            candidate_dirs.append(Path(env_path))

    # Common installation locations
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", str(program_files)))

    candidate_dirs.extend([
        system_root / "System32" / "Npcap",
        system_root / "System32",
        system_root / "SysWOW64" / "Npcap",
        program_files / "Npcap",
        program_files_x86 / "Npcap",
        program_files / "WinPcap",
        program_files_x86 / "WinPcap",
    ])

    added_paths = []
    driver_found = False
    
    for directory in candidate_dirs:
        wpcap_path = directory / "wpcap.dll"
        if wpcap_path.exists():
            driver_found = True
            
            # Avoid duplicate PATH entries
            current_path = os.environ.get("PATH", "")
            if str(directory) not in current_path.split(os.pathsep):
                os.environ["PATH"] = str(directory) + os.pathsep + current_path
                added_paths.append(directory)

            # Python 3.8+ requires add_dll_directory
            try:
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(str(directory))
            except Exception as e:
                logger.debug(f"Could not add DLL directory {directory}: {e}")

    if added_paths:
        logger.info(f"Added pcap driver locations: {', '.join(map(str, added_paths))}")
    
    if not driver_found:
        logger.warning(
            "wpcap.dll not found; ensure Npcap or WinPcap is installed"
        )
    
    return driver_found


def apply_scapy_config() -> None:
    """
    Apply Scapy configuration after import.
    
    Call this after importing Scapy modules to set cache directory.
    """
    global _SCAPY_CACHE_DIR
    
    if _SCAPY_CACHE_DIR:
        try:
            from scapy.config import conf as scapy_conf
            scapy_conf.cache_dir = _SCAPY_CACHE_DIR
            os.makedirs(scapy_conf.cache_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not apply Scapy config: {e}")