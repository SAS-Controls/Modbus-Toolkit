"""
SAS Modbus Toolkit — Main Application Window
Sidebar navigation and view management.
Matches the look and structure of the SAS Network Diagnostic Tool.
"""

import logging
import os
import sys
import tkinter as tk

import customtkinter as ctk
from PIL import Image

from ui.theme import *
from ui.master_view import MasterView
from ui.slave_view import SlaveView
from ui.scanner_view import ScannerView
from ui.diagnostics_view import DiagnosticsView
from ui.calculator_view import CalculatorView
from ui.help_view import HelpView

logger = logging.getLogger(__name__)


class App(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # ── Window ────────────────────────────────────────────────────────────
        self.title(APP_FULL_NAME)
        self.geometry("1300x820")
        self.minsize(1060, 640)
        self.configure(fg_color=BG_DARK)

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Try to set window icon
        try:
            ico_path = get_asset_path("icon.ico")
            png_path = get_asset_path("icon.png")
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
            elif os.path.exists(png_path):
                icon_img = tk.PhotoImage(file=png_path)
                self.iconphoto(True, icon_img)
                self._icon_ref = icon_img
        except Exception as e:
            logger.debug(f"Icon error: {e}")

        self._build_sidebar()
        self._build_main_area()
        self._show_master_view()

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        self._sidebar = ctk.CTkFrame(
            self, width=SIDEBAR_WIDTH, corner_radius=0,
            fg_color=BG_MEDIUM, border_width=0,
        )
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        # Logo
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent", height=100)
        logo_frame.pack(fill="x", padx=16, pady=(20, 8))
        logo_frame.pack_propagate(False)

        try:
            dark_logo_path = get_asset_path("logo.png")
            light_logo_path = get_asset_path("logo_light.png")
            if os.path.exists(dark_logo_path):
                dark_img = Image.open(dark_logo_path).convert("RGBA")
                light_img = Image.open(light_logo_path).convert("RGBA") \
                    if os.path.exists(light_logo_path) else dark_img
                aspect = dark_img.width / dark_img.height
                logo_w = SIDEBAR_WIDTH - 40
                logo_h = int(logo_w / aspect)
                if logo_h > 80:
                    logo_h = 80
                    logo_w = int(logo_h * aspect)
                ctk_logo = ctk.CTkImage(light_image=light_img, dark_image=dark_img,
                                        size=(logo_w, logo_h))
                ctk.CTkLabel(logo_frame, text="", image=ctk_logo,
                             fg_color="transparent").pack(pady=(5, 0))
                self._logo_ref = ctk_logo
        except Exception as e:
            logger.debug(f"Logo error: {e}")
            ctk.CTkLabel(logo_frame, text="SAS",
                         font=(FONT_FAMILY, 28, "bold"),
                         text_color=SAS_BLUE).pack(pady=(5, 0))

        ctk.CTkLabel(self._sidebar, text=APP_NAME,
                     font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                     text_color=TEXT_PRIMARY).pack(padx=16, pady=(4, 4))

        # Divider
        ctk.CTkFrame(self._sidebar, fg_color=BORDER_COLOR, height=1).pack(
            fill="x", padx=16, pady=10)

        # ── Nav: Master / Slave ───────────────────────────────────────────────
        self._nav_buttons = {}

        ctk.CTkLabel(self._sidebar, text="SIMULATION",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(
            fill="x", padx=20, pady=(0, 4))

        self._add_nav_btn("master",  "📡  Modbus Master",     self._show_master_view)
        self._add_nav_btn("slave",   "🖥  Slave Simulator",   self._show_slave_view)

        ctk.CTkFrame(self._sidebar, fg_color=BORDER_COLOR, height=1).pack(
            fill="x", padx=20, pady=8)

        ctk.CTkLabel(self._sidebar, text="DIAGNOSTICS",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(
            fill="x", padx=20, pady=(0, 4))

        self._add_nav_btn("scanner",     "🔍  Bus Scanner",        self._show_scanner_view)
        self._add_nav_btn("diagnostics", "🩺  Network Diagnostics", self._show_diagnostics_view)

        ctk.CTkFrame(self._sidebar, fg_color=BORDER_COLOR, height=1).pack(
            fill="x", padx=20, pady=8)

        ctk.CTkLabel(self._sidebar, text="REFERENCE",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(
            fill="x", padx=20, pady=(0, 4))

        self._add_nav_btn("calculator", "🧮  Data Calculator",  self._show_calculator_view)

        # ── Bottom ────────────────────────────────────────────────────────────
        ctk.CTkFrame(self._sidebar, fg_color="transparent").pack(fill="both", expand=True)

        bottom = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(0, 12))

        self._help_btn = ctk.CTkButton(
            bottom, text="📖  Help",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color="transparent", text_color=TEXT_SECONDARY,
            hover_color=BG_CARD_HOVER, anchor="w",
            height=36, corner_radius=6,
            command=self._show_help_view,
        )
        self._help_btn.pack(fill="x", pady=(0, 2))

        ctk.CTkFrame(bottom, fg_color=BORDER_COLOR, height=1).pack(
            fill="x", padx=4, pady=8)

        ctk.CTkLabel(bottom, text=APP_COMPANY,
                     font=(FONT_FAMILY, FONT_SIZE_TINY),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=4)
        ctk.CTkLabel(bottom, text=f"v{APP_VERSION}",
                     font=(FONT_FAMILY, FONT_SIZE_TINY),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=4)

    def _add_nav_btn(self, key: str, text: str, command):
        btn = ctk.CTkButton(
            self._sidebar, text=text,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color="transparent", text_color=TEXT_SECONDARY,
            hover_color=BG_CARD_HOVER, anchor="w",
            height=40, corner_radius=6,
            command=command,
        )
        btn.pack(fill="x", padx=12, pady=(0, 2))
        self._nav_buttons[key] = btn

    def _set_active_nav(self, key: str):
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(fg_color=BG_CARD, text_color=SAS_BLUE_LIGHT)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_SECONDARY)

    # ── Main Area ─────────────────────────────────────────────────────────────

    def _build_main_area(self):
        self._main = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        self._main.pack(side="right", fill="both", expand=True)

        self._master_view      = MasterView(self._main)
        self._slave_view       = SlaveView(self._main)
        self._scanner_view     = ScannerView(self._main)
        self._diagnostics_view = DiagnosticsView(self._main)
        self._calculator_view  = CalculatorView(self._main)
        self._help_view        = HelpView(self._main)

    def _hide_all(self):
        for v in (self._master_view, self._slave_view, self._scanner_view,
                  self._diagnostics_view, self._calculator_view, self._help_view):
            v.pack_forget()

    def _show_master_view(self):
        self._hide_all()
        self._master_view.pack(fill="both", expand=True)
        self._master_view.on_show()
        self._set_active_nav("master")

    def _show_slave_view(self):
        self._hide_all()
        self._slave_view.pack(fill="both", expand=True)
        self._slave_view.on_show()
        self._set_active_nav("slave")

    def _show_scanner_view(self):
        self._hide_all()
        self._scanner_view.pack(fill="both", expand=True)
        self._scanner_view.on_show()
        self._set_active_nav("scanner")

    def _show_diagnostics_view(self):
        self._hide_all()
        self._diagnostics_view.pack(fill="both", expand=True)
        self._diagnostics_view.on_show()
        self._set_active_nav("diagnostics")

    def _show_calculator_view(self):
        self._hide_all()
        self._calculator_view.pack(fill="both", expand=True)
        self._calculator_view.on_show()
        self._set_active_nav("calculator")

    def _show_help_view(self):
        self._hide_all()
        self._help_view.pack(fill="both", expand=True)
        self._help_view.on_show()
        self._set_active_nav("")
