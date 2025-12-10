# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller Spec File for Firewall Controller Agent GUI
- Enterprise Security

This spec file creates two executables:
1. SAINT.exe - Console mode (for service/CLI)
2. SAINT_GUI.exe - GUI mode (windowed, no console)
"""

import sys
import os

# Collect all submodules for proper packaging
hiddenimports = [
    # Core modules
    'core',
    'core.agent',
    'core.handlers',
    'core.lifecycle',
    'core.registry',
    
    # Config
    'config',
    'config.loader',
    'config.defaults',
    'config.validator',
    
    # Capture
    'capture',
    'capture.sniffer',
    'capture.extractors',
    'capture.scapy_config',
    
    # Firewall
    'firewall',
    'firewall.manager',
    'firewall.policy',
    'firewall.rules',
    'firewall.utils',
    
    # Whitelist
    'whitelist',
    'whitelist.manager',
    'whitelist.state',
    'whitelist.sync',
    'whitelist.monitor',
    
    # Services
    'services',
    'services.heartbeat',
    'services.windows_service',
    
    # Logging
    'logging_module',
    'logging_module.sender',
    
    # Network
    'network',
    'network.dns_resolver',
    
    # Cache
    'cache',
    'cache.lru_cache',
    
    # Shared
    'shared',
    'shared.time_utils',
    'shared.os_info',
    
    # Utils
    'utils',
    'utils.ip_detector',
    'utils.error_handler',
    'utils.validators',
    
    # GUI
    'gui',
    'gui.app',
    'gui.views',
    'gui.views.main_window',
    'gui.views.dashboard_view',
    'gui.views.firewall_view',
    'gui.views.whitelist_view',
    'gui.views.logs_view',
    'gui.views.settings_view',
    'gui.views.components',
    'gui.views.components.status_card',
    'gui.views.components.data_table',
    'gui.views.components.log_console',
    'gui.controllers',
    'gui.controllers.agent_controller',
    'gui.controllers.whitelist_controller',
    'gui.styles',
    'gui.styles.colors',
    'gui.styles.themes',
    'gui.styles.stylesheet',
    'gui.resources',
    'gui.resources.icons',
    
    # Third party
    'customtkinter',
    'darkdetect',
    'scapy',
    'scapy.all',
    'scapy.layers.dns',
    'scapy.layers.inet',
    'scapy.layers.http',
    'dns',
    'dns.resolver',
    'requests',
    'psutil',
    'zoneinfo',
]

# Data files to include
datas = [
    ('agent', 'agent'),
    ('agent/miku.ico', '.'),
]

# Collect customtkinter data files
try:
    import customtkinter
    ctk_path = os.path.dirname(customtkinter.__file__)
    datas.append((ctk_path, 'customtkinter'))
except ImportError:
    pass


# ========================================
# Console Application (Service/CLI)
# ========================================
a_console = Analysis(
    ['agent/agent_main.py'],
    pathex=['agent'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],  # Exclude tkinter for console version
    noarchive=False,
    optimize=0,
)

pyz_console = PYZ(a_console.pure)

exe_console = EXE(
    pyz_console,
    a_console.scripts,
    a_console.binaries,
    a_console.datas,
    [],
    name='SAINT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='agent/miku.ico',
    uac_admin=False,  # Request admin privileges
)


# ========================================
# GUI Application (Windowed)
# ========================================
a_gui = Analysis(
    ['agent/agent_gui.py'],
    pathex=['agent'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz_gui = PYZ(a_gui.pure)

exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    a_gui.binaries,
    a_gui.datas,
    [],
    name='SAINT-GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windowed mode - no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='agent/miku.ico',
    uac_admin=False,  # No admin required - can run in monitor mode
)
