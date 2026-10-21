from duel.score import direction_hit, mape, matured, next_bars
from duel.store import append, load

BARS = ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"]


def test_mape_known_values():
    assert mape([100, 100], [100, 50]) == 50.0  # 0% and 100% over two steps
    assert mape([110, 90], [100, 100]) == 10.0


def test_direction_hit_counts_zero_as_up():
    assert direction_hit([100, 100, 100, 100, 100], [101, 102, 103, 104, 105], 100)  # flat = up, actual up
    assert direction_hit([99, 98, 97, 96, 95], [101, 100, 99, 98, 97], 100)  # both down
    assert not direction_hit([99, 98, 97, 96, 95], [101, 102, 103, 104, 105], 100)  # disagree


def test_maturity_needs_five_later_bars():
    assert next_bars(BARS[:3], "2026-10-01") == ["2026-10-02", "2026-10-05"]
    assert next_bars(BARS, "2026-10-01") == BARS[1:6]
    assert matured(next_bars(BARS, "2026-10-01"))
    assert not matured(next_bars(BARS, "2026-10-02"))  # only 4 later bars
    assert not matured(next_bars(BARS, "2026-10-05"))
    assert next_bars(BARS, "2026-10-08") == []  # nothing after the last bar


def test_append_is_idempotent(tmp_path):
    path = tmp_path / "forecasts.jsonl"
    row = {"made_on": "2026-10-01", "ticker": "ENI.MI", "model": "naive",
           "values": [10.0] * 5, "q10": None, "q90": None, "dates": BARS[1:6], "live": True}
    assert append([row], path) == 1
    assert append([row], path) == 0  # same (made_on, ticker, model) skipped
    other = dict(row, model="kronos")
    assert append([other], path) == 1  # a different model still lands
    assert len(load(path)) == 2


def test_bar_completeness_rule():
    import datetime as dt
    from duel.fetch import is_complete
    utc = dt.timezone.utc
    d = dt.date(2026, 10, 21)
    assert is_complete(dt.date(2026, 10, 20), "stock", dt.datetime(2026, 10, 21, 6, 0, tzinfo=utc))
    assert not is_complete(d, "stock", dt.datetime(2026, 10, 21, 15, 44, tzinfo=utc))  # 17:44 Rome
    assert is_complete(d, "stock", dt.datetime(2026, 10, 21, 15, 45, tzinfo=utc))  # 17:45 Rome
    assert not is_complete(d, "crypto", dt.datetime(2026, 10, 21, 23, 0, tzinfo=utc))
    assert is_complete(dt.date(2026, 10, 20), "crypto", dt.datetime(2026, 10, 21, 0, 1, tzinfo=utc))


def test_stock_targets_skip_borsa_holidays():
    from duel.calendar import target_dates
    assert target_dates("2025-12-24", "stock") == ["2025-12-29", "2025-12-30", "2026-01-02", "2026-01-05", "2026-01-06"]
    assert target_dates("2026-04-02", "stock")[:2] == ["2026-04-07", "2026-04-08"]  # Good Friday, Easter Monday
    assert target_dates("2025-12-24", "crypto")[0] == "2025-12-25"


def test_scoring_needs_real_target_dates():
    from duel.report import _actual_after
    close_of = {"2025-12-24": 100.0, "2025-12-29": 101.0, "2025-12-30": 102.0, "2026-01-02": 103.0, "2026-01-05": 104.0}
    assert _actual_after(close_of, "2025-12-24", "stock") is None  # 6 Jan not in yet
    close_of["2026-01-06"] = 105.0
    assert _actual_after(close_of, "2025-12-24", "stock") == [101.0, 102.0, 103.0, 104.0, 105.0]


def test_csv_reload_keeps_floats(tmp_path, monkeypatch):
    import pandas as pd
    from duel import fetch
    monkeypatch.setattr(fetch, "PRICES_DIR", tmp_path)
    v = 3.9635000228881836
    df = pd.DataFrame({c: [v] for c in ["open", "high", "low", "close", "volume"]},
                      index=pd.DatetimeIndex(["2026-09-24"]))
    df.to_csv(tmp_path / "X.csv")
    assert fetch.load_cached("X")["close"].iloc[0] == v


def test_hourly_fallback_rejects_partial_day(monkeypatch):
    import datetime as dt
    import pandas as pd
    from duel import fetch
    base = pd.DataFrame({c: [100.0] * 12 for c in ["open", "high", "low", "close", "volume"]},
                        index=pd.bdate_range(end="2026-10-20", periods=12))

    real = fetch.is_complete

    def run(hours):
        idx = pd.DatetimeIndex([f"2026-10-21T{h:02d}:00:00+02:00" for h in hours])
        h = pd.DataFrame({"Open": 110.0, "High": 112.0, "Low": 109.0, "Close": 111.0, "Volume": 10.0}, index=idx)
        late = dt.datetime(2026, 10, 22, 0, 30, tzinfo=dt.timezone.utc)
        monkeypatch.setattr(fetch.yf, "download", lambda *a, **k: h)
        monkeypatch.setattr(fetch, "is_complete", lambda d, k: real(d, k, late))
        return fetch._fill_from_hourly("ENI.MI", base.copy())

    assert len(run([9, 10])) == len(base)  # morning-only feed at 00:30 UTC: skipped
    assert len(run([9, 10, 17])) == len(base) + 1  # last candle 17:00: session complete
