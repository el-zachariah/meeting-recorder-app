from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
import random
import time


@dataclass
class WaveformLevels:
    size: int = 48
    _values: deque[float] = field(default_factory=deque)

    def __post_init__(self) -> None:
        self._values = deque([0.0] * self.size, maxlen=self.size)

    def push(self, value: float) -> None:
        self._values.append(max(0.0, min(1.0, float(value))))

    def values(self) -> list[float]:
        return list(self._values)


def pseudo_level(t: float | None = None, index: int = 0) -> float:
    """Deterministic-looking fallback level for systems without live metering.

    This is intentionally local and cosmetic: it keeps the recording UI alive even
    when Pulse/PipeWire level probing is unavailable. It is not used to decide
    whether recording succeeds.
    """
    t = time.monotonic() if t is None else t
    base = math.sin(t * 3.1 + index * 0.73) * 0.5 + 0.5
    shimmer = math.sin(t * 7.7 + index * 1.31) * 0.18 + 0.18
    return max(0.04, min(0.95, base * 0.65 + shimmer))


class AudioLevelMonitor:
    """Best-effort audio level monitor placeholder.

    v0.3.0 keeps recording reliability decoupled from metering. Future versions can
    replace this with Pulse/PipeWire source RMS probing. Today it provides a smooth
    local animation and a clear status label instead of blocking release on Linux
    audio stack fragmentation.
    """

    def __init__(self, bars: int = 48) -> None:
        self.levels = WaveformLevels(size=bars)
        self.active = False
        self._rng = random.Random(42)

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False
        for _ in range(self.levels.size):
            self.levels.push(0.0)

    def tick(self) -> list[float]:
        if not self.active:
            self.levels.push(0.0)
            return self.levels.values()
        idx = len(self.levels.values())
        self.levels.push(pseudo_level(index=idx) * (0.92 + self._rng.random() * 0.08))
        return self.levels.values()
