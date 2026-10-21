from duel.assets import Asset
from duel.score import direction_hit, mape, matured, next_bars
from duel.store import append, load

MILAN = Asset("ENI.MI", "Eni", "Eni", "stock", "XMIL", "EUR")
NVDA = Asset("NVDA", "Nvidia", "Nvidia", "stock", "XNYS", "USD")
SIE = Asset("SIE.DE", "Siemens", "Siemens", "stock", "XETR", "EUR")
STM = Asset("STMMI.MI", "STMicroelectronics", "STMicro", "stock", "XMIL", "EUR")
BTC = Asset("BTC-USD", "Bitcoin", "Bitcoin", "crypto", "", "USD")

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
    assert is_complete(dt.date(2026, 10, 20), MILAN, dt.datetime(2026, 10, 21, 6, 0, tzinfo=utc))
    assert not is_complete(d, MILAN, dt.datetime(2026, 10, 21, 15, 44, tzinfo=utc))  # 17:44 Rome
    assert is_complete(d, MILAN, dt.datetime(2026, 10, 21, 15, 45, tzinfo=utc))  # 17:45 Rome
    assert not is_complete(d, BTC, dt.datetime(2026, 10, 21, 23, 0, tzinfo=utc))
    assert is_complete(dt.date(2026, 10, 20), BTC, dt.datetime(2026, 10, 21, 0, 1, tzinfo=utc))


def test_stock_targets_skip_borsa_holidays():
    from duel.calendar import target_dates
    assert target_dates("2025-12-24", MILAN) == ["2025-12-29", "2025-12-30", "2026-01-02", "2026-01-05", "2026-01-06"]
    assert target_dates("2026-04-02", MILAN)[:2] == ["2026-04-07", "2026-04-08"]  # Good Friday, Easter Monday
    assert target_dates("2025-12-24", BTC)[0] == "2025-12-25"


def test_scoring_needs_real_target_dates():
    from duel.report import _actual_after
    close_of = {"2025-12-24": 100.0, "2025-12-29": 101.0, "2025-12-30": 102.0, "2026-01-02": 103.0, "2026-01-05": 104.0}
    assert _actual_after(close_of, "2025-12-24", MILAN) is None  # 6 Jan not in yet
    close_of["2026-01-06"] = 105.0
    assert _actual_after(close_of, "2025-12-24", MILAN) == [101.0, 102.0, 103.0, 104.0, 105.0]


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
        monkeypatch.setattr(fetch, "is_complete", lambda d, a: real(d, a, late))
        return fetch._fill_from_hourly(MILAN, base.copy())

    assert len(run([9, 10])) == len(base)  # morning-only feed at 00:30 UTC: skipped
    assert len(run([9, 10, 17])) == len(base) + 1  # last candle 17:00: session complete


def test_us_thanksgiving_skipped_for_nvda():
    from duel.calendar import target_dates
    t = target_dates("2026-11-25", NVDA)
    assert t[0] == "2026-11-27" and "2026-11-26" not in t


def test_xetra_closed_christmas_eve():
    from duel.calendar import target_dates
    assert "2026-12-24" not in target_dates("2026-12-22", SIE)
    assert target_dates("2026-12-22", SIE)[0] == "2026-12-23"


def test_milan_easter_monday_skipped_for_stm():
    from duel.calendar import target_dates
    t = target_dates("2027-03-26", STM)  # Good Friday 26 Mar is closed too
    assert "2027-03-29" not in t and t[0] == "2027-03-30"
    assert target_dates("2027-03-25", STM)[0] == "2027-03-30"


def test_us_completeness_around_close_in_winter():
    import datetime as dt
    from duel.fetch import is_complete
    utc = dt.timezone.utc
    d = dt.date(2026, 12, 9)  # EST: 16:15 New York = 21:15 UTC
    assert not is_complete(d, NVDA, dt.datetime(2026, 12, 9, 20, 10, tzinfo=utc))
    assert is_complete(d, NVDA, dt.datetime(2026, 12, 9, 21, 50, tzinfo=utc))
