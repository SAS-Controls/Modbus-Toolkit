"""
SAS Modbus Toolkit — Theme & Branding
Defines all visual constants for the application using SAS brand identity.
Matches the SAS Network Diagnostic Tool visual language exactly.
"""

import os
import sys

# ── SAS Brand Colors ─────────────────────────────────────────────────────────
SAS_BLUE = "#0070BB"
SAS_BLUE_DARK = "#005A96"
SAS_BLUE_LIGHT = "#4F81BD"
SAS_BLUE_ACCENT = "#365F91"
SAS_ORANGE = "#E8722A"
SAS_ORANGE_DARK = "#C45E1F"
SAS_ORANGE_LIGHT = "#F09050"

# ── UI Colors ────────────────────────────────────────────────────────────────
# Each constant is a (light_mode, dark_mode) tuple.
BG_DARK = ("#D5D8DC", "#1E1E1E")
BG_MEDIUM = ("#C8CCD0", "#2B2B2B")
BG_CARD = ("#EAECF0", "#333333")
BG_CARD_HOVER = ("#DCE0E5", "#3E3E3E")
BG_INPUT = ("#FFFFFF", "#141414")
TEXT_PRIMARY = ("#1A1A2E", "#EAEAEA")
TEXT_SECONDARY = ("#4A5568", "#999999")
TEXT_MUTED = ("#718096", "#666666")
BORDER_COLOR = ("#B0B8C4", "#444444")
BORDER_ACTIVE = SAS_BLUE

# ── Status Colors ─────────────────────────────────────────────────────────────
STATUS_GOOD = "#22C55E"
STATUS_WARN = "#F59E0B"
STATUS_ERROR = "#EF4444"
STATUS_INFO = SAS_BLUE_LIGHT
STATUS_OFFLINE = "#6B7280"

# ── Log Colors ────────────────────────────────────────────────────────────────
LOG_TX = "#4F81BD"       # Outgoing requests (blue)
LOG_RX = "#22C55E"       # Successful responses (green)
LOG_ERROR = "#EF4444"    # Errors, exceptions (red)
LOG_WARN = "#F59E0B"     # Warnings, timeouts (yellow)
LOG_INFO = "#9CA3AF"     # Info/system messages (gray)

# ── Typography ───────────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"
FONT_SIZE_TITLE = 20
FONT_SIZE_HEADING = 16
FONT_SIZE_SUBHEADING = 14
FONT_SIZE_BODY = 12
FONT_SIZE_SMALL = 11
FONT_SIZE_TINY = 10

# ── Layout ────────────────────────────────────────────────────────────────────
SIDEBAR_WIDTH = 250
CARD_CORNER_RADIUS = 8
CARD_PADDING = 16
BUTTON_CORNER_RADIUS = 6
BUTTON_HEIGHT = 36
INPUT_HEIGHT = 36

# ── Application Info ─────────────────────────────────────────────────────────
APP_NAME = "SAS Modbus Toolkit"
APP_FULL_NAME = "SAS Modbus Toolkit"
APP_VERSION = "1.0.0"
APP_COMPANY = "Southern Automation Solutions"


def get_asset_path(filename: str) -> str:
    """Get absolute path to an asset file, handling both dev and PyInstaller modes."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, "assets", filename)


def resolve_color(color) -> str:
    """Resolve a theme color tuple to a single string for raw tkinter widgets."""
    if isinstance(color, (list, tuple)) and len(color) == 2:
        try:
            import customtkinter as ctk
            mode = ctk.get_appearance_mode()
            return color[0] if mode == "Light" else color[1]
        except Exception:
            return color[1]
    if isinstance(color, str) and " " in color and color.startswith("#"):
        parts = color.split()
        if len(parts) == 2 and all(p.startswith("#") for p in parts):
            try:
                import customtkinter as ctk
                mode = ctk.get_appearance_mode()
                return parts[0] if mode == "Light" else parts[1]
            except Exception:
                return parts[1]
    return color
