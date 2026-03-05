"""
SAS Modbus Toolkit — Modbus Slave (Simulator) View
Simulates a Modbus slave device for testing master tools and
commissioning new networks where no real device is available.
"""

import logging
import threading
import tkinter as tk
from typing import Dict, List, Optional

import customtkinter as ctk

from core.modbus_slave import ModbusSlaveServer, SlaveConfig, SlaveMode
from ui.theme import *
from ui.widgets import (
    LogBox, get_serial_ports, make_card, make_primary_button,
    make_secondary_button, make_danger_button, enable_touch_scroll
)

logger = logging.getLogger(__name__)

BAUD_RATES = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]
REG_PAGE_SIZE = 20  # Registers per page in the viewer


class SlaveView(ctk.CTkFrame):
    """Modbus Slave Simulator view."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._server = ModbusSlaveServer()
        self._server.on_started = self._on_started
        self._server.on_stopped = self._on_stopped
        self._server.on_error = self._on_server_error
        # on_register_changed is fired from simulation thread — route to main thread
        self._server.on_register_changed = lambda bank, addr, val: \
            self.after(0, lambda: self._on_reg_changed(bank, addr, val))

        self._holding_vars: Dict[int, ctk.CTkEntry] = {}
        self._input_vars:   Dict[int, ctk.CTkEntry] = {}
        self._coil_vars:    Dict[int, ctk.CTkCheckBox] = {}
        self._discrete_vars: Dict[int, ctk.CTkCheckBox] = {}

        self._hr_page = 0
        self._ir_page = 0

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=50)
        hdr.pack(fill="x", padx=24, pady=(16, 4))
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="🖥  Modbus Slave Simulator",
                      font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                      text_color=TEXT_PRIMARY, anchor="w").pack(side="left")

        self._status_badge = ctk.CTkLabel(
            hdr, text="⬤  Server Stopped",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            text_color=STATUS_OFFLINE,
        )
        self._status_badge.pack(side="right", padx=8)

        # ── Scrollable area ───────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True)
        enable_touch_scroll(self._scroll)

        self._build_config_card()
        self._build_register_tabs()
        self._build_log_card()

    def _build_config_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(4, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=10)

        # Row 1: Protocol + Slave ID + Simulate toggle + Start/Stop
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
        )
        self._slave_id_entry.insert(0, "1")
        self._slave_id_entry.pack(side="left", padx=(0, 24))

        # Simulate toggle
        self._sim_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            row1, text="Simulation Mode",
            variable=self._sim_var,
            command=self._toggle_simulation,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT_PRIMARY,
            fg_color=SAS_ORANGE, hover_color=SAS_ORANGE_DARK,
            border_color=BORDER_COLOR,
        ).pack(side="left", padx=(0, 24))

        ctk.CTkLabel(row1, text="(auto-varies HR0, IR0, Coil0)",
                      font=(FONT_FAMILY, FONT_SIZE_SMALL),
                      text_color=TEXT_MUTED).pack(side="left", padx=(0, 24))

        self._start_btn = make_primary_button(row1, "▶  Start Server", self._do_start, width=140)
        self._start_btn.pack(side="left", padx=(0, 6))

        self._stop_btn = make_danger_button(row1, "⏹  Stop Server", self._do_stop, width=140)
        self._stop_btn.pack(side="left")
        self._stop_btn.configure(state="disabled")

        # Row 2: TCP settings
        self._tcp_frame = ctk.CTkFrame(inner, fg_color="transparent")
        self._tcp_frame.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(self._tcp_frame, text="Bind Address:",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._tcp_host = ctk.CTkEntry(
            self._tcp_frame, width=150, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
        )
        self._tcp_host.insert(0, "0.0.0.0")
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

        # Tip label
        ctk.CTkLabel(
            self._tcp_frame,
            text="ℹ  Port 502 may require administrator rights",
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED,
        ).pack(side="left", padx=(16, 0))

        # Row 3: RTU settings
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

        ctk.CTkLabel(self._rtu_frame, text="Stop Bits:",
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

    def _build_register_tabs(self):
        """Build the tabbed register editor."""
        tabs = ctk.CTkTabview(self._scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS,
                               segmented_button_fg_color=BG_MEDIUM,
                               segmented_button_selected_color=SAS_BLUE,
                               segmented_button_selected_hover_color=SAS_BLUE_DARK,
                               segmented_button_unselected_color=BG_MEDIUM,
                               segmented_button_unselected_hover_color=BG_CARD_HOVER,
                               text_color=TEXT_PRIMARY)
        tabs.pack(fill="x", padx=24, pady=(0, 4))

        tabs.add("Holding Registers (FC03)")
        tabs.add("Input Registers (FC04)")
        tabs.add("Coils (FC01)")
        tabs.add("Discrete Inputs (FC02)")

        self._build_holding_tab(tabs.tab("Holding Registers (FC03)"))
        self._build_input_tab(tabs.tab("Input Registers (FC04)"))
        self._build_coils_tab(tabs.tab("Coils (FC01)"))
        self._build_discrete_tab(tabs.tab("Discrete Inputs (FC02)"))

    def _build_holding_tab(self, parent):
        """Holding registers — editable grid."""
        ctrl = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(ctrl, text="Holding Registers (read/write by master)",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left")

        make_secondary_button(ctrl, "Set All Zero", lambda: self._zero_holding(), width=110).pack(side="right", padx=(6, 0))
        make_primary_button(ctrl, "Apply Changes", lambda: self._apply_holding(), width=130).pack(side="right")

        # Navigation
        nav = ctk.CTkFrame(parent, fg_color="transparent")
        nav.pack(fill="x", padx=8, pady=(0, 4))

        ctk.CTkLabel(nav, text="Start Address:",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._hr_start = ctk.CTkEntry(nav, width=80, height=30,
                                        font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                        fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._hr_start.insert(0, "0")
        self._hr_start.pack(side="left", padx=(0, 12))

        make_secondary_button(nav, "◀ Prev", lambda: self._nav_hr(-1), width=80).pack(side="left", padx=(0, 4))
        make_secondary_button(nav, "Next ▶", lambda: self._nav_hr(1), width=80).pack(side="left")

        self._hr_page_lbl = ctk.CTkLabel(nav, text="",
                                           font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                           text_color=TEXT_MUTED)
        self._hr_page_lbl.pack(side="left", padx=12)

        # Grid
        self._hr_grid = ctk.CTkFrame(parent, fg_color="transparent")
        self._hr_grid.pack(fill="x", padx=8, pady=(0, 8))
        self._build_holding_grid()

    def _build_holding_grid(self):
        for widget in self._hr_grid.winfo_children():
            widget.destroy()
        self._holding_vars.clear()

        start = self._hr_page * REG_PAGE_SIZE
        self._hr_page_lbl.configure(text=f"Addresses {start}–{start+REG_PAGE_SIZE-1}")

        cols = 4
        for i in range(REG_PAGE_SIZE):
            addr = start + i
            row_f = i // cols
            col_f = i % cols

            cell = ctk.CTkFrame(self._hr_grid, fg_color="transparent")
            cell.grid(row=row_f, column=col_f, padx=4, pady=2, sticky="w")

            ctk.CTkLabel(cell, text=f"{addr:4d}:", width=45,
                          font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                          text_color=TEXT_MUTED, anchor="e").pack(side="left")

            ent = ctk.CTkEntry(cell, width=80, height=28,
                                font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                fg_color=BG_INPUT, border_color=BORDER_COLOR)
            ent.insert(0, str(self._server.get_holding_register(addr)))
            ent.pack(side="left", padx=(2, 0))
            self._holding_vars[addr] = ent

    def _nav_hr(self, direction: int):
        try:
            start = int(self._hr_start.get().strip())
        except Exception:
            start = 0
        self._hr_page = max(0, (start // REG_PAGE_SIZE) + direction)
        new_start = self._hr_page * REG_PAGE_SIZE
        self._hr_start.delete(0, "end")
        self._hr_start.insert(0, str(new_start))
        self._build_holding_grid()

    def _apply_holding(self):
        for addr, ent in self._holding_vars.items():
            try:
                val = int(ent.get().strip() or "0")
                self._server.set_holding_register(addr, val)
            except Exception:
                pass
        self._log_box.append(f"Holding registers updated (addr {self._hr_page * REG_PAGE_SIZE}+)", "ok")

    def _zero_holding(self):
        for addr, ent in self._holding_vars.items():
            ent.delete(0, "end")
            ent.insert(0, "0")
            self._server.set_holding_register(addr, 0)

    def _build_input_tab(self, parent):
        """Input registers — read-only by master, editable here."""
        ctrl = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(ctrl, text="Input Registers (read-only by master, set value here)",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left")

        make_primary_button(ctrl, "Apply Changes", lambda: self._apply_input(), width=130).pack(side="right")

        nav = ctk.CTkFrame(parent, fg_color="transparent")
        nav.pack(fill="x", padx=8, pady=(0, 4))

        ctk.CTkLabel(nav, text="Start Address:",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self._ir_start = ctk.CTkEntry(nav, width=80, height=30,
                                        font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                        fg_color=BG_INPUT, border_color=BORDER_COLOR)
        self._ir_start.insert(0, "0")
        self._ir_start.pack(side="left", padx=(0, 12))

        make_secondary_button(nav, "◀ Prev", lambda: self._nav_ir(-1), width=80).pack(side="left", padx=(0, 4))
        make_secondary_button(nav, "Next ▶", lambda: self._nav_ir(1), width=80).pack(side="left")

        self._ir_page_lbl = ctk.CTkLabel(nav, text="",
                                           font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                           text_color=TEXT_MUTED)
        self._ir_page_lbl.pack(side="left", padx=12)

        self._ir_grid = ctk.CTkFrame(parent, fg_color="transparent")
        self._ir_grid.pack(fill="x", padx=8, pady=(0, 8))
        self._build_input_grid()

    def _build_input_grid(self):
        for widget in self._ir_grid.winfo_children():
            widget.destroy()
        self._input_vars.clear()

        start = self._ir_page * REG_PAGE_SIZE
        self._ir_page_lbl.configure(text=f"Addresses {start}–{start+REG_PAGE_SIZE-1}")

        cols = 4
        for i in range(REG_PAGE_SIZE):
            addr = start + i
            row_f = i // cols
            col_f = i % cols

            cell = ctk.CTkFrame(self._ir_grid, fg_color="transparent")
            cell.grid(row=row_f, column=col_f, padx=4, pady=2, sticky="w")

            ctk.CTkLabel(cell, text=f"{addr:4d}:", width=45,
                          font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                          text_color=TEXT_MUTED, anchor="e").pack(side="left")

            ent = ctk.CTkEntry(cell, width=80, height=28,
                                font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                fg_color=BG_INPUT, border_color=BORDER_COLOR)
            ent.insert(0, str(self._server.get_input_register(addr)))
            ent.pack(side="left", padx=(2, 0))
            self._input_vars[addr] = ent

    def _nav_ir(self, direction: int):
        try:
            start = int(self._ir_start.get().strip())
        except Exception:
            start = 0
        self._ir_page = max(0, (start // REG_PAGE_SIZE) + direction)
        new_start = self._ir_page * REG_PAGE_SIZE
        self._ir_start.delete(0, "end")
        self._ir_start.insert(0, str(new_start))
        self._build_input_grid()

    def _apply_input(self):
        for addr, ent in self._input_vars.items():
            try:
                val = int(ent.get().strip() or "0")
                self._server.set_input_register(addr, val)
            except Exception:
                pass
        self._log_box.append(f"Input registers updated", "ok")

    def _build_coils_tab(self, parent):
        ctk.CTkLabel(parent, text="Coils (read/write by master — toggle ON/OFF here)",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY, anchor="w").pack(fill="x", padx=8, pady=(8, 4))

        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x", padx=8, pady=(0, 8))

        self._coil_vars.clear()
        cols = 8
        for i in range(40):
            row_f = i // cols
            col_f = i % cols
            var = ctk.BooleanVar(value=self._server.get_coil(i))
            cb = ctk.CTkCheckBox(grid, text=f"C{i:02d}",
                                  variable=var,
                                  font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                  text_color=TEXT_PRIMARY,
                                  fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
                                  border_color=BORDER_COLOR,
                                  width=70,
                                  command=lambda addr=i, v=var: self._server.set_coil(addr, v.get()))
            cb.grid(row=row_f, column=col_f, padx=4, pady=3, sticky="w")
            self._coil_vars[i] = var

    def _build_discrete_tab(self, parent):
        ctk.CTkLabel(parent, text="Discrete Inputs (read-only by master — toggle here to simulate sensor states)",
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_SECONDARY, anchor="w").pack(fill="x", padx=8, pady=(8, 4))

        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x", padx=8, pady=(0, 8))

        self._discrete_vars.clear()
        cols = 8
        for i in range(40):
            row_f = i // cols
            col_f = i % cols
            var = ctk.BooleanVar(value=self._server.get_discrete(i))
            cb = ctk.CTkCheckBox(grid, text=f"D{i:02d}",
                                  variable=var,
                                  font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                  text_color=TEXT_PRIMARY,
                                  fg_color=SAS_ORANGE, hover_color=SAS_ORANGE_DARK,
                                  border_color=BORDER_COLOR,
                                  width=70,
                                  command=lambda addr=i, v=var: self._server.set_discrete(addr, v.get()))
            cb.grid(row=row_f, column=col_f, padx=4, pady=3, sticky="w")
            self._discrete_vars[i] = var

    def _build_log_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 16))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PADDING, pady=(10, 4))

        ctk.CTkLabel(hdr, text="📋  Server Log",
                      font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                      text_color=TEXT_PRIMARY).pack(side="left")
        make_secondary_button(hdr, "Clear", lambda: self._log_box.clear(), width=80).pack(side="right")

        self._log_box = LogBox(card, height=140)
        self._log_box.pack(fill="x", padx=CARD_PADDING, pady=(0, 10))
        self._log_box.append("Slave server ready — configure and click Start Server", "info")

    # ── Server Control ────────────────────────────────────────────────────────

    def _do_start(self):
        config = self._build_config()
        if not config:
            return

        self._start_btn.configure(state="disabled", text="Starting...")
        self._log_box.append(f"Starting {config.mode.value} server...", "info")

        def _run():
            ok, msg = self._server.start(config)
            self.after(0, lambda: self._log_box.append(
                f"{'✓ ' + msg if ok else '✗ ' + msg}",
                "ok" if ok else "error"
            ))
            if not ok:
                self.after(0, lambda: self._start_btn.configure(state="normal", text="▶  Start Server"))

        threading.Thread(target=_run, daemon=True).start()

    def _do_stop(self):
        self._server.stop()

    def _build_config(self) -> Optional[SlaveConfig]:
        try:
            proto = self._proto_var.get()
            slave_id = int(self._slave_id_entry.get().strip() or "1")
            if proto == "TCP":
                port = int(self._tcp_port.get().strip() or "502")
                return SlaveConfig(
                    mode=SlaveMode.TCP,
                    slave_id=slave_id,
                    host=self._tcp_host.get().strip(),
                    port=port,
                )
            else:
                parity_map = {"None (N)": "N", "Even (E)": "E", "Odd (O)": "O"}
                return SlaveConfig(
                    mode=SlaveMode.RTU,
                    slave_id=slave_id,
                    serial_port=self._rtu_port.get(),
                    baudrate=int(self._rtu_baud.get()),
                    parity=parity_map.get(self._rtu_parity.get(), "N"),
                    stopbits=int(self._rtu_stop.get()),
                )
        except Exception as e:
            self._log_box.append(f"[ERROR] Invalid settings: {e}", "error")
            return None

    def _toggle_simulation(self):
        if self._sim_var.get():
            self._server.start_simulation()
            self._log_box.append("Simulation mode ON — HR0, IR0, Coil0 updating automatically", "info")
        else:
            self._server.stop_simulation()
            self._log_box.append("Simulation mode OFF", "muted")

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_started(self):
        def _ui():
            proto = self._proto_var.get()
            color = MODBUS_TCP_COLOR if proto == "TCP" else MODBUS_RTU_COLOR
            self._status_badge.configure(text="⬤  Server Running", text_color=color)
            self._start_btn.configure(state="disabled", text="▶  Start Server")
            self._stop_btn.configure(state="normal")
            self._proto_seg.configure(state="disabled")
        self.after(0, _ui)

    def _on_stopped(self):
        def _ui():
            self._status_badge.configure(text="⬤  Server Stopped", text_color=STATUS_OFFLINE)
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            self._proto_seg.configure(state="normal")
        self.after(0, _ui)

    def _on_server_error(self, msg: str):
        self.after(0, lambda: self._log_box.append(f"[ERROR] {msg}", "error"))

    def _on_reg_changed(self, bank: str, address: int, value):
        """Refresh the UI entry when a register is changed by simulation."""
        if bank == "holding" and address in self._holding_vars:
            e = self._holding_vars[address]
            e.delete(0, "end")
            e.insert(0, str(value))
        elif bank == "input" and address in self._input_vars:
            e = self._input_vars[address]
            e.delete(0, "end")
            e.insert(0, str(value))
        elif bank == "coil" and address in self._coil_vars:
            self._coil_vars[address].set(bool(value))

    def _on_proto_change(self, value: str):
        if value == "TCP":
            self._rtu_frame.pack_forget()
            self._tcp_frame.pack(fill="x", pady=(0, 4))
        else:
            self._tcp_frame.pack_forget()
            self._rtu_frame.pack(fill="x", pady=(0, 4))

    def on_show(self):
        pass
