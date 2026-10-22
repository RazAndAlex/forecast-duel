import datetime as dt
import json
import subprocess
from pathlib import Path

import pytest

from duel import crowd, report
from duel.score import luck_p

D1, D2 = dt.date(2026, 10, 19), dt.date(2026, 10, 20)
MARKET = {"clobTokenIds": '["up-tok","down-tok"]', "outcomes": '["Up","Down"]',
          "startDate": "2026-10-16T12:00:00Z"}
EVENT = [{"markets": [MARKET]}]


def test_calls_at_the_edge():
    assert [crowd.call(p) for p in (0.49, 0.5, 0.51)] == [-1, 0, 1]


def test_luck_p_known_values():
    assert luck_p(10, 10) == 1 / 1024
    assert luck_p(4, 2) == 11 / 16
    assert luck_p(0, 0) is None


def test_score_skips_no_call_and_unchanged():
    closes = {"2026-10-16": 100.0, "2026-10-19": 101.0, "2026-10-20": 101.0, "2026-10-21": 99.0}
    rows = [{"date": "2026-10-19", "up_price": 0.6}, {"date": "2026-10-20", "up_price": 0.7},
            {"date": "2026-10-21", "up_price": 0.5}]
    s = crowd.score(rows, closes)
    assert (s["n"], s["hits"], s["no_call"]) == (1, 1, 1)  # 10-20 unchanged, 10-21 at 0.5


def stub(history_by_url):
    def get(url):
        if "/events?" in url:
            return EVENT if "october-20" in url or "october-19" in url else {"_error": "x"}
        for key, val in history_by_url.items():
            if key in url:
                return val
        return {"_error": "x"}
    return get


def test_one_bad_day_does_not_stop_the_loop(tmp_path):
    path = tmp_path / "crowd.jsonl"
    get = stub({"startTs": {"history": [{"t": 1, "p": 0.42}]}})
    # 10-16 errors on every call; 10-19 and 10-20 must still be written
    n = crowd.fetch_crowd(weekdays=3, today=D2, get=lambda u: {"_error": "x"} if "october-16" in u else get(u),
                          path=path)
    assert n == 2
    assert [r["date"] for r in crowd.load(path)] == ["2026-10-19", "2026-10-20"]


def test_interval_max_fallback_when_window_is_empty():
    get = stub({"startTs": {"history": []}, "interval=max": {"history": [{"t": 5, "p": 0.7}]}})
    assert crowd.fetch_day(D2, get)["up_price"] == 0.7


def test_price_is_last_point_before_the_open():
    cut = int(dt.datetime.combine(D2, dt.time(9, 30), crowd.NY).timestamp())
    get = stub({"startTs": {"history": [{"t": 1, "p": 0.4}, {"t": cut, "p": 0.6}, {"t": cut + 60, "p": 0.9}]}})
    assert crowd.fetch_day(D2, get)["up_price"] == 0.6


def test_old_keys_unchanged(tmp_path):
    root = Path(report.ROOT)
    try:
        old = json.loads(subprocess.run(["git", "show", "main:site/data.json"], cwd=root, check=True,
                                        capture_output=True, text=True).stdout)
    except Exception:
        pytest.skip("no main branch to compare with")
    new = report.build(out_path=tmp_path / "data.json")
    for r in new["traders"]["rules"]:
        r.pop("days")  # added on branch history-page
    for k, v in old.items():
        if k != "generated_at":
            assert new[k] == v, k
    assert {"crowd", "traders", "luck"} <= set(new)
