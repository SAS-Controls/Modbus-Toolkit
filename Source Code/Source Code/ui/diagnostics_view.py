"""
SAS Modbus Toolkit — Network Diagnostics View
Advanced network health monitoring with response time charts,
error pattern analysis, and actionable troubleshooting recommendations.
"""

import logging
import threading
import time
import tkinter as tk
from datetime import datetime
from typing import List, Optional

import customtkinter as ctk

from core.modbus_master import ConnectionConfig, ConnectionMode, ModbusMasterEngine, PollConfig, TransactionRecord
from core.diagnostics import NetworkHealthMonitor, Severity
from ui.theme import *
from ui.widgets import (
    LogBox, MiniSparkline, HealthScoreWidget,
    get_serial_ports, make_card, make_primary_button,
    make_secondary_button, make_danger_button, enable_touch_scroll,
    resolve_color,
)

logger = logging.getLogger(__name__)

BAUD_RATES = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]

SEVERITY_ICONS = {
    Severity.PASS: ("✓", STATUS_GOOD),
    Severity.INFO: ("ℹ", STATUS_INFO),
    Severity.WARN: ("⚠", STATUS_WARN),
    Severity.FAIL: ("✗", STATUS_ERROR),
}


class DiagnosticsView(ctk.CTkFrame):
    """Advanced diagnostics view for Modbus network health analysis."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._engine = ModbusMasterEngine()
        self._health = NetworkHealthMonitor()
        self._engine.on_transaction = self._on_transaction
        self._engine.on_connected = self._on_connected
        self._engine.on_disconnected = self._on_disconnected

        self._running = False
        self._update_job = None

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=50)
        hdr.pack(fill="x", padx=24, pady=(16, 4))
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="🩺  Network Diagnostics",
                     font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(side="left")

        self._status_badge = ctk.CTkLabel(
            hdr, text="⬤  Idle",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            text_color=STATUS_OFFLINE,
        )
        self._status_badge.pack(side="right", padx=8)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True)
        enable_touch_scroll(self._scroll)

        self._build_connection_card()
        self._build_metrics_row()
        self._build_chart_card()
        self._build_findings_card()
        self._build_ref_card()

    def _build_connection_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(4, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=10)

        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(row1, text="Protocol:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._proto_var = ctk.StringVar(value="TCP")
        self._proto_seg = ctk.CTkSegmentedButton(
            row1, values=["TCP", "RTU"],
            variable=self._proto_var,
            command=self._on_proto_change,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            selected_color=SAS_BLUE, selected_hover_color=SAS_BLUE_DARK,
        )
        self._proto_seg.pack(side="left", padx=(0, 24))

        ctk.CTkLabel(row1, text="Slave ID:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._slave_id = ctk.CTkEntry(row1, width=60, height=INPUT_HEIGHT,
                                      font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                      fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._slave_id.insert(0, "1")
        self._slave_id.pack(side="left", padx=(0, 24))

        ctk.CTkLabel(row1, text="Poll Interval (s):", font=(FONT_FAMILY, FONT_SIZE_BODY),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._interval = ctk.CTkEntry(row1, width=60, height=INPUT_HEIGHT,
                                      font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                      fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._interval.insert(0, "0.5")
        self._interval.pack(side="left", padx=(0, 24))

        ctk.CTkLabel(row1, text="Timeout (s):", font=(FONT_FAMILY, FONT_SIZE_BODY),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._timeout_e = ctk.CTkEntry(row1, width=60, height=INPUT_HEIGHT,
                                       font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._timeout_e.insert(0, "1.0")
        self._timeout_e.pack(side="left", padx=(0, 24))

        self._start_btn = make_primary_button(row1, "▶  Start Test", self._do_start, width=140)
        self._start_btn.pack(side="left", padx=(0, 6))

        self._stop_btn = make_danger_button(row1, "⏹  Stop", self._do_stop, width=100)
        self._stop_btn.pack(side="left", padx=(0, 12))
        self._stop_btn.configure(state="disabled")

        make_secondary_button(row1, "⟳  Reset Stats", self._reset_stats, width=110).pack(side="left")

        # TCP row
        self._tcp_frame = ctk.CTkFrame(inner, fg_color="transparent")
        self._tcp_frame.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(self._tcp_frame, text="IP Address:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._tcp_host = ctk.CTkEntry(self._tcp_frame, width=160, height=INPUT_HEIGHT,
                                      font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                      fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._tcp_host.insert(0, "192.168.1.1")
        self._tcp_host.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(self._tcp_frame, text="Port:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._tcp_port = ctk.CTkEntry(self._tcp_frame, width=80, height=INPUT_HEIGHT,
                                      font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                      fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._tcp_port.insert(0, "502")
        self._tcp_port.pack(side="left")

        # RTU row
        self._rtu_frame = ctk.CTkFrame(inner, fg_color="transparent")
        ports = get_serial_ports()

        for label_text, widget_factory in [
            ("COM Port:", lambda p: self._make_port_combo(p, ports)),
            ("Baud Rate:", lambda p: self._make_baud_combo(p)),
            ("Parity:", lambda p: self._make_parity_combo(p)),
        ]:
            ctk.CTkLabel(self._rtu_frame, text=label_text,
                         font=(FONT_FAMILY, FONT_SIZE_BODY),
                         text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
            widget_factory(self._rtu_frame).pack(side="left", padx=(0, 16))

    def _make_port_combo(self, parent, ports):
        self._rtu_port = ctk.CTkComboBox(parent, values=ports, width=110, height=INPUT_HEIGHT,
                                          font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, border_color=BORDER_COLOR,
                                          button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
                                          dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY)
        self._rtu_port.set(ports[0] if ports else "COM1")
        return self._rtu_port

    def _make_baud_combo(self, parent):
        self._rtu_baud = ctk.CTkComboBox(parent, values=BAUD_RATES, width=100, height=INPUT_HEIGHT,
                                          font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, border_color=BORDER_COLOR,
                                          button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
                                          dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY)
        self._rtu_baud.set("9600")
        return self._rtu_baud

    def _make_parity_combo(self, parent):
        self._rtu_parity = ctk.CTkComboBox(parent,
                                            values=["None (N)", "Even (E)", "Odd (O)"],
                                            width=110, height=INPUT_HEIGHT,
                                            font=(FONT_FAMILY, FONT_SIZE_BODY),
                                            fg_color=BG_INPUT, border_color=BORDER_COLOR,
                                            button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
                                            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY)
        self._rtu_parity.set("None (N)")
        return self._rtu_parity

    def _build_metrics_row(self):
        """KPI metric cards + health score."""
        row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(0, 4))

        def metric_card(title, value, color, unit=""):
            card = make_card(row)
            card.pack(side="left", fill="both", expand=True, padx=(0, 6))
            ctk.CTkLabel(card, text=title,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_MUTED).pack(pady=(10, 0))
            lbl = ctk.CTkLabel(card, text=value,
                               font=(FONT_FAMILY, 26, "bold"),
                               text_color=color)
            lbl.pack()
            ctk.CTkLabel(card, text=unit,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_MUTED).pack(pady=(0, 10))
            return lbl

        self._lbl_total   = metric_card("Transactions", "0",  TEXT_PRIMARY)
        self._lbl_success = metric_card("Success Rate", "—",  STATUS_GOOD,    "%")
        self._lbl_errors  = metric_card("Errors",       "0",  STATUS_ERROR)
        self._lbl_timeout = metric_card("Timeouts",     "0",  STATUS_WARN)
        self._lbl_avg     = metric_card("Avg Response", "—",  SAS_BLUE_LIGHT, "ms")
        self._lbl_max     = metric_card("Max Response", "—",  TEXT_SECONDARY, "ms")
        self._lbl_jitter  = metric_card("Jitter (σ)",   "—",  TEXT_SECONDARY, "ms")

        self._health_widget = HealthScoreWidget(row, width=120)
        self._health_widget.pack(side="left", fill="both")

    def _build_chart_card(self):
        """Response time sparkline + error rate bar."""
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=12)

        # Response time chart
        ctk.CTkLabel(inner, text="Response Time — Last 60 Samples  (ms)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", pady=(0, 4))

        self._sparkline = MiniSparkline(inner, width=900, height=60,
                                        line_color=SAS_BLUE_LIGHT)
        self._sparkline.pack(fill="x", pady=(0, 8))

        # Error timeline — colored dots
        ctk.CTkLabel(inner, text="Error Timeline  (green = OK, red = error)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", pady=(0, 4))

        self._error_canvas = tk.Canvas(
            inner, height=20,
            bg=resolve_color(BG_CARD),
            highlightthickness=0,
        )
        self._error_canvas.pack(fill="x")

    def _build_findings_card(self):
        """Diagnostic findings panel."""
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 4))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PADDING, pady=(10, 4))

        ctk.CTkLabel(hdr, text="🔬  Diagnostic Findings",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")

        make_primary_button(hdr, "⟳  Analyze Now", self._run_analysis, width=130).pack(side="right")
        make_secondary_button(hdr, "Export Report", self._export_report, width=120).pack(side="right", padx=(0, 8))

        self._findings_frame = ctk.CTkScrollableFrame(card, fg_color="transparent", height=260)
        self._findings_frame.pack(fill="x", padx=CARD_PADDING, pady=(0, 10))
        enable_touch_scroll(self._findings_frame)

        self._no_findings_lbl = ctk.CTkLabel(
            self._findings_frame,
            text="No analysis yet — connect to a device and run a test, then click Analyze Now.",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT_MUTED,
        )
        self._no_findings_lbl.pack(pady=20)

    def _build_ref_card(self):
        """Quick Modbus reference card."""
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 16))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PADDING, pady=(10, 4))

        ctk.CTkLabel(hdr, text="📖  Modbus Exception Code Reference",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")

        ref_frame = ctk.CTkFrame(card, fg_color="transparent")
        ref_frame.pack(fill="x", padx=CARD_PADDING, pady=(0, 12))

        exceptions = [
            ("01", "Illegal Function",               "FC not supported by this device"),
            ("02", "Illegal Data Address",            "Register address out of range"),
            ("03", "Illegal Data Value",              "Value out of allowed range"),
            ("04", "Slave Device Failure",            "Internal device error — cycle power"),
            ("05", "Acknowledge",                     "Request accepted, needs more time"),
            ("06", "Slave Device Busy",               "Device busy — reduce poll rate"),
            ("08", "Memory Parity Error",             "Hardware fault on slave device"),
            ("0A", "Gateway Path Unavailable",        "Gateway cannot reach target"),
            ("0B", "Gateway Target No Response",      "Target device on gateway not responding"),
        ]

        cols = 3
        for i, (code, name, meaning) in enumerate(exceptions):
            col = i % cols
            row = i // cols
            cell = ctk.CTkFrame(ref_frame, fg_color=BG_MEDIUM, corner_radius=6)
            cell.grid(row=row, column=col, padx=4, pady=3, sticky="ew")
            ref_frame.columnconfigure(col, weight=1)

            ctk.CTkLabel(cell, text=f"0x{code}",
                         font=(FONT_FAMILY_MONO, FONT_SIZE_BODY, "bold"),
                         text_color=STATUS_WARN).pack(side="left", padx=(8, 6), pady=6)
            inner = ctk.CTkFrame(cell, fg_color="transparent")
            inner.pack(side="left", fill="x", expand=True, pady=6)
            ctk.CTkLabel(inner, text=name,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                         text_color=TEXT_PRIMARY, anchor="w").pack(fill="x")
            ctk.CTkLabel(inner, text=meaning,
                         font=(FONT_FAMILY, FONT_SIZE_TINY),
                         text_color=TEXT_MUTED, anchor="w").pack(fill="x")

    # ── Test Control ──────────────────────────────────────────────────────────

    def _do_start(self):
        if not self._engine.is_connected:
            config = self._build_config()
            if not config:
                return
            self._start_btn.configure(state="disabled", text="Connecting...")

            def _connect():
                ok, msg = self._engine.connect(config)
                if ok:
                    self.after(0, self._begin_polling)
                else:
                    self.after(0, lambda: self._start_btn.configure(
                        state="normal", text="▶  Start Test"))
            threading.Thread(target=_connect, daemon=True).start()
        else:
            self._begin_polling()

    def _begin_polling(self):
        try:
            sid = int(self._slave_id.get().strip() or "1")
            interval = float(self._interval.get().strip() or "0.5")
        except Exception:
            sid, interval = 1, 0.5

        poll = [PollConfig(row_id=0, address=0, count=10,
                           function_code=3, label="Diagnostic Poll")]
        self._engine.start_polling(poll, interval=interval, slave_id=sid)
        self._running = True
        self._start_btn.configure(state="disabled", text="▶  Running...")
        self._stop_btn.configure(state="normal")
        self._status_badge.configure(text="⬤  Running", text_color=STATUS_GOOD)
        self._schedule_ui_update()

    def _do_stop(self):
        self._engine.stop_polling()
        self._running = False
        self._start_btn.configure(state="normal", text="▶  Start Test")
        self._stop_btn.configure(state="disabled")
        self._status_badge.configure(text="⬤  Stopped", text_color=STATUS_WARN)
        if self._update_job:
            self.after_cancel(self._update_job)
            self._update_job = None
        self._run_analysis()

    def _reset_stats(self):
        self._health.reset()
        self._update_metrics()
        self._clear_findings()

    def _build_config(self) -> Optional[ConnectionConfig]:
        try:
            timeout = float(self._timeout_e.get().strip() or "1.0")
            slave_id = int(self._slave_id.get().strip() or "1")
            if self._proto_var.get() == "TCP":
                return ConnectionConfig(
                    mode=ConnectionMode.TCP,
                    host=self._tcp_host.get().strip(),
                    port=int(self._tcp_port.get().strip() or "502"),
                    slave_id=slave_id,
                    timeout=timeout,
                )
            else:
                parity_map = {"None (N)": "N", "Even (E)": "E", "Odd (O)": "O"}
                return ConnectionConfig(
                    mode=ConnectionMode.RTU,
                    serial_port=self._rtu_port.get(),
                    baudrate=int(self._rtu_baud.get()),
                    parity=parity_map.get(self._rtu_parity.get(), "N"),
                    slave_id=slave_id,
                    timeout=timeout,
                )
        except Exception as e:
            logger.error(f"Config error: {e}")
            return None

    # ── Live Updates ──────────────────────────────────────────────────────────

    def _schedule_ui_update(self):
        """Schedule periodic UI refresh while running."""
        if self._running:
            self._update_metrics()
            self._update_chart()
            self._update_job = self.after(1500, self._schedule_ui_update)

    def _update_metrics(self):
        """Refresh all KPI labels from health monitor data."""
        h = self._health
        self._lbl_total.configure(text=str(h.total_transactions))
        if h.total_transactions > 0:
            self._lbl_success.configure(text=f"{h.success_rate_pct:.1f}")
            err_color = STATUS_GOOD if h.error_rate_pct < 2 else (
                STATUS_WARN if h.error_rate_pct < 10 else STATUS_ERROR)
            self._lbl_errors.configure(text=str(h.error_count), text_color=err_color)
            self._lbl_timeout.configure(text=str(h.timeout_count))

            if h.avg_response_ms > 0:
                rt_color = (STATUS_GOOD if h.avg_response_ms < 100 else
                            STATUS_WARN if h.avg_response_ms < 500 else STATUS_ERROR)
                self._lbl_avg.configure(text=f"{h.avg_response_ms:.1f}", text_color=rt_color)
                self._lbl_max.configure(text=f"{h.max_response_ms:.1f}")
                self._lbl_jitter.configure(text=f"{h.jitter_ms:.1f}")

            score = h.compute_overall_health()
            from ui.theme import get_health_label
            self._health_widget.update_score(score, get_health_label(score))

    def _update_chart(self):
        """Redraw response time sparkline and error timeline."""
        times = self._health.get_response_time_history(60)
        if times:
            self._sparkline.update_data(times)

        errors = self._health.get_error_history(60)
        self._draw_error_timeline(errors)

    def _draw_error_timeline(self, flags: list):
        """Draw colored dots on the error timeline canvas."""
        c = self._error_canvas
        c.delete("all")
        if not flags:
            return
        w = c.winfo_width() or 900
        dot_w = max(4, w // max(1, len(flags)))
        for i, flag in enumerate(flags):
            x = i * dot_w
            color = STATUS_ERROR if flag else STATUS_GOOD
            c.create_rectangle(x, 2, x + dot_w - 1, 18, fill=color, outline="")

    # ── Analysis ─────────────────────────────────────────────────────────────

    def _run_analysis(self):
        """Generate findings and display them."""
        findings = self._health.generate_findings()
        self._clear_findings()

        if not findings:
            self._no_findings_lbl = ctk.CTkLabel(
                self._findings_frame,
                text="No findings yet — run a test first.",
                font=(FONT_FAMILY, FONT_SIZE_BODY),
                text_color=TEXT_MUTED,
            )
            self._no_findings_lbl.pack(pady=20)
            return

        for finding in findings:
            icon, color = SEVERITY_ICONS.get(finding.severity, ("•", TEXT_MUTED))
            row = ctk.CTkFrame(self._findings_frame,
                               fg_color=BG_MEDIUM, corner_radius=6)
            row.pack(fill="x", pady=3)

            # Severity icon strip
            strip = ctk.CTkFrame(row, fg_color=color, width=5, corner_radius=3)
            strip.pack(side="left", fill="y", padx=(0, 10))

            body = ctk.CTkFrame(row, fg_color="transparent")
            body.pack(side="left", fill="x", expand=True, pady=8)

            # Header row: icon + title + category
            title_row = ctk.CTkFrame(body, fg_color="transparent")
            title_row.pack(fill="x")

            ctk.CTkLabel(title_row, text=f"{icon}  {finding.title}",
                         font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                         text_color=color, anchor="w").pack(side="left")
            ctk.CTkLabel(title_row,
                         text=f"[{finding.category}]",
                         font=(FONT_FAMILY, FONT_SIZE_TINY),
                         text_color=TEXT_MUTED).pack(side="left", padx=8)

            # Detail
            ctk.CTkLabel(body, text=finding.detail,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w",
                         wraplength=800).pack(fill="x", pady=(2, 0))

            # Recommendation
            if finding.recommendation:
                rec_row = ctk.CTkFrame(body, fg_color="transparent")
                rec_row.pack(fill="x", pady=(3, 0))
                ctk.CTkLabel(rec_row, text="💡 ",
                             font=(FONT_FAMILY, FONT_SIZE_SMALL),
                             text_color=STATUS_INFO).pack(side="left")
                ctk.CTkLabel(rec_row, text=finding.recommendation,
                             font=(FONT_FAMILY, FONT_SIZE_SMALL),
                             text_color=STATUS_INFO, anchor="w",
                             wraplength=780).pack(side="left", fill="x")

            # Right padding
            ctk.CTkFrame(row, fg_color="transparent", width=10).pack(side="right")

    def _clear_findings(self):
        for w in self._findings_frame.winfo_children():
            w.destroy()

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_report(self):
        """Export a plain-text diagnostic report."""
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Diagnostic Report",
        )
        if not path:
            return
        try:
            h = self._health
            findings = h.generate_findings()
            lines = [
                "=" * 70,
                "SAS MODBUS TOOLKIT — NETWORK DIAGNOSTIC REPORT",
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 70,
                "",
                "SUMMARY",
                "-" * 40,
                f"  Total Transactions : {h.total_transactions}",
                f"  Success Rate       : {h.success_rate_pct:.1f}%",
                f"  Error Count        : {h.error_count}",
                f"  Timeout Count      : {h.timeout_count}",
                f"  Avg Response Time  : {h.avg_response_ms:.1f} ms",
                f"  Max Response Time  : {h.max_response_ms:.1f} ms",
                f"  Response Jitter    : {h.jitter_ms:.1f} ms",
                f"  Overall Health     : {h.compute_overall_health()} / 100",
                "",
                "FINDINGS",
                "-" * 40,
            ]
            for finding in findings:
                lines += [
                    f"  [{finding.severity.value}] {finding.category}: {finding.title}",
                    f"    {finding.detail}",
                ]
                if finding.recommendation:
                    lines.append(f"    > {finding.recommendation}")
                lines.append("")

            lines += ["=" * 70, "Southern Automation Solutions — SAS Modbus Toolkit", ""]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            logger.error(f"Export error: {e}")

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_transaction(self, rec):
        """Feed each transaction into the health monitor."""
        is_timeout = "timeout" in str(rec.error or "").lower()
        is_crc = "crc" in str(rec.error or "").lower()
        error_type = "crc" if is_crc else ("timeout" if is_timeout else "")
        self._health.record_transaction(
            slave_id=rec.slave_id,
            function_code=rec.function_code,
            response_ms=rec.response_time_ms,
            is_error=rec.error is not None,
            is_timeout=is_timeout,
            error_type=error_type,
        )

    def _on_connected(self):
        proto = self._proto_var.get()
        color = MODBUS_TCP_COLOR if proto == "TCP" else MODBUS_RTU_COLOR
        self.after(0, lambda: self._status_badge.configure(
            text="⬤  Connected", text_color=color))
        self.after(0, lambda: self._start_btn.configure(
            state="normal", text="▶  Start Test"))

    def _on_disconnected(self, msg):
        self.after(0, lambda: self._status_badge.configure(
            text="⬤  Disconnected", text_color=STATUS_OFFLINE))

    def _on_proto_change(self, value):
        if value == "TCP":
            self._rtu_frame.pack_forget()
            self._tcp_frame.pack(fill="x", pady=(0, 4))
        else:
            self._tcp_frame.pack_forget()
            self._rtu_frame.pack(fill="x", pady=(0, 4))

    def on_show(self):
        pass
