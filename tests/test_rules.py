from duel.rules import replay

RULE = {"id": "r", "wallet": "w", "text": "t", "if": [{"feature": "prior_day_return", "op": ">", "value": 0}],
        "then": "up", "else": "down"}


def _closes(n):
    return {f"2026-01-{i + 1:02d}" if i < 31 else f"2026-02-{i - 30:02d}": 100 + (i * 7 % 5) - 2 + i * 0.01 for i in range(n)}


def test_days_shape_and_agreement():
    for n in (20, 50):
        closes = _closes(n)
        out = replay(RULE, closes, [{"date": "2099-01-01", "up_price": 0.5}])
        days = out["days"]
        assert len(days) <= 60
        assert [d["date"] for d in days] == sorted(d["date"] for d in days)
        assert sum(d["hit"] for d in days) == out["hits"]
        assert days and set(days[0]) == {"date", "call", "actual", "hit"}
