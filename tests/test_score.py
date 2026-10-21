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
