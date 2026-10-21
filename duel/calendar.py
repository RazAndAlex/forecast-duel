"""Trading calendar for forecast targets: each asset's exchange sessions, every day for crypto."""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

import exchange_calendars as xcals
import pandas as pd

from .assets import Asset

# Manual override: extra closure days that the exchange_calendars package does not know yet.
EXTRA_CLOSED: set[dt.date] = set()


@lru_cache(maxsize=None)
def _cal(code: str):
    return xcals.get_calendar(code)


def is_open(d: dt.date, exchange: str) -> bool:
    return d not in EXTRA_CLOSED and _cal(exchange).is_session(pd.Timestamp(d))


def target_dates(made_on: str, asset: Asset) -> list[str]:
    """Next 5 sessions of the asset's exchange, or the next 5 calendar days for crypto."""
    d = dt.date.fromisoformat(made_on)
    out = []
    while len(out) < 5:
        d += dt.timedelta(days=1)
        if asset.kind == "crypto" or is_open(d, asset.exchange):
            out.append(d.isoformat())
    return out
