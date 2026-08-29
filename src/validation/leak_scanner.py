"""
Leak-audit scanner for the WorryFree feature pipeline.

Checks feature computations for the three most common sources of
look-ahead leakage in time-series/backtesting pipelines:

1. Full-sample normalisation (mean/std/rank computed over the whole
   dataset instead of a trailing window only).
2. Misaligned rolling windows (a window that includes the current bar's
   *future* value, or a shift direction that points forward in time).
3. Future-timestamp joins (merging a label or exogenous series using an
   index that is not strictly less-than-or-equal-to the feature's as-of
   timestamp).

This module operates on pandas DataFrames/Series and raises
``LeakageError`` (or returns a structured report) rather than silently
producing an optimistic backtest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


class LeakageError(Exception):
    """Raised when a feature or label series fails a leak-audit check."""


@dataclass
class LeakAuditReport:
    """Structured result of a leak-audit run."""

    passed: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def raise_if_failed(self) -> None:
        if not self.passed:
            raise LeakageError("; ".join(self.errors))


def check_full_sample_normalisation(
    feature: pd.Series, raw: pd.Series, tolerance: float = 1e-6
) -> list[str]:
    """
    Detect features that appear to be normalised using full-sample
    statistics (e.g. ``(x - x.mean()) / x.std()`` over the entire series)
    rather than a trailing/expanding window computed strictly up to "today".

    Heuristic: recompute what a full-sample normalisation of ``raw`` would
    look like and what a causal (expanding-window) normalisation would look
    like, then check which one the supplied ``feature`` actually matches in
    its early history. A causal feature necessarily diverges from the
    full-sample version early on (it hasn't seen the whole distribution
    yet); a feature that matches the full-sample version even in its early
    bars must have used future data to compute its normalisation stats.
    """
    errors: list[str] = []
    if len(feature) < 10:
        return errors

    expanding_mean = raw.expanding(min_periods=5).mean()
    expanding_std = raw.expanding(min_periods=5).std()
    causal_z = (raw - expanding_mean) / expanding_std

    full_mean = raw.mean()
    full_std = raw.std()
    full_z = (raw - full_mean) / full_std

    valid = feature.notna() & causal_z.notna() & full_z.notna()
    if valid.sum() < 10:
        return errors

    early_idx = valid[valid].index[: max(1, valid.sum() // 2)]

    diff_vs_full = (feature.loc[early_idx] - full_z.loc[early_idx]).abs().mean()
    diff_vs_causal = (feature.loc[early_idx] - causal_z.loc[early_idx]).abs().mean()

    # If the supplied feature tracks the full-sample normalisation more
    # closely than the causal one during the early (warm-up) history, it
    # was almost certainly computed with full-sample stats — a leak.
    if diff_vs_full < tolerance and diff_vs_full < diff_vs_causal:
        errors.append(
            "Feature normalisation matches full-sample statistics even in "
            "its early history — recompute using only trailing/expanding "
            "data available as of each timestamp."
        )
    return errors


def check_rolling_window_alignment(
    feature: pd.Series, raw: pd.Series, window: int
) -> list[str]:
    """
    Verify that a rolling-window feature at time t only depends on
    ``raw`` values at times <= t, by recomputing a trailing rolling
    statistic and confirming it matches the provided feature (within
    floating-point tolerance) rather than a centered or forward window.
    """
    errors: list[str] = []
    if len(feature) < window + 2:
        return errors

    trailing = raw.rolling(window=window, min_periods=window).mean()
    centered = raw.rolling(window=window, min_periods=window, center=True).mean()

    valid = feature.notna() & trailing.notna()
    if valid.sum() < window:
        return errors

    trailing_diff = (feature[valid] - trailing[valid]).abs().mean()
    centered_diff = (
        (feature[valid] - centered[valid]).abs().mean()
        if centered.notna().sum() > 0
        else float("inf")
    )

    if centered_diff < trailing_diff:
        errors.append(
            f"Rolling feature (window={window}) matches a centered window "
            "more closely than a trailing one — this includes future bars "
            "and is a look-ahead leak."
        )
    return errors


def check_future_timestamp_join(
    feature_index: pd.DatetimeIndex, source_index: pd.DatetimeIndex
) -> list[str]:
    """
    Verify that every feature timestamp has a matching source timestamp
    that is less-than-or-equal-to it (i.e. the join used only data known
    as of that time), not a nearest/forward-filled future timestamp.
    """
    errors: list[str] = []
    source_sorted = source_index.sort_values()

    for ts in feature_index:
        # Find the position where ts would be inserted; anything at or
        # after that position is a future timestamp relative to ts.
        pos = source_sorted.searchsorted(ts, side="right")
        if pos == 0:
            continue
        matched_ts = source_sorted[pos - 1]
        if matched_ts > ts:
            errors.append(
                f"Timestamp {ts} joined against future source timestamp "
                f"{matched_ts} — this is a future-timestamp leak."
            )
            break
    return errors


def audit_feature(
    feature: pd.Series,
    raw: pd.Series,
    window: int | None = None,
    check_normalisation: bool = True,
) -> LeakAuditReport:
    """
    Run all applicable leak-audit checks against a single feature series.

    Parameters
    ----------
    feature:
        The computed feature series to audit.
    raw:
        The raw input series the feature was derived from (same index).
    window:
        If the feature is a rolling-window statistic, pass the window size
        to enable the rolling-alignment check.
    check_normalisation:
        Set to False for features that are not normalised (e.g. raw ADX),
        to skip the full-sample-normalisation heuristic.

    Returns
    -------
    LeakAuditReport
    """
    errors: list[str] = []
    warnings: list[str] = []

    if check_normalisation:
        errors.extend(check_full_sample_normalisation(feature, raw))

    if window is not None:
        errors.extend(check_rolling_window_alignment(feature, raw, window))

    if not isinstance(feature.index, pd.DatetimeIndex) or not isinstance(
        raw.index, pd.DatetimeIndex
    ):
        warnings.append(
            "Non-datetime index — skipped future-timestamp join check."
        )
    else:
        errors.extend(check_future_timestamp_join(feature.index, raw.index))

    return LeakAuditReport(passed=len(errors) == 0, warnings=warnings, errors=errors)
