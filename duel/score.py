"""Scoring rules for matured forecasts. Pure functions, no I/O."""
from __future__ import annotations

import math


def sign_up(x: float) -> int:
    """Sign of a move, with 0 counted as up."""
    return 1 if x >= 0 else -1


def mape(pred: list[float], actual: list[float]) -> float:
    """Mean absolute percentage error over the 5 steps, in percent."""
    return sum(abs(p - a) / abs(a) for p, a in zip(pred, actual)) / len(actual) * 100


def direction_hit(pred: list[float], actual: list[float], last_close: float) -> bool:
    """Forecast and reality move the same way over the 5-step horizon."""
    return sign_up(pred[-1] - last_close) == sign_up(actual[-1] - last_close)


def next_bars(bars: list[str], made_on: str, k: int = 5) -> list[str]:
    """The first k bar dates strictly after made_on."""
    return [b for b in bars if b > made_on][:k]


def matured(next_actual: list[float]) -> bool:
    """A forecast can be scored once 5 later bars exist."""
    return len(next_actual) >= 5


def luck_p(n: int, hits: int) -> float | None:
    """Chance of at least `hits` right calls out of n by fair coin flips (one-sided binomial)."""
    if n == 0:
        return None
    return sum(math.comb(n, k) for k in range(hits, n + 1)) / 2**n
