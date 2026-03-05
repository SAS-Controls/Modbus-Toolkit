"""
SAS Modbus Toolkit — TCP Scanner View
Discovers Modbus TCP devices on a network by scanning IP ranges.
"""

import logging
import tkinter as tk
from typing import List

import customtkinter as ctk

from core.modbus_scanner import ModbusTCPScanner, DiscoveredModbusDevice
from core.settings_manager import AppSettings
from ui.theme import *

logger = logging.getLogger(__name__)


class TCPScannerView(ctk.CTkFrame):
    """Network scanner — finds Modbus TCP devices on a subnet."""

    def __init__(self, master_widget, settings: AppSettings, **kwargs):
        super().__init__(master_widget, fg_color=BG_DARK, **kwargs)
        self._settings = settings
        self._scanner = ModbusTCPScanner(
            on_device_found=self._on_device_found,
            on_progress=self._on_progress,
            on_complete=self._on_complete,
        )
        self._devices: List[DiscoveredModbusDevice] = []
        self._build_ui()

    def on_show(self):
        pass

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=BG_MEDIUM, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="🌐  Modbus TCP Network Scanner",
                     font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=20, pady=12)

        self._status_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(header, textvariable=self._status_var,
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=STATUS_INFO).pack(side="right", padx=16)

        # Body
        body = ctk.CTkFrame(self, fg_color=BG_DARK)
        body.pack(fill="both", expand=True)

        # Left config
        left = ctk.CTkFrame(body, fg_color=BG_MEDIUM, width=280, corner_radius=0)
        left.pack(side="left", fill="y", padx=(0, 1))
        left.pack_propagate(False)
        self._build_config(left)

        # Right results
        right = ctk.CTkFrame(body, fg_color=BG_DARK)
        right.pack(fill="both", expand=True)
        self._build_results(right)

    def _build_config(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(scroll, text="SCAN SETTINGS",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=16, pady=(16, 4))

        card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        card.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(card, text="Network (e.g. 192.168.1)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        self._network = ctk.CTkEntry(card, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                      fg_color=BG_INPUT, height=INPUT_HEIGHT)
        self._network.insert(0, self._settings.scanner_network)
        self._network.pack(fill="x", padx=12, pady=(0, 8))

        row_p = ctk.CTkFrame(card, fg_color="transparent")
        row_p.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row_p, text="Port",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._port = ctk.CTkEntry(row_p, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                   fg_color=BG_INPUT, height=INPUT_HEIGHT, width=80)
        self._port.insert(0, str(self._settings.scanner_port))
        self._port.pack(side="right")

        row_to = ctk.CTkFrame(card, fg_color="transparent")
        row_to.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row_to, text="Timeout (s)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._timeout = ctk.CTkEntry(row_to, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                      fg_color=BG_INPUT, height=INPUT_HEIGHT, width=70)
        self._timeout.insert(0, "1.0")
        self._timeout.pack(side="right")

        self._scan_btn = ctk.CTkButton(
            scroll, text="🔍  Scan Network",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
            height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._toggle_scan,
        )
        self._scan_btn.pack(fill="x", padx=16, pady=(4, 8))

        self._progress = ctk.CTkProgressBar(scroll, fg_color=BG_CARD,
                                             progress_color=SAS_BLUE, height=6)
        self._progress.set(0)
        self._progress.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(scroll,
                     text="ℹ  Scans all 254 hosts on the\nsubnet for Modbus TCP (port 502).\n\n"
                          "Devices that accept TCP connections\nand respond to Modbus queries\n"
                          "are listed with their unit IDs.",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED,
                     justify="left", anchor="w").pack(fill="x", padx=16, pady=(0, 12))

    def _build_results(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=0, height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="  Discovered Modbus TCP Devices",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=12)

        self._found_var = tk.StringVar(value="")
        ctk.CTkLabel(hdr, textvariable=self._found_var,
                     font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                     text_color=STATUS_GOOD).pack(side="right", padx=12)

        # Column headers
        col_hdr = ctk.CTkFrame(parent, fg_color=BG_MEDIUM, corner_radius=0, height=26)
        col_hdr.pack(fill="x")
        col_hdr.pack_propagate(False)

        for text, w in [("IP Address", 140), ("Port", 70), ("Unit IDs", 150),
                         ("Response", 100), ("Device Info", 200)]:
            ctk.CTkLabel(col_hdr, text=text, font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                         text_color=TEXT_MUTED, width=w, anchor="center").pack(side="left", padx=2)

        self._results_scroll = ctk.CTkScrollableFrame(parent, fg_color=BG_DARK, corner_radius=0)
        self._results_scroll.pack(fill="both", expand=True)

        # Empty state message
        self._empty_lbl = ctk.CTkLabel(
            self._results_scroll,
            text="Run a scan to discover Modbus TCP devices on the network",
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_MUTED,
        )
        self._empty_lbl.pack(pady=40)

    def _toggle_scan(self):
        if self._scanner.scanning:
            self._scanner.stop()
            self._scan_btn.configure(text="🔍  Scan Network", fg_color=SAS_BLUE)
            self._status_var.set("Cancelled")
        else:
            self._start_scan()

    def _start_scan(self):
        for w in self._results_scroll.winfo_children():
            w.destroy()
        self._devices.clear()
        self._found_var.set("")

        network = self._network.get().strip()
        try:
            port = int(self._port.get())
            timeout = float(self._timeout.get())
        except ValueError:
            port = 502
            timeout = 1.0

        self._scan_btn.configure(text="⏹  Stop", fg_color=STATUS_ERROR, hover_color="#DC2626")
        self._status_var.set("Scanning 192.168.x.1-254...")
        self._progress.set(0)

        self._scanner.start_scan(network, port, timeout)

    def _on_device_found(self, device: DiscoveredModbusDevice):
        self.after(0, lambda d=device: self._add_device_row(d))

    def _on_progress(self, pct: int, scanned: int, total: int, found: int):
        self.after(0, lambda p=pct/100, f=found: (
            self._progress.set(p),
            self._found_var.set(f"Found: {f}"),
            self._status_var.set(f"Scanning... {pct}%"),
        ))

    def _on_complete(self, results: List[DiscoveredModbusDevice]):
        self.after(0, lambda: (
            self._scan_btn.configure(text="🔍  Scan Network", fg_color=SAS_BLUE,
                                     hover_color=SAS_BLUE_DARK),
            self._progress.set(1.0),
            self._status_var.set(f"Complete — {len(results)} device(s) found"),
            self._found_var.set(f"✓ {len(results)} device(s) found"),
        ))
        if not results:
            self.after(0, lambda: self._empty_lbl.configure(
                text="No Modbus TCP devices found on this network"))
            self._empty_lbl.pack(pady=40)

    def _add_device_row(self, device: DiscoveredModbusDevice):
        if self._empty_lbl.winfo_ismapped():
            self._empty_lbl.pack_forget()

        row_bg = BG_CARD if len(self._results_scroll.winfo_children()) % 2 == 0 else BG_DARK
        row = ctk.CTkFrame(self._results_scroll, fg_color=row_bg, corner_radius=0, height=36)
        row.pack(fill="x")
        row.pack_propagate(False)

        ctk.CTkLabel(row, text=device.ip,
                     font=(FONT_FAMILY_MONO, FONT_SIZE_BODY, "bold"),
                     text_color=SAS_BLUE_LIGHT, width=140, anchor="center").pack(side="left", padx=2)

        ctk.CTkLabel(row, text=str(device.port),
                     font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                     text_color=TEXT_MUTED, width=70, anchor="center").pack(side="left", padx=2)

        ctk.CTkLabel(row, text=device.unit_summary,
                     font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                     text_color=TEXT_SECONDARY, width=150, anchor="center").pack(side="left", padx=2)

        ctk.CTkLabel(row, text=f"{device.response_time_ms:.1f}ms",
                     font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                     text_color=TEXT_MUTED, width=100, anchor="center").pack(side="left", padx=2)

        # Device info (from FC43 if available)
        info = ""
        if device.device_id_info:
            parts = [v for v in device.device_id_info.values() if v]
            info = " | ".join(parts[:2])
        ctk.CTkLabel(row, text=info or "—",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_MUTED, width=200, anchor="w").pack(side="left", padx=8)
