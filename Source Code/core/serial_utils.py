"""
SAS Modbus Toolkit — Serial Port Utilities
Helper functions for enumerating and validating serial ports.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


def get_available_ports() -> List[str]:
    """Return a sorted list of available serial port names."""
    ports = []
    try:
        import serial.tools.list_ports
        for port in serial.tools.list_ports.comports():
            ports.append(port.device)
        ports.sort()
    except ImportError:
        logger.warning("pyserial not installed — cannot enumerate ports")
        # Return fake COM ports for Windows
        import platform
        if platform.system() == "Windows":
            ports = [f"COM{i}" for i in range(1, 13)]
    except Exception as e:
        logger.error(f"Error enumerating ports: {e}")
    return ports or ["COM1", "COM2", "COM3", "COM4"]


def get_port_descriptions() -> dict:
    """Return a dict of port_name → description for the UI."""
    result = {}
    try:
        import serial.tools.list_ports
        for port in serial.tools.list_ports.comports():
            desc = port.description or port.device
            if port.manufacturer:
                desc = f"{port.device} — {port.manufacturer}"
            result[port.device] = desc
    except Exception:
        pass
    return result


def calculate_char_time_us(baudrate: int) -> float:
    """
    Calculate the time (µs) to transmit one character at the given baud rate.
    Modbus RTU uses 11 bits per character (1 start + 8 data + 1 parity + 1 stop,
    or 1 start + 8 data + 2 stop with no parity).
    """
    return (11 / baudrate) * 1_000_000


def calculate_t35_us(baudrate: int) -> float:
    """
    Calculate the Modbus RTU inter-frame gap (3.5 character times in µs).
    Below 19200 baud, calculated exactly. Above 19200, fixed at 1750µs per spec.
    """
    if baudrate <= 19200:
        return 3.5 * calculate_char_time_us(baudrate)
    else:
        return 1750.0  # Fixed 1.75ms per Modbus spec for high baud rates


def calculate_t15_us(baudrate: int) -> float:
    """Calculate the Modbus RTU inter-character timeout (1.5 char times)."""
    if baudrate <= 19200:
        return 1.5 * calculate_char_time_us(baudrate)
    else:
        return 750.0


def frame_timing_analysis(baudrate: int) -> dict:
    """Return a dict of timing values for RTU frame analysis display."""
    char_us = calculate_char_time_us(baudrate)
    t15_us = calculate_t15_us(baudrate)
    t35_us = calculate_t35_us(baudrate)

    # Typical frame size (slave address + FC + 2 addr + 2 count + 2 CRC = 8 bytes)
    typical_request_us = 8 * char_us
    # Typical response (addr + FC + byte_count + 20 bytes data + CRC ≈ 25 bytes)
    typical_response_us = 25 * char_us

    return {
        "char_time_us": round(char_us, 1),
        "t15_us": round(t15_us, 1),
        "t35_us": round(t35_us, 1),
        "t35_ms": round(t35_us / 1000, 3),
        "typical_request_ms": round(typical_request_us / 1000, 2),
        "typical_response_ms": round(typical_response_us / 1000, 2),
        "max_recommended_timeout_ms": round(max(t35_us * 10, 200000) / 1000, 0),
    }
