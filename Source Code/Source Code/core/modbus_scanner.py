"""
SAS Modbus Toolkit — Modbus Bus Scanner
Discovers Modbus devices on RTU buses and TCP networks.
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class ScanMode(Enum):
    RTU_BUS = "RTU Bus (Scan Slave IDs)"
    TCP_NETWORK = "TCP Network (Scan IP Range)"
    TCP_SINGLE = "TCP Single IP (Scan Slave IDs)"


@dataclass
class DiscoveredModbusDevice:
    """A Modbus device found during a scan."""
    slave_id: int
    host: Optional[str]     # IP for TCP scans
    port: int = 502
    responding: bool = True
    response_time_ms: float = 0.0
    # Device identity info (from FC43 MEI Read Device ID if supported)
    vendor: str = ""
    product: str = ""
    firmware: str = ""
    # Which function codes responded successfully
    supported_fc: List[int] = None
    notes: str = ""

    def __post_init__(self):
        if self.supported_fc is None:
            self.supported_fc = []

    @property
    def display_name(self) -> str:
        if self.vendor or self.product:
            return f"{self.vendor} {self.product}".strip()
        return f"Slave {self.slave_id}"


class ModbusBusScanner:
    """
    Scans for Modbus devices on RTU buses or TCP networks.

    Callbacks are fired from the scan thread — callers must handle
    thread-safe UI updates.
    """

    def __init__(self):
        self._scanning = False
        self._stop_event = threading.Event()
        self._scan_thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_device_found: Optional[Callable[[DiscoveredModbusDevice], None]] = None
        self.on_progress: Optional[Callable[[int, int, str], None]] = None  # current, total, status
        self.on_complete: Optional[Callable[[List[DiscoveredModbusDevice]], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    @property
    def is_scanning(self) -> bool:
        return self._scanning

    def start_rtu_scan(self, serial_port: str, baudrate: int = 9600,
                        parity: str = "N", stopbits: float = 1,
                        slave_id_start: int = 1, slave_id_end: int = 32,
                        timeout: float = 0.5):
        """
        Scan an RTU bus for responsive slaves.
        Probes each slave ID with a read holding registers request.
        """
        self._stop_event.clear()
        self._scanning = True
        self._scan_thread = threading.Thread(
            target=self._rtu_scan_thread,
            args=(serial_port, baudrate, parity, stopbits,
                  slave_id_start, slave_id_end, timeout),
            daemon=True,
            name="modbus-rtu-scan",
        )
        self._scan_thread.start()

    def start_tcp_scan(self, host: str, port: int = 502,
                        slave_id_start: int = 1, slave_id_end: int = 10,
                        timeout: float = 1.0):
        """
        Scan a single TCP host for responsive Modbus slave IDs.
        """
        self._stop_event.clear()
        self._scanning = True
        self._scan_thread = threading.Thread(
            target=self._tcp_scan_thread,
            args=(host, port, slave_id_start, slave_id_end, timeout),
            daemon=True,
            name="modbus-tcp-scan",
        )
        self._scan_thread.start()

    def start_tcp_network_scan(self, base_ip: str, start_octet: int, end_octet: int,
                                port: int = 502, timeout: float = 0.5):
        """
        Scan a range of IPs on a TCP network for Modbus devices.
        Tests each IP:port for Modbus connectivity (slave ID 1).
        """
        self._stop_event.clear()
        self._scanning = True
        self._scan_thread = threading.Thread(
            target=self._tcp_network_scan_thread,
            args=(base_ip, start_octet, end_octet, port, timeout),
            daemon=True,
            name="modbus-net-scan",
        )
        self._scan_thread.start()

    def stop_scan(self):
        """Stop an active scan."""
        self._stop_event.set()
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=5.0)
        self._scanning = False
        logger.info("Scan stopped by user")

    # ── RTU Scan Thread ───────────────────────────────────────────────────────

    def _rtu_scan_thread(self, serial_port, baudrate, parity, stopbits,
                          id_start, id_end, timeout):
        """Scan RTU bus for slaves IDs id_start through id_end."""
        devices = []
        try:
            from pymodbus.client import ModbusSerialClient
            client = ModbusSerialClient(
                port=serial_port,
                baudrate=baudrate,
                parity=parity,
                stopbits=stopbits,
                bytesize=8,
                timeout=timeout,
                retries=1,
            )
            if not client.connect():
                if self.on_error:
                    self.on_error(f"Could not open serial port {serial_port}")
                self._scanning = False
                return

            total = id_end - id_start + 1
            for i, slave_id in enumerate(range(id_start, id_end + 1)):
                if self._stop_event.is_set():
                    break

                status = f"Probing Slave ID {slave_id}..."
                if self.on_progress:
                    self.on_progress(i + 1, total, status)

                device = self._probe_slave(client, slave_id, host=None)
                if device:
                    devices.append(device)
                    logger.info(f"  Found RTU slave {slave_id}: {device.response_time_ms:.1f}ms")
                    if self.on_device_found:
                        self.on_device_found(device)

            client.close()

        except Exception as e:
            logger.error(f"RTU scan error: {e}")
            if self.on_error:
                self.on_error(str(e))

        self._scanning = False
        if self.on_complete:
            self.on_complete(devices)

    # ── TCP Single Host Scan Thread ───────────────────────────────────────────

    def _tcp_scan_thread(self, host, port, id_start, id_end, timeout):
        """Scan a single TCP host for responsive slave IDs."""
        devices = []
        try:
            from pymodbus.client import ModbusTcpClient
            client = ModbusTcpClient(host=host, port=port, timeout=timeout, retries=1)

            if not client.connect():
                if self.on_error:
                    self.on_error(f"Could not connect to {host}:{port}")
                self._scanning = False
                return

            total = id_end - id_start + 1
            for i, slave_id in enumerate(range(id_start, id_end + 1)):
                if self._stop_event.is_set():
                    break

                if self.on_progress:
                    self.on_progress(i + 1, total, f"Probing Slave ID {slave_id} @ {host}:{port}")

                device = self._probe_slave(client, slave_id, host=host, port=port)
                if device:
                    devices.append(device)
                    if self.on_device_found:
                        self.on_device_found(device)

            client.close()

        except Exception as e:
            logger.error(f"TCP scan error: {e}")
            if self.on_error:
                self.on_error(str(e))

        self._scanning = False
        if self.on_complete:
            self.on_complete(devices)

    # ── TCP Network Scan Thread ───────────────────────────────────────────────

    def _tcp_network_scan_thread(self, base_ip, start_octet, end_octet, port, timeout):
        """Scan a range of IP addresses for Modbus TCP devices."""
        devices = []
        try:
            from pymodbus.client import ModbusTcpClient

            total = end_octet - start_octet + 1
            for i, octet in enumerate(range(start_octet, end_octet + 1)):
                if self._stop_event.is_set():
                    break

                host = f"{base_ip}.{octet}"
                if self.on_progress:
                    self.on_progress(i + 1, total, f"Scanning {host}:{port}")

                try:
                    client = ModbusTcpClient(host=host, port=port, timeout=timeout, retries=0)
                    if client.connect():
                        device = self._probe_slave(client, slave_id=1, host=host, port=port)
                        client.close()
                        if device:
                            devices.append(device)
                            if self.on_device_found:
                                self.on_device_found(device)
                    else:
                        client.close()
                except Exception:
                    pass  # Host not responding — expected for most IPs

        except Exception as e:
            logger.error(f"Network scan error: {e}")
            if self.on_error:
                self.on_error(str(e))

        self._scanning = False
        if self.on_complete:
            self.on_complete(devices)

    # ── Device Probe ─────────────────────────────────────────────────────────

    def _probe_slave(self, client, slave_id: int, host: Optional[str] = None,
                      port: int = 502) -> Optional[DiscoveredModbusDevice]:
        """
        Probe a single slave ID with FC03 (read holding registers).
        Returns a DiscoveredModbusDevice if the slave responds, else None.
        """
        t0 = time.monotonic()
        try:
            result = client.read_holding_registers(address=0, count=1, device_id=slave_id)
            elapsed_ms = (time.monotonic() - t0) * 1000

            if result and not result.isError():
                device = DiscoveredModbusDevice(
                    slave_id=slave_id,
                    host=host,
                    port=port,
                    responding=True,
                    response_time_ms=elapsed_ms,
                )
                # Try to get device identity (FC43 — optional, many devices don't support it)
                self._try_read_device_id(client, slave_id, device)
                # Quick check which other FCs respond
                self._probe_function_codes(client, slave_id, device)
                return device

        except Exception:
            pass

        return None

    def _try_read_device_id(self, client, slave_id: int, device: DiscoveredModbusDevice):
        """Attempt FC43 MEI Read Device Identification (optional — many devices ignore it)."""
        try:
            result = client.read_device_information(read_code=0x01, object_id=0x00, device_id=slave_id)
            if result and not result.isError():
                info = result.information
                device.vendor   = info.get(0, b"").decode("ascii", errors="replace").strip("\x00")
                device.product  = info.get(1, b"").decode("ascii", errors="replace").strip("\x00")
                device.firmware = info.get(2, b"").decode("ascii", errors="replace").strip("\x00")
        except Exception:
            pass  # FC43 not supported — that's fine

    def _probe_function_codes(self, client, slave_id: int, device: DiscoveredModbusDevice):
        """Quick-probe which function codes the device supports."""
        # FC03 already confirmed; check FC01, FC02, FC04
        for fc, call in [
            (1, lambda: client.read_coils(address=0, count=1, device_id=slave_id)),
            (2, lambda: client.read_discrete_inputs(address=0, count=1, device_id=slave_id)),
            (4, lambda: client.read_input_registers(address=0, count=1, device_id=slave_id)),
        ]:
            try:
                r = call()
                if r and not r.isError():
                    device.supported_fc.append(fc)
            except Exception:
                pass
        device.supported_fc.append(3)  # FC03 already confirmed
        device.supported_fc.sort()
