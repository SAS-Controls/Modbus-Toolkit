"""
SAS Modbus Toolkit — Diagnostics View
Advanced diagnostic tools for troubleshooting Modbus network issues.
Includes: RTU bus health, multi-slave scanner, error analysis, timing calculator.
"""

import logging
import threading
import time
import tkinter as tk
from datetime import datetime
from typing import Optional, List

import customtkinter as ctk

from core.modbus_client import (ModbusClientWrapper, FunctionCode,
                                 EXCEPTION_CODES, BAUD_RATES)
from core.serial_utils import get_available_ports, frame_timing_analysis
from core.settings_manager import AppSettings
from ui.theme import *

logger = logging.getLogger(__name__)


class DiagnosticsView(ctk.CTkFrame):
    """Advanced diagnostics — bus health, slave scan, error analysis."""

    def __init__(self, master_widget, settings: AppSettings, **kwargs):
        super().__init__(master_widget, fg_color=BG_DARK, **kwargs)
        self._settings = settings
        self._build_ui()

    def on_show(self):
        pass

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=BG_MEDIUM, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="🔬  Network Diagnostics",
                     font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=20, pady=12)

        ctk.CTkLabel(header,
                     text="RTU Bus Health  •  Slave Discovery  •  Error Analysis  •  Timing Calculator",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(side="right", padx=20)

        # ── Tab Bar ───────────────────────────────────────────────────────────
        tab_bar = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0, height=40)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self._tab_btns: dict = {}
        tabs = [
            ("🔎  Slave Scanner", "scanner"),
            ("🩺  RTU Bus Health", "rtu_health"),
            ("⚠  Error Decoder", "errors"),
            ("⏱  Timing Calculator", "timing"),
        ]
        for label, key in tabs:
            btn = ctk.CTkButton(
                tab_bar, text=label, font=(FONT_FAMILY, FONT_SIZE_SMALL),
                fg_color="transparent", text_color=TEXT_SECONDARY,
                hover_color=BG_CARD_HOVER, height=36, corner_radius=0,
                command=lambda k=key: self._show_tab(k),
            )
            btn.pack(side="left", padx=2, pady=2)
            self._tab_btns[key] = btn

        # ── Content area ──────────────────────────────────────────────────────
        self._content = ctk.CTkFrame(self, fg_color=BG_DARK)
        self._content.pack(fill="both", expand=True)

        self._scanner_frame = self._build_slave_scanner()
        self._health_frame = self._build_rtu_health()
        self._error_frame = self._build_error_decoder()
        self._timing_frame = self._build_timing_calculator()

        self._show_tab("scanner")

    # ──────────────────────────────────────────────────────────────────────────
    # Slave Scanner tab
    # ──────────────────────────────────────────────────────────────────────────

    def _build_slave_scanner(self):
        """Scan RTU bus for all responding slave IDs (1-247)."""
        frame = ctk.CTkFrame(self._content, fg_color=BG_DARK)

        body = ctk.CTkFrame(frame, fg_color=BG_DARK)
        body.pack(fill="both", expand=True)

        # Left config
        left = ctk.CTkFrame(body, fg_color=BG_MEDIUM, width=280, corner_radius=0)
        left.pack(side="left", fill="y", padx=(0, 1))
        left.pack_propagate(False)

        scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(scroll, text="SCAN FOR SLAVES",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=16, pady=(16, 4))

        ctk.CTkLabel(scroll,
                     text="Walks slave IDs 1–247 and finds\nall devices that respond.\nWorks on RTU and TCP.",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     justify="left", anchor="w").pack(fill="x", padx=16, pady=(0, 12))

        # Protocol
        proto_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        proto_card.pack(fill="x", padx=16, pady=(0, 8))

        self._scan_proto = tk.StringVar(value="TCP")
        for label, val in [("TCP", "TCP"), ("RTU", "RTU")]:
            ctk.CTkRadioButton(
                proto_card, text=label, variable=self._scan_proto, value=val,
                font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_PRIMARY,
                fg_color=SAS_BLUE, command=self._scan_proto_change,
            ).pack(anchor="w", padx=12, pady=4)

        # TCP
        self._scan_tcp_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        self._scan_tcp_frame.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(self._scan_tcp_frame, text="IP Address",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        self._scan_host = ctk.CTkEntry(self._scan_tcp_frame, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                        fg_color=BG_INPUT, height=INPUT_HEIGHT)
        self._scan_host.insert(0, self._settings.tcp_host)
        self._scan_host.pack(fill="x", padx=12, pady=(0, 10))

        # RTU
        self._scan_rtu_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        ctk.CTkLabel(self._scan_rtu_frame, text="COM Port",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        self._scan_com = ctk.CTkComboBox(self._scan_rtu_frame, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, height=INPUT_HEIGHT, values=["COM1"])
        self._scan_com.pack(fill="x", padx=12, pady=(0, 8))

        r_baud = ctk.CTkFrame(self._scan_rtu_frame, fg_color="transparent")
        r_baud.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(r_baud, text="Baud",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._scan_baud = ctk.CTkComboBox(r_baud, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                           fg_color=BG_INPUT, height=INPUT_HEIGHT, width=100,
                                           values=[str(b) for b in BAUD_RATES])
        self._scan_baud.set("9600")
        self._scan_baud.pack(side="right")

        # ID range
        range_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        range_card.pack(fill="x", padx=16, pady=(0, 8))

        range_row = ctk.CTkFrame(range_card, fg_color="transparent")
        range_row.pack(fill="x", padx=12, pady=8)

        lc = ctk.CTkFrame(range_row, fg_color="transparent")
        lc.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkLabel(lc, text="Start ID", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_SECONDARY, anchor="w").pack(anchor="w")
        self._scan_start_id = ctk.CTkEntry(lc, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                            fg_color=BG_INPUT, height=INPUT_HEIGHT)
        self._scan_start_id.insert(0, "1")
        self._scan_start_id.pack(fill="x")

        rc = ctk.CTkFrame(range_row, fg_color="transparent")
        rc.pack(side="right", fill="x", expand=True)
        ctk.CTkLabel(rc, text="End ID", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_SECONDARY, anchor="w").pack(anchor="w")
        self._scan_end_id = ctk.CTkEntry(rc, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, height=INPUT_HEIGHT)
        self._scan_end_id.insert(0, "32")
        self._scan_end_id.pack(fill="x")

        to_row = ctk.CTkFrame(range_card, fg_color="transparent")
        to_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(to_row, text="Per-ID Timeout (s)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._scan_timeout = ctk.CTkEntry(to_row, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                           fg_color=BG_INPUT, height=INPUT_HEIGHT, width=70)
        self._scan_timeout.insert(0, "0.5")
        self._scan_timeout.pack(side="right")

        self._slave_scan_btn = ctk.CTkButton(
            scroll, text="🔍  Scan for Slaves",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
            height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._start_slave_scan,
        )
        self._slave_scan_btn.pack(fill="x", padx=16, pady=(4, 8))

        self._slave_scan_prog = ctk.CTkProgressBar(scroll, fg_color=BG_CARD,
                                                    progress_color=SAS_BLUE, height=6)
        self._slave_scan_prog.set(0)
        self._slave_scan_prog.pack(fill="x", padx=16, pady=(0, 16))

        # Right: results
        right = ctk.CTkFrame(body, fg_color=BG_DARK)
        right.pack(fill="both", expand=True)

        res_hdr = ctk.CTkFrame(right, fg_color=BG_CARD, corner_radius=0, height=36)
        res_hdr.pack(fill="x")
        res_hdr.pack_propagate(False)

        ctk.CTkLabel(res_hdr, text="  Discovered Slave Devices",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=12)
        self._found_count_var = tk.StringVar(value="")
        ctk.CTkLabel(res_hdr, textvariable=self._found_count_var,
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=STATUS_GOOD).pack(side="right", padx=12)

        col_hdr = ctk.CTkFrame(right, fg_color=BG_MEDIUM, corner_radius=0, height=26)
        col_hdr.pack(fill="x")
        col_hdr.pack_propagate(False)

        for text, w in [("Status", 80), ("Slave ID", 80), ("Response Time", 130),
                         ("FC03 Value[0]", 130), ("Notes", 250)]:
            ctk.CTkLabel(col_hdr, text=text, font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                         text_color=TEXT_MUTED, width=w, anchor="center").pack(side="left", padx=2)

        self._slave_results_scroll = ctk.CTkScrollableFrame(right, fg_color=BG_DARK, corner_radius=0)
        self._slave_results_scroll.pack(fill="both", expand=True)

        frame._scan_results = self._slave_results_scroll
        self._scan_proto_change()
        return frame

    def _scan_proto_change(self):
        proto = self._scan_proto.get()
        if proto == "TCP":
            self._scan_tcp_frame.pack(fill="x", padx=16, pady=(0, 8))
            self._scan_rtu_frame.pack_forget()
        else:
            self._scan_tcp_frame.pack_forget()
            self._scan_rtu_frame.pack(fill="x", padx=16, pady=(0, 8))

    def _start_slave_scan(self):
        """Scan for responding slave IDs."""
        # Clear results
        for w in self._slave_results_scroll.winfo_children():
            w.destroy()

        try:
            start_id = int(self._scan_start_id.get())
            end_id = int(self._scan_end_id.get())
            timeout = float(self._scan_timeout.get())
        except ValueError:
            return

        proto = self._scan_proto.get()
        client = ModbusClientWrapper()

        connected = False
        if proto == "TCP":
            host = self._scan_host.get().strip()
            connected = client.connect_tcp(host, 502, timeout)
        else:
            com = self._scan_com.get()
            try:
                baud = int(self._scan_baud.get())
            except ValueError:
                baud = 9600
            connected = client.connect_rtu(com, baud, timeout=timeout)

        if not connected:
            self._add_scan_result(None, None, None, "❌ Connection failed")
            return

        self._found_count_var.set("Scanning...")
        self._slave_scan_prog.set(0)
        found = [0]
        total = end_id - start_id + 1

        def scan_thread():
            for uid in range(start_id, end_id + 1):
                result = client.execute(FunctionCode.READ_HOLDING_REGISTERS, uid, 0, 1)
                pct = (uid - start_id + 1) / total
                self.after(0, lambda p=pct: self._slave_scan_prog.set(p))

                if result.success:
                    found[0] += 1
                    val = result.values[0] if result.values else 0
                    self.after(0, lambda u=uid, rt=result.response_time_ms, v=val:
                               self._add_scan_result(u, rt, v, "Device found"))
                elif result.exception_code:
                    # Exception means device IS there, just rejected the read
                    found[0] += 1
                    exc = EXCEPTION_CODES.get(result.exception_code, "Unknown exception")
                    self.after(0, lambda u=uid, rt=result.response_time_ms, ec=result.exception_code, ex=exc:
                               self._add_scan_result(u, rt, None,
                                                     f"Responds (Exception {ec}: {ex})"))

            client.disconnect()
            self.after(0, lambda: self._found_count_var.set(
                f"✓ Found {found[0]} device(s)"))

        threading.Thread(target=scan_thread, daemon=True).start()

    def _add_scan_result(self, slave_id, response_ms, first_val, note: str):
        row_bg = BG_CARD if len(self._slave_results_scroll.winfo_children()) % 2 == 0 else BG_DARK
        row = ctk.CTkFrame(self._slave_results_scroll, fg_color=row_bg,
                            corner_radius=0, height=30)
        row.pack(fill="x")
        row.pack_propagate(False)

        ok = slave_id is not None and response_ms is not None
        ctk.CTkLabel(row, text="●  Found" if ok else "—",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=STATUS_GOOD if ok else TEXT_MUTED,
                     width=80, anchor="center").pack(side="left", padx=2)

        ctk.CTkLabel(row, text=str(slave_id) if slave_id is not None else "—",
                     font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                     text_color=TEXT_PRIMARY, width=80, anchor="center").pack(side="left", padx=2)

        ctk.CTkLabel(row, text=f"{response_ms:.1f}ms" if response_ms is not None else "—",
                     font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                     text_color=TEXT_SECONDARY, width=130, anchor="center").pack(side="left", padx=2)

        ctk.CTkLabel(row, text=str(first_val) if first_val is not None else "—",
                     font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                     text_color=TEXT_MUTED, width=130, anchor="center").pack(side="left", padx=2)

        ctk.CTkLabel(row, text=note, font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_SECONDARY, width=250, anchor="w").pack(side="left", padx=8)

    # ──────────────────────────────────────────────────────────────────────────
    # RTU Bus Health tab
    # ──────────────────────────────────────────────────────────────────────────

    def _build_rtu_health(self):
        """Build RTU bus health check panel."""
        frame = ctk.CTkFrame(self._content, fg_color=BG_DARK)

        body = ctk.CTkFrame(frame, fg_color=BG_DARK)
        body.pack(fill="both", expand=True)

        left = ctk.CTkFrame(body, fg_color=BG_MEDIUM, width=290, corner_radius=0)
        left.pack(side="left", fill="y", padx=(0, 1))
        left.pack_propagate(False)

        scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(scroll, text="RTU BUS HEALTH CHECK",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=16, pady=(16, 4))

        ctk.CTkLabel(scroll,
                     text="Runs a burst of requests to a device\n"
                          "and analyzes response quality:\n"
                          "• Response time statistics\n"
                          "• Timeout rate\n"
                          "• Exception frequency\n"
                          "• Bus stability score",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     justify="left", anchor="w").pack(fill="x", padx=16, pady=(0, 12))

        # Connection
        conn_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        conn_card.pack(fill="x", padx=16, pady=(0, 8))

        self._health_proto = tk.StringVar(value="TCP")
        for label, val in [("TCP", "TCP"), ("RTU", "RTU")]:
            ctk.CTkRadioButton(
                conn_card, text=label, variable=self._health_proto, value=val,
                font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_PRIMARY,
                fg_color=SAS_BLUE,
            ).pack(anchor="w", padx=12, pady=4)

        ctk.CTkLabel(conn_card, text="Target IP / COM",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12)
        self._health_host = ctk.CTkEntry(conn_card, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, height=INPUT_HEIGHT)
        self._health_host.insert(0, self._settings.tcp_host)
        self._health_host.pack(fill="x", padx=12, pady=(2, 8))

        row_sid = ctk.CTkFrame(conn_card, fg_color="transparent")
        row_sid.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row_sid, text="Slave ID",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._health_sid = ctk.CTkEntry(row_sid, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                         fg_color=BG_INPUT, height=INPUT_HEIGHT, width=70)
        self._health_sid.insert(0, "1")
        self._health_sid.pack(side="right")

        # Test config
        test_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        test_card.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(test_card, text="TEST PARAMETERS",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=12, pady=(8, 4))

        row_cnt = ctk.CTkFrame(test_card, fg_color="transparent")
        row_cnt.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(row_cnt, text="Request Count",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._health_count = ctk.CTkEntry(row_cnt, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                           fg_color=BG_INPUT, height=INPUT_HEIGHT, width=80)
        self._health_count.insert(0, "100")
        self._health_count.pack(side="right")

        row_itv = ctk.CTkFrame(test_card, fg_color="transparent")
        row_itv.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row_itv, text="Interval (ms)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._health_interval = ctk.CTkEntry(row_itv, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                              fg_color=BG_INPUT, height=INPUT_HEIGHT, width=80)
        self._health_interval.insert(0, "50")
        self._health_interval.pack(side="right")

        self._health_btn = ctk.CTkButton(
            scroll, text="▶  Run Health Check",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
            height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._run_health_check,
        )
        self._health_btn.pack(fill="x", padx=16, pady=(4, 8))

        self._health_prog = ctk.CTkProgressBar(scroll, fg_color=BG_CARD,
                                                progress_color=SAS_BLUE, height=6)
        self._health_prog.set(0)
        self._health_prog.pack(fill="x", padx=16, pady=(0, 16))

        # Results panel
        right = ctk.CTkFrame(body, fg_color=BG_DARK)
        right.pack(fill="both", expand=True, padx=16, pady=16)

        # Score card
        score_row = ctk.CTkFrame(right, fg_color="transparent")
        score_row.pack(fill="x", pady=(0, 12))

        self._health_score_lbl = ctk.CTkLabel(
            score_row, text="—",
            font=(FONT_FAMILY, 64, "bold"), text_color=TEXT_MUTED)
        self._health_score_lbl.pack(side="left", padx=(0, 20))

        self._health_grade_lbl = ctk.CTkLabel(
            score_row, text="Run a health check\nto analyze bus quality",
            font=(FONT_FAMILY, FONT_SIZE_SUBHEADING),
            text_color=TEXT_MUTED, justify="left")
        self._health_grade_lbl.pack(side="left")

        # Stat cards
        stats_grid = ctk.CTkFrame(right, fg_color="transparent")
        stats_grid.pack(fill="x", pady=(0, 12))

        self._health_stats: dict = {}
        stat_defs = [
            ("Total Requests", "total", TEXT_SECONDARY),
            ("Successful", "success", STATUS_GOOD),
            ("Timeouts", "timeouts", STATUS_ERROR),
            ("Exceptions", "exceptions", STATUS_WARN),
            ("Min Response", "min_rt", TEXT_SECONDARY),
            ("Avg Response", "avg_rt", SAS_BLUE_LIGHT),
            ("Max Response", "max_rt", STATUS_WARN),
            ("Error Rate", "err_rate", STATUS_ERROR),
        ]
        for i, (label, key, color) in enumerate(stat_defs):
            card = ctk.CTkFrame(stats_grid, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
            card.grid(row=i // 4, column=i % 4, padx=4, pady=4, sticky="ew")
            stats_grid.columnconfigure(i % 4, weight=1)

            ctk.CTkLabel(card, text=label, font=(FONT_FAMILY, FONT_SIZE_TINY),
                         text_color=TEXT_MUTED).pack(pady=(6, 2))
            val_var = tk.StringVar(value="—")
            ctk.CTkLabel(card, textvariable=val_var,
                         font=(FONT_FAMILY, FONT_SIZE_HEADING, "bold"),
                         text_color=color).pack(pady=(0, 6))
            self._health_stats[key] = val_var

        # Findings/recommendations
        ctk.CTkLabel(right, text="Findings & Recommendations",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(8, 4))

        self._health_findings = tk.Text(
            right, font=(FONT_FAMILY, FONT_SIZE_SMALL),
            bg=resolve_color(BG_CARD), fg=resolve_color(TEXT_SECONDARY),
            relief="flat", bd=0, state="disabled", height=8, wrap="word",
        )
        self._health_findings.pack(fill="x")
        self._health_findings.tag_config("good", foreground=STATUS_GOOD)
        self._health_findings.tag_config("warn", foreground=STATUS_WARN)
        self._health_findings.tag_config("error", foreground=STATUS_ERROR)
        self._health_findings.tag_config("info", foreground=SAS_BLUE_LIGHT)

        return frame

    def _run_health_check(self):
        """Run the RTU bus health check in a background thread."""
        try:
            count = int(self._health_count.get())
            interval_ms = int(self._health_interval.get())
            slave_id = int(self._health_sid.get())
        except ValueError:
            return

        proto = self._health_proto.get()
        client = ModbusClientWrapper()

        connected = False
        if proto == "TCP":
            host = self._health_host.get().strip()
            connected = client.connect_tcp(host, 502, 2.0)
        else:
            com = self._health_host.get().strip()
            connected = client.connect_rtu(com, 9600, timeout=1.0)

        if not connected:
            self._write_finding("❌ Could not connect to device\n", "error")
            return

        self._health_btn.configure(state="disabled")
        self._health_prog.set(0)

        def test_thread():
            response_times = []
            timeouts = 0
            exceptions = 0
            success = 0

            for i in range(count):
                result = client.execute(FunctionCode.READ_HOLDING_REGISTERS, slave_id, 0, 1)
                pct = (i + 1) / count
                self.after(0, lambda p=pct: self._health_prog.set(p))

                if result.success:
                    success += 1
                    response_times.append(result.response_time_ms)
                elif result.exception_code:
                    exceptions += 1
                    response_times.append(result.response_time_ms)
                else:
                    timeouts += 1

                time.sleep(interval_ms / 1000)

            client.disconnect()
            self.after(0, lambda: self._display_health_results(
                count, success, timeouts, exceptions, response_times))

        threading.Thread(target=test_thread, daemon=True).start()

    def _display_health_results(self, total, success, timeouts, exceptions, response_times):
        """Display health check results and generate findings."""
        self._health_btn.configure(state="normal")

        err_rate = ((timeouts + exceptions) / total * 100) if total else 0
        avg_rt = sum(response_times) / len(response_times) if response_times else 0
        min_rt = min(response_times) if response_times else 0
        max_rt = max(response_times) if response_times else 0

        # Calculate health score (0-100)
        score = 100
        score -= min(50, int(err_rate * 2))
        if avg_rt > 500:
            score -= 20
        elif avg_rt > 200:
            score -= 10
        if max_rt > 2000:
            score -= 10
        score = max(0, score)

        # Determine grade
        if score >= 90:
            grade = "Excellent"; color = STATUS_GOOD
        elif score >= 70:
            grade = "Good"; color = STATUS_GOOD
        elif score >= 50:
            grade = "Fair"; color = STATUS_WARN
        elif score >= 30:
            grade = "Poor"; color = SAS_ORANGE
        else:
            grade = "Critical"; color = STATUS_ERROR

        self._health_score_lbl.configure(text=str(score), text_color=color)
        self._health_grade_lbl.configure(text=f"{grade} — Bus Health Score", text_color=color)

        self._health_stats["total"].set(str(total))
        self._health_stats["success"].set(str(success))
        self._health_stats["timeouts"].set(str(timeouts))
        self._health_stats["exceptions"].set(str(exceptions))
        self._health_stats["min_rt"].set(f"{min_rt:.1f}ms")
        self._health_stats["avg_rt"].set(f"{avg_rt:.1f}ms")
        self._health_stats["max_rt"].set(f"{max_rt:.1f}ms")
        self._health_stats["err_rate"].set(f"{err_rate:.1f}%")

        # Generate findings
        self._health_findings.configure(state="normal")
        self._health_findings.delete("1.0", "end")
        findings = []

        if err_rate == 0:
            findings.append(("✓ No errors detected — all requests answered successfully.\n", "good"))
        elif err_rate <= 1:
            findings.append((f"⚠  Low error rate ({err_rate:.1f}%) — likely acceptable, monitor for increase.\n", "warn"))
        elif err_rate <= 10:
            findings.append((f"⚠  Moderate error rate ({err_rate:.1f}%) — check cable connections, termination resistors, and ground loops.\n", "warn"))
        else:
            findings.append((f"❌ High error rate ({err_rate:.1f}%) — check wiring, cable distance, baud rate settings, and device power.\n", "error"))

        if timeouts > 0:
            findings.append((f"⚠  {timeouts} timeout(s) — device not responding. Check: power, slave ID, baud rate match.\n", "warn"))

        if exceptions > 0:
            findings.append((f"ℹ  {exceptions} exception(s) — device IS reachable but returning errors. See Error Decoder tab.\n", "info"))

        if avg_rt > 500:
            findings.append(("⚠  High average response time — reduce baud rate, check for bus overload or long cable runs.\n", "warn"))
        elif avg_rt < 50:
            findings.append(("✓ Fast response times — bus is healthy and lightly loaded.\n", "good"))

        if max_rt > avg_rt * 3:
            findings.append(("⚠  Inconsistent response times — possible bus contention or interference. Check for other masters on the network.\n", "warn"))

        for text, tag in findings:
            self._health_findings.insert("end", text, tag)

        self._health_findings.configure(state="disabled")

    # ──────────────────────────────────────────────────────────────────────────
    # Error Decoder tab
    # ──────────────────────────────────────────────────────────────────────────

    def _build_error_decoder(self):
        """Build the error decoder and reference panel."""
        frame = ctk.CTkFrame(self._content, fg_color=BG_DARK)

        scroll = ctk.CTkScrollableFrame(frame, fg_color=BG_DARK)
        scroll.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(scroll, text="Modbus Exception Code Reference",
                     font=(FONT_FAMILY, FONT_SIZE_HEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(scroll,
                     text="When a slave device can't process a request, it returns an exception response.\n"
                          "The function code in the response will have bit 7 set (FC + 0x80).\n"
                          "The exception code byte explains why the request was rejected.",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     justify="left", anchor="w").pack(fill="x", pady=(0, 16))

        # Exception code cards
        for code, description in EXCEPTION_CODES.items():
            card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
            card.pack(fill="x", pady=(0, 6))

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(8, 4))

            ctk.CTkLabel(top, text=f"Exception Code {code} (0x{code:02X})",
                         font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                         text_color=SAS_ORANGE).pack(side="left")

            ctk.CTkLabel(card, text=description,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w",
                         justify="left").pack(fill="x", padx=12)

            # Add tips for common codes
            tips = {
                2: "💡 Tip: Check your register address. Many devices use 0-based or 1-based addressing — try subtracting 1 from your address.",
                3: "💡 Tip: Verify the data type range. Some registers only accept specific values (e.g. 0/1 for booleans).",
                6: "💡 Tip: Device is busy — reduce your polling rate or increase the delay between requests.",
                1: "💡 Tip: Verify the device supports this function code. Check the device's Modbus register map documentation.",
            }
            if code in tips:
                ctk.CTkLabel(card, text=tips[code],
                             font=(FONT_FAMILY, FONT_SIZE_SMALL),
                             text_color=SAS_BLUE_LIGHT, anchor="w",
                             justify="left").pack(fill="x", padx=12, pady=(4, 0))

            ctk.CTkFrame(card, fg_color="transparent", height=4).pack()

        # Common issues section
        ctk.CTkFrame(scroll, fg_color=BORDER_COLOR, height=1).pack(fill="x", pady=12)
        ctk.CTkLabel(scroll, text="Common Commissioning Issues",
                     font=(FONT_FAMILY, FONT_SIZE_HEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 8))

        issues = [
            ("No response from any device",
             "STATUS_ERROR",
             "• Verify baud rate matches the device setting\n"
             "• Check parity and stop bits (most common: 8N1 or 8E1)\n"
             "• Confirm cable wiring: A(+) and B(-) not swapped\n"
             "• Ensure termination resistor (120Ω) is installed at both ends of RS485 bus\n"
             "• Verify the device is powered and in Modbus RTU mode"),

            ("Some devices respond, some don't",
             "STATUS_WARN",
             "• Each device must have a unique slave ID (1-247)\n"
             "• Check for ID conflicts — two devices with same ID will collide\n"
             "• Inspect stub cables — long branches cause reflections on RS485\n"
             "• Check for missing bias resistors on long networks"),

            ("Intermittent errors",
             "STATUS_WARN",
             "• Look for ground loops between devices — install isolation if needed\n"
             "• Check for electrical noise sources (VFDs, contactors) near the cable\n"
             "• Verify cable shielding is grounded at one end only\n"
             "• Try reducing baud rate (e.g. 19200 → 9600)"),

            ("Device responds but returns wrong values",
             "STATUS_INFO",
             "• Verify register addressing — some devices use 0-based (0-9999), others 1-based (1-10000)\n"
             "• Check data type: register might be a float32 split across two registers\n"
             "• Confirm byte order / word order for multi-register values (big-endian vs little-endian)\n"
             "• Review the device's Modbus map documentation"),
        ]

        for title, severity, body in issues:
            issue_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
            issue_card.pack(fill="x", pady=(0, 6))

            severity_color = {"STATUS_ERROR": STATUS_ERROR, "STATUS_WARN": STATUS_WARN,
                              "STATUS_INFO": SAS_BLUE_LIGHT}.get(severity, TEXT_SECONDARY)

            ctk.CTkLabel(issue_card, text=f"⚠  {title}",
                         font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                         text_color=severity_color, anchor="w").pack(fill="x", padx=12, pady=(8, 4))
            ctk.CTkLabel(issue_card, text=body,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w", justify="left").pack(
                fill="x", padx=12, pady=(0, 10))

        return frame

    # ──────────────────────────────────────────────────────────────────────────
    # Timing Calculator tab
    # ──────────────────────────────────────────────────────────────────────────

    def _build_timing_calculator(self):
        """Build RTU timing reference calculator."""
        frame = ctk.CTkFrame(self._content, fg_color=BG_DARK)

        scroll = ctk.CTkScrollableFrame(frame, fg_color=BG_DARK)
        scroll.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(scroll, text="Modbus RTU Timing Calculator",
                     font=(FONT_FAMILY, FONT_SIZE_HEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(scroll,
                     text="Modbus RTU uses silent gaps between frames to identify message boundaries.\n"
                          "Inter-frame gap (T3.5) = 3.5 character times. "
                          "Inter-character gap (T1.5) = 1.5 character times.\n"
                          "Incorrect timing is a common cause of framing errors on slow baud rates.",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     justify="left", anchor="w").pack(fill="x", pady=(0, 16))

        # Baud selector
        baud_row = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        baud_row.pack(fill="x", pady=(0, 16))

        inner = ctk.CTkFrame(baud_row, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(inner, text="Select Baud Rate",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")

        self._timing_baud = ctk.CTkSegmentedButton(
            inner, values=["1200", "2400", "4800", "9600", "19200", "38400", "115200"],
            font=(FONT_FAMILY, FONT_SIZE_SMALL), fg_color=BG_INPUT,
            selected_color=SAS_BLUE, command=self._update_timing_display,
        )
        self._timing_baud.set("9600")
        self._timing_baud.pack(side="right")

        # Results
        self._timing_results_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self._timing_results_frame.pack(fill="x")

        self._update_timing_display("9600")
        return frame

    def _update_timing_display(self, baud_str: str):
        """Update timing calculator results."""
        try:
            baud = int(baud_str)
        except ValueError:
            return

        timing = frame_timing_analysis(baud)

        for w in self._timing_results_frame.winfo_children():
            w.destroy()

        metrics = [
            ("1 Character Time", f"{timing['char_time_us']:.1f} µs",
             "Time to transmit one character (11 bits at this baud rate)"),
            ("T1.5 — Inter-Character Timeout", f"{timing['t15_us']:.1f} µs",
             "Gap within a frame — if exceeded, assume frame is complete"),
            ("T3.5 — Inter-Frame Gap", f"{timing['t35_ms']:.3f} ms",
             "Silent time required between complete frames on the bus"),
            ("Typical Request Frame (8 bytes)", f"{timing['typical_request_ms']:.2f} ms",
             "FC03 request: Addr(1) + FC(1) + Start(2) + Count(2) + CRC(2)"),
            ("Typical Response (25 bytes)", f"{timing['typical_response_ms']:.2f} ms",
             "FC03 response with ~10 registers of data"),
        ]

        for label, value, desc in metrics:
            card = ctk.CTkFrame(self._timing_results_frame, fg_color=BG_CARD,
                                corner_radius=CARD_CORNER_RADIUS)
            card.pack(fill="x", pady=(0, 6))

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=8)

            ctk.CTkLabel(row, text=label,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
            ctk.CTkLabel(row, text=value,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_SUBHEADING, "bold"),
                         text_color=SAS_BLUE_LIGHT).pack(side="right")

            ctk.CTkLabel(card, text=f"  {desc}",
                         font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED,
                         anchor="w").pack(fill="x", padx=12, pady=(0, 6))

        # Recommendation
        note_card = ctk.CTkFrame(self._timing_results_frame, fg_color=BG_MEDIUM,
                                  corner_radius=CARD_CORNER_RADIUS)
        note_card.pack(fill="x", pady=(8, 0))

        note = (f"💡 At {baud:,} baud, set your master's response timeout to at least "
                f"{timing['t35_ms'] * 10:.0f}ms to allow for propagation and processing time.\n"
                f"For long cable runs (>500m) or multi-drop networks, double this value.")
        if baud > 19200:
            note += "\n\nNote: Above 19,200 baud, Modbus spec mandates fixed 1.75ms inter-frame gap regardless of baud rate."

        ctk.CTkLabel(note_card, text=note,
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     justify="left", anchor="w", wraplength=700).pack(padx=12, pady=10)

    # ──────────────────────────────────────────────────────────────────────────
    # Tab management
    # ──────────────────────────────────────────────────────────────────────────

    def _show_tab(self, key: str):
        for frame in [self._scanner_frame, self._health_frame,
                      self._error_frame, self._timing_frame]:
            frame.pack_forget()

        active = {
            "scanner": self._scanner_frame, "rtu_health": self._health_frame,
            "errors": self._error_frame, "timing": self._timing_frame,
        }.get(key)

        if active:
            active.pack(fill="both", expand=True)

        for k, btn in self._tab_btns.items():
            btn.configure(
                fg_color=BG_CARD if k == key else "transparent",
                text_color=SAS_BLUE_LIGHT if k == key else TEXT_SECONDARY,
            )

    def _write_finding(self, text: str, tag: str = "info"):
        self._health_findings.configure(state="normal")
        self._health_findings.insert("end", text, tag)
        self._health_findings.configure(state="disabled")
