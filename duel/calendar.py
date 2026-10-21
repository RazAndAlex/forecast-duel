"""Trading calendar for forecast targets: Borsa Italiana sessions for stocks, every day for BTC."""
from __future__ import annotations

import datetime as dt

from dateutil.easter import easter  # ships with pandas

# Borsa Italiana closures that repeat every year (month, day).
# shortcut: fixed rules cover the regular calendar, not one-off closures; add them to EXTRA_CLOSED.
FIXED_CLOSED = {(1, 1), (5, 1), (8, 15), (12, 24), (12, 25), (12, 26), (12, 31)}
EXTRA_CLOSED: set[dt.date] = set()


def is_milan_open(d: dt.date) -> bool:
    if d.weekday() >= 5 or (d.month, d.day) in FIXED_CLOSED or d in EXTRA_CLOSED:
        return False
    e = easter(d.year)
    return d not in (e - dt.timedelta(days=2), e + dt.timedelta(days=1))  # Good Friday, Easter Monday


def target_dates(made_on: str, kind: str) -> list[str]:
    """Next 5 sessions: Milan trading days for stocks, calendar days for BTC."""
    d = dt.date.fromisoformat(made_on)
    out = []
    while len(out) < 5:
        d += dt.timedelta(days=1)
        if kind == "crypto" or is_milan_open(d):
            out.append(d.isoformat())
    return out
