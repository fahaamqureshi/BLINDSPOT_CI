from __future__ import annotations

import threading
from dataclasses import dataclass, field
from math import isfinite


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class BudgetGuard:
    max_calls: int
    max_cost_usd: float
    calls: int = 0
    cost_usd: float = 0.0
    parent: BudgetGuard | None = field(default=None, repr=False, compare=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.max_calls < 0 or not isfinite(self.max_cost_usd) or self.max_cost_usd < 0:
            raise ValueError("budget limits must be finite and nonnegative")

    def reserve(self, estimated_cost_usd: float) -> None:
        if not isfinite(estimated_cost_usd) or estimated_cost_usd < 0:
            raise ValueError("reservation must be finite and nonnegative")
        with self._lock:
            if self.calls + 1 > self.max_calls:
                raise BudgetExceeded(f"call limit reached ({self.max_calls})")
            if self.cost_usd + estimated_cost_usd > self.max_cost_usd + 1e-9:
                raise BudgetExceeded(f"USD budget would exceed ${self.max_cost_usd:.2f}")
            if self.parent is not None:
                self.parent.reserve(estimated_cost_usd)
            self.calls += 1
            self.cost_usd += estimated_cost_usd

    def charge(self, calls: int, cost_usd: float) -> None:
        """Add spend another guard already made (an experiment run) to this shared cap."""
        with self._lock:
            self.calls += calls
            self.cost_usd += cost_usd

    def release_cost(self, cost_usd: float) -> None:
        """Release a reservation refused before processing while retaining its call count."""
        with self._lock:
            if not isfinite(cost_usd) or cost_usd < 0:
                raise ValueError("refund must be finite and nonnegative")
            released = min(self.cost_usd, cost_usd)
            self.cost_usd -= released
            if self.parent is not None:
                self.parent.release_cost(released)

    def exhausted(self) -> bool:
        with self._lock:
            return self.calls >= self.max_calls or self.cost_usd >= self.max_cost_usd - 1e-9
