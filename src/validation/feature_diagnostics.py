"""
Feature diagnostics for the WorryFree volatility/regime feature set.

Provides quick sanity checks used before a feature is trusted in the
decision engine: distributional summary, correlation with a forward-looking
label (computed safely, purely for diagnostic reporting — never fed back
into the live feature), and a basic stability-over-time check.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class FeatureSummary:
    """Distributional summary for a single feature series."""

    name: str
    count: int
    mean: float
    std: float
    min: float
    max: float
    pct_missing: float


def summarize(feature: pd.Series, name: str = "feature") -> FeatureSummary:
    """
    Compute a distributional summary for a feature series, including the
    fraction of missing values (useful for spotting warm-up periods that
    got silently forward-filled instead of correctly left as NaN).
    """
    total = len(feature)
    valid = feature.dropna()
    pct_missing = 1.0 - (len(valid) / total) if total > 0 else 0.0

    return FeatureSummary(
        name=name,
        count=len(valid),
        mean=float(valid.mean()) if len(valid) else float("nan"),
        std=float(valid.std()) if len(valid) else float("nan"),
        min=float(valid.min()) if len(valid) else float("nan"),
        max=float(valid.max()) if len(valid) else float("nan"),
        pct_missing=float(pct_missing),
    )


def forward_return_correlation(
    feature: pd.Series, prices: pd.Series, horizon_days: int = 5
) -> float:
    """
    Diagnostic-only correlation between today's feature value and the
    subsequent ``horizon_days`` forward return.

    This intentionally uses future data (the forward return) and must
    never be used as a live input to the decision engine — it exists only
    to sanity-check that a feature has *some* predictive relationship
    before spending time wiring it into the strategy.

    Parameters
    ----------
    feature:
        Feature series, indexed the same as ``prices``.
    prices:
        Underlying close-price series.
    horizon_days:
        Number of trading days ahead used to compute the forward return.

    Returns
    -------
    float
        Pearson correlation coefficient between the feature and the
        forward return, computed over all overlapping, non-missing rows.
    """
    forward_return = prices.shift(-horizon_days) / prices - 1.0
    aligned = pd.concat([feature, forward_return], axis=1, keys=["feature", "fwd_ret"]).dropna()

    if len(aligned) < 10:
        return float("nan")

    corr = aligned["feature"].corr(aligned["fwd_ret"])
    return float(corr) if corr is not None else float("nan")


def rolling_stability(feature: pd.Series, window: int = 60) -> pd.Series:
    """
    Compute a rolling coefficient-of-variation (std / |mean|) for a feature
    to flag periods where its scale drifts sharply — often a sign of a
    bug (e.g. a units mismatch or an unintended regime break in how the
    feature is computed) rather than genuine market behaviour.

    Parameters
    ----------
    feature:
        Feature series to evaluate.
    window:
        Rolling window size in observations.

    Returns
    -------
    pd.Series
        Rolling coefficient of variation, same index as ``feature``.
    """
    rolling_mean = feature.rolling(window=window, min_periods=max(5, window // 4)).mean()
    rolling_std = feature.rolling(window=window, min_periods=max(5, window // 4)).std()

    with np.errstate(divide="ignore", invalid="ignore"):
        cov = rolling_std / rolling_mean.abs()

    return cov.replace([np.inf, -np.inf], np.nan)
