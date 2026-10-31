"""How many cases does a claim need? Plain arithmetic, no model.

With zero failures in n independent cases, the 95 percent upper bound on the true failure rate is
about 3 / n (the rule of three, Hanley and Lippman-Hand 1983). Solving 1 - (1 - p) ** n >= confidence
gives the number of failure-free cases needed to claim a failure rate below p.
"""
from __future__ import annotations

import math


def cases_needed(max_failure_rate: float, confidence: float = 0.95) -> int:
    """Failure-free cases needed to say the failure rate is below max_failure_rate."""
    if not 0 < max_failure_rate < 1 or not 0 < confidence < 1:
        raise ValueError("rate and confidence must be between 0 and 1")
    return math.ceil(math.log(1 - confidence) / math.log(1 - max_failure_rate))


def upper_bound_no_failures(n: int, confidence: float = 0.95) -> float:
    """Exact upper bound on the failure rate after n failure-free cases."""
    if n <= 0:
        return 1.0
    return 1 - (1 - confidence) ** (1 / n)
