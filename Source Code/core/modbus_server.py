"""
SAS Modbus Toolkit — Modbus Slave Simulator
Runs a Modbus TCP or RTU server that responds to master requests.
Runs in a background thread and provides callbacks for UI updates.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, List, Dict

logger = logging.getLogger(__name__)


@dataclass
class SlaveActivity:
    """A single master→slave transaction recorded by the slave."""
    timestamp: float = field(default_factory=time.time)
    slave_id: int = 0
    function_code: int = 0
    address: int = 0
    count: int = 0
    values: list = field(default_factory=list)
    is_write: bool = False
    client_addr: str = ""


class ModbusSlaveSimulator:
    """
    Simulates a Modbus slave device (TCP or RTU).
    Maintains four data blocks and responds to master requests.
    """

    MAX_COILS = 2000
    MAX_REGS = 1000

    def __init__(self, on_activity: Optional[Callable] = None):
        self._on_activity = on_activity
        self._server = None
        self._server_thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()

        # Data blocks (address-indexed dicts for flexibility)
        self.coils: Dict[int, bool] = {i: False for i in range(self.MAX_COILS)}
        self.discrete_inputs: Dict[int, bool] = {i: False for i in range(self.MAX_COILS)}
        self.holding_registers: Dict[int, int] = {i: 0 for i in range(self.MAX_REGS)}
        self.input_registers: Dict[int, int] = {i: 0 for i in range(self.MAX_REGS)}

        self.activity_log: List[SlaveActivity] = []
        self._lock = threading.Lock()
        self.request_count = 0
        self.write_count = 0

    def set_holding_register(self, address: int, value: int):
        with self._lock:
            self.holding_registers[address] = value & 0xFFFF

    def set_input_register(self, address: int, value: int):
        with self._lock:
            self.input_registers[address] = value & 0xFFFF

    def set_coil(self, address: int, value: bool):
        with self._lock:
            self.coils[address] = bool(value)

    def set_discrete_input(self, address: int, value: bool):
        with self._lock:
            self.discrete_inputs[address] = bool(value)

    def start_tcp(self, host: str = "0.0.0.0", port: int = 502,
                  slave_id: int = 1) -> bool:
        """Start the Modbus TCP slave server."""
        if self._running:
            self.stop()

        self._stop_event.clear()
        self._server_thread = threading.Thread(
            target=self._run_tcp, args=(host, port, slave_id),
            daemon=True, name="ModbusTCPSlave"
        )
        self._server_thread.start()
        time.sleep(0.3)  # Give server a moment to start
        return self._running

    def start_rtu(self, port: str, baudrate: int = 9600, parity: str = "N",
                  stopbits: int = 1, slave_id: int = 1) -> bool:
        """Start the Modbus RTU slave server."""
        if self._running:
            self.stop()

        self._stop_event.clear()
        self._server_thread = threading.Thread(
            target=self._run_rtu, args=(port, baudrate, parity, stopbits, slave_id),
            daemon=True, name="ModbusRTUSlave"
        )
        self._server_thread.start()
        time.sleep(0.5)
        return self._running

    def stop(self):
        """Stop the slave server."""
        self._stop_event.set()
        if self._server:
            try:
                self._server.server_close()
            except Exception:
                pass
        self._running = False
        logger.info("Modbus slave server stopped")

    def _build_context(self, slave_id: int):
        """Build pymodbus data context from current data blocks."""
        from pymodbus.datastore import (ModbusSlaveContext, ModbusServerContext,
                                         ModbusSequentialDataBlock)

        # Convert dicts to lists (pymodbus uses sequential blocks)
        co = [self.coils.get(i, False) for i in range(self.MAX_COILS)]
        di = [self.discrete_inputs.get(i, False) for i in range(self.MAX_COILS)]
        hr = [self.holding_registers.get(i, 0) for i in range(self.MAX_REGS)]
        ir = [self.input_registers.get(i, 0) for i in range(self.MAX_REGS)]

        slave_ctx = ModbusSlaveContext(
            co=ModbusSequentialDataBlock(0, co),
            di=ModbusSequentialDataBlock(0, di),
            hr=ModbusSequentialDataBlock(0, hr),
            ir=ModbusSequentialDataBlock(0, ir),
        )

        # Attach callback to detect writes
        slave_ctx._original_setValues = slave_ctx.setValues

        sim = self

        def patched_setValues(fc_as_hex, address, values):
            slave_ctx._original_setValues(fc_as_hex, address, values)
            activity = SlaveActivity(
                slave_id=slave_id, function_code=fc_as_hex,
                address=address, count=len(values),
                values=list(values), is_write=True
            )
            sim._record_activity(activity)

        slave_ctx.setValues = patched_setValues

        return ModbusServerContext(slaves={slave_id: slave_ctx}, single=False)

    def _record_activity(self, activity: SlaveActivity):
        """Record an activity entry and fire callback."""
        with self._lock:
            self.activity_log.append(activity)
            if len(self.activity_log) > 1000:
                self.activity_log.pop(0)
            self.request_count += 1
            if activity.is_write:
                self.write_count += 1

        if self._on_activity:
            try:
                self._on_activity(activity)
            except Exception as e:
                logger.debug(f"Activity callback error: {e}")

    def _run_tcp(self, host: str, port: int, slave_id: int):
        """Run TCP server in background thread."""
        try:
            from pymodbus.server import ModbusTcpServer
            from pymodbus.device import ModbusDeviceIdentification

            context = self._build_context(slave_id)
            identity = ModbusDeviceIdentification(
                info_name={
                    "VendorName": "Southern Automation Solutions",
                    "ProductCode": "SAS-Modbus-Sim",
                    "VendorUrl": "https://southernautomation.net",
                    "ProductName": "SAS Modbus Slave Simulator",
                    "ModelName": "SAS Modbus Toolkit",
                    "MajorMinorRevision": "1.0",
                }
            )

            self._server = ModbusTcpServer(
                context=context, identity=identity,
                address=(host, port)
            )
            self._running = True
            logger.info(f"Modbus TCP slave listening on {host}:{port} (unit {slave_id})")
            self._server.serve_forever()
        except Exception as e:
            logger.error(f"Modbus TCP slave error: {e}")
        finally:
            self._running = False

    def _run_rtu(self, port: str, baudrate: int, parity: str,
                 stopbits: int, slave_id: int):
        """Run RTU server in background thread."""
        try:
            from pymodbus.server import ModbusSerialServer
            from pymodbus.device import ModbusDeviceIdentification

            context = self._build_context(slave_id)
            identity = ModbusDeviceIdentification(
                info_name={
                    "VendorName": "Southern Automation Solutions",
                    "ProductCode": "SAS-Modbus-Sim",
                    "ProductName": "SAS Modbus Slave Simulator",
                }
            )

            self._server = ModbusSerialServer(
                context=context, identity=identity,
                port=port, baudrate=baudrate,
                parity=parity, stopbits=stopbits,
                framer="rtu",
            )
            self._running = True
            logger.info(f"Modbus RTU slave on {port} @ {baudrate}")
            self._server.serve_forever()
        except Exception as e:
            logger.error(f"Modbus RTU slave error: {e}")
        finally:
            self._running = False
