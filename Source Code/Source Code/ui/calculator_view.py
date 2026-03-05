"""
SAS Modbus Toolkit — Data Type Calculator View
Convert raw register values to engineering units and vice versa.
Also shows Modbus protocol reference tables.
"""

import struct
import logging
import tkinter as tk
from typing import List

import customtkinter as ctk

from core.data_types import (
    DataType, ALL_DATA_TYPE_NAMES, decode_registers, encode_value
)
from ui.theme import *
from ui.widgets import make_card, make_primary_button, make_secondary_button, enable_touch_scroll

logger = logging.getLogger(__name__)


class CalculatorView(ctk.CTkFrame):
    """Data type converter and Modbus protocol reference."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._build_ui()

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=50)
        hdr.pack(fill="x", padx=24, pady=(16, 4))
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🧮  Data Type Calculator",
                     font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(side="left")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True)
        enable_touch_scroll(self._scroll)

        self._build_converter_card()
        self._build_byte_order_card()
        self._build_fc_reference_card()
        self._build_address_reference_card()
        self._build_rtu_timing_card()
        self._build_exception_code_card()
        self._build_error_reference_card()

    # ── Register Value Converter ──────────────────────────────────────────────

    def _build_converter_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(4, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=12)

        ctk.CTkLabel(inner, text="Register Value Converter",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(row, text="Raw Register Values (space-separated):",
                     font=(FONT_FAMILY, FONT_SIZE_BODY),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 10))
        self._raw_entry = ctk.CTkEntry(
            row, width=300, height=INPUT_HEIGHT,
            font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
            fg_color=BG_INPUT, border_color=BORDER_COLOR,
            placeholder_text="e.g.  17219  17920",
        )
        self._raw_entry.pack(side="left", padx=(0, 12))
        make_primary_button(row, "Convert ▶", self._do_convert, width=110).pack(side="left")
        make_secondary_button(row, "Clear", self._clear_convert, width=80).pack(side="left", padx=(6, 0))

        # Results grid
        self._results_frame = ctk.CTkFrame(inner, fg_color="transparent")
        self._results_frame.pack(fill="x", pady=(8, 0))

        # Column headers
        for text, w in [("Data Type", 200), ("Decoded Value", 220), ("Registers Used", 110)]:
            ctk.CTkLabel(self._results_frame, text=text, width=w,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                         text_color=TEXT_MUTED, anchor="w").grid(
                row=0, column=["Data Type", "Decoded Value", "Registers Used"].index(text),
                padx=6, pady=2, sticky="w")

        ctk.CTkFrame(inner, fg_color=BORDER_COLOR, height=1).pack(fill="x", pady=4)

        self._result_labels = {}
        self._result_grid = ctk.CTkFrame(inner, fg_color="transparent")
        self._result_grid.pack(fill="x")

        # Pre-populate with common types
        common_types = [
            DataType.UINT16, DataType.INT16,
            DataType.FLOAT32_AB_CD, DataType.FLOAT32_CD_AB,
            DataType.UINT32_AB_CD, DataType.INT32_AB_CD,
            DataType.HEX, DataType.ASCII, DataType.BOOL,
        ]
        for i, dt in enumerate(common_types):
            ctk.CTkLabel(self._result_grid, text=dt.value, width=200,
                         font=(FONT_FAMILY, FONT_SIZE_BODY),
                         text_color=TEXT_SECONDARY, anchor="w").grid(
                row=i, column=0, padx=6, pady=2, sticky="w")
            val_lbl = ctk.CTkLabel(self._result_grid, text="—", width=220,
                                   font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                                   text_color=TEXT_PRIMARY, anchor="w")
            val_lbl.grid(row=i, column=1, padx=6, pady=2, sticky="w")
            ctk.CTkLabel(self._result_grid, text=str(self._reg_count(dt)), width=110,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                         text_color=TEXT_MUTED, anchor="w").grid(
                row=i, column=2, padx=6, pady=2, sticky="w")
            self._result_labels[dt] = val_lbl

    def _do_convert(self):
        raw_str = self._raw_entry.get().strip()
        if not raw_str:
            return
        try:
            parts = raw_str.replace(",", " ").split()
            # Accept decimal or hex (0xNNNN)
            regs = []
            for p in parts:
                if p.lower().startswith("0x"):
                    regs.append(int(p, 16))
                else:
                    regs.append(int(p))
        except Exception:
            for lbl in self._result_labels.values():
                lbl.configure(text="Parse error", text_color=STATUS_ERROR)
            return

        for dt, lbl in self._result_labels.items():
            decoded = decode_registers(regs, dt)
            color = TEXT_PRIMARY if decoded not in ("—", "need 2 regs", "need 4 regs") else TEXT_MUTED
            lbl.configure(text=decoded, text_color=color)

    def _clear_convert(self):
        self._raw_entry.delete(0, "end")
        for lbl in self._result_labels.values():
            lbl.configure(text="—", text_color=TEXT_MUTED)

    def _reg_count(self, dt: DataType) -> int:
        from core.data_types import DATA_TYPE_REGISTER_COUNT
        return DATA_TYPE_REGISTER_COUNT.get(dt, 1)

    # ── Byte Order Reference ──────────────────────────────────────────────────

    def _build_byte_order_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=12)

        ctk.CTkLabel(inner, text="Byte / Word Order Reference",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 8))

        info = [
            ("AB CD  (Big-Endian)",
             "Most significant register first. Standard Modbus byte order.\nCommon in: Schneider, ABB, most PLCs.",
             SAS_BLUE_LIGHT),
            ("CD AB  (Little-Endian Word)",
             "Least significant register first. Non-standard but common.\nCommon in: Enron Modbus, some Emerson/MOXA devices.",
             SAS_ORANGE_LIGHT),
            ("BA DC  (Byte-Swapped Big-Endian)",
             "Bytes swapped within each register.\nRare but seen in older Modicon equipment.",
             TEXT_MUTED),
            ("DC BA  (Byte-Swapped Little-Endian)",
             "Both registers swapped and bytes swapped.\nUsed by some IDEC and Mitsubishi devices.",
             TEXT_MUTED),
        ]

        for order, desc, color in info:
            row = ctk.CTkFrame(inner, fg_color=BG_MEDIUM, corner_radius=6)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=order, width=200,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_BODY, "bold"),
                         text_color=color, anchor="w").pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(row, text=desc,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w",
                         justify="left").pack(side="left", padx=8)

    # ── Function Code Reference ───────────────────────────────────────────────

    def _build_fc_reference_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=12)

        ctk.CTkLabel(inner, text="Function Code Reference",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 8))

        fcs = [
            ("01", "Read Coils",                  "1-bit",  "R",  "Reads ON/OFF status of output coils (0x)"),
            ("02", "Read Discrete Inputs",         "1-bit",  "R",  "Reads ON/OFF status of input bits (1x)"),
            ("03", "Read Holding Registers",       "16-bit", "R",  "Reads 16-bit read/write registers (4x) — most common"),
            ("04", "Read Input Registers",         "16-bit", "R",  "Reads 16-bit read-only registers (3x)"),
            ("05", "Write Single Coil",            "1-bit",  "W",  "Writes a single coil ON (0xFF00) or OFF (0x0000)"),
            ("06", "Write Single Register",        "16-bit", "W",  "Writes one 16-bit holding register — most common write"),
            ("0F", "Write Multiple Coils",         "1-bit",  "W",  "Writes multiple coils in one request"),
            ("10", "Write Multiple Registers",     "16-bit", "W",  "Writes multiple holding registers in one request"),
            ("16", "Mask Write Register",          "16-bit", "W",  "AND/OR mask on a single register — non-destructive bit write"),
            ("17", "Read/Write Multiple Regs",     "16-bit", "R/W","Read and write in a single transaction"),
            ("2B", "Read Device Identification",   "—",      "R",  "MEI FC43 — read vendor/product/firmware info (optional)"),
        ]

        # Header
        hdr = ctk.CTkFrame(inner, fg_color=BG_MEDIUM, corner_radius=6)
        hdr.pack(fill="x", pady=(0, 2))
        for text, w in [("FC", 50), ("Name", 220), ("Data", 70), ("R/W", 50), ("Description", 400)]:
            ctk.CTkLabel(hdr, text=text, width=w,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                         text_color=TEXT_MUTED, anchor="w").pack(side="left", padx=6, pady=4)

        for fc, name, data, rw, desc in fcs:
            rw_color = MODBUS_READ_COLOR if rw == "R" else (
                MODBUS_WRITE_COLOR if rw == "W" else SAS_BLUE_LIGHT)
            row = ctk.CTkFrame(inner, fg_color="transparent", height=30)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=f"0x{fc}", width=50,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_BODY, "bold"),
                         text_color=SAS_ORANGE, anchor="w").pack(side="left", padx=6)
            ctk.CTkLabel(row, text=name, width=220,
                         font=(FONT_FAMILY, FONT_SIZE_BODY),
                         text_color=TEXT_PRIMARY, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=data, width=70,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                         text_color=TEXT_MUTED, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=rw, width=50,
                         font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                         text_color=rw_color, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=desc,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w").pack(side="left")

    # ── Address Reference ─────────────────────────────────────────────────────

    def _build_address_reference_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 4))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=12)

        ctk.CTkLabel(inner, text="Modbus Address / Register Type Reference",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 8))

        rows = [
            ("0x  (Coils)",            "1–9999",       "FC01 Read / FC05+15 Write",  "1-bit output — relay, valve, digital out",   MODBUS_RTU_COLOR),
            ("1x  (Discrete Inputs)",  "10001–19999",   "FC02 Read only",             "1-bit input — sensor, limit switch",         TEXT_MUTED),
            ("3x  (Input Registers)",  "30001–39999",   "FC04 Read only",             "16-bit read-only — analog input, measured",  TEXT_MUTED),
            ("4x  (Holding Registers)","40001–49999",   "FC03 Read / FC06+16 Write",  "16-bit read/write — setpoints, config, data",MODBUS_TCP_COLOR),
        ]

        for reg_type, range_str, fc, description, color in rows:
            row = ctk.CTkFrame(inner, fg_color=BG_MEDIUM, corner_radius=6)
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(row, text=reg_type, width=180,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_BODY, "bold"),
                         text_color=color, anchor="w").pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(row, text=range_str, width=130,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
                         text_color=TEXT_MUTED, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=fc, width=240,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=description,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w").pack(side="left")

        ctk.CTkLabel(inner,
                     text="Note: Many devices use 0-based addressing (0–9998, 0–999, etc.). "
                          "Always subtract 1 from the 5-digit address to get the zero-based "
                          "PDU address used in the protocol frame.",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_MUTED,
                     wraplength=900, anchor="w").pack(fill="x", pady=(8, 0))

    # ── RTU Timing Reference ──────────────────────────────────────────────────

    def _build_rtu_timing_card(self):
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(0, 16))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=12)

        ctk.CTkLabel(inner, text="RTU Inter-Frame Timing (Silent Interval)",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(inner,
                     text="Modbus RTU uses silence gaps to separate frames. The minimum gap is "
                          "3.5 character times. At baud rates ≥ 19200, the spec allows a fixed "
                          "1.75ms inter-frame delay.",
                     font=(FONT_FAMILY, FONT_SIZE_BODY),
                     text_color=TEXT_SECONDARY,
                     wraplength=900, anchor="w").pack(fill="x", pady=(0, 10))

        timings = [
            (1200,   "32.3 ms",  "9.17 ms"),
            (2400,   "16.1 ms",  "4.58 ms"),
            (4800,   "8.1 ms",   "2.29 ms"),
            (9600,   "4.0 ms",   "1.15 ms"),
            (19200,  "1.75 ms",  "fixed"),
            (38400,  "1.75 ms",  "fixed"),
            (57600,  "1.75 ms",  "fixed"),
            (115200, "1.75 ms",  "fixed"),
        ]

        hdr = ctk.CTkFrame(inner, fg_color=BG_MEDIUM, corner_radius=6)
        hdr.pack(fill="x", pady=(0, 2))
        for text, w in [("Baud Rate", 120), ("3.5 Char Gap (Frame Sep.)", 220), ("1.5 Char Gap (Byte Sep.)", 220)]:
            ctk.CTkLabel(hdr, text=text, width=w,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                         text_color=TEXT_MUTED, anchor="w").pack(side="left", padx=6, pady=4)

        for baud, gap35, gap15 in timings:
            row = ctk.CTkFrame(inner, fg_color="transparent", height=28)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=f"{baud:,} bps", width=120,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                         text_color=TEXT_PRIMARY, anchor="w").pack(side="left", padx=6)
            ctk.CTkLabel(row, text=gap35, width=220,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                         text_color=SAS_ORANGE_LIGHT, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=gap15, width=220,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                         text_color=TEXT_SECONDARY, anchor="w").pack(side="left")

    # ── Modbus Exception Codes ────────────────────────────────────────────────

    def _build_exception_code_card(self):
        """Modbus protocol exception codes with full descriptions, causes, and fixes."""
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(4, 0))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=10)

        ctk.CTkLabel(inner, text="\u26a0\ufe0f  Modbus Exception Codes (Server Response Errors)",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(inner,
                     text="When a Modbus device cannot fulfill a request it returns an Exception Response. "
                          "The function code byte has bit 7 set (FC03=0x03 becomes 0x83). The next byte is the Exception Code.",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_SECONDARY, anchor="w", justify="left",
                     wraplength=1000).pack(fill="x", pady=(0, 8))

        exceptions = [
            ("0x01", "Illegal Function",
             "The function code is not recognized or not supported by this device.",
             "Use Bus Scanner to check supported FCs.\nCheck device manual for supported function codes."),
            ("0x02", "Illegal Data Address",
             "The register address or quantity requested is outside the device register map.",
             "Verify address in device documentation.\nCheck 0-based vs 1-based addressing (40001 = address 0 or 1?).\nReduce count if near end of valid range."),
            ("0x03", "Illegal Data Value",
             "A value in the request data is not allowable — out of range or invalid.",
             "FC05 coil write: only 0x0000 (OFF) or 0xFF00 (ON) are legal.\nMax 125 registers per FC03/04 request, 2000 coils per FC01/02.\nCheck valid value range in device manual."),
            ("0x04", "Server Device Failure",
             "An unrecoverable internal error occurred while performing the request.",
             "Check device for hardware faults or internal errors.\nPower cycle the device.\nContact manufacturer if persistent."),
            ("0x05", "Acknowledge",
             "Not an error — device accepted the request but needs more time to process it.",
             "Increase master timeout.\nPoll for completion using a status register or FC07.\nNormal for long operations: flash writes, calibration, resets."),
            ("0x06", "Server Device Busy",
             "Device is processing a long operation and cannot accept this request yet.",
             "Implement retry with 500ms\u20132000ms delay.\nReduce poll rate while device is busy.\nCheck if another master is accessing the same device."),
            ("0x08", "Memory Parity Error",
             "Device detected a parity error in extended memory (FC20/FC21 file records).",
             "Power cycle the device.\nDevice memory may need repair or reflash if persistent."),
            ("0x0A", "Gateway Path Unavailable",
             "Gateway could not allocate an internal path to process the request.",
             "Check gateway serial port configuration.\nVerify slave ID routing in gateway settings.\nReduce poll rate to avoid gateway overload."),
            ("0x0B", "Gateway Target Device Failed to Respond",
             "Gateway sent request to the serial device but received no response — device is unreachable via gateway.",
             "Verify slave ID matches the physical device.\nCheck the serial device is powered and wired correctly.\nIncrease gateway serial timeout.\nUse RTU Bus Scanner to test the serial side directly."),
        ]

        for code, name, desc, fix in exceptions:
            row = ctk.CTkFrame(inner, fg_color=BG_MEDIUM, corner_radius=6)
            row.pack(fill="x", pady=3)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(8, 4))
            ctk.CTkLabel(top, text=code,
                         font=(FONT_FAMILY_MONO, FONT_SIZE_BODY, "bold"),
                         text_color=STATUS_ERROR, width=48, anchor="w").pack(side="left")
            ctk.CTkLabel(top, text=name,
                         font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                         text_color=TEXT_PRIMARY, anchor="w").pack(side="left", padx=(6, 0))
            ctk.CTkLabel(row, text=desc,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=TEXT_SECONDARY, anchor="w", justify="left",
                         wraplength=950).pack(fill="x", padx=12, pady=(0, 4))
            ctk.CTkLabel(row, text=fix,
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=SAS_BLUE_LIGHT, anchor="w", justify="left",
                         wraplength=950).pack(fill="x", padx=12, pady=(0, 8))

    # ── Common Communication Errors ───────────────────────────────────────────

    def _build_error_reference_card(self):
        """Comprehensive guide to common Modbus errors, causes, and fixes."""
        card = make_card(self._scroll)
        card.pack(fill="x", padx=24, pady=(4, 16))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=10)

        ctk.CTkLabel(inner, text="\U0001f527  Common Communication Errors \u2014 Causes & Fixes",
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 6))

        categories = [
            ("\U0001f534  No Response / Timeout", [
                ("TCP \u2014 Device Not Reachable",
                 "TCP connection cannot be established at all.",
                 "Wrong IP or port (standard is 502; try 503, 1502).\nFirewall blocking port 502.\nDevice off or not in Modbus TCP server mode.\nPing the device first to confirm basic network reachability."),
                ("TCP \u2014 Connected but No Modbus Response",
                 "TCP handshake succeeds but no Modbus data is returned.",
                 "Wrong Unit/Slave ID (TCP devices often use ID 0 or 1).\nGateway device: Unit ID routes to downstream serial slave.\nRegister address not in device map (try address 0, count 1).\nCheck manufacturer documentation for connection requirements."),
                ("RTU \u2014 No Response at All",
                 "Master sends request but nothing comes back.",
                 "Wrong baud rate \u2014 most common cause. Try 9600, 19200, 38400, 115200.\nWrong slave ID.\nA/B wires swapped on RS-485 \u2014 swap and retry.\nWrong parity (N/E/O) or stop bits.\nRS-485 adapter not installed or COM port in use by another application.\nMissing termination resistors."),
                ("RTU \u2014 Intermittent No Response",
                 "Some polls succeed but others drop out sporadically.",
                 "Electrical noise from VFDs, motors, or contactors coupling into cable.\nMissing bias resistors \u2014 bus floats to undefined state during idle.\nGround loop between devices \u2014 connect shield at master end only.\nSlave turnaround time too fast \u2014 add inter-message delay.\nCable too long for baud rate in use.\nLoose terminal block connections."),
            ]),
            ("\U0001f7e1  CRC & Framing Errors (RTU)", [
                ("CRC Error \u2014 Checksum Mismatch",
                 "Data was corrupted between transmitter and receiver.",
                 "High EMI near the cable (route away from power wiring and VFD output cables).\nMissing termination \u2014 reflections corrupt signal.\nCable too long for baud rate.\nGround potential difference \u2014 use isolated RS-485 adapters in high-noise environments.\nDamaged cable or wrong cable type (must be shielded twisted pair)."),
                ("Framing Error \u2014 Invalid Character",
                 "UART detects a character framing violation in received data.",
                 "Baud rate mismatch between master and slave.\nStop bit mismatch (1 vs 2).\nParity mismatch (N/E/O).\nModbus RTU requires 8 data bits.\nTwo masters transmitting simultaneously on the same RS-485 bus."),
                ("Silent Interval Violation",
                 "RTU frame split mid-transmission, violating the 3.5-character gap rule.",
                 "USB-to-Serial adapter buffering characters and releasing in bursts.\nUse hardware-buffered adapter (FTDI chip preferred over CH340/PL2303).\nReduce baud rate to reduce timing sensitivity."),
            ]),
            ("\U0001f7e0  Data Integrity Issues", [
                ("Wrong Value Decoded",
                 "Communication succeeds but the displayed value makes no sense.",
                 "Wrong data type \u2014 try UINT16, INT16, FLOAT32 AB, FLOAT32 BA, INT32 AB, INT32 CD.\nByte order (endianness) mismatch \u2014 Modbus is big-endian but many PLCs store multi-register floats in little-endian order.\nScaling needed \u2014 raw value may need \u00f710, \u00f7100, or engineering unit conversion.\nWrong address \u2014 0-based vs 1-based (40001 = address 0 or address 1 depending on device).\nUse the Data Calculator above to test all type interpretations on raw register values."),
                ("32-bit Torn Read",
                 "A 32-bit value split across two registers reads incorrectly when polled separately.",
                 "Always read both registers of a 32-bit value in a single FC03 request (count=2).\nDo not read HR0 and HR1 in separate poll rows if they form a single FLOAT32 or INT32 value.\nUse FC16 (Write Multiple Registers) to write both words atomically."),
            ]),
            ("\U0001f535  TCP/IP & Network Issues", [
                ("Multiple Masters Conflict",
                 "Two masters competing for the same device simultaneously.",
                 "Modbus RTU is single-master only \u2014 only one master may transmit at a time.\nModbus TCP supports multiple connections but device may have limits (typically 4\u20138 clients).\nCheck if SCADA, HMI, or another scanner is already connected."),
                ("Connection Drops",
                 "TCP connection established but drops after idle period.",
                 "Device has idle timeout \u2014 increase poll rate or enable keep-alive.\nManaged switch or router timing out idle TCP sessions.\nIP address conflict on network.\nDevice firmware TCP stack issue \u2014 update firmware."),
                ("High Latency / Slow Response",
                 "Communication works but response times are much higher than expected.",
                 "Wireless, cellular, or VPN link in the path.\nDevice CPU overloaded \u2014 reduce poll rate.\nTCP Nagle algorithm delaying small packets \u2014 disable TCP_NODELAY.\nMeasure baseline ping round-trip time to separate network vs device latency."),
            ]),
            ("\u26a1  RS-485 Physical Layer", [
                ("Bus Completely Dead",
                 "No devices respond at all \u2014 bus appears totally unresponsive.",
                 "RS-485 adapter stuck in TX-enable mode \u2014 blocking all receive.\nMissing bias resistors \u2014 bus floating to indeterminate voltage.\nTwo devices with A/B swapped fighting each other.\nOpen circuit in cable \u2014 check terminal block connections.\nFaulty RS-485 adapter \u2014 try a different one."),
                ("Termination Problems",
                 "Errors increase with baud rate or cable length \u2014 signal quality issue.",
                 "Exactly ONE 120\u03a9 resistor at each physical end of the cable \u2014 never in the middle.\nOver-termination (3+ resistors) overloads the driver and reduces signal amplitude.\nSome RS-485 adapters have a built-in switchable terminator \u2014 check and enable if at the end."),
                ("Ground Loop / EMI",
                 "Errors correlate with nearby equipment switching (motors, contactors, VFDs).",
                 "Shield connected at both ends creates a ground loop \u2014 connect at master end only.\nAdd signal ground wire (third conductor) but do not create a loop.\nUse optically isolated RS-485 adapters near VFDs.\nRoute RS-485 cable in separate cable tray away from power wiring."),
                ("Bus Overloaded",
                 "Works with few devices but fails as more are added.",
                 "RS-485 supports max 32 unit loads \u2014 check each device datasheet for unit load count.\nAdd an RS-485 repeater to extend beyond 32 unit loads or cable length limits."),
            ]),
        ]

        for cat_title, errors in categories:
            cat_hdr = ctk.CTkFrame(inner, fg_color=BG_MEDIUM, corner_radius=6)
            cat_hdr.pack(fill="x", pady=(10, 2))
            ctk.CTkLabel(cat_hdr, text=cat_title,
                         font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                         text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", padx=12, pady=8)

            for err_name, err_desc, err_fix in errors:
                err_row = ctk.CTkFrame(inner, fg_color=BG_INPUT, corner_radius=4)
                err_row.pack(fill="x", pady=2)
                ctk.CTkLabel(err_row, text=err_name,
                             font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                             text_color=SAS_ORANGE_LIGHT, anchor="w").pack(
                    fill="x", padx=12, pady=(8, 2))
                ctk.CTkLabel(err_row, text=err_desc,
                             font=(FONT_FAMILY, FONT_SIZE_SMALL),
                             text_color=TEXT_SECONDARY, anchor="w", justify="left",
                             wraplength=950).pack(fill="x", padx=12, pady=(0, 4))
                ctk.CTkLabel(err_row, text=err_fix,
                             font=(FONT_FAMILY, FONT_SIZE_SMALL),
                             text_color=SAS_BLUE_LIGHT, anchor="w", justify="left",
                             wraplength=950).pack(fill="x", padx=12, pady=(0, 8))

    def on_show(self):
        pass
