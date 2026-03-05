"""
SAS Modbus Toolkit — Modbus Slave Simulator View
Simulates a Modbus slave device that responds to master requests.
Users can set register values and monitor incoming traffic.
"""

import logging
import threading
import time
import tkinter as tk
from datetime import datetime
from typing import Dict, List, Optional

import customtkinter as ctk

from core.modbus_server import ModbusSlaveSimulator, SlaveActivity
from core.serial_utils import get_available_ports, BAUD_RATES, PARITY_OPTIONS
from core.settings_manager import AppSettings
from ui.theme import *

logger = logging.getLogger(__name__)


class SlaveView(ctk.CTkFrame):
    """Modbus Slave Simulator — simulate a device that responds to masters."""

    def __init__(self, master_widget, settings: AppSettings, **kwargs):
        super().__init__(master_widget, fg_color=BG_DARK, **kwargs)
        self._settings = settings
        self._simulator = ModbusSlaveSimulator(on_activity=self._on_activity)
        self._running = False
        self._reg_entries: Dict[int, ctk.CTkEntry] = {}  # address → entry widget

        self._build_ui()

    def on_show(self):
        self._refresh_ports()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=BG_MEDIUM, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="📡  Modbus Slave Simulator",
                     font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=20, pady=12)

        self._status_var = tk.StringVar(value="● Stopped")
        self._status_lbl = ctk.CTkLabel(
            header, textvariable=self._status_var,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            text_color=STATUS_OFFLINE, fg_color=BG_CARD, corner_radius=12, padx=12, pady=4
        )
        self._status_lbl.pack(side="right", padx=16, pady=12)

        self._req_count_var = tk.StringVar(value="")
        ctk.CTkLabel(header, textvariable=self._req_count_var,
                     font=(FONT_FAMILY, FONT_SIZE_TINY), text_color=TEXT_MUTED).pack(side="right", padx=8)

        # ── Body ──────────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color=BG_DARK)
        body.pack(fill="both", expand=True)

        # Left: config
        left = ctk.CTkFrame(body, fg_color=BG_MEDIUM, width=280, corner_radius=0)
        left.pack(side="left", fill="y", padx=(0, 1))
        left.pack_propagate(False)
        self._build_config_panel(left)

        # Right: tabs for register data + activity log
        right = ctk.CTkFrame(body, fg_color=BG_DARK)
        right.pack(side="right", fill="both", expand=True)
        self._build_data_panel(right)

    def _build_config_panel(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Protocol
        ctk.CTkLabel(scroll, text="PROTOCOL", font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=16, pady=(16, 4))

        proto_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        proto_card.pack(fill="x", padx=16, pady=(0, 10))

        self._proto_var = tk.StringVar(value="TCP")
        for label, val in [("Modbus TCP", "TCP"), ("Modbus RTU (Serial)", "RTU")]:
            ctk.CTkRadioButton(
                proto_card, text=label, variable=self._proto_var, value=val,
                font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_PRIMARY,
                fg_color=SAS_BLUE, command=self._on_proto_change,
            ).pack(anchor="w", padx=12, pady=6)

        # Slave ID
        sid_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        sid_frame.pack(fill="x", padx=16, pady=(0, 8))

        sid_row = ctk.CTkFrame(sid_frame, fg_color="transparent")
        sid_row.pack(fill="x", padx=12, pady=10)
        ctk.CTkLabel(sid_row, text="Slave / Unit ID",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._slave_id = ctk.CTkEntry(sid_row, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, height=INPUT_HEIGHT, width=70)
        self._slave_id.insert(0, str(self._settings.slave_id))
        self._slave_id.pack(side="right")

        # TCP settings
        self._tcp_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        self._tcp_frame.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(self._tcp_frame, text="TCP LISTENER",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=SAS_BLUE, anchor="w").pack(fill="x", padx=12, pady=(8, 4))

        row_host = ctk.CTkFrame(self._tcp_frame, fg_color="transparent")
        row_host.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkLabel(row_host, text="Bind Address",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._tcp_host = ctk.CTkEntry(row_host, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, height=INPUT_HEIGHT, width=120)
        self._tcp_host.insert(0, "0.0.0.0")
        self._tcp_host.pack(side="right")

        row_port = ctk.CTkFrame(self._tcp_frame, fg_color="transparent")
        row_port.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row_port, text="Port",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._tcp_port = ctk.CTkEntry(row_port, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, height=INPUT_HEIGHT, width=80)
        self._tcp_port.insert(0, str(self._settings.slave_tcp_port))
        self._tcp_port.pack(side="right")

        # RTU settings (hidden initially)
        self._rtu_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)

        ctk.CTkLabel(self._rtu_frame, text="RTU / SERIAL",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=SAS_ORANGE, anchor="w").pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(self._rtu_frame, text="COM Port",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12)
        self._rtu_port = ctk.CTkComboBox(self._rtu_frame, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, height=INPUT_HEIGHT, values=["COM1"])
        self._rtu_port.pack(fill="x", padx=12, pady=(2, 8))

        row_b = ctk.CTkFrame(self._rtu_frame, fg_color="transparent")
        row_b.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkLabel(row_b, text="Baud Rate",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._rtu_baud = ctk.CTkComboBox(row_b, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, height=INPUT_HEIGHT, width=100,
                                          values=[str(b) for b in BAUD_RATES])
        self._rtu_baud.set("9600")
        self._rtu_baud.pack(side="right")

        row_p = ctk.CTkFrame(self._rtu_frame, fg_color="transparent")
        row_p.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row_p, text="Parity / Stop",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._rtu_parity = ctk.CTkSegmentedButton(
            row_p, values=["N", "E", "O"], font=(FONT_FAMILY, FONT_SIZE_SMALL),
            fg_color=BG_INPUT, selected_color=SAS_BLUE, width=90)
        self._rtu_parity.set("N")
        self._rtu_parity.pack(side="right")

        # Start/Stop button
        self._start_btn = ctk.CTkButton(
            scroll, text="▶  Start Slave",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg_color=STATUS_GOOD, hover_color="#16A34A",
            height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._toggle_server,
        )
        self._start_btn.pack(fill="x", padx=16, pady=(4, 16))

        # Info card
        ctk.CTkFrame(scroll, fg_color=BORDER_COLOR, height=1).pack(fill="x", padx=16, pady=4)
        info_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        info_card.pack(fill="x", padx=16, pady=(8, 16))

        ctk.CTkLabel(info_card, text="ℹ  How it works",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                     text_color=SAS_BLUE_LIGHT, anchor="w").pack(fill="x", padx=12, pady=(8, 4))

        info_text = ("Start the simulator, then use any Modbus master "
                     "to read/write this device. Edit register values "
                     "directly in the tables — masters will see your "
                     "changes immediately.")
        ctk.CTkLabel(info_card, text=info_text,
                     font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_SECONDARY, wraplength=220, justify="left",
                     anchor="w").pack(fill="x", padx=12, pady=(0, 10))

        self._on_proto_change()

    def _build_data_panel(self, parent):
        """Build tabbed register data + activity log panels."""
        # Tab bar
        tab_bar = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=0, height=36)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self._active_tab = tk.StringVar(value="holding")
        tabs = [
            ("Holding Registers (HR)", "holding"),
            ("Input Registers (IR)", "input"),
            ("Coils", "coils"),
            ("Activity Log", "log"),
        ]
        self._tab_btns = {}
        for label, key in tabs:
            btn = ctk.CTkButton(
                tab_bar, text=label, font=(FONT_FAMILY, FONT_SIZE_SMALL),
                fg_color="transparent", text_color=TEXT_SECONDARY,
                hover_color=BG_CARD_HOVER, height=32, corner_radius=0,
                command=lambda k=key: self._show_tab(k),
            )
            btn.pack(side="left", padx=2, pady=2)
            self._tab_btns[key] = btn

        # Content area
        self._content = ctk.CTkFrame(parent, fg_color=BG_DARK)
        self._content.pack(fill="both", expand=True)

        # Build each tab's frame
        self._hr_frame = self._build_register_table_tab("Holding Registers", 40,
                                                          "holding", editable=True)
        self._ir_frame = self._build_register_table_tab("Input Registers", 40,
                                                          "input", editable=True)
        self._coil_frame = self._build_coil_table_tab()
        self._log_frame = self._build_activity_log_tab()

        self._show_tab("holding")

    def _build_register_table_tab(self, title: str, count: int, data_type: str,
                                   editable: bool = True):
        """Build a tab showing a register table."""
        frame = ctk.CTkFrame(self._content, fg_color=BG_DARK)

        # Table header
        hdr = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=0, height=32)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text=f"  {title}  (edit values below — master will read them)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(side="left", padx=8)

        ctk.CTkButton(hdr, text="Fill 0s", font=(FONT_FAMILY, FONT_SIZE_TINY),
                      fg_color="transparent", text_color=TEXT_MUTED, hover_color=BG_CARD_HOVER,
                      height=24, width=60,
                      command=lambda: self._fill_registers(data_type, 0)).pack(side="right", padx=4)
        ctk.CTkButton(hdr, text="Fill Random", font=(FONT_FAMILY, FONT_SIZE_TINY),
                      fg_color="transparent", text_color=TEXT_MUTED, hover_color=BG_CARD_HOVER,
                      height=24, width=80,
                      command=lambda: self._fill_registers(data_type, -1)).pack(side="right", padx=2)

        # Column headers
        col_hdr = ctk.CTkFrame(frame, fg_color=BG_MEDIUM, corner_radius=0, height=26)
        col_hdr.pack(fill="x")
        col_hdr.pack_propagate(False)
        for text, w in [("Address", 80), ("Current Value", 130), ("Hex", 90), ("Set Value", 120)]:
            ctk.CTkLabel(col_hdr, text=text, font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                         text_color=TEXT_MUTED, width=w, anchor="center").pack(side="left", padx=2)

        # Scrollable rows
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        entries = {}
        val_labels = {}

        for i in range(count):
            bg = BG_CARD if i % 2 == 0 else BG_DARK
            row = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=0, height=30)
            row.pack(fill="x")
            row.pack_propagate(False)

            ctk.CTkLabel(row, text=str(i), font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                         text_color=TEXT_MUTED, width=80, anchor="center").pack(side="left")

            val_lbl = ctk.CTkLabel(row, text="0", font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                    text_color=TEXT_PRIMARY, width=130, anchor="center")
            val_lbl.pack(side="left")
            val_labels[i] = val_lbl

            hex_lbl = ctk.CTkLabel(row, text="0x0000", font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                    text_color=TEXT_MUTED, width=90, anchor="center")
            hex_lbl.pack(side="left")

            entry = ctk.CTkEntry(row, font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                                  fg_color=BG_INPUT, height=24, width=120,
                                  placeholder_text="set value")
            entry.pack(side="left", padx=4)

            def apply_value(evt, addr=i, e=entry, v=val_lbl, h=hex_lbl, dt=data_type):
                try:
                    val = int(e.get()) & 0xFFFF
                    if dt == "holding":
                        self._simulator.set_holding_register(addr, val)
                    else:
                        self._simulator.set_input_register(addr, val)
                    v.configure(text=str(val), text_color=STATUS_GOOD)
                    h.configure(text=f"0x{val:04X}")
                    e.delete(0, "end")
                    # Flash green then back
                    v.after(800, lambda: v.configure(text_color=TEXT_PRIMARY))
                except ValueError:
                    pass

            entry.bind("<Return>", apply_value)
            entries[i] = entry

        frame._entries = entries
        frame._val_labels = val_labels
        frame._data_type = data_type
        return frame

    def _build_coil_table_tab(self):
        """Build the coils table tab."""
        frame = ctk.CTkFrame(self._content, fg_color=BG_DARK)

        hdr = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=0, height=32)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="  Coils (FC01) & Discrete Inputs (FC02) — toggle to set ON/OFF",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(side="left", padx=8)

        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Show 32 coils in a grid
        self._coil_switches = {}
        COLS = 8
        for i in range(32):
            row_i = i // COLS
            col_i = i % COLS
            if col_i == 0:
                grid_row = ctk.CTkFrame(scroll, fg_color="transparent")
                grid_row.pack(fill="x", padx=8, pady=2)

            cell = ctk.CTkFrame(grid_row, fg_color=BG_CARD, corner_radius=6, width=90, height=60)
            cell.pack(side="left", padx=4)
            cell.pack_propagate(False)

            ctk.CTkLabel(cell, text=f"C{i:03d}", font=(FONT_FAMILY_MONO, FONT_SIZE_TINY),
                         text_color=TEXT_MUTED).pack(pady=(6, 0))

            sw_var = tk.BooleanVar(value=False)

            def toggle(v=sw_var, addr=i):
                self._simulator.set_coil(addr, v.get())
                self._simulator.set_discrete_input(addr, v.get())

            sw = ctk.CTkSwitch(cell, text="", variable=sw_var, onvalue=True, offvalue=False,
                                fg_color=BG_INPUT, progress_color=STATUS_GOOD,
                                command=lambda v=sw_var, a=i: self._toggle_coil(v, a))
            sw.pack(pady=(0, 6))
            self._coil_switches[i] = sw_var

        return frame

    def _toggle_coil(self, var: tk.BooleanVar, address: int):
        val = var.get()
        self._simulator.set_coil(address, val)
        self._simulator.set_discrete_input(address, val)

    def _build_activity_log_tab(self):
        """Build the activity log tab."""
        frame = ctk.CTkFrame(self._content, fg_color=BG_DARK)

        hdr = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=0, height=32)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="  Incoming Request Log",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=8)
        ctk.CTkButton(hdr, text="Clear", font=(FONT_FAMILY, FONT_SIZE_TINY),
                      fg_color="transparent", text_color=TEXT_MUTED, hover_color=BG_CARD_HOVER,
                      height=24, width=50, command=self._clear_log).pack(side="right", padx=8)

        self._log_text = tk.Text(
            frame, font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
            bg=resolve_color(BG_DARK), fg=resolve_color(TEXT_SECONDARY),
            relief="flat", bd=0, state="disabled", wrap="none",
        )
        self._log_text.pack(fill="both", expand=True, padx=2, pady=2)
        self._log_text.tag_config("read", foreground=LOG_TX)
        self._log_text.tag_config("write", foreground=SAS_ORANGE)
        self._log_text.tag_config("info", foreground=LOG_INFO)

        scroll = ctk.CTkScrollbar(frame, command=self._log_text.yview)
        scroll.pack(side="right", fill="y")
        self._log_text.configure(yscrollcommand=scroll.set)

        return frame

    def _show_tab(self, key: str):
        """Switch active tab."""
        for frame in [self._hr_frame, self._ir_frame, self._coil_frame, self._log_frame]:
            frame.pack_forget()

        active = {"holding": self._hr_frame, "input": self._ir_frame,
                  "coils": self._coil_frame, "log": self._log_frame}.get(key)
        if active:
            active.pack(fill="both", expand=True)

        for k, btn in self._tab_btns.items():
            if k == key:
                btn.configure(fg_color=BG_CARD, text_color=SAS_BLUE_LIGHT)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_SECONDARY)

        self._active_tab.set(key)

    def _on_proto_change(self):
        proto = self._proto_var.get()
        if proto == "TCP":
            self._tcp_frame.pack(fill="x", padx=16, pady=(0, 8))
            self._rtu_frame.pack_forget()
        else:
            self._tcp_frame.pack_forget()
            self._rtu_frame.pack(fill="x", padx=16, pady=(0, 8))

    def _refresh_ports(self):
        try:
            ports = get_available_ports()
            if ports:
                self._rtu_port.configure(values=ports)
                self._rtu_port.set(ports[0])
        except Exception:
            pass

    def _toggle_server(self):
        if self._running:
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self):
        proto = self._proto_var.get()
        try:
            slave_id = int(self._slave_id.get())
        except ValueError:
            slave_id = 1

        self._start_btn.configure(text="Starting...", state="disabled")
        self.update()

        def start_thread():
            success = False
            if proto == "TCP":
                host = self._tcp_host.get().strip()
                try:
                    port = int(self._tcp_port.get())
                except ValueError:
                    port = 502
                success = self._simulator.start_tcp(host, port, slave_id)
            else:
                com = self._rtu_port.get()
                try:
                    baud = int(self._rtu_baud.get())
                except ValueError:
                    baud = 9600
                parity = self._rtu_parity.get()
                success = self._simulator.start_rtu(com, baud, parity, 1, slave_id)

            self.after(0, lambda: self._on_start_result(success, proto, slave_id))

        threading.Thread(target=start_thread, daemon=True).start()

    def _on_start_result(self, success: bool, proto: str, slave_id: int):
        if success:
            self._running = True
            self._start_btn.configure(text="⏹  Stop Slave", fg_color=STATUS_ERROR,
                                       hover_color="#DC2626", state="normal")
            self._status_var.set("● Running")
            self._status_lbl.configure(text_color=STATUS_GOOD)
            self._append_log(f"Slave started — {proto}, Unit ID {slave_id}", "info")
        else:
            self._start_btn.configure(text="▶  Start Slave", fg_color=STATUS_GOOD,
                                       hover_color="#16A34A", state="normal")
            self._append_log("Failed to start — check port/IP and try again", "info")

    def _stop_server(self):
        self._simulator.stop()
        self._running = False
        self._start_btn.configure(text="▶  Start Slave", fg_color=STATUS_GOOD,
                                   hover_color="#16A34A")
        self._status_var.set("● Stopped")
        self._status_lbl.configure(text_color=STATUS_OFFLINE)
        self._append_log("Slave stopped", "info")

    def _on_activity(self, activity: SlaveActivity):
        """Called when the slave receives a request (from background thread)."""
        self.after(0, lambda a=activity: self._render_activity(a))

    def _render_activity(self, activity: SlaveActivity):
        fc_name = {1: "FC01 Coils", 2: "FC02 DI", 3: "FC03 HR", 4: "FC04 IR",
                   5: "FC05 Write Coil", 6: "FC06 Write Reg",
                   15: "FC15 Write Coils", 16: "FC16 Write Regs"}.get(
            activity.function_code, f"FC{activity.function_code:02d}")

        ts = datetime.fromtimestamp(activity.timestamp).strftime("%H:%M:%S.%f")[:-3]
        tag = "write" if activity.is_write else "read"

        if activity.is_write:
            msg = (f"[{ts}]  WRITE  {fc_name} | "
                   f"Addr {activity.address} | "
                   f"Values: {activity.values[:8]}"
                   + (" ..." if len(activity.values) > 8 else "") + "\n")
        else:
            msg = (f"[{ts}]  READ   {fc_name} | "
                   f"Addr {activity.address} | "
                   f"Count {activity.count}\n")

        self._append_log(msg.rstrip(), tag)

        # Update stats
        self._req_count_var.set(
            f"Requests: {self._simulator.request_count}  "
            f"Writes: {self._simulator.write_count}")

    def _fill_registers(self, data_type: str, fill_val: int):
        """Fill all registers with a value (-1 = random)."""
        import random
        frame = self._hr_frame if data_type == "holding" else self._ir_frame
        for addr, lbl in frame._val_labels.items():
            val = random.randint(0, 65535) if fill_val < 0 else fill_val
            if data_type == "holding":
                self._simulator.set_holding_register(addr, val)
            else:
                self._simulator.set_input_register(addr, val)
            lbl.configure(text=str(val))

    def _append_log(self, message: str, tag: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if not message.startswith("["):
            message = f"[{ts}]  {message}"
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def destroy(self):
        self._simulator.stop()
        super().destroy()
