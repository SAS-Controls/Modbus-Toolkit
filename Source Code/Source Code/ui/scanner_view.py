"""
SAS Modbus Toolkit — Bus Scanner View
Scans RTU buses and TCP networks to discover Modbus devices.
"""

import logging
import threading
import tkinter as tk
from typing import List

import customtkinter as ctk

from core.modbus_scanner import DiscoveredModbusDevice, ModbusBusScanner, ScanMode
from ui.theme import *
from ui.widgets import (
    LogBox, get_serial_ports, make_card, make_primary_button,
    make_secondary_button, make_danger_button, enable_touch_scroll
)

logger = logging.getLogger(__name__)

BAUD_RATES = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]


class ScannerView(ctk.CTkFrame):
    """Bus Scanner view — find Modbus devices on RTU or TCP networks."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._scanner = ModbusBusScanner()
        self._scanner.on_device_found = self._on_device_found
        self._scanner.on_progress = self._on_progress
        self._scanner.on_complete = self._on_complete
        self._scanner.on_error = self._on_scan_error

        self._devices: List[DiscoveredModbusDevice] = []
        self._build_ui()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=50)
        hdr.pack(fill="x", padx=24, pady=(16, 4))
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="🔍  Bus Scanner",
                      font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                      text_color=TEXT_PRIMARY, anchor="w").pack(side="left")

        self._scan_count_lbl = ctk.CTkLabel(hdr, text="",
                                              font=(FONT_FAMILY, FONT_SIZE_BODY),
                                              text_color=TEXT_MUTED)
        self._scan_count_lbl.pack(side="right", padx=8)

        # ── Scrollable area ───────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True)
        enable_touch_scroll(self._scroll)

        self._build_config_card()
        self._build_results_card()

    def _build_config_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(4, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=10)

        # Scan mode selector
        ctk.CTkLabel(inner, text="Scan Mode:",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY, anchor="w").pack(anchor="w", pady=(0, 6))

        self._mode_var = ctk.StringVar(value=ScanMode.RTU_BUS.value)
        modes_frame = ctk.CTkFrame(inner, fg_color="transparent")
        modes_frame.pack(anchor="w", pady=(0, 12))

        for mode in ScanMode:
            ctk.CTkRadioButton(
                modes_frame, text=mode.value,
                variable=self._mode_var, value=mode.value,
                command=self._on_mode_change,
                font=(FONT_FAMILY, FONT_SIZE_BODY),
                text_color=TEXT_PRIMARY,
                fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                border_color=BORDER_COLOR,
            ).pack(side="left", padx=(0, 24))

        ctk.CTkFrame(inner, fg_color=BORDER_COLOR, height=1).pack(fill="x", pady=(0, 10))

        # ── RTU settings ──────────────────────────────────────────────────────
        self._rtu_frame = ctk.CTkFrame(inner, fg_color="transparent")
        self._rtu_frame.pack(fill="x", pady=(0, 4))

        row1 = ctk.CTkFrame(self._rtu_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 8))

        ports = get_serial_ports()
        ctk.CTkLabel(row1, text="COM Port:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._rtu_port = ctk.CTkComboBox(
            row1, values=ports, width=110, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY,
        )
        self._rtu_port.set(ports[0] if ports else "COM1")
        self._rtu_port.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row1, text="Baud:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._rtu_baud = ctk.CTkComboBox(
            row1, values=BAUD_RATES, width=100, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY,
        )
        self._rtu_baud.set("9600")
        self._rtu_baud.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row1, text="Parity:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._rtu_parity = ctk.CTkComboBox(
            row1, values=["None (N)", "Even (E)", "Odd (O)"], width=110,
            height=INPUT_HEIGHT, font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY,
        )
        self._rtu_parity.set("None (N)")
        self._rtu_parity.pack(side="left", padx=(0, 16))

        row2 = ctk.CTkFrame(self._rtu_frame, fg_color="transparent")
        row2.pack(fill="x")

        ctk.CTkLabel(row2, text="Slave ID Range:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._rtu_start_id = ctk.CTkEntry(row2, width=60, height=INPUT_HEIGHT,
                                            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                            fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._rtu_start_id.insert(0, "1")
        self._rtu_start_id.pack(side="left")

        ctk.CTkLabel(row2, text="to", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=8)

        self._rtu_end_id = ctk.CTkEntry(row2, width=60, height=INPUT_HEIGHT,
                                          font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._rtu_end_id.insert(0, "32")
        self._rtu_end_id.pack(side="left")

        ctk.CTkLabel(row2, text="(max 247)",
                      font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(side="left", padx=8)

        ctk.CTkLabel(row2, text="Probe Timeout (s):", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(16, 6))
        self._rtu_timeout = ctk.CTkEntry(row2, width=60, height=INPUT_HEIGHT,
                                           font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                           fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._rtu_timeout.insert(0, "0.5")
        self._rtu_timeout.pack(side="left")

        # ── TCP settings ──────────────────────────────────────────────────────
        self._tcp_frame = ctk.CTkFrame(inner, fg_color="transparent")

        tcp_row1 = ctk.CTkFrame(self._tcp_frame, fg_color="transparent")
        tcp_row1.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(tcp_row1, text="IP Address:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._tcp_host = ctk.CTkEntry(tcp_row1, width=160, height=INPUT_HEIGHT,
                                        font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                        fg_color=BG_INPUT, border_color=BORDER_COLOR,
                                        placeholder_text="192.168.1.1")
        self._tcp_host.insert(0, "192.168.1.1")
        self._tcp_host.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(tcp_row1, text="Port:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._tcp_port = ctk.CTkEntry(tcp_row1, width=80, height=INPUT_HEIGHT,
                                        font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                        fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._tcp_port.insert(0, "502")
        self._tcp_port.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(tcp_row1, text="Timeout (s):", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._tcp_timeout = ctk.CTkEntry(tcp_row1, width=60, height=INPUT_HEIGHT,
                                           font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                           fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._tcp_timeout.insert(0, "1.0")
        self._tcp_timeout.pack(side="left")

        tcp_row2 = ctk.CTkFrame(self._tcp_frame, fg_color="transparent")
        tcp_row2.pack(fill="x")

        ctk.CTkLabel(tcp_row2, text="IP Scan Range (last octet):", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._net_start = ctk.CTkEntry(tcp_row2, width=60, height=INPUT_HEIGHT,
                                         font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                         fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._net_start.insert(0, "1")
        self._net_start.pack(side="left")
        ctk.CTkLabel(tcp_row2, text="to", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=8)
        self._net_end = ctk.CTkEntry(tcp_row2, width=60, height=INPUT_HEIGHT,
                                       font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._net_end.insert(0, "20")
        self._net_end.pack(side="left")
        ctk.CTkLabel(tcp_row2, text="(used for TCP Network scan only)",
                      font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(side="left", padx=8)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=(12, 0))

        self._scan_btn = make_primary_button(btn_row, "🔍  Start Scan", self._do_scan, width=150)
        self._scan_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = make_danger_button(btn_row, "⏹  Stop", self._do_stop, width=100)
        self._stop_btn.pack(side="left", padx=(0, 24))
        self._stop_btn.configure(state="disabled")

        self._progress_bar = ctk.CTkProgressBar(btn_row, width=300, height=12,
                                                  fg_color=BG_MEDIUM, progress_color=SAS_BLUE)
        self._progress_bar.pack(side="left", padx=(0, 12))
        self._progress_bar.set(0)

        self._progress_lbl = ctk.CTkLabel(btn_row, text="",
                                            font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                            text_color=TEXT_MUTED)
        self._progress_lbl.pack(side="left")

    def _build_results_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 16))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PADDING, pady=(10, 4))

        ctk.CTkLabel(hdr, text="📋  Discovered Devices",
                      font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                      text_color=TEXT_PRIMARY).pack(side="left")

        make_secondary_button(hdr, "Clear Results", self._clear_results, width=120).pack(side="right", padx=(6, 0))
        make_secondary_button(hdr, "Export CSV", self._export_results, width=110).pack(side="right")

        # Column headers
        col_hdr = ctk.CTkFrame(card, fg_color=BG_MEDIUM)
        col_hdr.pack(fill="x", padx=CARD_PADDING, pady=(0, 2))

        for text, w in [("Slave ID", 80), ("Host / Port", 160), ("Response", 100),
                          ("FC Support", 180), ("Vendor", 160), ("Product", 200)]:
            ctk.CTkLabel(col_hdr, text=text, width=w,
                          font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                          text_color=TEXT_MUTED, anchor="w").pack(side="left", padx=6, pady=4)

        # Results container (scrollable)
        self._results_scroll = ctk.CTkScrollableFrame(card, fg_color="transparent", height=280)
        self._results_scroll.pack(fill="x", padx=CARD_PADDING, pady=(0, 10))
        enable_touch_scroll(self._results_scroll)

        self._results_frame = ctk.CTkFrame(self._results_scroll, fg_color="transparent")
        self._results_frame.pack(fill="x")

        self._empty_lbl = ctk.CTkLabel(self._results_frame,
                                        text="No devices found yet. Run a scan to discover devices.",
                                        font=(FONT_FAMILY, FONT_SIZE_BODY),
                                        text_color=TEXT_MUTED)
        self._empty_lbl.pack(pady=20)

    # ── Scan Control ──────────────────────────────────────────────────────────

    def _do_scan(self):
        self._clear_results()
        self._devices.clear()
        mode_str = self._mode_var.get()

        try:
            mode = ScanMode(mode_str)
        except Exception:
            mode = ScanMode.RTU_BUS

        self._scan_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._progress_bar.set(0)
        self._progress_lbl.configure(text="Starting scan...")

        try:
            if mode == ScanMode.RTU_BUS:
                self._scanner.start_rtu_scan(
                    serial_port=self._rtu_port.get(),
                    baudrate=int(self._rtu_baud.get()),
                    parity={"None (N)": "N", "Even (E)": "E", "Odd (O)": "O"}.get(
                        self._rtu_parity.get(), "N"),
                    slave_id_start=int(self._rtu_start_id.get().strip() or "1"),
                    slave_id_end=min(247, int(self._rtu_end_id.get().strip() or "32")),
                    timeout=float(self._rtu_timeout.get().strip() or "0.5"),
                )
            elif mode == ScanMode.TCP_SINGLE:
                self._scanner.start_tcp_scan(
                    host=self._tcp_host.get().strip(),
                    port=int(self._tcp_port.get().strip() or "502"),
                    slave_id_start=1,
                    slave_id_end=10,
                    timeout=float(self._tcp_timeout.get().strip() or "1.0"),
                )
            elif mode == ScanMode.TCP_NETWORK:
                # Parse base IP from TCP host field (remove last octet)
                host = self._tcp_host.get().strip()
                parts = host.rsplit(".", 1)
                base_ip = parts[0] if len(parts) == 2 else "192.168.1"
                self._scanner.start_tcp_network_scan(
                    base_ip=base_ip,
                    start_octet=int(self._net_start.get().strip() or "1"),
                    end_octet=int(self._net_end.get().strip() or "20"),
                    port=int(self._tcp_port.get().strip() or "502"),
                    timeout=float(self._tcp_timeout.get().strip() or "0.5"),
                )
        except Exception as e:
            self._scan_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            self._progress_lbl.configure(text=f"Error: {e}", text_color=STATUS_ERROR)

    def _do_stop(self):
        self._scanner.stop_scan()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_device_found(self, device: DiscoveredModbusDevice):
        self._devices.append(device)
        self.after(0, lambda d=device: self._add_result_row(d))
        self.after(0, lambda: self._scan_count_lbl.configure(
            text=f"{len(self._devices)} device(s) found"))

    def _on_progress(self, current: int, total: int, status: str):
        pct = current / max(1, total)
        self.after(0, lambda: self._progress_bar.set(pct))
        self.after(0, lambda: self._progress_lbl.configure(
            text=f"{status}  ({current}/{total})", text_color=TEXT_MUTED))

    def _on_complete(self, devices):
        self.after(0, self._scan_complete, devices)

    def _scan_complete(self, devices):
        self._scan_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._progress_bar.set(1.0)
        count = len(devices)
        self._progress_lbl.configure(
            text=f"Scan complete — {count} device(s) found",
            text_color=STATUS_GOOD if count > 0 else TEXT_MUTED,
        )
        if count == 0 and self._empty_lbl.winfo_exists():
            self._empty_lbl.configure(text="No devices found. Check connections and settings.")

    def _on_scan_error(self, msg: str):
        self.after(0, lambda: self._progress_lbl.configure(
            text=f"Error: {msg}", text_color=STATUS_ERROR))
        self.after(0, lambda: self._scan_btn.configure(state="normal"))
        self.after(0, lambda: self._stop_btn.configure(state="disabled"))

    def _add_result_row(self, device: DiscoveredModbusDevice):
        if self._empty_lbl and self._empty_lbl.winfo_exists():
            self._empty_lbl.pack_forget()

        row = ctk.CTkFrame(self._results_frame,
                            fg_color=BG_CARD, corner_radius=4, height=36)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        # Slave ID with color indicator
        id_color = MODBUS_TCP_COLOR if device.host else MODBUS_RTU_COLOR
        ctk.CTkLabel(row, text=f"  {device.slave_id}", width=80,
                      font=(FONT_FAMILY_MONO, FONT_SIZE_BODY, "bold"),
                      text_color=id_color, anchor="w").pack(side="left")

        # Host/port
        host_str = f"{device.host}:{device.port}" if device.host else "RTU Bus"
        ctk.CTkLabel(row, text=host_str, width=160,
                      font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                      text_color=TEXT_PRIMARY, anchor="w").pack(side="left", padx=6)

        # Response time
        ctk.CTkLabel(row, text=f"{device.response_time_ms:.1f}ms", width=100,
                      font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                      text_color=STATUS_GOOD, anchor="w").pack(side="left", padx=6)

        # Supported FCs
        fc_str = ", ".join(f"FC{fc:02d}" for fc in device.supported_fc) or "FC03"
        ctk.CTkLabel(row, text=fc_str, width=180,
                      font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                      text_color=TEXT_SECONDARY, anchor="w").pack(side="left", padx=6)

        # Vendor
        ctk.CTkLabel(row, text=device.vendor or "—", width=160,
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY, anchor="w").pack(side="left", padx=6)

        # Product
        ctk.CTkLabel(row, text=device.product or "—", width=200,
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY, anchor="w").pack(side="left", padx=6)

    def _clear_results(self):
        for widget in self._results_frame.winfo_children():
            widget.destroy()
        self._empty_lbl = ctk.CTkLabel(
            self._results_frame,
            text="No devices found yet. Run a scan to discover devices.",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT_MUTED)
        self._empty_lbl.pack(pady=20)
        self._scan_count_lbl.configure(text="")
        self._devices.clear()

    def _export_results(self):
        if not self._devices:
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Export Scan Results",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("SlaveID,Host,Port,ResponseMs,SupportedFC,Vendor,Product\n")
                for d in self._devices:
                    fcs = ";".join(str(fc) for fc in d.supported_fc)
                    f.write(f"{d.slave_id},{d.host or ''},{d.port},"
                             f"{d.response_time_ms:.1f},{fcs},{d.vendor},{d.product}\n")
        except Exception as e:
            logger.error(f"Export error: {e}")

    def _on_mode_change(self):
        mode_str = self._mode_var.get()
        if mode_str == ScanMode.RTU_BUS.value:
            self._tcp_frame.pack_forget()
            self._rtu_frame.pack(fill="x", pady=(0, 4))
        else:
            self._rtu_frame.pack_forget()
            self._tcp_frame.pack(fill="x", pady=(0, 4))

    def on_show(self):
        pass
