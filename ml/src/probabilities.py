"""Calibrated probabilities that a month lands below / within / above the band around the area's usual level.

The reference level T (tiers.py: same calendar month in the last 12 complete months) and the band
(config.TIER_THRESHOLDS_PCT, e.g. -10% / +10%) are exactly the ones the tiers use. Only the output changes: instead
of one label from the point forecast F, we give the chance of each outcome, using how far reality has landed from
the forecast in the past.

Error distribution. r = actual / forecast over the shipped model's out-of-sample backtest points, the SAME pool the
80% range uses (intervals.py: forecasts below 1 are left out). Then, for the realised value r x F,

    p_below  = P(r x F < T x (1 + lo/100)) = P(r < c_lo),   c_lo = T (1 + lo/100) / F
    p_above  = P(r x F > T x (1 + hi/100)) = 1 - P(r < c_hi), c_hi = T (1 + hi/100) / F
    p_within = 1 - p_below - p_above

P(r < c) is a SMOOTHED empirical CDF of the ratios, one of two forms (evaluate.py picks the one with the lower
out-of-sample Brier score and forecast.py reads that choice from evaluation.json):

    "kde"        Gaussian kernel on log-ratios, bandwidth by Scott's rule (h = sd(log r) x n^(-1/5)):
                 P(r < c) = z + (1 - z) x mean_i Phi((log c - log r_i) / h)
    "lognormal"  P(r < c) = z + (1 - z) x Phi((log c - mu) / sigma), mu / sigma = mean / sd of log r

z is the share of ratios that are exactly 0 (a month with no reported incidents; log undefined): they count as a
point mass at 0, i.e. always below any positive threshold.

Everything is closed-form and vectorised, so the result is deterministic. Areas whose tier would be
"insufficient_data" (tiers.tier rule), or that have no reference level yet, get NaN probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.special import ndtr

import common  # noqa: F401  (sets up sys.path for config)
import config
import intervals
import tiers

METHODS = ["kde", "lognormal"]
DEFAULT_METHOD = "kde"
OUTCOMES = ["below_typical", "typical", "above_typical"]   # ordered; column order of every probability array
DECIMALS = 3


@dataclass
class RatioDistribution:
    """Smoothed distribution of r = actual / forecast."""
    method: str
    log_ratios: np.ndarray = field(repr=False)   # log of the positive ratios, sorted
    zero_share: float
    bandwidth: float                              # kde only (Scott's rule)
    mu: float                                     # lognormal only
    sigma: float                                  # lognormal only
    n_ratios: int

    def cdf(self, c) -> np.ndarray:
        """P(r < c), vectorised over c; 0 for c <= 0."""
        c = np.asarray(c, dtype=float)
        out = np.zeros(c.shape, dtype=float)
        pos = c > 0
        logc = np.log(c[pos])
        if self.method == "kde":
            cont = ndtr((logc[:, None] - self.log_ratios[None, :]) / self.bandwidth).mean(axis=1)
        elif self.method == "lognormal":
            cont = ndtr((logc - self.mu) / self.sigma)
        else:
            raise ValueError(f"unknown probability method {self.method!r}")
        out[pos] = self.zero_share + (1 - self.zero_share) * cont
        return np.clip(out, 0.0, 1.0)


def fit_distribution(actual, forecast, method: str = DEFAULT_METHOD) -> RatioDistribution:
    """Ratios actual / forecast with the same exclusion rule as the 80% range (forecast >= 1)."""
    actual = np.asarray(actual, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    keep = forecast >= intervals.MIN_FORECAST_FOR_RATIO
    ratios = actual[keep] / forecast[keep]
    positive = np.sort(np.log(ratios[ratios > 0]))
    sd = float(positive.std(ddof=1))
    return RatioDistribution(
        method=method,
        log_ratios=positive,
        zero_share=float(np.mean(ratios <= 0)),
        bandwidth=sd * len(positive) ** (-1 / 5),
        mu=float(positive.mean()),
        sigma=sd,
        n_ratios=int(keep.sum()),
    )


def eligible(typical, area_mean_incidents) -> np.ndarray:
    """True where tiers.tier would return a real tier: a reference level exists, is positive, and the area is large
    enough (area_mean_incidents >= config.TIER_MIN_MEAN)."""
    t = np.asarray(typical, dtype=float)
    a = np.asarray(area_mean_incidents, dtype=float)
    ok = ~np.isnan(t) & ~np.isnan(a)
    ok[ok] = (a[ok] >= config.TIER_MIN_MEAN) & (t[ok] > 0)
    return ok


def band_probabilities(forecast, typical, area_mean_incidents, dist: RatioDistribution,
                       thresholds: tuple[float, float] | None = None) -> np.ndarray:
    """(n, 3) array of [p_below, p_within, p_above]; rows that are not eligible are NaN."""
    lo, hi = thresholds if thresholds is not None else config.TIER_THRESHOLDS_PCT
    f = np.clip(np.asarray(forecast, dtype=float), 1e-9, None)
    t = np.asarray(typical, dtype=float)
    ok = eligible(typical, area_mean_incidents)
    out = np.full((len(f), 3), np.nan)
    p_below = dist.cdf(t[ok] * (1 + lo / 100) / f[ok])
    p_above = 1.0 - dist.cdf(t[ok] * (1 + hi / 100) / f[ok])
    out[ok, 0] = p_below
    out[ok, 2] = p_above
    out[ok, 1] = np.clip(1.0 - p_below - p_above, 0.0, 1.0)
    return out


def most_likely(probs: np.ndarray) -> np.ndarray:
    """Argmax label per row (OUTCOMES order; first wins on an exact tie); None for NaN rows."""
    labels = np.array(OUTCOMES, dtype=object)[np.argmax(np.nan_to_num(probs, nan=-1.0), axis=1)]
    labels[np.isnan(probs).any(axis=1)] = None
    return labels


def round_probabilities(probs: np.ndarray, decimals: int = DECIMALS) -> np.ndarray:
    """Round each row to `decimals` so it sums to exactly 1 (largest-remainder method; ties go to the earlier
    column). NaN rows stay NaN."""
    scale = 10 ** decimals
    out = np.full(probs.shape, np.nan)
    ok = ~np.isnan(probs).any(axis=1)
    p = probs[ok] / probs[ok].sum(axis=1, keepdims=True) * scale
    units = np.floor(p + 1e-9)
    missing = (scale - units.sum(axis=1)).astype(int)
    order = np.argsort(-(p - units), axis=1, kind="stable")
    for i, k in enumerate(missing):
        units[i, order[i, :k]] += 1
    out[ok] = units / scale
    return out


def realised_outcome(actual, typical, area_mean_incidents, thresholds=None) -> np.ndarray:
    """Index into OUTCOMES of the realised tier (same tiers.py rule); -1 where there is no real tier."""
    labels = tiers.tier_frame(actual, typical, area_mean_incidents, thresholds)["tier"]
    lookup = {t: i for i, t in enumerate(OUTCOMES)}
    return np.array([lookup.get(x, -1) for x in labels], dtype=int)


def describe(dist: RatioDistribution) -> str:
    """One sentence for meta.json / the report."""
    lo, hi = config.TIER_THRESHOLDS_PCT
    if dist.method == "kde":
        shape = (f"a Gaussian-kernel smoothed distribution of the log-ratios (Scott's-rule bandwidth "
                 f"{dist.bandwidth:.3f})")
    else:
        shape = f"a lognormal fitted to them (mu {dist.mu:+.3f}, sigma {dist.sigma:.3f})"
    return (f"Each probability is the chance that the realised month lands below {lo:g}%, within, or above +{hi:g}% "
            f"of the area's usual level (same calendar month in the last {config.TIER_WINDOW_MONTHS} complete "
            f"months), from the point forecast and {shape} of {dist.n_ratios} past ratios actual / forecast "
            f"(the same backtest points as the 80% range).")
