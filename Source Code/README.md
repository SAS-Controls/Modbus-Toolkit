# SAS Modbus Toolkit

**Southern Automation Solutions** — Professional Modbus commissioning and diagnostics tool.

---

## Overview

The SAS Modbus Toolkit is a Windows desktop application for industrial automation professionals. It provides everything needed to commission, test, and diagnose Modbus RTU and TCP networks from a single laptop — replacing multiple outdated free tools with one clean, modern interface.

---

## Features

### 📡 Modbus Master
- Connect to any Modbus TCP or RTU device
- Configurable poll table — up to 20 register ranges with custom labels
- Supports FC01, FC02, FC03, FC04 reads
- Write operations: FC05 (coil), FC06 (single register), FC15 (multiple coils), FC16 (multiple registers)
- Full data type decoding: UINT16, INT16, FLOAT32 (AB CD / CD AB), INT32, UINT32, HEX, ASCII, individual bits, BOOL
- Live transaction log with CSV export
- Configurable polling interval

### 🖥 Slave Simulator
- Simulate a full Modbus device on TCP or RTU
- Live-editable register banks: Holding Registers, Input Registers, Coils, Discrete Inputs
- Up to 1000 registers per bank
- **Simulation Mode** — auto-varies HR0 (sine wave), HR1 (ramp), IR0 (temperature), Coil0 (toggle), HR2 (counter) so masters see realistic changing data
- Supports multiple simultaneous master connections (TCP mode)

### 🔍 Bus Scanner
- **RTU Bus Scan** — probe slave IDs 1–247 on any RS-485 bus
- **TCP Single IP** — scan a device for active slave IDs
- **TCP Network Scan** — scan an IP range for Modbus-enabled devices
- Detects supported function codes per device
- Reads vendor/product info via FC43 MEI (where supported)
- Export results to CSV

### 🩺 Network Diagnostics
- Continuous health monitoring with live KPI metrics
- Response time sparkline chart (last 60 samples)
- Error timeline visualization
- Automated diagnostic findings with severity levels:
  - Error rate analysis
  - Timeout pattern detection
  - Response time performance scoring
  - Jitter / noise detection
  - CRC error flagging
  - Modbus exception code analysis
- Actionable recommendations for every finding
- Overall network health score (0–100)
- Export plain-text diagnostic reports

### 🧮 Data Calculator
- Paste raw register values and instantly decode to all formats
- Byte/word order reference (AB CD, CD AB, BA DC, DC BA)
- Complete function code reference table
- Modbus address / register type reference (0x, 1x, 3x, 4x)
- RTU inter-frame timing chart for all baud rates

---

## Requirements

- Windows 10 / 11
- Python 3.10+ (for running from source)
- For RTU: USB-to-RS485 adapter (e.g. FTDI-based)
- For TCP: Network connection to target device
- Port 502 for Modbus TCP slave mode may require running as Administrator

---

## Quick Start

### Run from Source
```
Double-click run.bat
```
This creates a virtual environment, installs dependencies, and launches the app.

### Build Standalone EXE
```
Double-click build.bat
```
Output: `dist\SAS-Modbus-Toolkit.exe` — no Python required on target PC.

### Manual Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## Project Structure

```
Source Code/
├── main.py              # Entry point, logging setup
├── app.py               # Main window, sidebar navigation
├── requirements.txt
├── build.bat            # PyInstaller build script
├── run.bat              # Quick launch from source
├── assets/
│   ├── icon.ico
│   ├── icon.png
│   ├── logo.png
│   └── logo_light.png
├── core/
│   ├── modbus_master.py   # TCP/RTU master engine
│   ├── modbus_slave.py    # Slave simulator server
│   ├── modbus_scanner.py  # Bus / network scanner
│   ├── diagnostics.py     # Health scoring & findings
│   └── data_types.py      # Register encode/decode
└── ui/
    ├── theme.py            # Colors, fonts, constants
    ├── widgets.py          # Shared widget components
    ├── master_view.py      # Modbus Master view
    ├── slave_view.py       # Slave Simulator view
    ├── scanner_view.py     # Bus Scanner view
    ├── diagnostics_view.py # Network Diagnostics view
    ├── calculator_view.py  # Data Calculator & reference
    └── help_view.py        # Help & quick reference
```

---

## Dependencies

| Package        | Purpose                        |
|----------------|-------------------------------|
| `customtkinter`| Modern UI framework            |
| `pymodbus`     | Modbus TCP/RTU client & server |
| `pyserial`     | Serial port access (RTU)       |
| `Pillow`       | Image loading (logo/icons)     |
| `pyinstaller`  | Build standalone executable    |

---

## RTU Wiring Notes

**RS-485 Two-Wire:**
- A (–) → A (–) on all devices
- B (+) → B (+) on all devices
- Termination: 120Ω at each **end** of the cable run only
- Bias: pull B (+) up, A (–) down — only at one device

**Troubleshooting RTU:**
1. Wrong slave ID is the most common mistake — start with ID 1
2. Swap A and B if no response (some devices label them opposite)
3. Check baud rate matches all devices on the bus
4. Verify termination is only at the two physical ends of the cable

---

© 2026 Southern Automation Solutions · Contact@SASControls.com
