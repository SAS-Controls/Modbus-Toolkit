"""
SAS Modbus Toolkit — Data Type Utilities
Convert raw Modbus register values to engineering-friendly formats.
"""

import struct
from enum import Enum
from typing import List, Optional, Union


class DataType(Enum):
    """Supported data type interpretations for Modbus registers."""
    INT16   = "INT16"    # Signed 16-bit integer (1 register)
    UINT16  = "UINT16"   # Unsigned 16-bit integer (1 register)
    INT32_AB_CD = "INT32 (AB CD)"  # Signed 32-bit, big-endian word order (2 registers)
    INT32_CD_AB = "INT32 (CD AB)"  # Signed 32-bit, little-endian word order (2 registers)
    UINT32_AB_CD = "UINT32 (AB CD)" # Unsigned 32-bit, big-endian word order
    UINT32_CD_AB = "UINT32 (CD AB)" # Unsigned 32-bit, little-endian word order
    FLOAT32_AB_CD = "FLOAT32 (AB CD)" # IEEE 754 float, big-endian word order (2 registers)
    FLOAT32_CD_AB = "FLOAT32 (CD AB)" # IEEE 754 float, little-endian word order
    FLOAT64 = "FLOAT64"  # IEEE 754 double (4 registers)
    BIT_0   = "Bit 0"
    BIT_1   = "Bit 1"
    BIT_2   = "Bit 2"
    BIT_3   = "Bit 3"
    BIT_4   = "Bit 4"
    BIT_5   = "Bit 5"
    BIT_6   = "Bit 6"
    BIT_7   = "Bit 7"
    BIT_8   = "Bit 8"
    BIT_9   = "Bit 9"
    BIT_10  = "Bit 10"
    BIT_11  = "Bit 11"
    BIT_12  = "Bit 12"
    BIT_13  = "Bit 13"
    BIT_14  = "Bit 14"
    BIT_15  = "Bit 15"
    HEX     = "HEX"      # Raw hex display
    ASCII   = "ASCII"    # 2-char ASCII string
    BOOL    = "BOOL"     # Non-zero = True


# How many registers each data type consumes
DATA_TYPE_REGISTER_COUNT = {
    DataType.INT16:   1,
    DataType.UINT16:  1,
    DataType.INT32_AB_CD: 2,
    DataType.INT32_CD_AB: 2,
    DataType.UINT32_AB_CD: 2,
    DataType.UINT32_CD_AB: 2,
    DataType.FLOAT32_AB_CD: 2,
    DataType.FLOAT32_CD_AB: 2,
    DataType.FLOAT64: 4,
    DataType.HEX:  1,
    DataType.ASCII: 1,
    DataType.BOOL: 1,
}
# Bit types all use 1 register
for _bit in [DataType.BIT_0, DataType.BIT_1, DataType.BIT_2, DataType.BIT_3,
             DataType.BIT_4, DataType.BIT_5, DataType.BIT_6, DataType.BIT_7,
             DataType.BIT_8, DataType.BIT_9, DataType.BIT_10, DataType.BIT_11,
             DataType.BIT_12, DataType.BIT_13, DataType.BIT_14, DataType.BIT_15]:
    DATA_TYPE_REGISTER_COUNT[_bit] = 1

# Simple types for the dropdown (most common)
COMMON_DATA_TYPES = [
    DataType.UINT16,
    DataType.INT16,
    DataType.FLOAT32_AB_CD,
    DataType.FLOAT32_CD_AB,
    DataType.UINT32_AB_CD,
    DataType.INT32_AB_CD,
    DataType.HEX,
    DataType.ASCII,
    DataType.BOOL,
]

ALL_DATA_TYPE_NAMES = [dt.value for dt in DataType]
COMMON_DATA_TYPE_NAMES = [dt.value for dt in COMMON_DATA_TYPES]


def decode_registers(registers: List[int], data_type: DataType,
                     decimal_places: int = 3) -> str:
    """
    Decode a list of raw register values into a human-readable string.

    Args:
        registers: Raw 16-bit register values from Modbus response.
        data_type: The interpretation to apply.
        decimal_places: Number of decimal places for float formatting.

    Returns:
        Formatted string representation of the value.
    """
    if not registers:
        return "—"

    try:
        if data_type == DataType.INT16:
            val = registers[0]
            if val >= 32768:
                val -= 65536
            return str(val)

        elif data_type == DataType.UINT16:
            return str(registers[0])

        elif data_type == DataType.HEX:
            return f"0x{registers[0]:04X}"

        elif data_type == DataType.ASCII:
            hi = (registers[0] >> 8) & 0xFF
            lo = registers[0] & 0xFF
            chars = "".join(chr(b) if 32 <= b < 127 else "." for b in (hi, lo))
            return f'"{chars}"'

        elif data_type == DataType.BOOL:
            return "TRUE" if registers[0] != 0 else "FALSE"

        elif data_type in (DataType.BIT_0, DataType.BIT_1, DataType.BIT_2, DataType.BIT_3,
                           DataType.BIT_4, DataType.BIT_5, DataType.BIT_6, DataType.BIT_7,
                           DataType.BIT_8, DataType.BIT_9, DataType.BIT_10, DataType.BIT_11,
                           DataType.BIT_12, DataType.BIT_13, DataType.BIT_14, DataType.BIT_15):
            bit_num = int(data_type.value.split()[1])
            bit_val = (registers[0] >> bit_num) & 1
            return "1" if bit_val else "0"

        elif data_type in (DataType.FLOAT32_AB_CD, DataType.FLOAT32_CD_AB):
            if len(registers) < 2:
                return "need 2 regs"
            if data_type == DataType.FLOAT32_AB_CD:
                raw = struct.pack(">HH", registers[0], registers[1])
            else:
                raw = struct.pack(">HH", registers[1], registers[0])
            val = struct.unpack(">f", raw)[0]
            if val != val:  # NaN check
                return "NaN"
            fmt = f"{{:.{decimal_places}f}}"
            return fmt.format(val)

        elif data_type in (DataType.INT32_AB_CD, DataType.INT32_CD_AB,
                           DataType.UINT32_AB_CD, DataType.UINT32_CD_AB):
            if len(registers) < 2:
                return "need 2 regs"
            if "AB CD" in data_type.value:
                raw = struct.pack(">HH", registers[0], registers[1])
            else:
                raw = struct.pack(">HH", registers[1], registers[0])
            if "UINT" in data_type.value:
                val = struct.unpack(">I", raw)[0]
            else:
                val = struct.unpack(">i", raw)[0]
            return str(val)

        elif data_type == DataType.FLOAT64:
            if len(registers) < 4:
                return "need 4 regs"
            raw = struct.pack(">HHHH", registers[0], registers[1], registers[2], registers[3])
            val = struct.unpack(">d", raw)[0]
            fmt = f"{{:.{decimal_places}f}}"
            return fmt.format(val)

    except Exception as e:
        return f"Err: {e}"

    return "—"


def encode_value(value_str: str, data_type: DataType) -> Optional[List[int]]:
    """
    Encode a string value into Modbus register(s) for writing.

    Returns:
        List of 16-bit register values, or None if encoding fails.
    """
    try:
        if data_type in (DataType.UINT16, DataType.INT16):
            val = int(float(value_str))
            if data_type == DataType.INT16:
                val = max(-32768, min(32767, val))
                if val < 0:
                    val += 65536
            else:
                val = max(0, min(65535, val))
            return [val]

        elif data_type == DataType.HEX:
            val = int(value_str, 16) & 0xFFFF
            return [val]

        elif data_type == DataType.BOOL:
            val = 1 if value_str.strip().upper() in ("1", "TRUE", "ON", "YES") else 0
            return [val]

        elif data_type in (DataType.FLOAT32_AB_CD, DataType.FLOAT32_CD_AB):
            val = float(value_str)
            raw = struct.pack(">f", val)
            hi, lo = struct.unpack(">HH", raw)
            if data_type == DataType.FLOAT32_AB_CD:
                return [hi, lo]
            else:
                return [lo, hi]

        elif data_type in (DataType.INT32_AB_CD, DataType.INT32_CD_AB):
            val = int(float(value_str))
            raw = struct.pack(">i", val)
            hi, lo = struct.unpack(">HH", raw)
            if "AB CD" in data_type.value:
                return [hi, lo]
            else:
                return [lo, hi]

        elif data_type in (DataType.UINT32_AB_CD, DataType.UINT32_CD_AB):
            val = int(float(value_str))
            raw = struct.pack(">I", val)
            hi, lo = struct.unpack(">HH", raw)
            if "AB CD" in data_type.value:
                return [hi, lo]
            else:
                return [lo, hi]

    except Exception:
        return None

    return None


def get_register_count(data_type: DataType) -> int:
    """Return the number of registers needed for this data type."""
    return DATA_TYPE_REGISTER_COUNT.get(data_type, 1)


def format_coil_value(value: bool) -> str:
    """Format a coil/discrete input value."""
    return "ON" if value else "OFF"


def registers_to_hex_string(registers: List[int]) -> str:
    """Convert register list to compact hex string."""
    return " ".join(f"{r:04X}" for r in registers)
