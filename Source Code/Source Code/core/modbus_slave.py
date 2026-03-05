"""
SAS Modbus Toolkit — Modbus Slave (Simulator) Engine
Simulates a Modbus TCP or RTU slave device for network testing.
Runs the server in a background asyncio thread so the UI stays responsive.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Max registers per bank
MAX_COILS = 1000
MAX_DISCRETE = 1000
MAX_HOLDING = 1000
MAX_INPUT = 1000


class SlaveMode(Enum):
    TCP = "TCP"
    RTU = "RTU"


@dataclass
class SlaveConfig:
    mode: SlaveMode = SlaveMode.TCP
    slave_id: int = 1
    # TCP
    host: str = "0.0.0.0"
    port: int = 502
    # RTU
    serial_port: str = "COM1"
    baudrate: int = 9600
    parity: str = "N"
    stopbits: float = 1
    bytesize: int = 8
    timeout: float = 1.0


class ModbusSlaveServer:
    """
    Simulates a Modbus slave (server) for commissioning and testing.

    Register banks:
        - Coils (FC01/FC05/FC15) — 1-bit read/write
        - Discrete Inputs (FC02) — 1-bit read-only
        - Holding Registers (FC03/FC06/FC16) — 16-bit read/write
        - Input Registers (FC04) — 16-bit read-only

    All banks are pre-populated with zeros and can be edited via the UI
    while the server is running.
    """

    def __init__(self):
        self._config: Optional[SlaveConfig] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None

        # Register storage (flat lists, index = address)
        self._coils:      List[bool] = [False] * MAX_COILS
        self._discrete:   List[bool] = [False] * MAX_DISCRETE
        self._holding:    List[int]  = [0] * MAX_HOLDING
        self._input_regs: List[int]  = [0] * MAX_INPUT

        # Simulate mode — auto-updates certain registers
        self._simulate = False
        self._sim_thread: Optional[threading.Thread] = None
        self._sim_stop = threading.Event()

        # Access counter (how many times each holding reg was read/written)
        self._access_count: Dict[int, int] = {}

        # Callbacks
        self.on_started: Optional[Callable] = None
        self.on_stopped: Optional[Callable] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_register_changed: Optional[Callable[[str, int, object], None]] = None

    # ── Start / Stop ─────────────────────────────────────────────────────────

    def start(self, config: SlaveConfig) -> Tuple[bool, str]:
        """Start the Modbus slave server."""
        if self._running:
            return False, "Server already running"

        self._config = config

        try:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="modbus-slave",
            )
            self._thread.start()
            # Give it a moment to start up
            time.sleep(0.5)
            if self._running:
                logger.info(f"Modbus slave started: {self._describe()}")
                if self.on_started:
                    self.on_started()
                return True, f"Slave server running on {self._describe()}"
            else:
                return False, "Server failed to start — check settings and port availability"
        except Exception as e:
            msg = f"Failed to start slave: {e}"
            logger.error(msg)
            return False, msg

    def stop(self):
        """Stop the Modbus slave server."""
        self.stop_simulation()

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        self._running = False
        self._loop = None
        self._thread = None
        self._server = None

        logger.info("Modbus slave stopped")
        if self.on_stopped:
            self.on_stopped()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Register Access ───────────────────────────────────────────────────────

    def get_holding_register(self, address: int) -> int:
        if 0 <= address < MAX_HOLDING:
            return self._holding[address]
        return 0

    def set_holding_register(self, address: int, value: int):
        if 0 <= address < MAX_HOLDING:
            value = max(0, min(65535, int(value)))
            self._holding[address] = value
            self._update_datastore_holding(address, value)
            if self.on_register_changed:
                self.on_register_changed("holding", address, value)

    def get_input_register(self, address: int) -> int:
        if 0 <= address < MAX_INPUT:
            return self._input_regs[address]
        return 0

    def set_input_register(self, address: int, value: int):
        if 0 <= address < MAX_INPUT:
            value = max(0, min(65535, int(value)))
            self._input_regs[address] = value
            self._update_datastore_input(address, value)
            if self.on_register_changed:
                self.on_register_changed("input", address, value)

    def get_coil(self, address: int) -> bool:
        if 0 <= address < MAX_COILS:
            return self._coils[address]
        return False

    def set_coil(self, address: int, value: bool):
        if 0 <= address < MAX_COILS:
            self._coils[address] = bool(value)
            self._update_datastore_coil(address, value)
            if self.on_register_changed:
                self.on_register_changed("coil", address, value)

    def get_discrete(self, address: int) -> bool:
        if 0 <= address < MAX_DISCRETE:
            return self._discrete[address]
        return False

    def set_discrete(self, address: int, value: bool):
        if 0 <= address < MAX_DISCRETE:
            self._discrete[address] = bool(value)
            self._update_datastore_discrete(address, value)

    def get_holding_block(self, start: int, count: int) -> List[int]:
        end = min(start + count, MAX_HOLDING)
        return self._holding[start:end]

    def set_holding_block(self, start: int, values: List[int]):
        for i, v in enumerate(values):
            addr = start + i
            if addr < MAX_HOLDING:
                self._holding[addr] = max(0, min(65535, int(v)))

    # ── Simulation Mode ───────────────────────────────────────────────────────

    def start_simulation(self):
        """
        Auto-vary several holding registers and input registers to simulate
        a live device — useful for testing master tools.
        """
        if self._simulate:
            return
        self._simulate = True
        self._sim_stop.clear()
        self._sim_thread = threading.Thread(
            target=self._sim_loop, daemon=True, name="modbus-sim"
        )
        self._sim_thread.start()
        logger.info("Simulation mode started")

    def stop_simulation(self):
        if self._simulate:
            self._simulate = False
            self._sim_stop.set()
            if self._sim_thread and self._sim_thread.is_alive():
                self._sim_thread.join(timeout=2.0)
            self._sim_stop.clear()

    def _sim_loop(self):
        """Continuously update simulated registers with realistic values."""
        import math
        t = 0.0
        while not self._sim_stop.wait(0.2):
            t += 0.2
            # Sine wave on HR0 (0–1000)
            hr0 = int(500 + 500 * math.sin(t * 0.5))
            self.set_holding_register(0, hr0)

            # Ramp on HR1 (0–65535 over 30 seconds)
            hr1 = int((t % 30) / 30 * 65535)
            self.set_holding_register(1, hr1)

            # Toggle coil 0 every 2 seconds
            if int(t) % 2 == 0:
                self.set_coil(0, True)
            else:
                self.set_coil(0, False)

            # Random-ish on IR0 (temperature simulation 200–800 = 20.0–80.0°C * 10)
            import random
            ir0 = int(self._input_regs[0] + random.randint(-5, 5))
            ir0 = max(200, min(800, ir0))
            self.set_input_register(0, ir0)

            # Counter on HR2
            self.set_holding_register(2, (self._holding[2] + 1) & 0xFFFF)

    # ── Internal Server ───────────────────────────────────────────────────────

    def _run_loop(self):
        """Entry point for the background server thread."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            logger.error(f"Slave server error: {e}")
            if self.on_error:
                self.on_error(str(e))
        finally:
            self._running = False

    async def _serve(self):
        """Start the pymodbus async server."""
        try:
            from pymodbus.datastore import (
                ModbusSequentialDataBlock,
                ModbusDeviceContext,
                ModbusServerContext,
            )

            co = ModbusSequentialDataBlock(0, [int(v) for v in self._coils])
            di = ModbusSequentialDataBlock(0, [int(v) for v in self._discrete])
            hr = ModbusSequentialDataBlock(0, list(self._holding))
            ir = ModbusSequentialDataBlock(0, list(self._input_regs))

            store = ModbusDeviceContext(co=co, di=di, hr=hr, ir=ir)
            context = ModbusServerContext(devices=store, single=True)

            # Save context reference for live updates
            self._context = context
            self._store = store

            self._running = True

            if self._config.mode == SlaveMode.TCP:
                from pymodbus.server import StartAsyncTcpServer
                await StartAsyncTcpServer(
                    context=context,
                    address=(self._config.host, self._config.port),
                )
            else:
                from pymodbus.server import StartAsyncSerialServer
                await StartAsyncSerialServer(
                    context=context,
                    port=self._config.serial_port,
                    baudrate=self._config.baudrate,
                    parity=self._config.parity,
                    stopbits=self._config.stopbits,
                    bytesize=self._config.bytesize,
                )
        except Exception as e:
            self._running = False
            logger.error(f"Server async error: {e}")
            if self.on_error:
                self.on_error(f"Server error: {e}")

    def _update_datastore_holding(self, address: int, value: int):
        """Push a live value change into the pymodbus data store."""
        try:
            if hasattr(self, '_store') and self._store:
                # pymodbus datastore uses 1-based addressing internally for some FCs
                self._store.setValues(3, address + 1, [value])
        except Exception:
            pass  # Store may not be ready yet

    def _update_datastore_input(self, address: int, value: int):
        try:
            if hasattr(self, '_store') and self._store:
                self._store.setValues(4, address + 1, [value])
        except Exception:
            pass

    def _update_datastore_coil(self, address: int, value: bool):
        try:
            if hasattr(self, '_store') and self._store:
                self._store.setValues(1, address + 1, [value])
        except Exception:
            pass

    def _update_datastore_discrete(self, address: int, value: bool):
        try:
            if hasattr(self, '_store') and self._store:
                self._store.setValues(2, address + 1, [value])
        except Exception:
            pass

    def _describe(self) -> str:
        if not self._config:
            return "unknown"
        if self._config.mode == SlaveMode.TCP:
            return f"{self._config.host}:{self._config.port} (Slave ID {self._config.slave_id})"
        else:
            return f"{self._config.serial_port} @ {self._config.baudrate} baud"
