"""
SAS Modbus Toolkit — Theme & Branding
Defines all visual constants using SAS brand identity.
Matches the SAS Network Diagnostic Tool theme exactly.
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

# ── Modbus Protocol Colors ───────────────────────────────────────────────────
MODBUS_RTU_COLOR = "#E8722A"    # Orange for RTU (serial)
MODBUS_TCP_COLOR = "#0070BB"    # Blue for TCP (Ethernet)
MODBUS_READ_COLOR = "#22C55E"   # Green for read operations
MODBUS_WRITE_COLOR = "#F59E0B"  # Amber for write operations
MODBUS_ERROR_COLOR = "#EF4444"  # Red for errors
MODBUS_TIMEOUT_COLOR = "#F97316" # Orange for timeouts

# ── UI Colors ────────────────────────────────────────────────────────────────
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

# ── Status Colors ────────────────────────────────────────────────────────────
STATUS_GOOD = "#22C55E"
STATUS_WARN = "#F59E0B"
STATUS_ERROR = "#EF4444"
STATUS_INFO = SAS_BLUE_LIGHT
STATUS_OFFLINE = "#6B7280"

# ── Health Score Colors ───────────────────────────────────────────────────────
HEALTH_CRITICAL = "#EF4444"
HEALTH_POOR = "#F97316"
HEALTH_FAIR = "#F59E0B"
HEALTH_GOOD = "#84CC16"
HEALTH_EXCELLENT = "#22C55E"

# ── Typography ───────────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"
FONT_SIZE_TITLE = 20
FONT_SIZE_HEADING = 16
FONT_SIZE_SUBHEADING = 14
FONT_SIZE_BODY = 12
FONT_SIZE_SMALL = 11
FONT_SIZE_TINY = 10

# ── Layout ───────────────────────────────────────────────────────────────────
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
    """Get the absolute path to an asset file."""
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


def get_health_color(score: int) -> str:
    """Return the appropriate color for a health score (0-100)."""
    if score >= 90:
        return HEALTH_EXCELLENT
    elif score >= 70:
        return HEALTH_GOOD
    elif score >= 50:
        return HEALTH_FAIR
    elif score >= 30:
        return HEALTH_POOR
    else:
        return HEALTH_CRITICAL


def get_health_label(score: int) -> str:
    """Return a human-readable label for a health score."""
    if score >= 90:
        return "Excellent"
    elif score >= 70:
        return "Good"
    elif score >= 50:
        return "Fair"
    elif score >= 30:
        return "Poor"
    else:
        return "Critical"
