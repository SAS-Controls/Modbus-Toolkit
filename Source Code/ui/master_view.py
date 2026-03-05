"""
SAS Modbus Toolkit — Modbus Master View
Connects to slave devices (TCP or RTU) and performs read/write operations.
"""

import logging
import threading
import time
import tkinter as tk
from datetime import datetime
from typing import List, Optional

import customtkinter as ctk

from core.modbus_client import (ModbusClientWrapper, FunctionCode, FC_LABELS,
                                 EXCEPTION_CODES, BAUD_RATES, PARITY_OPTIONS,
                                 STOPBIT_OPTIONS, ModbusResult)
from core.serial_utils import get_available_ports
from core.settings_manager import AppSettings
from ui.theme import *

logger = logging.getLogger(__name__)

FC_LIST = [
    ("FC01 – Read Coils", FunctionCode.READ_COILS),
    ("FC02 – Read Discrete Inputs", FunctionCode.READ_DISCRETE_INPUTS),
    ("FC03 – Read Holding Registers", FunctionCode.READ_HOLDING_REGISTERS),
    ("FC04 – Read Input Registers", FunctionCode.READ_INPUT_REGISTERS),
    ("FC05 – Write Single Coil", FunctionCode.WRITE_SINGLE_COIL),
    ("FC06 – Write Single Register", FunctionCode.WRITE_SINGLE_REGISTER),
    ("FC15 – Write Multiple Coils", FunctionCode.WRITE_MULTIPLE_COILS),
    ("FC16 – Write Multiple Registers", FunctionCode.WRITE_MULTIPLE_REGISTERS),
]

IS_WRITE_FC = {FunctionCode.WRITE_SINGLE_COIL, FunctionCode.WRITE_SINGLE_REGISTER,
               FunctionCode.WRITE_MULTIPLE_COILS, FunctionCode.WRITE_MULTIPLE_REGISTERS}
IS_COIL_FC = {FunctionCode.READ_COILS, FunctionCode.READ_DISCRETE_INPUTS,
              FunctionCode.WRITE_SINGLE_COIL, FunctionCode.WRITE_MULTIPLE_COILS}


class MasterView(ctk.CTkFrame):
    """Modbus Master simulator — connect and read/write device registers."""

    def __init__(self, master_widget, settings: AppSettings, **kwargs):
        super().__init__(master_widget, fg_color=BG_DARK, **kwargs)
        self._settings = settings
        self._client = ModbusClientWrapper()
        self._poll_thread: Optional[threading.Thread] = None
        self._polling = False
        self._poll_interval_ms = 1000
        self._register_rows: List[dict] = []
        self._current_fc = FunctionCode.READ_HOLDING_REGISTERS
        self._log_entries: list = []

        self._build_ui()
        self.on_show()

    def on_show(self):
        self._refresh_ports()

    def _build_ui(self):
        """Construct the full master view layout."""
        # ── Header ───────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=BG_MEDIUM, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="⚡  Modbus Master",
                     font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=20, pady=12)

        # Connection status badge
        self._status_badge_var = tk.StringVar(value="● Disconnected")
        self._status_badge = ctk.CTkLabel(
            header, textvariable=self._status_badge_var,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            text_color=STATUS_OFFLINE,
            fg_color=BG_CARD, corner_radius=12, padx=12, pady=4,
        )
        self._status_badge.pack(side="right", padx=16, pady=12)

        # Stats row
        self._stats_var = tk.StringVar(value="")
        ctk.CTkLabel(header, textvariable=self._stats_var,
                     font=(FONT_FAMILY, FONT_SIZE_TINY),
                     text_color=TEXT_MUTED).pack(side="right", padx=8)

        # ── Main Body (horizontal split: left panel + right content) ─────────
        body = ctk.CTkFrame(self, fg_color=BG_DARK)
        body.pack(fill="both", expand=True)

        # LEFT: Connection + Request panel
        left = ctk.CTkFrame(body, fg_color=BG_MEDIUM, width=280, corner_radius=0)
        left.pack(side="left", fill="y", padx=(0, 1))
        left.pack_propagate(False)
        self._build_left_panel(left)

        # RIGHT: Register table + Transaction log
        right = ctk.CTkFrame(body, fg_color=BG_DARK)
        right.pack(side="right", fill="both", expand=True)
        self._build_right_panel(right)

    def _build_left_panel(self, parent):
        """Build connection settings and request configuration."""
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                         scrollbar_button_color=BG_CARD)
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        pad = {"padx": 16, "pady": (0, 6)}

        # ── Protocol Selection ────────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="PROTOCOL", font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=16, pady=(16, 4))

        proto_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        proto_frame.pack(fill="x", padx=16, pady=(0, 12))

        self._proto_var = tk.StringVar(value="TCP")
        for label, val in [("Modbus TCP", "TCP"), ("Modbus RTU (Serial)", "RTU")]:
            ctk.CTkRadioButton(
                proto_frame, text=label, variable=self._proto_var, value=val,
                font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_PRIMARY,
                fg_color=SAS_BLUE, command=self._on_proto_change,
            ).pack(anchor="w", padx=12, pady=6)

        # ── TCP Settings ──────────────────────────────────────────────────────
        self._tcp_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        self._tcp_frame.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(self._tcp_frame, text="TCP / ETHERNET",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=SAS_BLUE, anchor="w").pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(self._tcp_frame, text="IP Address",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12)
        self._tcp_host = ctk.CTkEntry(self._tcp_frame, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, height=INPUT_HEIGHT,
                                       placeholder_text="192.168.1.100")
        self._tcp_host.pack(fill="x", padx=12, pady=(2, 8))
        self._tcp_host.insert(0, self._settings.tcp_host)

        row = ctk.CTkFrame(self._tcp_frame, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row, text="Port", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_SECONDARY).pack(side="left")
        self._tcp_port = ctk.CTkEntry(row, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, height=INPUT_HEIGHT, width=80)
        self._tcp_port.pack(side="right")
        self._tcp_port.insert(0, str(self._settings.tcp_port))

        # ── RTU Settings ──────────────────────────────────────────────────────
        self._rtu_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)

        ctk.CTkLabel(self._rtu_frame, text="SERIAL / RTU",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=SAS_ORANGE, anchor="w").pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(self._rtu_frame, text="COM Port",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12)
        self._rtu_port = ctk.CTkComboBox(self._rtu_frame,
                                          font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, height=INPUT_HEIGHT, values=["COM1"])
        self._rtu_port.pack(fill="x", padx=12, pady=(2, 8))

        row2 = ctk.CTkFrame(self._rtu_frame, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkLabel(row2, text="Baud Rate",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._rtu_baud = ctk.CTkComboBox(row2, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, height=INPUT_HEIGHT, width=100,
                                          values=[str(b) for b in BAUD_RATES])
        self._rtu_baud.set(str(self._settings.rtu_baud))
        self._rtu_baud.pack(side="right")

        row3 = ctk.CTkFrame(self._rtu_frame, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row3, text="Parity",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._rtu_parity = ctk.CTkSegmentedButton(
            row3, values=["None", "Even", "Odd"],
            font=(FONT_FAMILY, FONT_SIZE_SMALL), fg_color=BG_INPUT,
            selected_color=SAS_BLUE, width=150,
        )
        self._rtu_parity.set("None")
        self._rtu_parity.pack(side="right")

        row4 = ctk.CTkFrame(self._rtu_frame, fg_color="transparent")
        row4.pack(fill="x", padx=12, pady=(4, 12))
        ctk.CTkLabel(row4, text="Stop Bits",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._rtu_stop = ctk.CTkSegmentedButton(
            row4, values=["1", "2"],
            font=(FONT_FAMILY, FONT_SIZE_SMALL), fg_color=BG_INPUT,
            selected_color=SAS_BLUE, width=80,
        )
        self._rtu_stop.set("1")
        self._rtu_stop.pack(side="right")

        # ── Connection Timeout ────────────────────────────────────────────────
        row_to = ctk.CTkFrame(scroll, fg_color="transparent")
        row_to.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(row_to, text="Timeout (sec)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._timeout_entry = ctk.CTkEntry(row_to, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                            fg_color=BG_INPUT, height=INPUT_HEIGHT, width=70)
        self._timeout_entry.insert(0, "3.0")
        self._timeout_entry.pack(side="right")

        # ── Connect Button ────────────────────────────────────────────────────
        self._connect_btn = ctk.CTkButton(
            scroll, text="Connect",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
            height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._toggle_connect,
        )
        self._connect_btn.pack(fill="x", padx=16, pady=(0, 20))

        # ── Divider ───────────────────────────────────────────────────────────
        ctk.CTkFrame(scroll, fg_color=BORDER_COLOR, height=1).pack(fill="x", padx=16, pady=4)

        # ── Request Configuration ─────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="REQUEST",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=16, pady=(12, 4))

        req_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        req_card.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(req_card, text="Function Code",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        fc_labels = [fc[0] for fc in FC_LIST]
        self._fc_combo = ctk.CTkComboBox(
            req_card, values=fc_labels,
            font=(FONT_FAMILY, FONT_SIZE_SMALL), fg_color=BG_INPUT,
            height=INPUT_HEIGHT, command=self._on_fc_change,
        )
        self._fc_combo.set(fc_labels[2])  # Default FC03
        self._fc_combo.pack(fill="x", padx=12, pady=(0, 8))

        # Slave ID + Address
        row_sa = ctk.CTkFrame(req_card, fg_color="transparent")
        row_sa.pack(fill="x", padx=12, pady=(0, 6))

        left_col = ctk.CTkFrame(row_sa, fg_color="transparent")
        left_col.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkLabel(left_col, text="Slave / Unit ID",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(anchor="w")
        self._slave_id = ctk.CTkEntry(left_col, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, height=INPUT_HEIGHT)
        self._slave_id.insert(0, str(self._settings.master_slave_id))
        self._slave_id.pack(fill="x")

        right_col = ctk.CTkFrame(row_sa, fg_color="transparent")
        right_col.pack(side="right", fill="x", expand=True)
        ctk.CTkLabel(right_col, text="Start Address",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(anchor="w")
        self._start_addr = ctk.CTkEntry(right_col, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                         fg_color=BG_INPUT, height=INPUT_HEIGHT)
        self._start_addr.insert(0, str(self._settings.master_address))
        self._start_addr.pack(fill="x")

        # Count row
        row_cnt = ctk.CTkFrame(req_card, fg_color="transparent")
        row_cnt.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row_cnt, text="Register Count / Value",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._count_entry = ctk.CTkEntry(row_cnt, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, height=INPUT_HEIGHT, width=80)
        self._count_entry.insert(0, str(self._settings.master_count))
        self._count_entry.pack(side="right")

        # Write values (shown for write FCs)
        self._write_frame = ctk.CTkFrame(req_card, fg_color="transparent")
        ctk.CTkLabel(self._write_frame, text="Write Values (comma-separated)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=0)
        self._write_values = ctk.CTkEntry(self._write_frame,
                                           font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                           fg_color=BG_INPUT, height=INPUT_HEIGHT,
                                           placeholder_text="e.g. 100, 200, 300")
        self._write_values.pack(fill="x", pady=(2, 8))

        # Action Buttons
        btn_row = ctk.CTkFrame(req_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 12))

        self._read_btn = ctk.CTkButton(
            btn_row, text="▶  Read",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg_color=STATUS_GOOD, hover_color="#16A34A",
            height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._do_read,
        )
        self._read_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self._write_btn = ctk.CTkButton(
            btn_row, text="✎  Write",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg_color=SAS_ORANGE, hover_color=SAS_ORANGE_DARK,
            height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._do_write,
        )
        self._write_btn.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # ── Poll Controls ─────────────────────────────────────────────────────
        ctk.CTkFrame(scroll, fg_color=BORDER_COLOR, height=1).pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(scroll, text="AUTO-POLL",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=16, pady=(8, 4))

        poll_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        poll_card.pack(fill="x", padx=16, pady=(0, 16))

        poll_row = ctk.CTkFrame(poll_card, fg_color="transparent")
        poll_row.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(poll_row, text="Interval (ms)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._poll_interval = ctk.CTkEntry(poll_row, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                            fg_color=BG_INPUT, height=INPUT_HEIGHT, width=80)
        self._poll_interval.insert(0, "1000")
        self._poll_interval.pack(side="right")

        self._poll_btn = ctk.CTkButton(
            poll_card, text="▶  Start Polling",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
            height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._toggle_poll,
        )
        self._poll_btn.pack(fill="x", padx=12, pady=(0, 12))

        # Update visibility
        self._on_proto_change()
        self._on_fc_change(self._fc_combo.get())

    def _build_right_panel(self, parent):
        """Build the register table and transaction log."""
        # ── Register Table (top half) ─────────────────────────────────────────
        table_frame = ctk.CTkFrame(parent, fg_color=BG_MEDIUM, corner_radius=0)
        table_frame.pack(fill="both", expand=True, padx=0, pady=(0, 1))

        # Table header
        tbl_header = ctk.CTkFrame(table_frame, fg_color=BG_CARD, corner_radius=0, height=36)
        tbl_header.pack(fill="x")
        tbl_header.pack_propagate(False)

        ctk.CTkLabel(tbl_header, text="📊  Register Data",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=16)

        # Format toggles
        fmt_row = ctk.CTkFrame(tbl_header, fg_color="transparent")
        fmt_row.pack(side="right", padx=12)
        ctk.CTkLabel(fmt_row, text="Display:",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(side="left", padx=(0, 6))
        self._display_fmt = ctk.CTkSegmentedButton(
            fmt_row, values=["Dec", "Hex", "Bin", "Float32"],
            font=(FONT_FAMILY, FONT_SIZE_SMALL), fg_color=BG_INPUT,
            selected_color=SAS_BLUE, height=28,
            command=self._refresh_table_display,
        )
        self._display_fmt.set("Dec")
        self._display_fmt.pack(side="left")

        # Table content (scrollable canvas)
        self._table_container = ctk.CTkScrollableFrame(
            table_frame, fg_color=BG_DARK, corner_radius=0,
        )
        self._table_container.pack(fill="both", expand=True)

        # Column headers
        hdr = ctk.CTkFrame(self._table_container, fg_color=BG_CARD, corner_radius=0, height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        for text, w in [("Address", 100), ("Dec", 100), ("Hex", 90), ("Binary", 140), ("Signed", 100), ("Write Value", 120)]:
            ctk.CTkLabel(hdr, text=text, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                         text_color=TEXT_SECONDARY, width=w, anchor="center").pack(side="left", padx=1)

        # Register rows will be built dynamically
        self._reg_rows_frame = ctk.CTkFrame(self._table_container, fg_color="transparent")
        self._reg_rows_frame.pack(fill="both", expand=True)

        self._build_register_rows(10)

        # ── Transaction Log (bottom third) ────────────────────────────────────
        log_frame = ctk.CTkFrame(parent, fg_color=BG_DARK, corner_radius=0, height=200)
        log_frame.pack(fill="x", side="bottom")
        log_frame.pack_propagate(False)

        log_header = ctk.CTkFrame(log_frame, fg_color=BG_CARD, corner_radius=0, height=32)
        log_header.pack(fill="x")
        log_header.pack_propagate(False)

        ctk.CTkLabel(log_header, text="📋  Transaction Log",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=12)

        ctk.CTkButton(log_header, text="Clear",
                      font=(FONT_FAMILY, FONT_SIZE_TINY),
                      fg_color="transparent", text_color=TEXT_MUTED,
                      hover_color=BG_CARD_HOVER, height=24, width=50,
                      command=self._clear_log).pack(side="right", padx=8)

        self._log_text = tk.Text(
            log_frame, font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
            bg=resolve_color(BG_DARK), fg=resolve_color(TEXT_SECONDARY),
            insertbackground=resolve_color(TEXT_PRIMARY),
            selectbackground=SAS_BLUE, relief="flat", bd=0,
            state="disabled", wrap="none",
        )
        self._log_text.pack(fill="both", expand=True, padx=2, pady=2)

        # Tag colors
        self._log_text.tag_config("tx", foreground=LOG_TX)
        self._log_text.tag_config("rx", foreground=LOG_RX)
        self._log_text.tag_config("err", foreground=LOG_ERROR)
        self._log_text.tag_config("warn", foreground=LOG_WARN)
        self._log_text.tag_config("info", foreground=LOG_INFO)

        log_scroll = ctk.CTkScrollbar(log_frame, command=self._log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self._log_text.configure(yscrollcommand=log_scroll.set)

    def _build_register_rows(self, count: int):
        """Build or rebuild the register display rows."""
        for widget in self._reg_rows_frame.winfo_children():
            widget.destroy()
        self._register_rows.clear()

        for i in range(count):
            row_frame = ctk.CTkFrame(
                self._reg_rows_frame,
                fg_color=BG_CARD if i % 2 == 0 else BG_DARK,
                corner_radius=0, height=30,
            )
            row_frame.pack(fill="x")
            row_frame.pack_propagate(False)

            addr_lbl = ctk.CTkLabel(row_frame, text=str(i),
                                     font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                     text_color=TEXT_MUTED, width=100, anchor="center")
            addr_lbl.pack(side="left", padx=1)

            dec_lbl = ctk.CTkLabel(row_frame, text="—",
                                    font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                    text_color=TEXT_SECONDARY, width=100, anchor="center")
            dec_lbl.pack(side="left", padx=1)

            hex_lbl = ctk.CTkLabel(row_frame, text="—",
                                    font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                    text_color=TEXT_MUTED, width=90, anchor="center")
            hex_lbl.pack(side="left", padx=1)

            bin_lbl = ctk.CTkLabel(row_frame, text="—",
                                    font=(FONT_FAMILY_MONO, FONT_SIZE_TINY),
                                    text_color=TEXT_MUTED, width=140, anchor="center")
            bin_lbl.pack(side="left", padx=1)

            signed_lbl = ctk.CTkLabel(row_frame, text="—",
                                       font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                       text_color=TEXT_MUTED, width=100, anchor="center")
            signed_lbl.pack(side="left", padx=1)

            write_entry = ctk.CTkEntry(row_frame, font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                        fg_color=BG_INPUT, height=24, width=120)
            write_entry.pack(side="left", padx=(2, 4))

            self._register_rows.append({
                "addr": addr_lbl, "dec": dec_lbl, "hex": hex_lbl,
                "bin": bin_lbl, "signed": signed_lbl, "write": write_entry,
                "value": 0, "row_frame": row_frame,
            })

    def _update_register_table(self, result: ModbusResult):
        """Populate the register table with fresh values from a read."""
        start_addr = result.address
        values = result.values
        count = len(values)
        fmt = self._display_fmt.get()

        # Rebuild rows if count changed
        if count != len(self._register_rows):
            self._build_register_rows(count)

        for i, val in enumerate(values):
            row = self._register_rows[i]
            row["value"] = val
            addr = start_addr + i

            row["addr"].configure(text=str(addr))

            if isinstance(val, bool):
                display_val = "1" if val else "0"
                row["dec"].configure(text=display_val, text_color=STATUS_GOOD if val else TEXT_SECONDARY)
                row["hex"].configure(text="—")
                row["bin"].configure(text="—")
                row["signed"].configure(text="—")
            else:
                unsigned = val & 0xFFFF
                signed = unsigned if unsigned < 32768 else unsigned - 65536

                row["dec"].configure(text=str(unsigned),
                                      text_color=TEXT_PRIMARY)
                row["hex"].configure(text=f"0x{unsigned:04X}")
                row["bin"].configure(text=f"{unsigned:016b}")
                row["signed"].configure(text=str(signed),
                                         text_color=STATUS_WARN if signed < 0 else TEXT_SECONDARY)

    def _refresh_table_display(self, fmt: str = None):
        """Re-render the table when display format changes (no new reads)."""
        pass  # Values already shown in all formats simultaneously

    def _on_proto_change(self):
        """Show/hide TCP vs RTU settings panels."""
        proto = self._proto_var.get()
        if proto == "TCP":
            self._tcp_frame.pack(fill="x", padx=16, pady=(0, 8))
            self._rtu_frame.pack_forget()
        else:
            self._tcp_frame.pack_forget()
            self._rtu_frame.pack(fill="x", padx=16, pady=(0, 8))

    def _on_fc_change(self, selection: str):
        """Update UI based on selected function code."""
        fc = self._get_fc_from_selection(selection)
        if fc is None:
            return
        self._current_fc = fc
        is_write = fc in IS_WRITE_FC
        if is_write:
            self._write_frame.pack(fill="x", padx=12, pady=(0, 4))
            self._read_btn.configure(state="disabled", fg_color=BG_CARD)
            self._write_btn.configure(state="normal", fg_color=SAS_ORANGE)
        else:
            self._write_frame.pack_forget()
            self._read_btn.configure(state="normal", fg_color=STATUS_GOOD)
            self._write_btn.configure(state="disabled", fg_color=BG_CARD)

    def _get_fc_from_selection(self, label: str) -> Optional[FunctionCode]:
        for lbl, fc in FC_LIST:
            if lbl == label:
                return fc
        return None

    def _refresh_ports(self):
        """Update the COM port list."""
        try:
            ports = get_available_ports()
            if ports:
                self._rtu_port.configure(values=ports)
                self._rtu_port.set(self._settings.rtu_port if self._settings.rtu_port in ports else ports[0])
        except Exception:
            pass

    def _toggle_connect(self):
        """Connect or disconnect from the target device."""
        if self._client.connected:
            self._do_disconnect()
        else:
            self._do_connect()

    def _do_connect(self):
        proto = self._proto_var.get()
        try:
            timeout = float(self._timeout_entry.get())
        except ValueError:
            timeout = 3.0

        self._connect_btn.configure(text="Connecting...", state="disabled")
        self.update()

        def connect_thread():
            success = False
            if proto == "TCP":
                host = self._tcp_host.get().strip()
                try:
                    port = int(self._tcp_port.get())
                except ValueError:
                    port = 502
                success = self._client.connect_tcp(host, port, timeout)
            else:
                com = self._rtu_port.get()
                try:
                    baud = int(self._rtu_baud.get())
                except ValueError:
                    baud = 9600
                parity_map = {"None": "N", "Even": "E", "Odd": "O"}
                parity = parity_map.get(self._rtu_parity.get(), "N")
                stop = int(self._rtu_stop.get())
                success = self._client.connect_rtu(com, baud, parity, stop, timeout=timeout)

            self.after(0, lambda: self._on_connect_result(success, proto))

        threading.Thread(target=connect_thread, daemon=True).start()

    def _on_connect_result(self, success: bool, proto: str):
        if success:
            self._connect_btn.configure(text="Disconnect", fg_color=STATUS_ERROR,
                                         hover_color="#DC2626", state="normal")
            self._status_badge_var.set("● Connected")
            self._status_badge.configure(text_color=STATUS_GOOD)
            self._append_log(f"Connected via {proto}", "rx")
        else:
            self._connect_btn.configure(text="Connect", fg_color=SAS_BLUE,
                                         hover_color=SAS_BLUE_DARK, state="normal")
            self._status_badge_var.set("● Disconnected")
            self._status_badge.configure(text_color=STATUS_OFFLINE)
            self._append_log("Connection failed — check IP/port/cable and try again", "err")

    def _do_disconnect(self):
        self._stop_polling()
        self._client.disconnect()
        self._connect_btn.configure(text="Connect", fg_color=SAS_BLUE,
                                     hover_color=SAS_BLUE_DARK)
        self._status_badge_var.set("● Disconnected")
        self._status_badge.configure(text_color=STATUS_OFFLINE)
        self._append_log("Disconnected", "info")

    def _do_read(self):
        """Perform a single read request."""
        if not self._client.connected:
            self._append_log("Not connected — connect to a device first", "warn")
            return
        threading.Thread(target=self._execute_read, daemon=True).start()

    def _execute_read(self):
        fc = self._current_fc
        try:
            slave_id = int(self._slave_id.get())
            address = int(self._start_addr.get())
            count = int(self._count_entry.get())
        except ValueError:
            self.after(0, lambda: self._append_log("Invalid parameters — check Slave ID, Address, and Count", "err"))
            return

        result = self._client.execute(fc, slave_id, address, count)
        self.after(0, lambda: self._handle_read_result(result))

    def _handle_read_result(self, result: ModbusResult):
        if result.success:
            self._update_register_table(result)
            self._append_log(
                f"FC{result.function_code:02d} ← Slave {result.slave_id} | "
                f"Addr {result.address} | {len(result.values)} registers | "
                f"{result.response_time_ms:.1f}ms",
                "rx"
            )
            self._update_stats()
        else:
            self._append_log(
                f"FC{result.function_code:02d} ✗ Slave {result.slave_id} | "
                f"{result.error_msg}",
                "err"
            )
            if result.exception_code:
                self._append_log(
                    f"  ↳ Exception {result.exception_code}: {result.exception_description}",
                    "warn"
                )
            self._update_stats()

    def _do_write(self):
        """Perform a single write request."""
        if not self._client.connected:
            self._append_log("Not connected — connect to a device first", "warn")
            return
        threading.Thread(target=self._execute_write, daemon=True).start()

    def _execute_write(self):
        fc = self._current_fc
        try:
            slave_id = int(self._slave_id.get())
            address = int(self._start_addr.get())
        except ValueError:
            self.after(0, lambda: self._append_log("Invalid Slave ID or Address", "err"))
            return

        # Parse write values
        raw_vals = self._write_values.get().strip()
        if not raw_vals:
            raw_vals = self._count_entry.get().strip()

        try:
            if fc in (FunctionCode.WRITE_SINGLE_COIL,):
                values = [int(raw_vals.split(",")[0].strip()) != 0]
            elif fc == FunctionCode.WRITE_SINGLE_REGISTER:
                values = [int(raw_vals.split(",")[0].strip())]
            else:
                values = [int(v.strip()) for v in raw_vals.split(",") if v.strip()]
        except ValueError:
            self.after(0, lambda: self._append_log("Invalid write value — enter integers", "err"))
            return

        result = self._client.execute(fc, slave_id, address, len(values), values)
        self.after(0, lambda: self._handle_write_result(result, values))

    def _handle_write_result(self, result: ModbusResult, values: list):
        if result.success:
            self._append_log(
                f"FC{result.function_code:02d} → Slave {result.slave_id} | "
                f"Addr {result.address} | Written: {values} | "
                f"{result.response_time_ms:.1f}ms",
                "tx"
            )
        else:
            self._append_log(
                f"FC{result.function_code:02d} ✗ Write failed | {result.error_msg}", "err"
            )
            if result.exception_code:
                self._append_log(
                    f"  ↳ Exception {result.exception_code}: {result.exception_description}",
                    "warn"
                )
        self._update_stats()

    def _toggle_poll(self):
        if self._polling:
            self._stop_polling()
        else:
            self._start_polling()

    def _start_polling(self):
        if not self._client.connected:
            self._append_log("Connect to a device before polling", "warn")
            return
        try:
            self._poll_interval_ms = max(100, int(self._poll_interval.get()))
        except ValueError:
            self._poll_interval_ms = 1000

        self._polling = True
        self._poll_btn.configure(text="⏹  Stop Polling", fg_color=STATUS_ERROR,
                                  hover_color="#DC2626")
        self._append_log(f"Auto-poll started — interval: {self._poll_interval_ms}ms", "info")
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _stop_polling(self):
        self._polling = False
        self._poll_btn.configure(text="▶  Start Polling", fg_color=SAS_BLUE,
                                  hover_color=SAS_BLUE_DARK)

    def _poll_loop(self):
        while self._polling and self._client.connected:
            fc = self._current_fc
            if fc not in IS_WRITE_FC:
                try:
                    slave_id = int(self._slave_id.get())
                    address = int(self._start_addr.get())
                    count = int(self._count_entry.get())
                except ValueError:
                    break

                result = self._client.execute(fc, slave_id, address, count)
                if result.success:
                    self.after(0, lambda r=result: self._update_register_table(r))
                    self.after(0, self._update_stats)
                else:
                    self.after(0, lambda r=result: self._append_log(
                        f"Poll error: {r.error_msg}", "err"))

            interval_s = self._poll_interval_ms / 1000
            time.sleep(interval_s)

    def _update_stats(self):
        stats = (
            f"Requests: {self._client.total_requests}  ✓ {self._client.successful_requests}  "
            f"✗ {self._client.failed_requests}  |  "
            f"Avg: {self._client.avg_response_ms:.1f}ms  "
            f"Min: {self._client.min_response_ms:.1f}ms  "
            f"Max: {self._client.max_response_ms:.1f}ms"
        )
        self._stats_var.set(stats)

    def _append_log(self, message: str, tag: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{ts}]  {message}\n"
        self._log_text.configure(state="normal")
        self._log_text.insert("end", line, tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

        self._log_entries.append(line)
        if len(self._log_entries) > 2000:
            self._log_entries.pop(0)

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")
        self._log_entries.clear()

    def destroy(self):
        self._polling = False
        self._client.disconnect()
        super().destroy()
