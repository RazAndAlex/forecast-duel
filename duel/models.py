"""Model wrappers. One model lives in memory at a time, always on CPU."""
from __future__ import annotations

import gc

import pandas as pd
import torch


class KronosModel:
    """Kronos-base through the vendored Kronos code; mean of 5 sampled paths."""

    def __init__(self):
        from vendor.kronos_model import Kronos, KronosPredictor, KronosTokenizer

        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
        net = Kronos.from_pretrained("NeoQuasar/Kronos-base")
        self.predictor = KronosPredictor(net, tokenizer, device="cpu", max_context=512)

    def forecast(self, df: pd.DataFrame, y_dates: list[str]) -> list[float]:
        torch.manual_seed(0)
        x_ts = pd.Series(pd.to_datetime(df.index))
        y_ts = pd.Series(pd.to_datetime(y_dates))
        pred = self.predictor.predict(
            df.reset_index(drop=True),
            x_ts,
            y_ts,
            pred_len=5,
            T=1.0,
            top_p=0.9,
            sample_count=5,
            verbose=False,
        )
        return pred["close"].tolist()

    def free(self):
        del self.predictor
        gc.collect()


class TimestralModel:
    """Timestral-209M: median path plus the quantile levels nearest 10% and 90%."""

    def __init__(self):
        import numpy as np
        from timestral import TimestralForecaster

        self._np = np
        self.fc = TimestralForecaster.from_pretrained("mistralai/Timestral-209M", device="cpu")
        levels = self.fc.quantile_levels
        self.i10 = min(range(len(levels)), key=lambda i: abs(levels[i] - 0.1))
        self.i90 = min(range(len(levels)), key=lambda i: abs(levels[i] - 0.9))

    def forecast(self, closes: list[float]):
        out = self.fc.forecast(
            self._np.asarray(closes, dtype="float32")[-1024:], prediction_length=5
        )
        q = out.quantiles[0, 0]  # (H, Q)
        return out.median[0, 0].tolist(), q[:, self.i10].tolist(), q[:, self.i90].tolist()

    def free(self):
        del self.fc
        gc.collect()
