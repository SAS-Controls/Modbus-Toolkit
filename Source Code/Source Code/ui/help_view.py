"""
SAS Modbus Toolkit — Help View
Comprehensive searchable help with quick-start guides, reference tables,
troubleshooting trees, and keyboard shortcuts.
"""

import customtkinter as ctk
from ui.theme import *
from ui.widgets import make_card, make_primary_button, make_secondary_button, enable_touch_scroll


class HelpView(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._build_ui()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=50)
        hdr.pack(fill="x", padx=24, pady=(16, 4))
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="📖  Help & User Guide",
                     font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(side="left")

        # ── Tab bar ───────────────────────────────────────────────────────────
        tab_bar = ctk.CTkFrame(self, fg_color=BG_MEDIUM, corner_radius=0, height=40)
        tab_bar.pack(fill="x", padx=0)
        tab_bar.pack_propagate(False)

        self._tab_btns = {}
        self._tab_frames = {}
        tabs = [
            ("quick_start",  "🚀  Quick Start"),
            ("addressing",   "📍  Addressing"),
            ("data_types",   "🔢  Data Types"),
            ("troubleshoot", "🔧  Troubleshoot"),
            ("shortcuts",    "⌨️  Tips & Shortcuts"),
        ]
        for key, label in tabs:
            btn = ctk.CTkButton(
                tab_bar, text=label,
                font=(FONT_FAMILY, FONT_SIZE_SMALL),
                fg_color="transparent", text_color=TEXT_SECONDARY,
                hover_color=BG_CARD, height=38, corner_radius=0,
                command=lambda k=key: self._show_tab(k),
            )
            btn.pack(side="left", padx=2)
            self._tab_btns[key] = btn

        # ── Scrollable content area ───────────────────────────────────────────
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True)

        for key, _ in tabs:
            scroll = ctk.CTkScrollableFrame(self._content, fg_color="transparent")
            enable_touch_scroll(scroll)
            self._tab_frames[key] = scroll

        self._build_quick_start()
        self._build_addressing()
        self._build_data_types()
        self._build_troubleshoot()
        self._build_shortcuts()

        self._show_tab("quick_start")

    def _show_tab(self, key: str):
        for k, frame in self._tab_frames.items():
            frame.pack_forget()
        self._tab_frames[key].pack(fill="both", expand=True)
        for k, btn in self._tab_btns.items():
            if k == key:
                btn.configure(fg_color=BG_CARD, text_color=SAS_BLUE_LIGHT)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_SECONDARY)

    # ── Section builders ──────────────────────────────────────────────────────

    def _section(self, parent, title: str, icon: str = "") -> ctk.CTkFrame:
        card = make_card(parent)
        card.pack(fill="x", padx=24, pady=(4, 0))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=CARD_PADDING, pady=10)
        ctk.CTkLabel(inner, text=f"{icon}  {title}" if icon else title,
                     font=(FONT_FAMILY, FONT_SIZE_SUBHEADING, "bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 8))
        return inner

    def _item(self, parent, title: str, body: str,
              title_color=None, body_color=None):
        row = ctk.CTkFrame(parent, fg_color=BG_MEDIUM, corner_radius=6)
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text=title,
                     font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                     text_color=title_color or SAS_BLUE_LIGHT,
                     anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(row, text=body,
                     font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=body_color or TEXT_SECONDARY,
                     anchor="w", justify="left", wraplength=950).pack(
            fill="x", padx=12, pady=(0, 8))

    def _table(self, parent, headers: list, rows: list, col_widths: list = None):
        """Render a simple table using frames."""
        tbl = ctk.CTkFrame(parent, fg_color="transparent")
        tbl.pack(fill="x", pady=4)
        n = len(headers)
        widths = col_widths or [200] * n

        # Header row
        hdr_row = ctk.CTkFrame(tbl, fg_color=BG_INPUT, corner_radius=4)
        hdr_row.pack(fill="x", pady=(0, 2))
        for i, h in enumerate(headers):
            ctk.CTkLabel(hdr_row, text=h, width=widths[i],
                         font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                         text_color=TEXT_PRIMARY, anchor="w").pack(
                side="left", padx=8, pady=5)

        # Data rows
        for row_data in rows:
            data_row = ctk.CTkFrame(tbl, fg_color=BG_MEDIUM, corner_radius=4)
            data_row.pack(fill="x", pady=1)
            for i, cell in enumerate(row_data):
                w = widths[i] if i < len(widths) else 200
                ctk.CTkLabel(data_row, text=str(cell), width=w,
                             font=(FONT_FAMILY_MONO if i in (0, 2) else FONT_FAMILY, FONT_SIZE_SMALL),
                             text_color=SAS_ORANGE_LIGHT if i == 0 else TEXT_SECONDARY,
                             anchor="w").pack(side="left", padx=8, pady=4)

    # ── Quick Start Tab ───────────────────────────────────────────────────────

    def _build_quick_start(self):
        p = self._tab_frames["quick_start"]

        inner = self._section(p, "Modbus Master — Read Live Data from a Device", "📡")
        steps = [
            ("Step 1 — Choose connection type", "Select TCP for an Ethernet/Wi-Fi device. Select RTU for a serial RS-485 device."),
            ("Step 2 — Enter connection details",
             "TCP: Enter the device IP address and port (default 502) and Slave ID (usually 1).\n"
             "RTU: Select the COM port, baud rate, parity (N/E/O), and Slave ID from your device manual."),
            ("Step 3 — Click Connect", "The status badge turns blue/orange when connected. If it fails, check settings."),
            ("Step 4 — Add poll rows", "Each row reads a block of registers. Enter: Start Address (0-based), Count (how many), "
             "Function Code, a Tag Label, and the Data Type. The 'Reg #' column shows the traditional register number automatically."),
            ("Step 5 — Start Poll", "Click ▶ Start Poll. Values update live. Raw values and decoded values both display."),
            ("Step 6 — Write a value", "Use the Write panel at the bottom. Choose FC06 for a single register, FC16 for multiple. "
             "Enter the address, value, and data type, then click ⬆ Write."),
        ]
        for title, body in steps:
            self._item(inner, title, body)

        inner2 = self._section(p, "Slave Simulator — Simulate a Modbus Device", "🖥")
        steps2 = [
            ("Step 1 — Choose mode", "TCP to simulate a network device. RTU to simulate a serial slave (requires a COM port)."),
            ("Step 2 — Set Slave ID and port", "Default Slave ID is 1. For TCP default port is 502 — use 5020+ if running without admin rights."),
            ("Step 3 — Start Server", "Click ▶ Start Server. The server log confirms it's running."),
            ("Step 4 — Edit registers", "Click the Holding Registers, Input Registers, Coils, or Discrete Inputs tabs. "
             "Type new values and click Apply. Changes take effect immediately while the server is running."),
            ("Simulation Mode", "Toggle Simulation Mode ON to auto-vary HR0 (sine wave), HR1 (ramp), HR2 (counter), "
             "IR0 (random walk), and Coil 0 (toggle). Useful for testing a master without writing register values manually."),
        ]
        for title, body in steps2:
            self._item(inner2, title, body)

        inner3 = self._section(p, "Bus Scanner — Find Devices on the Network", "🔍")
        steps3 = [
            ("RTU Bus Scan", "Scans slave IDs 1–247 on a serial port. Each ID is probed with FC03. "
             "Found devices show slave ID, response time, and which function codes they support."),
            ("TCP Single IP", "Tests multiple Unit IDs on one IP address. Useful when a gateway is forwarding to multiple serial devices."),
            ("TCP Network Range", "Scans an IP range (e.g., 192.168.1.1 – .254). Each IP is tested for port 502 "
             "and a Modbus response. Shows all Modbus TCP devices on the network."),
            ("Export Results", "Click Export CSV to save the scan results for documentation."),
        ]
        for title, body in steps3:
            self._item(inner3, title, body)

        inner4 = self._section(p, "Network Diagnostics — Measure Communication Quality", "🩺")
        steps4 = [
            ("Connect and Start Test", "Configure connection to any known Modbus device and click ▶ Start Test. "
             "The tool continuously polls and records every transaction."),
            ("Health Score", "The 0–100 score combines error rate (50%), response time (30%), and jitter (20%). "
             "90+ = Excellent, 70–89 = Good, 50–69 = Fair, <50 = Poor."),
            ("Analyze Now", "Generates a written diagnostic report with categorized findings and specific recommendations. "
             "Export the report as a text file for customer documentation."),
        ]
        for title, body in steps4:
            self._item(inner4, title, body)

        ctk.CTkFrame(p, height=16, fg_color="transparent").pack()

    # ── Addressing Tab ────────────────────────────────────────────────────────

    def _build_addressing(self):
        p = self._tab_frames["addressing"]

        inner = self._section(p, "0-Based vs 1-Based Addressing", "📍")
        self._item(inner, "What this tool uses — 0-based (protocol) addressing",
                   "Addresses in this tool match the Modbus wire protocol. The first register in each bank is address 0.\n"
                   "Most Modbus libraries and PLCs use 0-based addressing internally.\n"
                   "The 'Reg #' column in the poll table automatically shows the 1-based traditional number for reference.")
        self._item(inner, "Traditional 1-based (register number) addressing",
                   "Device manuals often list registers in 1-based format: 40001, 40002, etc.\n"
                   "To convert: subtract the bank offset and subtract 1.\n"
                   "Example: Manual says HR 40100 → Address = 40100 - 40000 - 1 = 99")

        inner2 = self._section(p, "Register Bank Reference Table", "")
        self._table(inner2,
                    ["Register Type", "FC to Read", "FC to Write", "1-Based Range", "0-Based Address", "Example"],
                    [
                        ["Coils (1-bit R/W)",         "FC01", "FC05 / FC15", "00001–09999", "0–9998", "00001 = Addr 0"],
                        ["Discrete Inputs (1-bit R)", "FC02", "—",           "10001–19999", "0–9998", "10001 = Addr 0"],
                        ["Input Registers (16-bit R)", "FC04", "—",          "30001–39999", "0–9998", "30001 = Addr 0"],
                        ["Holding Registers (16-bit R/W)", "FC03", "FC06 / FC16", "40001–49999", "0–9998", "40001 = Addr 0"],
                    ],
                    [200, 80, 120, 130, 140, 160])

        inner3 = self._section(p, "Quick Conversion Examples", "")
        self._table(inner3,
                    ["Manual Shows", "Register Type", "Protocol Address to Enter"],
                    [
                        ["40001", "Holding Register", "0"],
                        ["40002", "Holding Register", "1"],
                        ["40100", "Holding Register", "99"],
                        ["40501", "Holding Register", "500"],
                        ["30001", "Input Register",   "0"],
                        ["30050", "Input Register",   "49"],
                        ["10001", "Discrete Input",   "0"],
                        ["00001", "Coil",             "0"],
                    ],
                    [200, 200, 300])

        self._item(
            self._section(p, "Function Code Selection Guide", ""),
            "Which FC should I choose?",
            "FC01 — Read Coils: Read 1-bit outputs the master can also write (digital outputs, control bits)\n"
            "FC02 — Read Discrete Inputs: Read 1-bit inputs (push buttons, limit switches, sensor states)\n"
            "FC03 — Read Holding Registers: Read 16-bit registers the master can also write (setpoints, parameters) ← most common\n"
            "FC04 — Read Input Registers: Read 16-bit read-only values (measured process variables, sensor readings)\n"
            "FC05 — Write Single Coil: Force one coil ON (0xFF00) or OFF (0x0000)\n"
            "FC06 — Write Single Register: Write one 16-bit holding register ← most common write\n"
            "FC15 — Write Multiple Coils: Write a block of coils in one transaction\n"
            "FC16 — Write Multiple Registers: Write a block of registers — required for 32-bit values (FLOAT32, INT32)"
        )
        ctk.CTkFrame(p, height=16, fg_color="transparent").pack()

    # ── Data Types Tab ────────────────────────────────────────────────────────

    def _build_data_types(self):
        p = self._tab_frames["data_types"]

        inner = self._section(p, "Data Type Reference", "🔢")
        self._item(inner, "What is a Data Type?",
                   "Each Modbus register holds 16 bits (one word). To interpret the raw bits as a meaningful value, "
                   "you choose a data type. Some types span multiple registers (e.g., FLOAT32 uses 2 registers).\n"
                   "If the decoded value looks wrong, try a different data type or byte order variant.")

        self._table(inner,
                    ["Data Type", "Regs Used", "Range / Format", "When to Use"],
                    [
                        ["UINT16",       "1", "0 to 65,535",                          "Unsigned integer — counters, raw sensor values"],
                        ["INT16",        "1", "-32,768 to +32,767",                   "Signed integer — temperature with negatives"],
                        ["UINT32_AB",    "2", "0 to 4,294,967,295",                   "32-bit unsigned, high word first (big-endian)"],
                        ["UINT32_BA",    "2", "0 to 4,294,967,295",                   "32-bit unsigned, low word first (little-endian)"],
                        ["INT32_AB",     "2", "±2.1 billion",                         "32-bit signed, high word first"],
                        ["INT32_BA",     "2", "±2.1 billion",                         "32-bit signed, low word first"],
                        ["FLOAT32_AB",   "2", "IEEE 754 float, high word first",       "Most common float format (Allen-Bradley, Siemens)"],
                        ["FLOAT32_BA",   "2", "IEEE 754 float, low word first",        "Some older devices use reversed word order"],
                        ["FLOAT32_ABCD", "2", "IEEE 754 float, big-endian bytes",      "Full byte-swap variant"],
                        ["FLOAT32_CDAB", "2", "IEEE 754 float, little-endian bytes",   "Full byte-swap, reversed words"],
                        ["FLOAT64",      "4", "Double precision float",                "High precision measurements"],
                        ["BCD16",        "1", "0–9999 (4 BCD digits)",                "Older devices encoding decimal in hex digits"],
                        ["BCD32",        "2", "0–99,999,999 (8 BCD digits)",           "Extended BCD — rare"],
                        ["ASCII",        "1+", "2 ASCII chars per register",           "Device name, serial number strings"],
                        ["BOOL_BIT0",    "1", "Bit 0 of register (0 or 1)",           "Single flag packed in a holding register"],
                        ["HEX",         "1", "Hex display of raw word",               "Debugging — show register as 0x00FF"],
                    ],
                    [130, 80, 240, 380])

        inner2 = self._section(p, "Byte Order (Endianness) Explained", "")
        self._item(inner2, "Why are there AB and BA variants?",
                   "A FLOAT32 or INT32 value spans two 16-bit registers. The question is: which register holds the HIGH word?\n\n"
                   "Example — the float 1.0 in IEEE 754 is 0x3F800000:\n"
                   "  FLOAT32_AB (big-endian): Register[0]=0x3F80, Register[1]=0x0000  ← Allen-Bradley, most Modbus devices\n"
                   "  FLOAT32_BA (little-endian): Register[0]=0x0000, Register[1]=0x3F80  ← some older Modicon/GE devices\n\n"
                   "If your value looks like garbage, try the other byte order variant.\n"
                   "Use the Data Calculator tab to test all variants simultaneously on any raw register values.")

        self._item(inner2, "Scaling — when the value is 10x or 100x too large",
                   "Many devices store values as integers with an implied decimal point.\n"
                   "Example: Temperature 23.5°C stored as 235 (multiply by 0.1 to get engineering units).\n"
                   "Check the device manual for scale factors — the raw UINT16 value may need dividing by 10, 100, or 1000.")

        ctk.CTkFrame(p, height=16, fg_color="transparent").pack()

    # ── Troubleshooting Tab ───────────────────────────────────────────────────

    def _build_troubleshoot(self):
        p = self._tab_frames["troubleshoot"]

        s1 = self._section(p, "No Response — Diagnostic Tree", "🔴")

        self._item(s1, "TCP — Can you ping the device?",
                   "NO → Wrong IP, device off, firewall. Ping first: open cmd, type 'ping 192.168.x.x'.\n"
                   "YES but no Modbus → Wrong port (try 502, 503, 1502), wrong Slave/Unit ID, device not in server mode.")
        self._item(s1, "RTU — Does the COM port open?",
                   "NO → Wrong COM port number, port in use by another app (close other serial tools), driver not installed.\n"
                   "Open Device Manager → Ports (COM & LPT) to see which COM number your adapter is.")
        self._item(s1, "RTU — COM port opens but no response?",
                   "1. Baud rate mismatch — most common cause. Try 9600, then 19200, 38400, 115200.\n"
                   "2. Wrong slave ID — try 1, 2, or use Bus Scanner to sweep all IDs.\n"
                   "3. A/B wires swapped — swap the two RS-485 signal wires and retry.\n"
                   "4. Wrong parity — check device manual (N=None, E=Even, O=Odd).\n"
                   "5. Missing termination — add 120Ω resistors at both ends of the cable.")

        s2 = self._section(p, "Exception Code Errors", "🟠")
        exc_rows = [
            ["0x01", "Illegal Function",       "Device doesn't support that FC",     "Check supported FCs with Bus Scanner"],
            ["0x02", "Illegal Data Address",   "Register doesn't exist on device",   "Check register map, verify 0-based vs 1-based"],
            ["0x03", "Illegal Data Value",      "Value or count out of range",        "FC05 coil: use 0x0000 or 0xFF00 only; max 125 regs per request"],
            ["0x04", "Server Device Failure",  "Internal fault on device",           "Power cycle device; check device diagnostics"],
            ["0x06", "Server Device Busy",     "Device processing long operation",   "Retry after 1–2 seconds; reduce poll rate"],
            ["0x0B", "Gateway No Response",    "Serial device behind gateway silent","Check slave ID routing; verify serial device is powered"],
        ]
        self._table(s2, ["Code", "Name", "Cause", "Fix"],
                    exc_rows, [60, 160, 240, 380])

        s3 = self._section(p, "Data Looks Wrong", "🟡")
        self._item(s3, "Value is a large meaningless number",
                   "The data type or byte order is wrong.\n"
                   "Try: UINT16 → INT16 → FLOAT32_AB → FLOAT32_BA → INT32_AB → INT32_BA\n"
                   "Paste the raw register values into the Data Calculator tab to see all interpretations at once.")
        self._item(s3, "Value is 10x, 100x, or 1000x too large or small",
                   "The device stores values as scaled integers. Check the device manual for a scale factor (e.g., ÷10 for one decimal place).")
        self._item(s3, "32-bit float reads differently on each poll",
                   "You may be reading both halves of the float in separate rows. Read both registers (address X, count 2) in one row "
                   "and select FLOAT32_AB as the data type.")

        s4 = self._section(p, "CRC & Framing Errors (RTU)", "🔴")
        self._item(s4, "CRC errors on an otherwise working bus",
                   "• Electrical noise — route cable away from VFD output wiring and motor cables.\n"
                   "• Cable too long for baud rate — reduce baud or shorten cable.\n"
                   "• Missing termination resistors — reflections corrupt data.\n"
                   "• Ground loop — connect shield at master end only.")
        self._item(s4, "High jitter (erratic response times)",
                   "Jitter > 20ms on a wired RS-485 bus indicates electrical noise or bus loading issues.\n"
                   "Use Network Diagnostics to track jitter over time and correlate with equipment operation.")

        ctk.CTkFrame(p, height=16, fg_color="transparent").pack()

    # ── Tips & Shortcuts Tab ──────────────────────────────────────────────────

    def _build_shortcuts(self):
        p = self._tab_frames["shortcuts"]

        s1 = self._section(p, "Tips for Faster Workflows", "💡")
        tips = [
            ("Use Read Once before starting a poll",
             "Click 'Read Once' to verify a single row works before clicking Start Poll. "
             "This confirms the address and data type are correct before logging repeated data."),
            ("Use the Bus Scanner first on unknown devices",
             "If you don't know the slave ID or which registers exist, run a Bus Scanner sweep first. "
             "It identifies responding devices and which function codes they support."),
            ("Export CSV for customer records",
             "Both the poll table log and scan results support CSV export. "
             "Use this to document device configurations or baseline network performance."),
            ("Pin common connection settings",
             "The connection fields remember your last entry. "
             "Set up your connection once and use Connect/Disconnect without re-entering details."),
            ("Test 32-bit types with count=2",
             "For FLOAT32, INT32, UINT32: enter count=2 in the poll row and select the correct "
             "FLOAT32_AB or INT32_AB data type. The tool reads both registers and decodes them together."),
            ("Use the Slave Simulator to test your master code",
             "Start a TCP slave on port 5020 (no admin rights needed), then point your PLC or master "
             "at your PC's IP. Edit registers live to simulate different device states."),
            ("Network Diagnostics before and after changes",
             "Run a 5-minute diagnostic baseline before any cable or network changes, and another "
             "after. Compare health scores and jitter to confirm improvement."),
        ]
        for title, body in tips:
            self._item(s1, title, body)

        s2 = self._section(p, "RS-485 Wiring Checklist", "✅")
        checklist = [
            ("☐  Termination", "120Ω resistor across A–B at EACH physical end of the cable (never in the middle)"),
            ("☐  Bias resistors", "560Ω pull-up on B(+) and pull-down on A(–) — on ONE device only"),
            ("☐  Polarity", "A(–) to A(–) and B(+) to B(+) across all devices — if in doubt, swap and test"),
            ("☐  Shield grounding", "Connect cable shield at the master/controller end ONLY — prevents ground loops"),
            ("☐  Cable type", "Use shielded twisted pair (Belden 9841 or equivalent) — not regular wire"),
            ("☐  Cable routing", "Keep RS-485 cable in its own cable tray, away from power and VFD output wiring"),
            ("☐  Cable length", "9600 bps → max ~1200m | 19200 → ~600m | 38400 → ~300m | 115200 → ~100m"),
        ]
        for title, body in checklist:
            self._item(s2, title, body, title_color=STATUS_GOOD)

        s3 = self._section(p, "Common RS-485 Adapter Recommendations", "🔌")
        self._item(s3, "Recommended adapter chips",
                   "FTDI FT232R / FT232H — most reliable, best driver support\n"
                   "Prolific PL2303 — widespread, works well\n"
                   "CH340 / CH341 — budget, works but some timing issues at high baud rates\n\n"
                   "Look for adapters with hardware auto TX/RX switching — avoids half-duplex timing issues.\n"
                   "For noisy environments, use optically isolated RS-485 adapters (e.g., Waveshare USB-to-RS485-B).")

        ctk.CTkFrame(p, height=16, fg_color="transparent").pack()
        ctk.CTkLabel(p,
                     text="Southern Automation Solutions  ·  Contact@SASControls.com  ·  229-563-2897",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL),
                     text_color=TEXT_MUTED).pack(pady=(0, 16))

    def on_show(self):
        pass
