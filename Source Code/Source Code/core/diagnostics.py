"""
SAS Modbus Toolkit — Network Diagnostics Engine
Tracks communication quality, analyzes error patterns, and generates
actionable recommendations for troubleshooting Modbus networks.
"""

import logging
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Severity(Enum):
    PASS = "PASS"
    INFO = "INFO"
    WARN = "WARNING"
    FAIL = "FAIL"


@dataclass
class DiagnosticFinding:
    """A single diagnostic observation."""
    severity: Severity
    category: str
    title: str
    detail: str
    recommendation: str = ""


@dataclass
class ResponseSample:
    """One request/response timing sample."""
    timestamp: float
    slave_id: int
    function_code: int
    response_ms: float
    is_error: bool
    is_timeout: bool
    error_type: str = ""  # "crc", "timeout", "exception", "invalid"


class NetworkHealthMonitor:
    """
    Continuously monitors Modbus transaction health and produces
    diagnostic reports with scored health indicators.

    Feed samples via record_transaction() from the master engine callbacks.
    """

    WINDOW_SIZE = 200  # Rolling window of samples for analysis

    def __init__(self):
        self._samples: deque = deque(maxlen=self.WINDOW_SIZE)
        self._slave_stats: Dict[int, List[ResponseSample]] = {}
        self._start_time = time.monotonic()
        self._total_transactions = 0
        self._total_errors = 0
        self._total_timeouts = 0
        self._crc_errors = 0
        self._exception_codes: Dict[int, int] = {}  # exception code -> count

    def record_transaction(self, slave_id: int, function_code: int,
                            response_ms: float, is_error: bool,
                            is_timeout: bool = False, error_type: str = "",
                            exception_code: Optional[int] = None):
        """Record a completed Modbus transaction for analysis."""
        sample = ResponseSample(
            timestamp=time.monotonic(),
            slave_id=slave_id,
            function_code=function_code,
            response_ms=response_ms,
            is_error=is_error,
            is_timeout=is_timeout,
            error_type=error_type,
        )
        self._samples.append(sample)

        self._total_transactions += 1
        if is_error:
            self._total_errors += 1
        if is_timeout:
            self._total_timeouts += 1
        if error_type == "crc":
            self._crc_errors += 1
        if exception_code is not None:
            self._exception_codes[exception_code] = \
                self._exception_codes.get(exception_code, 0) + 1

        if slave_id not in self._slave_stats:
            self._slave_stats[slave_id] = []
        self._slave_stats[slave_id].append(sample)
        # Keep per-slave history bounded
        if len(self._slave_stats[slave_id]) > 100:
            self._slave_stats[slave_id].pop(0)

    def reset(self):
        """Clear all recorded data."""
        self._samples.clear()
        self._slave_stats.clear()
        self._start_time = time.monotonic()
        self._total_transactions = 0
        self._total_errors = 0
        self._total_timeouts = 0
        self._crc_errors = 0
        self._exception_codes.clear()

    # ── Statistics ────────────────────────────────────────────────────────────

    @property
    def total_transactions(self) -> int:
        return self._total_transactions

    @property
    def error_count(self) -> int:
        return self._total_errors

    @property
    def timeout_count(self) -> int:
        return self._total_timeouts

    @property
    def error_rate_pct(self) -> float:
        if self._total_transactions == 0:
            return 0.0
        return (self._total_errors / self._total_transactions) * 100

    @property
    def success_rate_pct(self) -> float:
        return 100.0 - self.error_rate_pct

    def get_response_times(self) -> List[float]:
        """Return response times from successful samples in the rolling window."""
        return [s.response_ms for s in self._samples if not s.is_error]

    @property
    def avg_response_ms(self) -> float:
        times = self.get_response_times()
        return statistics.mean(times) if times else 0.0

    @property
    def max_response_ms(self) -> float:
        times = self.get_response_times()
        return max(times) if times else 0.0

    @property
    def min_response_ms(self) -> float:
        times = self.get_response_times()
        return min(times) if times else 0.0

    @property
    def jitter_ms(self) -> float:
        """Response time standard deviation — high jitter indicates noise."""
        times = self.get_response_times()
        return statistics.stdev(times) if len(times) >= 2 else 0.0

    def get_slave_stats(self, slave_id: int) -> Dict:
        """Get per-slave statistics."""
        samples = self._slave_stats.get(slave_id, [])
        if not samples:
            return {"count": 0, "errors": 0, "avg_ms": 0.0, "health": 0}
        errors = sum(1 for s in samples if s.is_error)
        times = [s.response_ms for s in samples if not s.is_error]
        return {
            "count": len(samples),
            "errors": errors,
            "error_rate": (errors / len(samples) * 100) if samples else 0,
            "avg_ms": statistics.mean(times) if times else 0.0,
            "max_ms": max(times) if times else 0.0,
            "health": self._calc_slave_health(samples),
        }

    # ── Health Scoring ────────────────────────────────────────────────────────

    def compute_overall_health(self) -> int:
        """
        Compute an overall network health score from 0 to 100.
        
        Scoring breakdown:
          - 50 pts: Error rate  (0% = 50pts, 5% = 25pts, >20% = 0pts)
          - 30 pts: Response time (< 50ms = 30pts, 50-200ms = 20pts, >500ms = 0pts)
          - 20 pts: Jitter      (< 10ms = 20pts, 10-50ms = 10pts, >100ms = 0pts)
        """
        if self._total_transactions < 3:
            return 0  # Not enough data

        # Error rate score
        err_rate = self.error_rate_pct
        if err_rate == 0:
            err_score = 50
        elif err_rate <= 1:
            err_score = 45
        elif err_rate <= 5:
            err_score = 30
        elif err_rate <= 10:
            err_score = 15
        elif err_rate <= 20:
            err_score = 5
        else:
            err_score = 0

        # Response time score
        avg_ms = self.avg_response_ms
        if avg_ms == 0:
            rt_score = 30
        elif avg_ms < 50:
            rt_score = 30
        elif avg_ms < 100:
            rt_score = 25
        elif avg_ms < 200:
            rt_score = 18
        elif avg_ms < 500:
            rt_score = 10
        elif avg_ms < 1000:
            rt_score = 5
        else:
            rt_score = 0

        # Jitter score
        jitter = self.jitter_ms
        if jitter == 0:
            jit_score = 20
        elif jitter < 10:
            jit_score = 20
        elif jitter < 25:
            jit_score = 15
        elif jitter < 50:
            jit_score = 10
        elif jitter < 100:
            jit_score = 5
        else:
            jit_score = 0

        return min(100, err_score + rt_score + jit_score)

    def _calc_slave_health(self, samples: List[ResponseSample]) -> int:
        if not samples:
            return 0
        errors = sum(1 for s in samples if s.is_error)
        err_pct = errors / len(samples) * 100
        if err_pct == 0:
            return 100
        elif err_pct < 5:
            return 80
        elif err_pct < 10:
            return 60
        elif err_pct < 25:
            return 40
        else:
            return 20

    # ── Diagnostics Report ────────────────────────────────────────────────────

    def generate_findings(self) -> List[DiagnosticFinding]:
        """
        Analyze all collected data and return a list of diagnostic findings
        with severity levels and actionable recommendations.
        """
        findings = []

        if self._total_transactions < 5:
            findings.append(DiagnosticFinding(
                severity=Severity.INFO,
                category="Data",
                title="Insufficient Data",
                detail="Not enough transactions recorded for a meaningful analysis. "
                       "Run polling for at least 30 seconds.",
                recommendation="Start polling and wait for at least 20-30 transactions.",
            ))
            return findings

        # ── Error Rate ──
        err_rate = self.error_rate_pct
        if err_rate == 0:
            findings.append(DiagnosticFinding(
                severity=Severity.PASS,
                category="Errors",
                title="No Communication Errors",
                detail=f"0 errors in {self._total_transactions} transactions.",
            ))
        elif err_rate < 2:
            findings.append(DiagnosticFinding(
                severity=Severity.WARN,
                category="Errors",
                title="Minor Error Rate",
                detail=f"{err_rate:.1f}% error rate ({self._total_errors}/{self._total_transactions} transactions).",
                recommendation="Monitor over a longer period. Could be noise or an intermittent connection.",
            ))
        elif err_rate < 10:
            findings.append(DiagnosticFinding(
                severity=Severity.WARN,
                category="Errors",
                title="Elevated Error Rate",
                detail=f"{err_rate:.1f}% error rate ({self._total_errors}/{self._total_transactions} transactions).",
                recommendation="Check cable quality, termination resistors, and ground connections. "
                               "Verify baud rate and parity match all devices on the bus.",
            ))
        else:
            findings.append(DiagnosticFinding(
                severity=Severity.FAIL,
                category="Errors",
                title="High Error Rate",
                detail=f"{err_rate:.1f}% error rate — communication is unreliable.",
                recommendation="Verify wiring: check for shorts, open circuits, improper termination. "
                               "Ensure only ONE 120Ω terminator at each end of an RS-485 bus. "
                               "Check for ground loops. Verify all devices use the same baud rate.",
            ))

        # ── Timeouts ──
        if self._total_timeouts > 0:
            to_pct = (self._total_timeouts / self._total_transactions) * 100
            if to_pct > 5:
                findings.append(DiagnosticFinding(
                    severity=Severity.FAIL,
                    category="Timeouts",
                    title="Frequent Timeouts",
                    detail=f"{self._total_timeouts} timeouts ({to_pct:.1f}% of transactions).",
                    recommendation="Check if slave devices are powered and on the network. "
                                   "Increase the timeout setting. For RTU, verify the correct "
                                   "COM port, baud rate, and slave ID. Ensure no address conflicts.",
                ))
            elif to_pct > 0:
                findings.append(DiagnosticFinding(
                    severity=Severity.WARN,
                    category="Timeouts",
                    title="Occasional Timeouts",
                    detail=f"{self._total_timeouts} timeouts detected.",
                    recommendation="Could indicate marginal cable, grounding issue, or overloaded device. "
                                   "Try increasing the timeout value by 50%.",
                ))

        # ── Response Time ──
        avg_ms = self.avg_response_ms
        max_ms = self.max_response_ms
        if avg_ms > 0:
            if avg_ms < 50:
                findings.append(DiagnosticFinding(
                    severity=Severity.PASS,
                    category="Performance",
                    title="Excellent Response Times",
                    detail=f"Avg: {avg_ms:.1f}ms  Max: {max_ms:.1f}ms",
                ))
            elif avg_ms < 150:
                findings.append(DiagnosticFinding(
                    severity=Severity.PASS,
                    category="Performance",
                    title="Good Response Times",
                    detail=f"Avg: {avg_ms:.1f}ms  Max: {max_ms:.1f}ms",
                ))
            elif avg_ms < 500:
                findings.append(DiagnosticFinding(
                    severity=Severity.WARN,
                    category="Performance",
                    title="Slow Response Times",
                    detail=f"Avg: {avg_ms:.1f}ms — may affect application performance.",
                    recommendation="Check bus load (too many devices or too much data per scan). "
                                   "Reduce polling rate or read fewer registers per request. "
                                   "For RTU, increase baud rate if all devices support it.",
                ))
            else:
                findings.append(DiagnosticFinding(
                    severity=Severity.FAIL,
                    category="Performance",
                    title="Very Slow Response Times",
                    detail=f"Avg: {avg_ms:.1f}ms — significantly above acceptable range.",
                    recommendation="Device may be overloaded or bus traffic is too high. "
                                   "Check cable length (RTU RS-485 max ~1200m at 9600 baud). "
                                   "Consider reducing the number of registers per poll request.",
                ))

        # ── Jitter / Noise ──
        jitter = self.jitter_ms
        if len(self.get_response_times()) >= 5:
            if jitter > 50:
                findings.append(DiagnosticFinding(
                    severity=Severity.WARN,
                    category="Signal Quality",
                    title="High Response Time Jitter",
                    detail=f"Jitter (std dev): {jitter:.1f}ms — inconsistent response times suggest noise or interference.",
                    recommendation="For RTU: check shield grounding, routing near power cables, "
                                   "or EMI sources (VFDs, large motors). "
                                   "Ensure proper RS-485 bias resistors are installed if the bus is idle between scans. "
                                   "For TCP: check for network congestion or switch issues.",
                ))
            elif jitter > 20:
                findings.append(DiagnosticFinding(
                    severity=Severity.INFO,
                    category="Signal Quality",
                    title="Moderate Response Time Jitter",
                    detail=f"Jitter: {jitter:.1f}ms — some variability but within acceptable range.",
                ))

        # ── CRC Errors ──
        if self._crc_errors > 0:
            crc_pct = (self._crc_errors / self._total_transactions) * 100
            findings.append(DiagnosticFinding(
                severity=Severity.FAIL if crc_pct > 2 else Severity.WARN,
                category="Signal Quality",
                title="CRC Errors Detected",
                detail=f"{self._crc_errors} CRC errors ({crc_pct:.1f}%). "
                       "Data corruption on the wire.",
                recommendation="CRC errors typically mean electrical noise or signal integrity issues. "
                               "Check: cable quality (use shielded twisted pair), proper termination "
                               "(120Ω at each end), no stubs over 1 meter, ground shield at one end only, "
                               "routing away from high-voltage and power cables.",
            ))

        # ── Modbus Exception Codes ──
        for exc_code, count in self._exception_codes.items():
            exc_name, exc_meaning, exc_fix = _EXCEPTION_CODE_INFO.get(
                exc_code,
                (f"Code {exc_code}", "Unknown exception", "Consult device documentation.")
            )
            findings.append(DiagnosticFinding(
                severity=Severity.WARN,
                category="Exception Codes",
                title=f"Modbus Exception {exc_code}: {exc_name}",
                detail=f"{count} occurrence(s). {exc_meaning}",
                recommendation=exc_fix,
            ))

        return findings

    def get_response_time_history(self, max_points: int = 60) -> List[float]:
        """Return recent response times for charting."""
        times = [s.response_ms for s in self._samples if not s.is_error]
        if len(times) > max_points:
            times = times[-max_points:]
        return times

    def get_error_history(self, max_points: int = 60) -> List[int]:
        """Return binary error flags (0=ok, 1=error) for recent samples."""
        flags = [1 if s.is_error else 0 for s in self._samples]
        if len(flags) > max_points:
            flags = flags[-max_points:]
        return flags


# ── Modbus Exception Code Reference ──────────────────────────────────────────
_EXCEPTION_CODE_INFO = {
    1: ("Illegal Function",
        "The slave does not recognize or support the requested function code.",
        "Verify the function code is appropriate for this device. Check device manual."),
    2: ("Illegal Data Address",
        "The requested address is not in the slave's valid range.",
        "Verify the register address exists on this device. Check device manual for address map."),
    3: ("Illegal Data Value",
        "A value in the request is outside the allowed range.",
        "Check the value being written. Some registers have min/max limits."),
    4: ("Slave Device Failure",
        "An unrecoverable error occurred in the slave device.",
        "The slave device has an internal fault. Cycle power to the device and check for other fault indicators."),
    5: ("Acknowledge",
        "The slave accepted the request but needs more time to process it.",
        "Increase the master timeout value. The device is busy."),
    6: ("Slave Device Busy",
        "The slave is currently processing a long-duration request.",
        "Reduce polling rate. The device may be overloaded."),
    8: ("Memory Parity Error",
        "The slave detected a memory parity error.",
        "Hardware fault on the slave device. Contact device manufacturer."),
    10: ("Gateway Path Unavailable",
        "The gateway cannot establish communication with the target device.",
        "Check gateway configuration and slave connectivity."),
    11: ("Gateway Target Device Failed to Respond",
        "The target device on the other side of a gateway is not responding.",
        "Verify the target device is online and check gateway routing."),
}
