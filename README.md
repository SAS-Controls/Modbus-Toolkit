# SAS Modbus Toolkit

## What Is It?

The SAS Modbus Toolkit is a standalone Windows desktop application that gives you a complete Modbus diagnostic workbench in one portable `.exe`. No PLC software, no licenses, no internet connection required — just connect and work.

Built for the situations that come up daily in industrial automation: commissioning a new drive, chasing a communication fault, verifying register values before writing PLC code, or handing a customer a clean network health report.

---

## Features

| Module | What It Does |
|---|---|
| **Modbus Master** | Read and write registers on any Modbus TCP or RTU device. Live polling table with decoded values, transaction log, CSV export. |
| **Slave Simulator** | Turn your PC into a Modbus slave. Edit registers live while the server runs. Built-in simulation mode auto-varies registers for master testing. |
| **Bus Scanner** | Discover devices automatically — RTU bus sweep (IDs 1–247), TCP single-host unit ID sweep, or full IP range network scan. |
| **Network Diagnostics** | Continuous health monitoring with a 0–100 composite score (error rate + response time + jitter). Generates written diagnostic reports. |
| **Data Calculator** | Convert raw register values across 16+ data types simultaneously. Includes byte order reference, RTU timing tables, and full offline error reference. |
| **Error Reference** | Built-in offline reference: all Modbus exception codes (0x01–0x0B) with causes and fixes, plus 20+ real-world communication error scenarios. |

---


## Quick Start

### TCP Connection (Ethernet/Wi-Fi Device)

1. Launch the app and click **Modbus Master** in the sidebar
2. Select **TCP** mode
3. Enter the device IP, port (default `502`), and Slave ID (usually `1`)
4. Click **Connect** — status badge turns green when connected
5. Add poll rows with the register address, count, function code, and data type
6. Click **▶ Start Poll** to begin live reading

### RTU Connection (RS-485 Serial Device)

1. Connect your USB-to-RS485 adapter and note the COM port in Device Manager
2. Select **RTU** mode
3. Choose the COM port, baud rate, parity, and Slave ID from your device manual
4. Click **Connect** — if no response, try **swapping the A and B wires** first

---

## Modbus Addressing Reference

Addresses in this tool follow the **0-based Modbus wire protocol**. Device manuals often use 1-based register numbers. The **Reg #** column in the poll table converts automatically.

| Register Bank | Read FC | Write FC | 0-Based Address | 1-Based Example |
|---|---|---|---|---|
| Holding Registers (R/W) | FC03 | FC06 / FC16 | 0–9998 | 40001 = Address 0 |
| Input Registers (R/O) | FC04 | — | 0–9998 | 30001 = Address 0 |
| Discrete Inputs (R/O) | FC02 | — | 0–9998 | 10001 = Address 0 |
| Coils (R/W) | FC01 | FC05 / FC15 | 0–9998 | 00001 = Address 0 |

**Quick conversion:** `Address = (Manual register number) - (bank offset)`

Examples: `40100 → 40100 - 40000 - 1 = 99` | `30001 → 30001 - 30000 - 1 = 0`

---

## Data Types

Each Modbus register holds 16 bits. Supported data types:

| Type | Registers | Notes |
|---|---|---|
| `UINT16` | 1 | 0–65535. Most common. |
| `INT16` | 1 | -32768–32767. Signed. |
| `FLOAT32_AB` | 2 | IEEE 754, high word first — Allen-Bradley, most PLCs |
| `FLOAT32_BA` | 2 | IEEE 754, low word first — some legacy devices |
| `INT32_AB / UINT32_AB` | 2 | 32-bit signed/unsigned, big-endian |
| `INT32_BA / UINT32_BA` | 2 | 32-bit signed/unsigned, little-endian |
| `FLOAT64` | 4 | Double precision |
| `BCD16 / BCD32` | 1–2 | Binary-coded decimal |
| `ASCII` | 1+ | 2 chars per register |
| `BOOL_BIT0` | 1 | Single bit flag |
| `HEX` | 1 | Raw hex display |

> **Tip:** If the value looks wrong, open the **Data Calculator** tab and paste the raw register values — it shows all 16 interpretations at once.

---

## Installation

### Option A — Pre-built Executable (Recommended)

Download `SAS-Modbus-Toolkit.exe` from the [Releases](../../releases) page. No installation needed — just run it.

> First launch takes 5–15 seconds while PyInstaller extracts the runtime. Subsequent launches are instant.

### Option B — Run from Source

**Requirements:** Python 3.11+, Windows 10/11

```bash
git clone https://github.com/your-org/SAS-Modbus-Toolkit.git
cd "SAS-Modbus-Toolkit/Source Code"

# Create virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Run the app
python main.py
```

### Option C — Build Your Own .exe

```bash
cd "Source Code"
build.bat
# Output: dist\SAS-Modbus-Toolkit.exe
```

Requires `pip install pyinstaller`.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `customtkinter` | ≥ 5.2.0 | Modern UI framework |
| `pymodbus` | ≥ 3.6.0 | Modbus TCP/RTU client and server |
| `pyserial` | ≥ 3.5 | Serial port access for RTU |
| `Pillow` | ≥ 10.0.0 | Image handling |

---

## Project Structure

```
Source Code/
├── main.py                   # Entry point
├── app.py                    # Main window and sidebar navigation
├── requirements.txt
├── build.bat                 # PyInstaller build script
├── setup_tools.bat           # One-click venv + pip install
│
├── core/
│   ├── modbus_master.py      # Modbus client engine (TCP + RTU)
│   ├── modbus_slave.py       # Modbus server engine
│   ├── modbus_scanner.py     # Bus and network scanner
│   ├── diagnostics.py        # Health score and diagnostic report engine
│   └── data_types.py         # 16 data type encoders/decoders
│
└── ui/
    ├── theme.py              # SAS brand colors, fonts, constants
    ├── widgets.py            # Shared widgets (LogBox, HealthScore, etc.)
    ├── master_view.py        # Modbus Master tab UI
    ├── slave_view.py         # Slave Simulator tab UI
    ├── scanner_view.py       # Bus Scanner tab UI
    ├── diagnostics_view.py   # Network Diagnostics tab UI
    ├── calculator_view.py    # Data Calculator + Error Reference tab UI
    └── help_view.py          # In-app help and user guide
```

---

## Troubleshooting

### No response on TCP
- Ping the device IP first (`cmd → ping 192.168.x.x`)
- Try port 503 or 1502 if 502 doesn't work
- Verify Slave/Unit ID — TCP devices often use ID 0 or 1
- Check Windows Firewall isn't blocking port 502

### No response on RTU
- Wrong baud rate is the #1 cause — try 9600, 19200, 38400, 115200 in order
- **Swap the A and B wires** — polarity reversal is very common
- Verify parity (N/E/O) and stop bits from device manual
- Check COM port in Device Manager; close other serial tools

### Wrong decoded value
- Try a different data type — the raw bits are correct, interpretation might be wrong
- Use the **Data Calculator** to see all interpretations at once
- Check for a scale factor in the device manual (e.g., value 235 = 23.5°C)
- For 32-bit values, try both `_AB` and `_BA` byte order variants

### Modbus Exception Codes

| Code | Name | Most Common Fix |
|---|---|---|
| `0x01` | Illegal Function | Device doesn't support that FC — check with Bus Scanner |
| `0x02` | Illegal Data Address | Register doesn't exist — check device manual, verify 0-based addressing |
| `0x03` | Illegal Data Value | FC05 coil: use `0xFF00` (ON) or `0x0000` (OFF); max 125 regs per request |
| `0x04` | Server Device Failure | Internal device fault — power cycle |
| `0x06` | Server Device Busy | Retry after 1–2 seconds |
| `0x0B` | Gateway No Response | Check slave ID routing and serial wiring behind the gateway |

---

## RS-485 Wiring Quick Reference

```
Master                                              Slave(s)
  ┌──────────┐   B(+) ──────────────────────────── B(+) ┌──────────┐
  │          │   A(-) ──────────────────────────── A(-) │          │
  │  120Ω ↕  │   Shield ─────────────────────────────  │  120Ω ↕  │
  └──────────┘   (ground at master end only)            └──────────┘
  [terminate here]                               [terminate here]
```

- **Termination:** 120Ω resistor at **each physical end** of the cable
- **Bias:** 560Ω pull-up on B(+) and pull-down on A(-) on **one device only**
- **Cable:** Shielded twisted pair (Belden 9841 or equivalent)
- **Shield:** Connect at master end only — both ends creates ground loop noise
- **Max length:** 9600 bps ≈ 1200m | 19200 ≈ 600m | 38400 ≈ 300m | 115200 ≈ 100m

---

## About Southern Automation Solutions

We design and build custom industrial automation systems — PLC programming, HMI development, industrial networking, and R&D integration work.

| | |
|---|---|
| **Email** | Contact@SASControls.com |
| **Phone** | 229-563-2897 |
| **Location** | Valdosta, GA 31601 |

---

## License

This software is proprietary and developed by Southern Automation Solutions. All rights reserved.

For licensing inquiries or enterprise support, contact Contact@SASControls.com.

---

*Built with Python, customtkinter, and pymodbus.*
