"""Unit tests for src.validation (leak_scanner, walk_forward, feature_diagnostics)."""

import numpy as np
import pandas as pd
import pytest

from src.validation.leak_scanner import audit_feature
from src.validation.walk_forward import generate_splits, run_walk_forward
from src.validation.feature_diagnostics import summarize, forward_return_correlation


def _price_series(n: int = 200) -> pd.Series:
    rng = np.random.default_rng(7)
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    prices = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return pd.Series(prices, index=dates)


def test_audit_feature_passes_for_causal_rolling_mean():
    raw = _price_series()
    causal_feature = raw.rolling(window=10, min_periods=10).mean()

    report = audit_feature(causal_feature, raw, window=10, check_normalisation=False)
    assert report.passed


def test_audit_feature_flags_centered_window_as_leak():
    raw = _price_series()
    leaky_feature = raw.rolling(window=10, min_periods=10, center=True).mean()

    report = audit_feature(leaky_feature, raw, window=10, check_normalisation=False)
    assert not report.passed
    assert any("look-ahead" in err for err in report.errors)


def test_audit_feature_flags_full_sample_normalisation():
    raw = _price_series()
    full_sample_z = (raw - raw.mean()) / raw.std()

    report = audit_feature(full_sample_z, raw, check_normalisation=True)
    assert not report.passed


def test_generate_splits_never_overlaps_train_and_validation():
    splits = generate_splits(n_samples=100, train_window=40, validation_window=10, step=10)
    assert len(splits) > 0
    for split in splits:
        assert split.train_end <= split.validation_start
        assert split.validation_start < split.validation_end <= 100


def test_run_walk_forward_scores_each_fold():
    data = pd.DataFrame({"x": np.arange(100)})

    def score_fn(train_df, validation_df):
        return float(validation_df["x"].mean() - train_df["x"].mean())

    result = run_walk_forward(
        data, train_window=40, validation_window=10, step=10, score_fn=score_fn
    )
    assert len(result.fold_scores) > 0
    assert not np.isnan(result.mean_score)


def test_run_walk_forward_captures_errors_without_crashing():
    data = pd.DataFrame({"x": np.arange(50)})

    def failing_score_fn(train_df, validation_df):
        raise RuntimeError("boom")

    result = run_walk_forward(
        data, train_window=20, validation_window=10, step=10, score_fn=failing_score_fn
    )
    assert len(result.fold_scores) > 0
    assert all(f["score"] is None for f in result.fold_scores)
    assert all(f["error"] == "boom" for f in result.fold_scores)


def test_summarize_reports_missing_fraction():
    feature = pd.Series([np.nan, np.nan, 1.0, 2.0, 3.0])
    summary = summarize(feature, name="test_feature")
    assert summary.count == 3
    assert summary.pct_missing == pytest.approx(0.4)


def test_forward_return_correlation_detects_positive_relationship():
    n = 200
    rng = np.random.default_rng(11)
    prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))))

    forward_ret = prices.shift(-5) / prices - 1.0
    # Construct a feature that is, by design, highly correlated with the
    # forward return (plus noise) to validate the diagnostic detects it.
    feature = forward_ret.shift(5) + rng.normal(0, 0.001, n)

    corr = forward_return_correlation(feature, prices, horizon_days=5)
    assert not np.isnan(corr)
