"""80% uncertainty range from backtest error ratios (contract decision 6).

For every backtest point we have an actual value and the model's forecast. The ratio
actual / forecast, pooled across all areas and both folds, tells us how far reality typically lands
from the forecast in relative terms. Its lower and upper quantiles (Q10 and Q90 for an 80% level)
become multipliers:

    interval_low  = forecast x q_low
    interval_high = forecast x q_high      (both clipped at 0)

Forecasts below 1 are dropped before computing ratios: dividing by a near-zero forecast (only
possible in tiny areas such as Musqueam) produces huge ratios that would widen every area's range.

Because the ratios are pooled, every area gets the same relative width: large areas get wide ranges
in absolute terms, small areas narrow ones.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import common  # noqa: F401  (sets up sys.path for config)
import config

MIN_FORECAST_FOR_RATIO = 1.0


@dataclass
class RatioInterval:
    q_low: float
    q_high: float
    level: float
    n_ratios: int

    def apply(self, forecast):
        """forecast (scalar or array) -> (low, high), clipped at 0."""
        f = np.asarray(forecast, dtype=float)
        return np.clip(f * self.q_low, 0, None), np.clip(f * self.q_high, 0, None)


def fit_ratios(actual, forecast, level: float = config.INTERVAL_LEVEL) -> RatioInterval:
    """Quantiles of actual / forecast at (1-level)/2 and 1-(1-level)/2, e.g. Q10 and Q90 for 80%."""
    actual = np.asarray(actual, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    keep = forecast >= MIN_FORECAST_FOR_RATIO
    ratios = actual[keep] / forecast[keep]
    a = (1 - level) / 2
    return RatioInterval(
        q_low=float(np.quantile(ratios, a)),
        q_high=float(np.quantile(ratios, 1 - a)),
        level=level,
        n_ratios=int(keep.sum()),
    )


def coverage(actual, low, high) -> float:
    """Share of actual values inside [low, high]."""
    actual = np.asarray(actual, dtype=float)
    return float(np.mean((actual >= np.asarray(low)) & (actual <= np.asarray(high))))
