"""
SAS Modbus Toolkit — Modbus TCP Scanner
Scans an IP range for Modbus TCP devices by attempting connections and
reading basic register data for device fingerprinting.
"""

import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# Well-known Modbus register patterns for device identification
FINGERPRINT_READS = [
    (3, 1, 0, 4),    # FC03, unit 1, addr 0, count 4
    (3, 255, 0, 4),  # FC03, unit 255 (broadcast-style)
    (4, 1, 0, 4),    # FC04 input registers
]


@dataclass
class DiscoveredModbusDevice:
    """A Modbus device found on the network."""
    ip: str
    port: int = 502
    unit_ids: List[int] = field(default_factory=list)
    response_time_ms: float = 0.0
    registers: dict = field(default_factory=dict)   # unit_id → [reg values]
    device_id_info: dict = field(default_factory=dict)
    is_modbus: bool = False
    error: str = ""

    @property
    def display_name(self) -> str:
        if self.device_id_info.get("product_name"):
            return self.device_id_info["product_name"]
        return self.ip

    @property
    def unit_summary(self) -> str:
        if not self.unit_ids:
            return "No responding units"
        if len(self.unit_ids) == 1:
            return f"Unit ID: {self.unit_ids[0]}"
        return f"Units: {', '.join(str(u) for u in self.unit_ids[:6])}" + (
            f" +{len(self.unit_ids)-6} more" if len(self.unit_ids) > 6 else "")


class ModbusTCPScanner:
    """
    Scans a subnet for Modbus TCP devices.
    Uses lightweight socket probing followed by full Modbus validation.
    """

    def __init__(self, on_device_found: Optional[Callable] = None,
                 on_progress: Optional[Callable] = None,
                 on_complete: Optional[Callable] = None):
        self._on_device_found = on_device_found
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.results: List[DiscoveredModbusDevice] = []
        self.scanning = False

    def start_scan(self, network: str, port: int = 502,
                   timeout: float = 1.0, max_threads: int = 50,
                   scan_units: bool = True):
        """Start scanning a network (e.g. '192.168.1') for Modbus TCP devices."""
        self._stop_event.clear()
        self.results.clear()
        self.scanning = True

        self._thread = threading.Thread(
            target=self._scan_network,
            args=(network, port, timeout, max_threads, scan_units),
            daemon=True, name="ModbusScanner"
        )
        self._thread.start()

    def stop(self):
        """Cancel a running scan."""
        self._stop_event.set()
        self.scanning = False

    def _scan_network(self, network: str, port: int, timeout: float,
                      max_threads: int, scan_units: bool):
        """Main scan logic — runs in background thread."""
        # Build IP list
        base = network.rstrip(".")
        hosts = [f"{base}.{i}" for i in range(1, 255)]
        total = len(hosts)
        found = 0

        semaphore = threading.Semaphore(max_threads)
        result_lock = threading.Lock()
        threads = []

        for idx, ip in enumerate(hosts):
            if self._stop_event.is_set():
                break

            semaphore.acquire()

            def probe(ip=ip, idx=idx):
                try:
                    device = self._probe_host(ip, port, timeout, scan_units)
                    if device and device.is_modbus:
                        with result_lock:
                            self.results.append(device)
                            nonlocal found
                            found += 1
                        if self._on_device_found:
                            self._on_device_found(device)
                finally:
                    semaphore.release()

                pct = int(((idx + 1) / total) * 100)
                if self._on_progress:
                    self._on_progress(pct, idx + 1, total, found)

            t = threading.Thread(target=probe, daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=2.0)

        self.scanning = False
        if self._on_complete:
            self._on_complete(self.results)

    def _probe_host(self, ip: str, port: int, timeout: float,
                    scan_units: bool) -> Optional[DiscoveredModbusDevice]:
        """Probe a single host for Modbus TCP."""
        # Phase 1: TCP port check (fast)
        if not self._tcp_port_open(ip, port, timeout):
            return None

        # Phase 2: Modbus validation
        device = DiscoveredModbusDevice(ip=ip, port=port)
        t0 = time.perf_counter()

        try:
            from pymodbus.client import ModbusTcpClient

            client = ModbusTcpClient(host=ip, port=port, timeout=timeout)
            if not client.connect():
                return None

            device.response_time_ms = (time.perf_counter() - t0) * 1000

            # Try unit IDs 1, 2, 255 quickly
            units_to_try = [1, 2, 255] if not scan_units else list(range(1, 10)) + [255]

            for uid in units_to_try:
                if self._stop_event.is_set():
                    break
                try:
                    rsp = client.read_holding_registers(0, 4, slave=uid)
                    if not rsp.isError():
                        device.is_modbus = True
                        device.unit_ids.append(uid)
                        device.registers[uid] = list(rsp.registers)
                except Exception:
                    pass

                try:
                    rsp = client.read_input_registers(0, 4, slave=uid)
                    if not rsp.isError() and uid not in device.unit_ids:
                        device.is_modbus = True
                        device.unit_ids.append(uid)
                except Exception:
                    pass

            # Try FC43 device identification
            if device.is_modbus:
                device.device_id_info = self._read_device_id(
                    client, device.unit_ids[0] if device.unit_ids else 1)

            client.close()

        except Exception as e:
            logger.debug(f"Probe error {ip}: {e}")

        return device

    def _tcp_port_open(self, ip: str, port: int, timeout: float) -> bool:
        """Quick TCP socket check to see if port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout * 0.5)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _read_device_id(self, client, unit_id: int) -> dict:
        """Attempt FC43 MEI device ID read."""
        try:
            from pymodbus.mei_message import ReadDeviceInformationRequest
            req = ReadDeviceInformationRequest(read_code=1, object_id=0x00, slave=unit_id)
            rsp = client.execute(req)
            if not rsp.isError() and hasattr(rsp, 'information'):
                info = rsp.information
                return {
                    "vendor": info.get(0, b"").decode(errors="replace"),
                    "product_code": info.get(1, b"").decode(errors="replace"),
                    "revision": info.get(2, b"").decode(errors="replace"),
                }
        except Exception:
            pass
        return {}
