# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller Spec File for Firewall Controller Agent GUI
- Education Security

This spec file creates:
1. SAINT_GUI.exe - GUI mode (windowed, no console)
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
    [],
    exclude_binaries=True,
    name='SAINT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Windowed mode - no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='agent/miku.ico',
    uac_admin=True,  # Require admin to run
)

coll = COLLECT(
    exe_gui,
    a_gui.binaries,
    a_gui.zipfiles,
    a_gui.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SAINT',
)
