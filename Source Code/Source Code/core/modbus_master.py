"""
SAS Modbus Toolkit — Modbus Master Engine
Manages Modbus TCP and RTU master (client) connections.
Handles polling, reads, writes, and transaction logging.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConnectionMode(Enum):
    TCP = "TCP"
    RTU = "RTU"


class FunctionCode(Enum):
    FC01_READ_COILS = 1
    FC02_READ_DISCRETE_INPUTS = 2
    FC03_READ_HOLDING_REGISTERS = 3
    FC04_READ_INPUT_REGISTERS = 4
    FC05_WRITE_SINGLE_COIL = 5
    FC06_WRITE_SINGLE_REGISTER = 6
    FC15_WRITE_MULTIPLE_COILS = 15
    FC16_WRITE_MULTIPLE_REGISTERS = 16


FC_NAMES = {
    1:  "FC01 Read Coils",
    2:  "FC02 Read Discrete Inputs",
    3:  "FC03 Read Holding Registers",
    4:  "FC04 Read Input Registers",
    5:  "FC05 Write Single Coil",
    6:  "FC06 Write Single Register",
    15: "FC15 Write Multiple Coils",
    16: "FC16 Write Multiple Registers",
}


@dataclass
class TransactionRecord:
    """A single Modbus request/response transaction."""
    timestamp: datetime
    direction: str          # "TX" or "RX"
    slave_id: int
    function_code: int
    address: int
    count: int
    values: Optional[List] = None
    error: Optional[str] = None
    response_time_ms: float = 0.0
    raw_bytes: str = ""

    def format_log_line(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        fc_name = FC_NAMES.get(self.function_code, f"FC{self.function_code:02d}")
        if self.error:
            status = f"ERROR: {self.error}"
        elif self.values is not None:
            if len(self.values) <= 4:
                val_str = str(self.values)
            else:
                val_str = f"[{self.values[0]}, {self.values[1]}, ... ({len(self.values)} values)]"
            status = f"OK  {val_str}  ({self.response_time_ms:.1f}ms)"
        else:
            status = "TX"
        return f"[{ts}]  Slave {self.slave_id:3d}  {fc_name:<32s}  Addr:{self.address:5d}  Cnt:{self.count:4d}  {status}"


@dataclass
class PollConfig:
    """Configuration for a single poll row in the master table."""
    row_id: int
    address: int
    count: int
    function_code: int = 3          # Default: read holding registers
    label: str = ""
    data_type: str = "UINT16"
    decimal_places: int = 3
    enabled: bool = True


@dataclass
class ConnectionConfig:
    """Modbus connection parameters."""
    mode: ConnectionMode = ConnectionMode.TCP
    # TCP
    host: str = "192.168.1.1"
    port: int = 502
    # RTU
    serial_port: str = "COM1"
    baudrate: int = 9600
    parity: str = "N"       # N, E, O
    stopbits: float = 1
    bytesize: int = 8
    # Common
    slave_id: int = 1
    timeout: float = 1.0
    retries: int = 1


class ModbusMasterEngine:
    """
    Modbus master (client) engine supporting TCP and RTU.

    Runs a background polling thread and fires callbacks when data changes.
    All callbacks are invoked from the background thread — callers must
    ensure thread-safe UI updates (typically via widget.after()).
    """

    def __init__(self):
        self._client = None
        self._config: Optional[ConnectionConfig] = None
        self._connected = False
        self._polling = False
        self._poll_interval = 1.0  # seconds

        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Transaction log (ring buffer)
        self._max_log = 500
        self._log: List[TransactionRecord] = []

        # Callbacks — set by the UI layer
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable[[str], None]] = None
        self.on_poll_result: Optional[Callable[[int, int, List], None]] = None
        self.on_transaction: Optional[Callable[[TransactionRecord], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None

    # ── Connection Management ─────────────────────────────────────────────────

    def connect(self, config: ConnectionConfig) -> Tuple[bool, str]:
        """
        Establish a Modbus connection.

        Returns:
            (success, message) tuple.
        """
        self.disconnect()
        self._config = config

        try:
            if config.mode == ConnectionMode.TCP:
                from pymodbus.client import ModbusTcpClient
                self._client = ModbusTcpClient(
                    host=config.host,
                    port=config.port,
                    timeout=config.timeout,
                    retries=config.retries,
                )
            else:
                from pymodbus.client import ModbusSerialClient
                self._client = ModbusSerialClient(
                    port=config.serial_port,
                    baudrate=config.baudrate,
                    parity=config.parity,
                    stopbits=config.stopbits,
                    bytesize=config.bytesize,
                    timeout=config.timeout,
                    retries=config.retries,
                )

            ok = self._client.connect()
            if not ok:
                self._client = None
                msg = f"Could not connect to {self._describe_target(config)}"
                logger.warning(msg)
                return False, msg

            self._connected = True
            logger.info(f"Connected to {self._describe_target(config)}")
            if self.on_connected:
                self.on_connected()
            return True, "Connected"

        except Exception as e:
            self._client = None
            msg = f"Connection error: {e}"
            logger.error(msg)
            return False, msg

    def disconnect(self):
        """Disconnect from the Modbus device and stop polling."""
        self.stop_polling()
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        if self._connected:
            self._connected = False
            if self.on_disconnected:
                self.on_disconnected("Disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    # ── Single Read/Write Operations ──────────────────────────────────────────

    def read_registers(self, address: int, count: int, function_code: int = 3,
                       slave_id: Optional[int] = None) -> Tuple[bool, str, Optional[List]]:
        """
        Perform a single read operation.

        Returns:
            (success, message, values) where values is a list of int or bool.
        """
        if not self.is_connected:
            return False, "Not connected", None

        sid = slave_id if slave_id is not None else (self._config.slave_id if self._config else 1)
        t0 = time.monotonic()

        try:
            result = self._execute_read(function_code, address, count, sid)
            elapsed_ms = (time.monotonic() - t0) * 1000

            if result is None or result.isError():
                err_msg = str(result) if result else "No response"
                self._log_transaction(sid, function_code, address, count,
                                      error=err_msg, elapsed_ms=elapsed_ms)
                if self.on_error:
                    self.on_error(f"Read error: {err_msg}")
                return False, err_msg, None

            values = self._extract_values(result, function_code)
            self._log_transaction(sid, function_code, address, count,
                                  values=values, elapsed_ms=elapsed_ms)
            return True, "OK", values

        except Exception as e:
            elapsed_ms = (time.monotonic() - t0) * 1000
            err_msg = str(e)
            self._log_transaction(sid, function_code, address, count,
                                  error=err_msg, elapsed_ms=elapsed_ms)
            logger.error(f"Read exception: {e}")
            return False, err_msg, None

    def write_register(self, address: int, value: int,
                       slave_id: Optional[int] = None) -> Tuple[bool, str]:
        """Write a single holding register (FC06)."""
        if not self.is_connected:
            return False, "Not connected"

        sid = slave_id if slave_id is not None else (self._config.slave_id if self._config else 1)
        t0 = time.monotonic()
        try:
            result = self._client.write_register(address=address, value=value & 0xFFFF, device_id=sid)
            elapsed_ms = (time.monotonic() - t0) * 1000
            if result is None or result.isError():
                err_msg = str(result) if result else "No response"
                self._log_transaction(sid, 6, address, 1, error=err_msg, elapsed_ms=elapsed_ms)
                return False, err_msg
            self._log_transaction(sid, 6, address, 1, values=[value], elapsed_ms=elapsed_ms)
            return True, "OK"
        except Exception as e:
            elapsed_ms = (time.monotonic() - t0) * 1000
            self._log_transaction(sid, 6, address, 1, error=str(e), elapsed_ms=elapsed_ms)
            logger.error(f"Write register error: {e}")
            return False, str(e)

    def write_registers(self, address: int, values: List[int],
                        slave_id: Optional[int] = None) -> Tuple[bool, str]:
        """Write multiple holding registers (FC16)."""
        if not self.is_connected:
            return False, "Not connected"

        sid = slave_id if slave_id is not None else (self._config.slave_id if self._config else 1)
        t0 = time.monotonic()
        try:
            result = self._client.write_registers(address=address, values=values, device_id=sid)
            elapsed_ms = (time.monotonic() - t0) * 1000
            if result is None or result.isError():
                err_msg = str(result) if result else "No response"
                self._log_transaction(sid, 16, address, len(values), error=err_msg, elapsed_ms=elapsed_ms)
                return False, err_msg
            self._log_transaction(sid, 16, address, len(values), values=values, elapsed_ms=elapsed_ms)
            return True, "OK"
        except Exception as e:
            elapsed_ms = (time.monotonic() - t0) * 1000
            self._log_transaction(sid, 16, address, len(values), error=str(e), elapsed_ms=elapsed_ms)
            return False, str(e)

    def write_coil(self, address: int, value: bool,
                   slave_id: Optional[int] = None) -> Tuple[bool, str]:
        """Write a single coil (FC05)."""
        if not self.is_connected:
            return False, "Not connected"

        sid = slave_id if slave_id is not None else (self._config.slave_id if self._config else 1)
        t0 = time.monotonic()
        try:
            result = self._client.write_coil(address=address, value=value, device_id=sid)
            elapsed_ms = (time.monotonic() - t0) * 1000
            if result is None or result.isError():
                err_msg = str(result) if result else "No response"
                self._log_transaction(sid, 5, address, 1, error=err_msg, elapsed_ms=elapsed_ms)
                return False, err_msg
            self._log_transaction(sid, 5, address, 1, values=[int(value)], elapsed_ms=elapsed_ms)
            return True, "OK"
        except Exception as e:
            elapsed_ms = (time.monotonic() - t0) * 1000
            self._log_transaction(sid, 5, address, 1, error=str(e), elapsed_ms=elapsed_ms)
            return False, str(e)

    # ── Polling ───────────────────────────────────────────────────────────────

    def start_polling(self, poll_configs: List[PollConfig], interval: float = 1.0,
                      slave_id: Optional[int] = None):
        """Start background polling for a list of register ranges."""
        if self._polling:
            self.stop_polling()

        self._poll_interval = max(0.1, interval)
        self._stop_event.clear()
        self._polling = True

        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            args=(poll_configs, slave_id),
            daemon=True,
            name="modbus-poll",
        )
        self._poll_thread.start()
        logger.info(f"Polling started: {len(poll_configs)} items @ {interval}s")

    def stop_polling(self):
        """Stop the background polling thread."""
        if self._polling:
            self._polling = False
            self._stop_event.set()
            if self._poll_thread and self._poll_thread.is_alive():
                self._poll_thread.join(timeout=3.0)
            self._poll_thread = None
            logger.info("Polling stopped")

    def _poll_loop(self, poll_configs: List[PollConfig], slave_id: Optional[int]):
        """Background thread: continuously polls all enabled register ranges."""
        sid = slave_id if slave_id is not None else (self._config.slave_id if self._config else 1)

        while not self._stop_event.wait(0):
            loop_start = time.monotonic()

            for cfg in poll_configs:
                if self._stop_event.is_set():
                    break
                if not cfg.enabled or not self.is_connected:
                    continue

                success, _, values = self.read_registers(cfg.address, cfg.count,
                                                          cfg.function_code, sid)
                if success and values is not None and self.on_poll_result:
                    self.on_poll_result(cfg.row_id, cfg.address, values)

            # Wait for remainder of interval
            elapsed = time.monotonic() - loop_start
            wait_time = max(0.0, self._poll_interval - elapsed)
            self._stop_event.wait(wait_time)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _execute_read(self, function_code: int, address: int, count: int, slave_id: int):
        """Execute a Modbus read by function code."""
        if function_code == 1:
            return self._client.read_coils(address=address, count=count, device_id=slave_id)
        elif function_code == 2:
            return self._client.read_discrete_inputs(address=address, count=count, device_id=slave_id)
        elif function_code == 3:
            return self._client.read_holding_registers(address=address, count=count, device_id=slave_id)
        elif function_code == 4:
            return self._client.read_input_registers(address=address, count=count, device_id=slave_id)
        else:
            raise ValueError(f"Unsupported read function code: {function_code}")

    def _extract_values(self, result, function_code: int) -> List:
        """Extract values from a pymodbus result object."""
        if function_code in (1, 2):
            return list(result.bits[:result.count] if hasattr(result, 'count') else result.bits)
        else:
            return list(result.registers)

    def _log_transaction(self, slave_id: int, fc: int, address: int, count: int,
                         values=None, error: Optional[str] = None, elapsed_ms: float = 0):
        """Add a transaction to the ring-buffer log."""
        rec = TransactionRecord(
            timestamp=datetime.now(),
            direction="TX/RX",
            slave_id=slave_id,
            function_code=fc,
            address=address,
            count=count,
            values=values,
            error=error,
            response_time_ms=elapsed_ms,
        )
        with self._lock:
            self._log.append(rec)
            if len(self._log) > self._max_log:
                self._log.pop(0)

        if self.on_transaction:
            self.on_transaction(rec)

    def get_log(self) -> List[TransactionRecord]:
        """Return a copy of the transaction log."""
        with self._lock:
            return list(self._log)

    def clear_log(self):
        """Clear the transaction log."""
        with self._lock:
            self._log.clear()

    @staticmethod
    def _describe_target(config: ConnectionConfig) -> str:
        if config.mode == ConnectionMode.TCP:
            return f"{config.host}:{config.port}"
        else:
            return f"{config.serial_port} @ {config.baudrate} baud"
