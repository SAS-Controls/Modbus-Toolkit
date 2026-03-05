"""
SAS Modbus Toolkit — Modbus Client (Master)
Wraps pymodbus for both TCP and RTU connections with consistent result objects.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, List

logger = logging.getLogger(__name__)


class FunctionCode(IntEnum):
    READ_COILS = 1
    READ_DISCRETE_INPUTS = 2
    READ_HOLDING_REGISTERS = 3
    READ_INPUT_REGISTERS = 4
    WRITE_SINGLE_COIL = 5
    WRITE_SINGLE_REGISTER = 6
    WRITE_MULTIPLE_COILS = 15
    WRITE_MULTIPLE_REGISTERS = 16


FC_LABELS = {
    FunctionCode.READ_COILS: "FC01 – Read Coils",
    FunctionCode.READ_DISCRETE_INPUTS: "FC02 – Read Discrete Inputs",
    FunctionCode.READ_HOLDING_REGISTERS: "FC03 – Read Holding Registers",
    FunctionCode.READ_INPUT_REGISTERS: "FC04 – Read Input Registers",
    FunctionCode.WRITE_SINGLE_COIL: "FC05 – Write Single Coil",
    FunctionCode.WRITE_SINGLE_REGISTER: "FC06 – Write Single Register",
    FunctionCode.WRITE_MULTIPLE_COILS: "FC15 – Write Multiple Coils",
    FunctionCode.WRITE_MULTIPLE_REGISTERS: "FC16 – Write Multiple Registers",
}

EXCEPTION_CODES = {
    1: "Illegal Function — Device does not support this function code",
    2: "Illegal Data Address — Register address is out of range for this device",
    3: "Illegal Data Value — Value written is not valid for this register",
    4: "Slave Device Failure — Internal error in the device",
    5: "Acknowledge — Request accepted but processing not complete (use FC11 to check)",
    6: "Slave Device Busy — Device is busy, retry the request",
    8: "Memory Parity Error — Memory parity error detected in the device",
    10: "Gateway Path Unavailable — Gateway cannot find path to target device",
    11: "Gateway Target Failed to Respond — Device behind gateway did not respond",
}

BAUD_RATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
PARITY_OPTIONS = {"None": "N", "Even": "E", "Odd": "O"}
STOPBIT_OPTIONS = {"1": 1, "2": 2}


@dataclass
class ModbusResult:
    """Result from a single Modbus transaction."""
    success: bool
    function_code: int
    slave_id: int
    address: int
    count: int
    values: List = field(default_factory=list)
    error_msg: str = ""
    exception_code: int = 0
    response_time_ms: float = 0.0
    raw_request: bytes = b""
    raw_response: bytes = b""
    timestamp: float = field(default_factory=time.time)

    @property
    def exception_description(self) -> str:
        if self.exception_code:
            return EXCEPTION_CODES.get(self.exception_code,
                                       f"Unknown Exception Code {self.exception_code}")
        return ""


class ModbusClientWrapper:
    """
    Unified wrapper around pymodbus for TCP and RTU connections.
    Tracks statistics and provides connection management.
    """

    def __init__(self):
        self._client = None
        self._protocol = "TCP"
        self.connected = False

        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.timeout_count = 0
        self.exception_count = 0
        self.total_response_time_ms = 0.0
        self.response_times: List[float] = []  # last 100 response times

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100

    @property
    def avg_response_ms(self) -> float:
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    @property
    def min_response_ms(self) -> float:
        return min(self.response_times) if self.response_times else 0.0

    @property
    def max_response_ms(self) -> float:
        return max(self.response_times) if self.response_times else 0.0

    def reset_stats(self):
        """Reset all communication statistics."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.timeout_count = 0
        self.exception_count = 0
        self.total_response_time_ms = 0.0
        self.response_times.clear()

    def connect_tcp(self, host: str, port: int = 502, timeout: float = 3.0) -> bool:
        """Connect to a Modbus TCP device."""
        try:
            from pymodbus.client import ModbusTcpClient
            self.disconnect()
            self._client = ModbusTcpClient(host=host, port=port, timeout=timeout)
            self._protocol = "TCP"
            result = self._client.connect()
            self.connected = result
            if result:
                logger.info(f"Connected to Modbus TCP: {host}:{port}")
            else:
                logger.warning(f"Failed to connect to Modbus TCP: {host}:{port}")
            return result
        except Exception as e:
            logger.error(f"TCP connection error: {e}")
            self.connected = False
            return False

    def connect_rtu(self, port: str, baudrate: int = 9600, parity: str = "N",
                    stopbits: int = 1, bytesize: int = 8, timeout: float = 1.0) -> bool:
        """Connect via Modbus RTU over serial."""
        try:
            from pymodbus.client import ModbusSerialClient
            self.disconnect()
            self._client = ModbusSerialClient(
                port=port,
                baudrate=baudrate,
                parity=parity,
                stopbits=stopbits,
                bytesize=bytesize,
                timeout=timeout,
            )
            self._protocol = "RTU"
            result = self._client.connect()
            self.connected = result
            if result:
                logger.info(f"Connected to Modbus RTU: {port} @ {baudrate} {parity}{bytesize}{stopbits}")
            else:
                logger.warning(f"Failed to connect to Modbus RTU: {port}")
            return result
        except Exception as e:
            logger.error(f"RTU connection error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Close the current connection."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self.connected = False

    def execute(self, fc: FunctionCode, slave_id: int, address: int,
                count: int = 1, values: list = None) -> ModbusResult:
        """
        Execute a Modbus transaction and return a ModbusResult.
        Thread-safe — can be called from background threads.
        """
        if not self._client or not self.connected:
            return ModbusResult(
                success=False, function_code=int(fc), slave_id=slave_id,
                address=address, count=count, error_msg="Not connected"
            )

        self.total_requests += 1
        start = time.perf_counter()

        try:
            response = self._dispatch(fc, slave_id, address, count, values or [])
            elapsed_ms = (time.perf_counter() - start) * 1000

            if response is None or response.isError():
                self.failed_requests += 1
                # Try to extract exception code
                exc_code = 0
                err_msg = "Request failed"
                if hasattr(response, 'exception_code'):
                    exc_code = response.exception_code
                    err_msg = f"Modbus Exception {exc_code}: {EXCEPTION_CODES.get(exc_code, 'Unknown')}"
                    self.exception_count += 1
                elif response is None:
                    err_msg = "No response (timeout)"
                    self.timeout_count += 1
                return ModbusResult(
                    success=False, function_code=int(fc), slave_id=slave_id,
                    address=address, count=count, error_msg=err_msg,
                    exception_code=exc_code, response_time_ms=elapsed_ms
                )

            # Extract values
            result_values = self._extract_values(fc, response, count)
            self.successful_requests += 1
            self.response_times.append(elapsed_ms)
            if len(self.response_times) > 200:
                self.response_times.pop(0)

            return ModbusResult(
                success=True, function_code=int(fc), slave_id=slave_id,
                address=address, count=count, values=result_values,
                response_time_ms=elapsed_ms
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.failed_requests += 1
            logger.error(f"Modbus execute error: {e}")
            return ModbusResult(
                success=False, function_code=int(fc), slave_id=slave_id,
                address=address, count=count,
                error_msg=str(e), response_time_ms=elapsed_ms
            )

    def _dispatch(self, fc: FunctionCode, slave_id: int, address: int,
                  count: int, values: list):
        """Dispatch the correct pymodbus call for the given function code."""
        c = self._client
        kw = {"slave": slave_id}

        if fc == FunctionCode.READ_COILS:
            return c.read_coils(address, count, **kw)
        elif fc == FunctionCode.READ_DISCRETE_INPUTS:
            return c.read_discrete_inputs(address, count, **kw)
        elif fc == FunctionCode.READ_HOLDING_REGISTERS:
            return c.read_holding_registers(address, count, **kw)
        elif fc == FunctionCode.READ_INPUT_REGISTERS:
            return c.read_input_registers(address, count, **kw)
        elif fc == FunctionCode.WRITE_SINGLE_COIL:
            val = bool(values[0]) if values else False
            return c.write_coil(address, val, **kw)
        elif fc == FunctionCode.WRITE_SINGLE_REGISTER:
            val = int(values[0]) if values else 0
            return c.write_register(address, val, **kw)
        elif fc == FunctionCode.WRITE_MULTIPLE_COILS:
            bools = [bool(v) for v in values]
            return c.write_coils(address, bools, **kw)
        elif fc == FunctionCode.WRITE_MULTIPLE_REGISTERS:
            ints = [int(v) & 0xFFFF for v in values]
            return c.write_registers(address, ints, **kw)
        return None

    def _extract_values(self, fc: FunctionCode, response, count: int) -> list:
        """Extract register/coil values from pymodbus response."""
        if fc in (FunctionCode.READ_COILS, FunctionCode.READ_DISCRETE_INPUTS):
            return list(response.bits[:count])
        elif fc in (FunctionCode.READ_HOLDING_REGISTERS, FunctionCode.READ_INPUT_REGISTERS):
            return list(response.registers[:count])
        # Write responses don't carry back values — return empty
        return []

    def read_device_id(self, slave_id: int) -> dict:
        """Attempt to read device identification via FC43/MEI (best-effort)."""
        result = {}
        try:
            from pymodbus.mei_message import ReadDeviceInformationRequest
            req = ReadDeviceInformationRequest(read_code=1, object_id=0x00, slave=slave_id)
            rsp = self._client.execute(req)
            if not rsp.isError() and hasattr(rsp, 'information'):
                info = rsp.information
                result = {
                    "vendor": info.get(0, b"").decode(errors="replace"),
                    "product_code": info.get(1, b"").decode(errors="replace"),
                    "revision": info.get(2, b"").decode(errors="replace"),
                }
        except Exception:
            pass
        return result
