"""
SAS Modbus Toolkit — Modbus Master View
Full-featured Modbus master: poll registers, read/write values,
supports TCP and RTU, live data display, transaction log.
"""

import logging
import threading
import tkinter as tk
from datetime import datetime
from typing import Dict, List, Optional

import customtkinter as ctk

from core.modbus_master import (
    ConnectionConfig, ConnectionMode, ModbusMasterEngine, PollConfig, TransactionRecord, FC_NAMES
)
from core.data_types import (
    DataType, COMMON_DATA_TYPE_NAMES, decode_registers, encode_value, get_register_count
)
from core.diagnostics import NetworkHealthMonitor
from ui.theme import *
from ui.widgets import (
    LogBox, MiniSparkline, HealthScoreWidget,
    get_serial_ports, make_card, make_primary_button,
    make_secondary_button, make_danger_button, enable_touch_scroll
)

logger = logging.getLogger(__name__)

POLL_TABLE_COLS = ("addr", "count", "label", "raw", "decoded", "type", "status")
MAX_ROWS = 20
BAUD_RATES = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]
FC_READ_OPTIONS = {
    "FC01 – Read Coils": 1,
    "FC02 – Read Discrete Inputs": 2,
    "FC03 – Read Holding Registers": 3,
    "FC04 – Read Input Registers": 4,
}
FC_WRITE_OPTIONS = {
    "FC05 – Write Single Coil": 5,
    "FC06 – Write Single Register": 6,
    "FC15 – Write Multiple Coils": 15,
    "FC16 – Write Multiple Registers": 16,
}

# Maps FC -> (bank short name, numeric offset for 5-digit register numbers)
# HR 40001 = address 0 (FC03), IR 30001 = address 0 (FC04), etc.
FC_REG_INFO = {
    1: ("Coil",  0),      # 00001 = address 0
    2: ("DI",    10000),  # 10001 = address 0
    3: ("HR",    40000),  # 40001 = address 0
    4: ("IR",    30000),  # 30001 = address 0
}


def _addr_to_reg_label(address: int, fc: int) -> str:
    """Convert 0-based address + FC to human Modbus register number string."""
    bank, offset = FC_REG_INFO.get(fc, ("?", 0))
    return f"{bank} {offset + address + 1}"


class MasterView(ctk.CTkFrame):
    """Modbus Master view with poll table, live data, and write panel."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._engine = ModbusMasterEngine()
        self._engine.on_connected = self._on_connected
        self._engine.on_disconnected = self._on_disconnected
        # Poll results come from a background thread — must route through after() for thread safety
        self._engine.on_poll_result = lambda rid, addr, vals:             self.after(0, lambda: self._on_poll_result(rid, addr, list(vals)))
        self._engine.on_transaction = lambda rec:             self.after(0, lambda: self._on_transaction(rec))
        self._engine.on_error = lambda msg:             self.after(0, lambda: self._on_engine_error(msg))

        self._health = NetworkHealthMonitor()
        self._poll_configs: List[PollConfig] = []
        self._row_vars: Dict[int, dict] = {}   # row_id -> {addr, count, label, fc, type, raw, decoded, status}
        self._next_row_id = 0
        self._polling = False

        self._build_ui()
        self._add_default_rows()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=50)
        hdr.pack(fill="x", padx=24, pady=(16, 4))
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="📡  Modbus Master",
                      font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                      text_color=TEXT_PRIMARY, anchor="w").pack(side="left")

        self._conn_badge = ctk.CTkLabel(
            hdr, text="⬤  Disconnected",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            text_color=STATUS_OFFLINE,
        )
        self._conn_badge.pack(side="right", padx=8)

        # ── Scrollable main area ──────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=0, pady=0)
        enable_touch_scroll(self._scroll)

        self._build_connection_card()
        self._build_poll_card()
        self._build_write_card()
        self._build_log_card()

    def _build_connection_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(4, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=10)

        # Row 1: Protocol selector + Slave ID + Connect/Disconnect
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
        self._slave_id_entry = ctk.CTkEntry(
            row1, width=60, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            placeholder_text="1",
        )
        self._slave_id_entry.insert(0, "1")
        self._slave_id_entry.pack(side="left", padx=(0, 24))

        self._connect_btn = make_primary_button(row1, "🔌  Connect", self._do_connect, width=130)
        self._connect_btn.pack(side="left", padx=(0, 6))

        self._disconnect_btn = make_danger_button(row1, "✖  Disconnect", self._do_disconnect, width=130)
        self._disconnect_btn.pack(side="left")
        self._disconnect_btn.configure(state="disabled")

        # Row 2: TCP settings
        self._tcp_frame = ctk.CTkFrame(inner, fg_color="transparent")
        self._tcp_frame.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(self._tcp_frame, text="IP Address:",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._tcp_host = ctk.CTkEntry(
            self._tcp_frame, width=160, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            placeholder_text="192.168.1.1",
        )
        self._tcp_host.insert(0, "192.168.1.1")
        self._tcp_host.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(self._tcp_frame, text="Port:",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._tcp_port = ctk.CTkEntry(
            self._tcp_frame, width=80, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
        )
        self._tcp_port.insert(0, "502")
        self._tcp_port.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(self._tcp_frame, text="Timeout (s):",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._timeout_entry = ctk.CTkEntry(
            self._tcp_frame, width=70, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
        )
        self._timeout_entry.insert(0, "1.0")
        self._timeout_entry.pack(side="left")

        # Row 3: RTU settings (hidden initially)
        self._rtu_frame = ctk.CTkFrame(inner, fg_color="transparent")

        ports = get_serial_ports()
        ctk.CTkLabel(self._rtu_frame, text="COM Port:",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._rtu_port = ctk.CTkComboBox(
            self._rtu_frame, values=ports, width=110, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY,
        )
        self._rtu_port.set(ports[0] if ports else "COM1")
        self._rtu_port.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(self._rtu_frame, text="Baud:",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._rtu_baud = ctk.CTkComboBox(
            self._rtu_frame, values=BAUD_RATES, width=100, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY,
        )
        self._rtu_baud.set("9600")
        self._rtu_baud.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(self._rtu_frame, text="Parity:",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._rtu_parity = ctk.CTkComboBox(
            self._rtu_frame, values=["None (N)", "Even (E)", "Odd (O)"], width=110,
            height=INPUT_HEIGHT, font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY,
        )
        self._rtu_parity.set("None (N)")
        self._rtu_parity.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(self._rtu_frame, text="Stop:",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._rtu_stop = ctk.CTkComboBox(
            self._rtu_frame, values=["1", "2"], width=60, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY,
        )
        self._rtu_stop.set("1")
        self._rtu_stop.pack(side="left")

    def _build_poll_card(self):
        """Build the polling table card."""
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 4))

        # ── Card Header ────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PADDING, pady=(10, 0))

        ctk.CTkLabel(hdr, text="📊  Poll Table",
                      font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                      text_color=TEXT_PRIMARY).pack(side="left")

        # Polling controls (right side)
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right")

        ctk.CTkLabel(right, text="Interval (s):",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._poll_interval = ctk.CTkEntry(
            right, width=60, height=32,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
        )
        self._poll_interval.insert(0, "1.0")
        self._poll_interval.pack(side="left", padx=(0, 12))

        self._poll_btn = make_primary_button(right, "▶  Start Poll", self._toggle_poll, width=130)
        self._poll_btn.pack(side="left", padx=(0, 6))

        make_secondary_button(right, "Read Once", self._read_once, width=100).pack(side="left", padx=(0, 6))
        make_secondary_button(right, "+ Add Row", self._add_row, width=100).pack(side="left")

        # ── Address Info Banner ────────────────────────────────────────────────
        info = ctk.CTkFrame(card, fg_color=BG_MEDIUM, corner_radius=4)
        info.pack(fill="x", padx=CARD_PADDING, pady=(6, 4))
        ctk.CTkLabel(info,
                     text="ℹ️  Addresses are 0-based (protocol address).  "
                          "HR 40001 = Addr 0  •  HR 40100 = Addr 99  •  "
                          "IR 30001 = Addr 0  •  Coil 00001 = Addr 0  •  "
                          "DI 10001 = Addr 0. "
                          "The ‘Reg #’ column shows the traditional 5-digit register number for reference.",
                     font=(FONT_FAMILY, FONT_SIZE_TINY),
                     text_color=TEXT_MUTED, anchor="w", justify="left",
                     wraplength=900).pack(fill="x", padx=10, pady=5)

        # ── Column Headers ─────────────────────────────────────────────────────
        col_hdr = ctk.CTkFrame(card, fg_color="transparent")
        col_hdr.pack(fill="x", padx=CARD_PADDING, pady=(4, 2))

        headers = [
            ("Addr (0-based)", 70), ("Reg #", 80), ("Count", 50), ("Function Code / Register Bank", 190),
            ("Tag Label", 150), ("Data Type", 140),
            ("Raw (hex/int)", 110), ("Decoded Value", 130), ("Status", 72), ("", 30)
        ]
        for text, w in headers:
            ctk.CTkLabel(col_hdr, text=text, width=w,
                          font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                          text_color=TEXT_MUTED, anchor="w").pack(side="left", padx=2)

        ctk.CTkFrame(card, fg_color=BORDER_COLOR, height=1).pack(fill="x", padx=CARD_PADDING)

        # ── Row Container ──────────────────────────────────────────────────────
        self._rows_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._rows_frame.pack(fill="x", padx=CARD_PADDING, pady=(4, 10))

    def _build_write_card(self):
        """Build the write operations card."""
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=10)

        ctk.CTkLabel(inner, text="✍  Write Value",
                      font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                      text_color=TEXT_PRIMARY).pack(anchor="w", pady=(0, 8))

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")

        ctk.CTkLabel(row, text="Function:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._write_fc = ctk.CTkComboBox(
            row, values=list(FC_WRITE_OPTIONS.keys()),
            width=260, height=INPUT_HEIGHT,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY,
            command=self._on_write_fc_change,
        )
        self._write_fc.set("FC06 – Write Single Register")
        self._write_fc.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row, text="Address:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._write_addr = ctk.CTkEntry(
            row, width=80, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            placeholder_text="0",
        )
        self._write_addr.insert(0, "0")
        self._write_addr.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row, text="Value:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._write_val = ctk.CTkEntry(
            row, width=130, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            placeholder_text="0",
        )
        self._write_val.insert(0, "0")
        self._write_val.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row, text="Type:", font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._write_type = ctk.CTkComboBox(
            row, values=COMMON_DATA_TYPE_NAMES, width=160, height=INPUT_HEIGHT,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY,
        )
        self._write_type.set("UINT16")
        self._write_type.pack(side="left", padx=(0, 16))

        make_primary_button(row, "⬆  Write", self._do_write, width=100).pack(side="left")

        self._write_status = ctk.CTkLabel(row, text="",
                                           font=(FONT_FAMILY, FONT_SIZE_BODY),
                                           text_color=STATUS_GOOD)
        self._write_status.pack(side="left", padx=12)

    def _build_log_card(self):
        """Build the transaction log card."""
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 16))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PADDING, pady=(10, 4))

        ctk.CTkLabel(hdr, text="📋  Transaction Log",
                      font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                      text_color=TEXT_PRIMARY).pack(side="left")

        make_secondary_button(hdr, "Clear", self._clear_log, width=80).pack(side="right")
        make_secondary_button(hdr, "Export CSV", self._export_log, width=100).pack(side="right", padx=(0, 6))

        self._log_box = LogBox(card, height=180)
        self._log_box.pack(fill="x", padx=CARD_PADDING, pady=(0, 10))

    # ── Row Management ────────────────────────────────────────────────────────

    def _add_default_rows(self):
        """Add a few starter rows to the poll table."""
        defaults = [
            (0, 10, 3, "Holding Registers 0-9", "UINT16"),
            (100, 5, 4, "Input Registers 100-104", "UINT16"),
        ]
        for addr, count, fc, label, dtype in defaults:
            self._add_row(addr=addr, count=count, fc=fc, label=label, dtype=dtype)

    def _add_row(self, addr: int = 0, count: int = 1, fc: int = 3,
                  label: str = "", dtype: str = "UINT16"):
        """Add a new row to the poll table."""
        if len(self._poll_configs) >= MAX_ROWS:
            return

        row_id = self._next_row_id
        self._next_row_id += 1

        row_frame = ctk.CTkFrame(self._rows_frame, fg_color="transparent", height=36)
        row_frame.pack(fill="x", pady=1)
        row_frame.pack_propagate(False)

        # Address (0-based)
        addr_e = ctk.CTkEntry(row_frame, width=70, height=30,
                               font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                               fg_color=BG_INPUT, border_color=BORDER_COLOR)
        addr_e.insert(0, str(addr))
        addr_e.pack(side="left", padx=2)

        # Reg # label (1-based, updates live) 
        reg_lbl = ctk.CTkLabel(row_frame, text=_addr_to_reg_label(addr, fc),
                                width=80, height=30,
                                font=(FONT_FAMILY_MONO, FONT_SIZE_TINY),
                                text_color=SAS_ORANGE_LIGHT, anchor="w")
        reg_lbl.pack(side="left", padx=2)

        # Count
        count_e = ctk.CTkEntry(row_frame, width=50, height=30,
                                font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                fg_color=BG_INPUT, border_color=BORDER_COLOR)
        count_e.insert(0, str(count))
        count_e.pack(side="left", padx=2)

        # Function code
        fc_names = list(FC_READ_OPTIONS.keys())
        fc_combo = ctk.CTkComboBox(row_frame, values=fc_names, width=190, height=30,
                                    font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                    fg_color=BG_INPUT, border_color=BORDER_COLOR,
                                    button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
                                    dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY)
        # Set to matching FC name
        for name, code in FC_READ_OPTIONS.items():
            if code == fc:
                fc_combo.set(name)
                break
        fc_combo.pack(side="left", padx=2)

        # Live update reg# when address or FC changes
        def _update_reg_lbl(*_):
            try:
                a = int(addr_e.get())
            except ValueError:
                a = 0
            fc_sel = FC_READ_OPTIONS.get(fc_combo.get(), 3)
            reg_lbl.configure(text=_addr_to_reg_label(a, fc_sel))
        addr_e.bind("<KeyRelease>", _update_reg_lbl)
        fc_combo.configure(command=lambda v: _update_reg_lbl())

        # Label
        label_e = ctk.CTkEntry(row_frame, width=150, height=30,
                                font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                fg_color=BG_INPUT, border_color=BORDER_COLOR,
                                placeholder_text="Tag name...")
        if label:
            label_e.insert(0, label)
        label_e.pack(side="left", padx=2)

        # Data type
        type_combo = ctk.CTkComboBox(row_frame, values=COMMON_DATA_TYPE_NAMES, width=140, height=30,
                                      font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                      fg_color=BG_INPUT, border_color=BORDER_COLOR,
                                      button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
                                      dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT_PRIMARY)
        type_combo.set(dtype)
        type_combo.pack(side="left", padx=2)

        # Raw value display (read-only)
        raw_lbl = ctk.CTkLabel(row_frame, text="—", width=110,
                                font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                text_color=TEXT_SECONDARY, anchor="w")
        raw_lbl.pack(side="left", padx=2)

        # Decoded value display
        dec_lbl = ctk.CTkLabel(row_frame, text="—", width=130,
                                font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                text_color=TEXT_PRIMARY, anchor="w")
        dec_lbl.pack(side="left", padx=2)

        # Status
        status_lbl = ctk.CTkLabel(row_frame, text="—", width=72,
                                   font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                   text_color=TEXT_MUTED, anchor="w")
        status_lbl.pack(side="left", padx=2)

        # Delete button
        del_btn = ctk.CTkButton(row_frame, text="✕", width=28, height=28,
                                 fg_color="transparent", text_color=TEXT_MUTED,
                                 hover_color=BG_CARD_HOVER,
                                 font=(FONT_FAMILY, FONT_SIZE_BODY),
                                 command=lambda rid=row_id: self._delete_row(rid))
        del_btn.pack(side="left", padx=2)

        # Store references
        self._row_vars[row_id] = {
            "frame": row_frame,
            "addr": addr_e,
            "count": count_e,
            "fc": fc_combo,
            "label": label_e,
            "type": type_combo,
            "raw": raw_lbl,
            "decoded": dec_lbl,
            "status": status_lbl,
        }

        # Create PollConfig entry
        cfg = PollConfig(row_id=row_id, address=addr, count=count, function_code=fc)
        self._poll_configs.append(cfg)

    def _delete_row(self, row_id: int):
        if row_id in self._row_vars:
            self._row_vars[row_id]["frame"].destroy()
            del self._row_vars[row_id]
            self._poll_configs = [c for c in self._poll_configs if c.row_id != row_id]

    def _collect_poll_configs(self) -> List[PollConfig]:
        """Read all row entries and build fresh PollConfig list."""
        configs = []
        for row_id, widgets in self._row_vars.items():
            try:
                addr = int(widgets["addr"].get().strip())
                count = max(1, min(125, int(widgets["count"].get().strip())))
                fc_name = widgets["fc"].get()
                fc = FC_READ_OPTIONS.get(fc_name, 3)
                label = widgets["label"].get().strip()
                dtype = widgets["type"].get()
                configs.append(PollConfig(
                    row_id=row_id, address=addr, count=count,
                    function_code=fc, label=label, data_type=dtype,
                ))
            except Exception:
                pass
        return configs

    # ── Connection ────────────────────────────────────────────────────────────

    def _do_connect(self):
        config = self._build_connection_config()
        if not config:
            return

        self._connect_btn.configure(state="disabled", text="Connecting...")
        self.after(50, lambda: self._connect_async(config))

    def _connect_async(self, config: ConnectionConfig):
        def _run():
            ok, msg = self._engine.connect(config)
            self.after(0, lambda: self._on_connect_result(ok, msg))

        threading.Thread(target=_run, daemon=True).start()

    def _on_connect_result(self, ok: bool, msg: str):
        self._connect_btn.configure(state="normal", text="🔌  Connect")
        if not ok:
            self._log_box.append(f"[ERROR] {msg}", "error")

    def _do_disconnect(self):
        self._engine.disconnect()
        self._log_box.append("Disconnected", "muted")

    def _build_connection_config(self) -> Optional[ConnectionConfig]:
        try:
            proto = self._proto_var.get()
            slave_id = int(self._slave_id_entry.get().strip() or "1")
            timeout = float(self._timeout_entry.get().strip() or "1.0")

            if proto == "TCP":
                host = self._tcp_host.get().strip()
                port = int(self._tcp_port.get().strip() or "502")
                return ConnectionConfig(
                    mode=ConnectionMode.TCP,
                    host=host, port=port,
                    slave_id=slave_id, timeout=timeout,
                )
            else:
                parity_map = {"None (N)": "N", "Even (E)": "E", "Odd (O)": "O"}
                return ConnectionConfig(
                    mode=ConnectionMode.RTU,
                    serial_port=self._rtu_port.get(),
                    baudrate=int(self._rtu_baud.get()),
                    parity=parity_map.get(self._rtu_parity.get(), "N"),
                    stopbits=int(self._rtu_stop.get()),
                    slave_id=slave_id, timeout=timeout,
                )
        except Exception as e:
            self._log_box.append(f"[ERROR] Invalid connection settings: {e}", "error")
            return None

    # ── Polling ───────────────────────────────────────────────────────────────

    def _toggle_poll(self):
        if self._polling:
            self._engine.stop_polling()
            self._polling = False
            self._poll_btn.configure(text="▶  Start Poll", fg_color=SAS_BLUE,
                                       hover_color=SAS_BLUE_DARK)
            self._log_box.append("Polling stopped", "muted")
        else:
            if not self._engine.is_connected:
                self._log_box.append("[!] Connect to a device before polling", "warn")
                return
            configs = self._collect_poll_configs()
            if not configs:
                self._log_box.append("[!] No valid rows in the poll table", "warn")
                return
            try:
                interval = float(self._poll_interval.get().strip() or "1.0")
            except Exception:
                interval = 1.0
            sid = None
            try:
                sid = int(self._slave_id_entry.get().strip())
            except Exception:
                pass
            self._engine.start_polling(configs, interval=interval, slave_id=sid)
            self._polling = True
            self._poll_btn.configure(text="⏹  Stop Poll", fg_color=STATUS_ERROR,
                                       hover_color="#C53030")
            self._log_box.append(f"Polling started — {len(configs)} item(s) @ {interval}s", "info")

    def _read_once(self):
        """Perform a single read of all poll table rows."""
        if not self._engine.is_connected:
            self._log_box.append("[!] Not connected — click Connect first", "warn")
            return
        configs = self._collect_poll_configs()
        if not configs:
            self._log_box.append("[!] No valid rows in poll table", "warn")
            return
        try:
            sid = int(self._slave_id_entry.get().strip())
        except Exception:
            sid = 1

        self._log_box.append(f"Reading {len(configs)} row(s) once...", "info")

        def _run():
            any_ok = False
            for cfg in configs:
                try:
                    ok, msg, values = self._engine.read_registers(
                        cfg.address, cfg.count, cfg.function_code, sid
                    )
                    if ok and values is not None:
                        any_ok = True
                        # Must schedule UI update on main thread
                        self.after(0, lambda rid=cfg.row_id, a=cfg.address, v=list(values):
                                    self._on_poll_result(rid, a, v))
                    else:
                        err = msg or "No response"
                        self.after(0, lambda rid=cfg.row_id, e=err:
                                    self._mark_row_error(rid, e))
                        self.after(0, lambda e=err:
                                    self._log_box.append(f"[ERROR] Read failed: {e}", "error"))
                except Exception as exc:
                    self.after(0, lambda rid=cfg.row_id, e=str(exc):
                                self._mark_row_error(rid, e))
                    self.after(0, lambda e=str(exc):
                                self._log_box.append(f"[ERROR] Exception: {e}", "error"))

        threading.Thread(target=_run, daemon=True, name="read-once").start()

    # ── Write ─────────────────────────────────────────────────────────────────

    def _do_write(self):
        if not self._engine.is_connected:
            self._write_status.configure(text="Not connected", text_color=STATUS_ERROR)
            return

        fc_name = self._write_fc.get()
        fc = FC_WRITE_OPTIONS.get(fc_name, 6)

        try:
            addr = int(self._write_addr.get().strip())
            val_str = self._write_val.get().strip()
        except Exception:
            self._write_status.configure(text="Invalid address/value", text_color=STATUS_ERROR)
            return

        try:
            sid = int(self._slave_id_entry.get().strip())
        except Exception:
            sid = 1

        dtype_str = self._write_type.get()
        try:
            dtype = DataType(dtype_str)
        except Exception:
            dtype = DataType.UINT16

        def _run():
            if fc == 5:
                val_bool = val_str.strip().upper() in ("1", "TRUE", "ON", "YES")
                ok, msg = self._engine.write_coil(addr, val_bool, sid)
            elif fc == 6:
                encoded = encode_value(val_str, dtype)
                if not encoded:
                    self.after(0, lambda: self._write_status.configure(
                        text="Encode failed", text_color=STATUS_ERROR))
                    return
                ok, msg = self._engine.write_register(addr, encoded[0], sid)
            elif fc == 16:
                encoded = encode_value(val_str, dtype)
                if not encoded:
                    self.after(0, lambda: self._write_status.configure(
                        text="Encode failed", text_color=STATUS_ERROR))
                    return
                ok, msg = self._engine.write_registers(addr, encoded, sid)
            else:
                ok, msg = False, "Unsupported write FC"

            color = STATUS_GOOD if ok else STATUS_ERROR
            self.after(0, lambda: self._write_status.configure(
                text=("✓ Written" if ok else f"✗ {msg}"), text_color=color))

        threading.Thread(target=_run, daemon=True).start()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_connected(self):
        self.after(0, self._update_connected_state, True)

    def _on_disconnected(self, msg: str):
        self.after(0, self._update_connected_state, False)

    def _update_connected_state(self, connected: bool):
        if connected:
            proto = self._proto_var.get()
            color = MODBUS_TCP_COLOR if proto == "TCP" else MODBUS_RTU_COLOR
            self._conn_badge.configure(text="⬤  Connected", text_color=color)
            self._connect_btn.configure(state="disabled")
            self._disconnect_btn.configure(state="normal")
            target = self._tcp_host.get() if proto == "TCP" else self._rtu_port.get()
            self._log_box.append(f"✓ Connected to {target}", "ok")
        else:
            if self._polling:
                self._polling = False
                self._poll_btn.configure(text="▶  Start Poll", fg_color=SAS_BLUE,
                                           hover_color=SAS_BLUE_DARK)
            self._conn_badge.configure(text="⬤  Disconnected", text_color=STATUS_OFFLINE)
            self._connect_btn.configure(state="normal")
            self._disconnect_btn.configure(state="disabled")

    def _mark_row_error(self, row_id: int, msg: str):
        """Mark a poll row as errored."""
        if row_id not in self._row_vars:
            return
        widgets = self._row_vars[row_id]
        widgets["raw"].configure(text="—", text_color=TEXT_MUTED)
        widgets["decoded"].configure(text="—", text_color=TEXT_MUTED)
        short = msg[:30] + "…" if len(msg) > 30 else msg
        widgets["status"].configure(text=f"ERR: {short}", text_color=STATUS_ERROR)

    def _on_poll_result(self, row_id: int, address: int, values: list):
        """Update a row's display with new polled values."""
        if row_id not in self._row_vars:
            return
        widgets = self._row_vars[row_id]
        dtype_str = widgets["type"].get()

        # Raw display
        if all(isinstance(v, bool) for v in values):
            raw = " ".join("1" if v else "0" for v in values[:8])
            if len(values) > 8:
                raw += "..."
        else:
            raw = " ".join(str(v) for v in values[:4])
            if len(values) > 4:
                raw += "..."
        widgets["raw"].configure(text=raw, text_color=TEXT_SECONDARY)

        # Decoded display
        try:
            dtype = DataType(dtype_str)
        except Exception:
            dtype = DataType.UINT16

        if all(isinstance(v, bool) for v in values):
            decoded = " ".join("ON" if v else "OFF" for v in values[:4])
        else:
            int_vals = [int(v) for v in values]
            decoded = decode_registers(int_vals, dtype)
        widgets["decoded"].configure(text=decoded, text_color=TEXT_PRIMARY)
        widgets["status"].configure(text="OK ✓", text_color=STATUS_GOOD)

        # Record for health monitor
        try:
            self._health.record_transaction(1, 3, 10.0, False)
        except Exception:
            pass

    def _on_transaction(self, rec: TransactionRecord):
        """Append a transaction to the log box."""
        tag = "error" if rec.error else "ok"
        self.after(0, lambda: self._log_box.append(rec.format_log_line(), tag))

    def _on_engine_error(self, msg: str):
        self.after(0, lambda: self._log_box.append(f"[ERROR] {msg}", "error"))

    # ── Protocol Change ───────────────────────────────────────────────────────

    def _on_proto_change(self, value: str):
        if value == "TCP":
            self._rtu_frame.pack_forget()
            self._tcp_frame.pack(fill="x", pady=(0, 4))
        else:
            self._tcp_frame.pack_forget()
            self._rtu_frame.pack(fill="x", pady=(0, 4))

    def _on_write_fc_change(self, value: str):
        """Adjust write panel hints based on selected FC."""
        if "Coil" in value:
            self._write_val.configure(placeholder_text="1 or 0 / TRUE/FALSE")
        else:
            self._write_val.configure(placeholder_text="value")

    # ── Log ───────────────────────────────────────────────────────────────────

    def _clear_log(self):
        self._log_box.clear()
        self._engine.clear_log()

    def _export_log(self):
        """Export transaction log to CSV."""
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Export Transaction Log",
        )
        if not path:
            return
        try:
            records = self._engine.get_log()
            with open(path, "w", encoding="utf-8") as f:
                f.write("Timestamp,SlaveID,FunctionCode,Address,Count,Values,Error,ResponseTimeMs\n")
                for r in records:
                    vals = str(r.values or "").replace(",", ";")
                    f.write(f"{r.timestamp.isoformat()},{r.slave_id},{r.function_code},"
                             f"{r.address},{r.count},{vals},{r.error or ''},{r.response_time_ms:.1f}\n")
            self._log_box.append(f"Log exported to {path}", "info")
        except Exception as e:
            self._log_box.append(f"Export error: {e}", "error")

    def on_show(self):
        """Called when this view becomes active."""
        pass
