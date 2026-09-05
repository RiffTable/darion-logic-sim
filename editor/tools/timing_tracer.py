"""
TimingTracer  ─  lightweight, non-invasive signal recorder
===========================================================
Works as a *twin* of task_manager: it does NOT modify the
simulation engine but instead provides a minimal hook that
any module can call to record signal events.

Data model for one signal:
    {
        "name"       : str,
        "is_clock"   : bool,       # inputlimit == 0 → clock
        "events"     : [(time: int, value: int), ...]
    }

The UI layer calls:
    tracer.record(gate)           # after every complete_task call
    tracer.clear()                # when the user wants a fresh capture
    tracer.snapshot() → dict      # get current trace for rendering
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Gates import Gate

# ── Signal types we care about ────────────────────────────────────────────────
try:
    from Const import VARIABLE_ID, BUFFER_ID, HIGH, LOW, UNKNOWN
except ImportError:          # fallback when imported from outside `engine/`
    VARIABLE_ID = 6
    BUFFER_ID    = 8
    HIGH        = 1
    LOW         = 0
    UNKNOWN     = 2


class _Signal:
    """One signal track inside the tracer."""
    __slots__ = ["name", "is_clock", "events", "_last_value"]

    def __init__(self, name: str, is_clock: bool):
        self.name       = name
        self.is_clock   = is_clock
        self.events: list[tuple[int, int]] = []   # (Global_Clock, value)
        self._last_value: int = -999               # sentinel "never recorded"

    def push(self, time: int, value: int):
        """Only store a transition (deduplicate consecutive same-value edges)."""
        if value != self._last_value:
            self.events.append((time, value))
            self._last_value = value

    def reset(self):
        self.events.clear()
        self._last_value = -999


class TimingTracer:
    """
    Singleton-friendly recorder.  Create one instance and pass it around.

    Usage in the engine glue layer (canvas.py or Circuit.py patch):

        tracer = TimingTracer()
        # after complete_task():
        tracer.record(gate, Global_Clock)
    """

    def __init__(self):
        # Ordered dict so signals appear in the order they were first seen
        self._signals: dict[int, _Signal] = {}   # gate.location → _Signal
        self.recording: bool = False
        self.start_time: int = 0

    # ── Control ───────────────────────────────────────────────────────────────

    def start(self, current_time: int = 0):
        """Begin (or restart) a capture session."""
        self.clear()
        self.recording  = True
        self.start_time = current_time

    def stop(self):
        self.recording = False

    def clear(self):
        self._signals.clear()
        self.recording  = False
        self.start_time = 0

    # ── Recording ─────────────────────────────────────────────────────────────

    def record(self, gate: "Gate", global_clock: int):
        """
        Call this after every complete_task() for any gate whose output may
        have changed.  The gate must be a Variable/Clock (VARIABLE_ID) or
        Probe (BUFFER_ID) to be captured.

        NOTE: the recording guard (self.recording check) is intentionally
        performed by the caller (Circuit.complete_task) before this method
        is invoked, so this method does not short-circuit on recording=False.
        """
        gate_id = gate.id
        if gate_id not in (VARIABLE_ID, BUFFER_ID):
            return

        loc      = gate.location
        is_clock = (gate.inputlimit == 0)
        name     = gate.custom_name if gate.custom_name else gate.codename
        value    = gate.output

        if loc not in self._signals:
            self._signals[loc] = _Signal(name, is_clock)

        sig = self._signals[loc]
        sig.name     = name      # pick up renames dynamically
        sig.is_clock = is_clock
        sig.push(global_clock - self.start_time, value)

    # ── Query ─────────────────────────────────────────────────────────────────

    def snapshot(self) -> list[dict]:
        """
        Return an ordered list of signal dicts, each:
            {
                "name"     : str,
                "is_clock" : bool,
                "events"   : [(rel_time: int, value: int), ...]
            }
        Clocks come first (sorted by location), then probes.
        """
        clocks = []
        probes = []
        for sig in self._signals.values():
            entry = {
                "name"    : sig.name,
                "is_clock": sig.is_clock,
                "events"  : list(sig.events),
            }
            (clocks if sig.is_clock else probes).append(entry)

        return clocks + probes

    def has_data(self) -> bool:
        return any(len(s.events) > 0 for s in self._signals.values())

    def max_time(self) -> int:
        """Return the latest recorded timestamp (relative)."""
        t = 0
        for sig in self._signals.values():
            if sig.events:
                t = max(t, sig.events[-1][0])
        return t


# ── Module-level singleton ────────────────────────────────────────────────────
tracer = TimingTracer()
