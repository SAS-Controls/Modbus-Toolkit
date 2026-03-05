"""
SAS Modbus Toolkit — Register Explorer View
Systematically scans a device's register address space to discover
which registers exist, their values, and map the device's data layout.
"""

import logging
import threading
import time
import tkinter as tk
from datetime import datetime
from typing import Optional

import customtkinter as ctk

from core.modbus_client import ModbusClientWrapper, FunctionCode, BAUD_RATES
from core.serial_utils import get_available_ports
from core.settings_manager import AppSettings
from ui.theme import *

logger = logging.getLogger(__name__)


class ExplorerView(ctk.CTkFrame):
    """Register Explorer — discover a device's full register map."""

    def __init__(self, master_widget, settings: AppSettings, **kwargs):
        super().__init__(master_widget, fg_color=BG_DARK, **kwargs)
        self._settings = settings
        self._client = ModbusClientWrapper()
        self._scanning = False
        self._scan_thread: Optional[threading.Thread] = None
        self._results: list = []  # (address, value, status)

        self._build_ui()

    def on_show(self):
        self._refresh_ports()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=BG_MEDIUM, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="🗺  Register Explorer",
                     font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=20, pady=12)

        self._prog_var = tk.StringVar(value="")
        ctk.CTkLabel(header, textvariable=self._prog_var,
                     font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_MUTED).pack(side="right", padx=16)

        self._status_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(header, textvariable=self._status_var,
                     font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                     text_color=STATUS_INFO).pack(side="right", padx=4)

        # ── Body ──────────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color=BG_DARK)
        body.pack(fill="both", expand=True)

        # Left config
        left = ctk.CTkFrame(body, fg_color=BG_MEDIUM, width=290, corner_radius=0)
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

        # Protocol
        ctk.CTkLabel(scroll, text="CONNECTION",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=16, pady=(16, 4))

        proto_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        proto_card.pack(fill="x", padx=16, pady=(0, 8))

        self._proto_var = tk.StringVar(value="TCP")
        for label, val in [("Modbus TCP", "TCP"), ("Modbus RTU (Serial)", "RTU")]:
            ctk.CTkRadioButton(
                proto_card, text=label, variable=self._proto_var, value=val,
                font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_PRIMARY,
                fg_color=SAS_BLUE, command=self._on_proto_change,
            ).pack(anchor="w", padx=12, pady=5)

        # TCP
        self._tcp_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        self._tcp_frame.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(self._tcp_frame, text="IP Address",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        self._tcp_host = ctk.CTkEntry(self._tcp_frame, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, height=INPUT_HEIGHT)
        self._tcp_host.insert(0, self._settings.tcp_host)
        self._tcp_host.pack(fill="x", padx=12, pady=(0, 8))

        row_p = ctk.CTkFrame(self._tcp_frame, fg_color="transparent")
        row_p.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row_p, text="Port", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_SECONDARY).pack(side="left")
        self._tcp_port = ctk.CTkEntry(row_p, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, height=INPUT_HEIGHT, width=80)
        self._tcp_port.insert(0, "502")
        self._tcp_port.pack(side="right")

        # RTU
        self._rtu_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        ctk.CTkLabel(self._rtu_frame, text="COM Port",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        self._rtu_port = ctk.CTkComboBox(self._rtu_frame, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, height=INPUT_HEIGHT, values=["COM1"])
        self._rtu_port.pack(fill="x", padx=12, pady=(0, 8))

        rtu_row = ctk.CTkFrame(self._rtu_frame, fg_color="transparent")
        rtu_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(rtu_row, text="Baud",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._rtu_baud = ctk.CTkComboBox(rtu_row, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                          fg_color=BG_INPUT, height=INPUT_HEIGHT, width=100,
                                          values=[str(b) for b in BAUD_RATES])
        self._rtu_baud.set("9600")
        self._rtu_baud.pack(side="right")

        # Slave ID + FC
        scan_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS)
        scan_card.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(scan_card, text="SCAN SETTINGS",
                     font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(fill="x", padx=12, pady=(8, 4))

        row_sid = ctk.CTkFrame(scan_card, fg_color="transparent")
        row_sid.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(row_sid, text="Slave ID",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._slave_id = ctk.CTkEntry(row_sid, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, height=INPUT_HEIGHT, width=70)
        self._slave_id.insert(0, "1")
        self._slave_id.pack(side="right")

        ctk.CTkLabel(scan_card, text="Function Code",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(fill="x", padx=12)
        self._fc_combo = ctk.CTkComboBox(
            scan_card, values=[
                "FC03 – Read Holding Registers",
                "FC04 – Read Input Registers",
                "FC01 – Read Coils",
                "FC02 – Read Discrete Inputs",
            ],
            font=(FONT_FAMILY, FONT_SIZE_SMALL), fg_color=BG_INPUT, height=INPUT_HEIGHT,
        )
        self._fc_combo.set("FC03 – Read Holding Registers")
        self._fc_combo.pack(fill="x", padx=12, pady=(2, 8))

        # Address range
        range_row = ctk.CTkFrame(scan_card, fg_color="transparent")
        range_row.pack(fill="x", padx=12, pady=(0, 6))

        left_col = ctk.CTkFrame(range_row, fg_color="transparent")
        left_col.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkLabel(left_col, text="Start Addr",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(anchor="w")
        self._start_addr = ctk.CTkEntry(left_col, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                         fg_color=BG_INPUT, height=INPUT_HEIGHT)
        self._start_addr.insert(0, "0")
        self._start_addr.pack(fill="x")

        right_col = ctk.CTkFrame(range_row, fg_color="transparent")
        right_col.pack(side="right", fill="x", expand=True)
        ctk.CTkLabel(right_col, text="End Addr",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY,
                     anchor="w").pack(anchor="w")
        self._end_addr = ctk.CTkEntry(right_col, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                       fg_color=BG_INPUT, height=INPUT_HEIGHT)
        self._end_addr.insert(0, "99")
        self._end_addr.pack(fill="x")

        # Chunk size
        chunk_row = ctk.CTkFrame(scan_card, fg_color="transparent")
        chunk_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(chunk_row, text="Block Size",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._chunk_size = ctk.CTkComboBox(chunk_row, values=["1", "4", "8", "16", "32", "64"],
                                            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                            fg_color=BG_INPUT, height=INPUT_HEIGHT, width=80)
        self._chunk_size.set("16")
        self._chunk_size.pack(side="right")

        # Timeout
        to_row = ctk.CTkFrame(scan_card, fg_color="transparent")
        to_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(to_row, text="Timeout (s)",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SECONDARY).pack(side="left")
        self._timeout = ctk.CTkEntry(to_row, font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                      fg_color=BG_INPUT, height=INPUT_HEIGHT, width=70)
        self._timeout.insert(0, "1.0")
        self._timeout.pack(side="right")

        # Scan button
        self._scan_btn = ctk.CTkButton(
            scroll, text="🔍  Scan Register Map",
            font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
            fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
            height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._toggle_scan,
        )
        self._scan_btn.pack(fill="x", padx=16, pady=(4, 8))

        # Progress bar
        self._progress = ctk.CTkProgressBar(scroll, fg_color=BG_CARD,
                                             progress_color=SAS_BLUE, height=6)
        self._progress.set(0)
        self._progress.pack(fill="x", padx=16, pady=(0, 16))

        # Export button
        ctk.CTkButton(
            scroll, text="📤  Export CSV",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            fg_color="transparent", text_color=TEXT_SECONDARY,
            border_color=BORDER_COLOR, border_width=1,
            hover_color=BG_CARD_HOVER, height=32, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._export_csv,
        ).pack(fill="x", padx=16, pady=(0, 16))

        self._on_proto_change()

    def _build_results(self, parent):
        """Build the results grid and summary panel."""
        # Summary stats row
        stats_frame = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=0, height=40)
        stats_frame.pack(fill="x")
        stats_frame.pack_propagate(False)

        self._found_var = tk.StringVar(value="—")
        self._missing_var = tk.StringVar(value="—")
        self._total_var = tk.StringVar(value="—")

        for label, var, color in [
            ("Responding", self._found_var, STATUS_GOOD),
            ("Timeout/Error", self._missing_var, STATUS_ERROR),
            ("Scanned", self._total_var, TEXT_SECONDARY),
        ]:
            cell = ctk.CTkFrame(stats_frame, fg_color="transparent")
            cell.pack(side="left", padx=20)
            ctk.CTkLabel(cell, text=label, font=(FONT_FAMILY, FONT_SIZE_TINY),
                         text_color=TEXT_MUTED).pack()
            ctk.CTkLabel(cell, textvariable=var, font=(FONT_FAMILY, FONT_SIZE_HEADING, "bold"),
                         text_color=color).pack()

        # Column headers
        col_hdr = ctk.CTkFrame(parent, fg_color=BG_MEDIUM, corner_radius=0, height=28)
        col_hdr.pack(fill="x")
        col_hdr.pack_propagate(False)

        for text, w in [("Status", 80), ("Address", 80), ("Decimal", 100),
                         ("Hex", 90), ("Binary", 150), ("Signed", 90), ("Float32 (pair)", 130)]:
            ctk.CTkLabel(col_hdr, text=text, font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                         text_color=TEXT_MUTED, width=w, anchor="center").pack(side="left", padx=1)

        # Scrollable results
        self._results_scroll = ctk.CTkScrollableFrame(parent, fg_color=BG_DARK, corner_radius=0)
        self._results_scroll.pack(fill="both", expand=True)

        self._result_rows = []

    def _add_result_row(self, address: int, value: Optional[int], status: str):
        """Add a single result row to the results table."""
        is_ok = status == "OK"
        row_bg = BG_CARD if len(self._result_rows) % 2 == 0 else BG_DARK

        row = ctk.CTkFrame(self._results_scroll, fg_color=row_bg, corner_radius=0, height=28)
        row.pack(fill="x")
        row.pack_propagate(False)

        # Status dot
        status_color = STATUS_GOOD if is_ok else STATUS_ERROR
        status_text = "●  OK" if is_ok else "✗  No Resp"
        ctk.CTkLabel(row, text=status_text, font=(FONT_FAMILY, FONT_SIZE_TINY, "bold"),
                     text_color=status_color, width=80, anchor="center").pack(side="left", padx=1)

        ctk.CTkLabel(row, text=str(address), font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                     text_color=TEXT_SECONDARY, width=80, anchor="center").pack(side="left", padx=1)

        if is_ok and value is not None:
            unsigned = value & 0xFFFF
            signed = unsigned if unsigned < 32768 else unsigned - 65536

            ctk.CTkLabel(row, text=str(unsigned), font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                         text_color=TEXT_PRIMARY, width=100, anchor="center").pack(side="left", padx=1)
            ctk.CTkLabel(row, text=f"0x{unsigned:04X}", font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                         text_color=TEXT_MUTED, width=90, anchor="center").pack(side="left", padx=1)
            ctk.CTkLabel(row, text=f"{unsigned:016b}", font=(FONT_FAMILY_MONO, FONT_SIZE_TINY),
                         text_color=TEXT_MUTED, width=150, anchor="center").pack(side="left", padx=1)
            ctk.CTkLabel(row, text=str(signed), font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                         text_color=STATUS_WARN if signed < 0 else TEXT_MUTED,
                         width=90, anchor="center").pack(side="left", padx=1)
        else:
            for w in [100, 90, 150, 90, 130]:
                ctk.CTkLabel(row, text="—", font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                             text_color=TEXT_MUTED, width=w, anchor="center").pack(side="left", padx=1)

        self._result_rows.append(row)

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

    def _toggle_scan(self):
        if self._scanning:
            self._scanning = False
            self._scan_btn.configure(text="🔍  Scan Register Map", fg_color=SAS_BLUE)
            self._status_var.set("Cancelled")
        else:
            self._start_scan()

    def _start_scan(self):
        # Clear previous results
        for w in self._results_scroll.winfo_children():
            w.destroy()
        self._result_rows.clear()
        self._results.clear()

        try:
            start = int(self._start_addr.get())
            end = int(self._end_addr.get())
            slave_id = int(self._slave_id.get())
            chunk = int(self._chunk_size.get())
            timeout = float(self._timeout.get())
        except ValueError:
            self._status_var.set("Invalid parameters")
            return

        # Determine FC
        fc_text = self._fc_combo.get()
        fc_map = {
            "FC03": FunctionCode.READ_HOLDING_REGISTERS,
            "FC04": FunctionCode.READ_INPUT_REGISTERS,
            "FC01": FunctionCode.READ_COILS,
            "FC02": FunctionCode.READ_DISCRETE_INPUTS,
        }
        fc = fc_map.get(fc_text[:4], FunctionCode.READ_HOLDING_REGISTERS)

        # Connect
        proto = self._proto_var.get()
        connected = False
        if proto == "TCP":
            host = self._tcp_host.get().strip()
            try:
                port = int(self._tcp_port.get())
            except ValueError:
                port = 502
            connected = self._client.connect_tcp(host, port, timeout)
        else:
            com = self._rtu_port.get()
            try:
                baud = int(self._rtu_baud.get())
            except ValueError:
                baud = 9600
            connected = self._client.connect_rtu(com, baud, timeout=timeout)

        if not connected:
            self._status_var.set("Connection failed")
            return

        self._scanning = True
        self._scan_btn.configure(text="⏹  Stop", fg_color=STATUS_ERROR, hover_color="#DC2626")
        self._status_var.set("Scanning...")
        self._found_var.set("0")
        self._missing_var.set("0")
        self._total_var.set("0")

        self._scan_thread = threading.Thread(
            target=self._scan_loop,
            args=(start, end, slave_id, fc, chunk, timeout),
            daemon=True
        )
        self._scan_thread.start()

    def _scan_loop(self, start: int, end: int, slave_id: int,
                   fc: FunctionCode, chunk: int, timeout: float):
        total = end - start + 1
        found = 0
        missing = 0
        scanned = 0
        addr = start

        while addr <= end and self._scanning:
            count = min(chunk, end - addr + 1)
            result = self._client.execute(fc, slave_id, addr, count)

            if result.success:
                for i, val in enumerate(result.values):
                    v = val if not isinstance(val, bool) else (1 if val else 0)
                    self._results.append((addr + i, v, "OK"))
                    self.after(0, lambda a=addr+i, v=v: self._add_result_row(a, v, "OK"))
                    found += 1
            else:
                # On error, probe individually to find gaps
                for i in range(count):
                    if not self._scanning:
                        break
                    single = self._client.execute(fc, slave_id, addr + i, 1)
                    if single.success and single.values:
                        v = single.values[0]
                        v = v if not isinstance(v, bool) else (1 if v else 0)
                        self._results.append((addr + i, v, "OK"))
                        self.after(0, lambda a=addr+i, vv=v: self._add_result_row(a, vv, "OK"))
                        found += 1
                    else:
                        self._results.append((addr + i, None, "TIMEOUT"))
                        self.after(0, lambda a=addr+i: self._add_result_row(a, None, "TIMEOUT"))
                        missing += 1

            scanned += count
            addr += count
            pct = scanned / total

            self.after(0, lambda p=pct, f=found, m=missing, s=scanned: self._update_scan_progress(p, f, m, s))

        self.after(0, self._scan_complete)

    def _update_scan_progress(self, pct: float, found: int, missing: int, scanned: int):
        self._progress.set(pct)
        self._found_var.set(str(found))
        self._missing_var.set(str(missing))
        self._total_var.set(str(scanned))
        self._prog_var.set(f"{int(pct * 100)}% complete")

    def _scan_complete(self):
        self._scanning = False
        self._client.disconnect()
        self._scan_btn.configure(text="🔍  Scan Register Map", fg_color=SAS_BLUE,
                                  hover_color=SAS_BLUE_DARK)
        self._progress.set(1.0)
        self._status_var.set("Scan Complete")
        self._prog_var.set(f"{len(self._results)} registers scanned")

    def _export_csv(self):
        """Export results to CSV file."""
        if not self._results:
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Register Map"
        )
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Address", "Value (Unsigned)", "Value (Hex)", "Value (Signed)", "Status"])
                for addr, val, status in self._results:
                    if val is not None:
                        unsigned = val & 0xFFFF
                        signed = unsigned if unsigned < 32768 else unsigned - 65536
                        writer.writerow([addr, unsigned, f"0x{unsigned:04X}", signed, status])
                    else:
                        writer.writerow([addr, "", "", "", status])
            self._status_var.set(f"Exported: {path.split('/')[-1]}")
        except Exception as e:
            self._status_var.set(f"Export failed: {e}")
