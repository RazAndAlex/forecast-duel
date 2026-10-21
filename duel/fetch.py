"""Fetch daily OHLCV bars and cache them to data/prices/<ticker>.csv."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from .assets import Asset

ROOT = Path(__file__).resolve().parent.parent
PRICES_DIR = ROOT / "data" / "prices"


# exchange -> (timezone, close, first hour of the last hourly candle). Yahoo's hourly index is
# already in exchange-local time, and the last candle of a full session starts at that hour.
EXCHANGES = {
    "XNYS": ("America/New_York", dt.time(16, 0), 15),
    "XETR": ("Europe/Berlin", dt.time(17, 30), 17),
    "XMIL": ("Europe/Rome", dt.time(17, 30), 17),
}
SETTLE = dt.timedelta(minutes=15)


def is_complete(day: dt.date, asset: Asset, now: dt.datetime | None = None) -> bool:
    """Stocks: complete before today (exchange time), or today 15 min after the close. Crypto: before today (UTC)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if asset.kind == "crypto":
        return day < now.astimezone(ZoneInfo("UTC")).date()
    tz, close, _ = EXCHANGES[asset.exchange]
    local = now.astimezone(ZoneInfo(tz))
    cutoff = (dt.datetime.combine(day, close) + SETTLE).time()
    return day < local.date() or (day == local.date() and local.time() >= cutoff)


def _fill_from_hourly(asset: Asset, df: pd.DataFrame) -> pd.DataFrame:
    """Yahoo's daily feed sometimes skips a session that its hourly feed has; rebuild it."""
    h = yf.download(asset.ticker, period="10d", interval="1h", auto_adjust=True, progress=False)
    if h is None or h.empty:
        return df
    if isinstance(h.columns, pd.MultiIndex):
        h.columns = h.columns.get_level_values(0)
    h = h.rename(columns=str.lower)
    ts = pd.to_datetime(h.index).tz_localize(None)  # drops the tz, keeps exchange wall time
    h.index = ts.normalize()
    # A complete day has an hourly candle starting at the exchange's last-candle hour or later.
    closed = pd.Series(ts.hour, index=h.index).groupby(level=0).max() >= EXCHANGES[asset.exchange][2]
    agg = h.groupby(level=0).agg(open=("open", "first"), high=("high", "max"),
                                 low=("low", "min"), close=("close", "last"), volume=("volume", "sum"))
    missing = agg[~agg.index.isin(df.index) & (agg.index > df.index[-10])]
    missing = missing[[is_complete(d.date(), asset) and closed[d] for d in missing.index]]
    return pd.concat([df, missing]).sort_index() if len(missing) else df


def fetch(asset: Asset) -> pd.DataFrame:
    """~600 trading days of adjusted daily bars, today's incomplete bar dropped."""
    PRICES_DIR.mkdir(parents=True, exist_ok=True)
    ticker = asset.ticker
    start = (dt.date.today() - dt.timedelta(days=920)).isoformat()
    df = yf.download(ticker, start=start, interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"no bars returned for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    if asset.kind != "crypto":
        df = _fill_from_hourly(asset, df)
    df = df[[is_complete(d.date(), asset) for d in df.index]]
    df.to_csv(PRICES_DIR / f"{ticker}.csv")
    return df


def load_cached(ticker: str) -> pd.DataFrame:
    df = pd.read_csv(PRICES_DIR / f"{ticker}.csv", index_col=0, parse_dates=True,
                     float_precision="round_trip")
    return df[["open", "high", "low", "close", "volume"]]
