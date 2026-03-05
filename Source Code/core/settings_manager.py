"""
SAS Modbus Toolkit — Settings Manager
Persists application settings to a JSON file in AppData.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "SAS" / "ModbusToolkit"
SETTINGS_FILE = APP_DATA_DIR / "settings.json"


@dataclass
class AppSettings:
    theme: str = "Dark"

    # Last TCP settings
    tcp_host: str = "192.168.1.100"
    tcp_port: int = 502

    # Last RTU settings
    rtu_port: str = "COM1"
    rtu_baud: int = 9600
    rtu_parity: str = "N"
    rtu_stopbits: int = 1

    # Last master settings
    master_slave_id: int = 1
    master_fc: int = 3
    master_address: int = 0
    master_count: int = 10
    master_poll_ms: int = 1000

    # Last slave settings
    slave_id: int = 1
    slave_tcp_port: int = 502
    slave_tcp_host: str = "0.0.0.0"

    # Scanner settings
    scanner_network: str = "192.168.1"
    scanner_port: int = 502

    # Explorer settings
    explorer_start: int = 0
    explorer_end: int = 100

    # Log settings
    log_max_entries: int = 1000
    log_timestamps: bool = True
    log_raw_bytes: bool = False

    # Window
    window_geometry: str = ""


def get_settings() -> AppSettings:
    """Load settings from disk, creating defaults if needed."""
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            s = AppSettings()
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            return s
    except Exception as e:
        logger.warning(f"Could not load settings: {e}")
    return AppSettings()


def save_settings(settings: AppSettings):
    """Save settings to disk."""
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(asdict(settings), f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save settings: {e}")
