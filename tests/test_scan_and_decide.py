"""Unit tests for src.main.scan() and src.main.decide() robustness against
non-finite feature values — e.g. yfinance appending a placeholder bar with
NaN OHLC for a day when no trading session has occurred yet (weekends,
holidays, or requests made right after midnight before real data lands)."""

import math

import numpy as np
import pandas as pd
import pytest
import yfinance as yf

from src.main import decide, scan


class _FakeTicker:
    """Duck-typed stand-in for yfinance.Ticker exposing only .history()."""

    def __init__(self, frame: pd.DataFrame):
        self._frame = frame

    def history(self, period: str = "6mo") -> pd.DataFrame:
        return self._frame


def _real_history(n_days: int, trailing_nan_rows: int = 0) -> pd.DataFrame:
    """Build a synthetic daily-close DataFrame with a mild upward random
    walk, optionally followed by trailing_nan_rows all-NaN rows to
    mimic yfinance's placeholder-bar behaviour."""
    rng = np.random.default_rng(42)
    closes = 100.0 + np.cumsum(rng.normal(loc=0.05, scale=1.0, size=n_days))
    dates = pd.date_range("2026-01-01", periods=n_days, freq="B")
    frame = pd.DataFrame({"close": closes}, index=dates)

    if trailing_nan_rows:
        nan_dates = pd.date_range(
            dates[-1] + pd.Timedelta(days=1), periods=trailing_nan_rows, freq="D"
        )
        nan_frame = pd.DataFrame({"close": [math.nan] * trailing_nan_rows}, index=nan_dates)
        frame = pd.concat([frame, nan_frame])

    return frame


def test_scan_drops_trailing_nan_placeholder_bar(monkeypatch):
    # 90 real sessions plus one trailing NaN "today" bar — matches the
    # real-world shape of the bug (an early-morning/weekend request before
    # yfinance has real data for the newest calendar day).
    frame = _real_history(n_days=90, trailing_nan_rows=1)
    monkeypatch.setattr(yf, "Ticker", lambda symbol: _FakeTicker(frame))

    records = scan(["SPY"])

    assert len(records) == 1
    record = records[0]
    # The underlying price must come from the last REAL close, not NaN.
    assert math.isfinite(record["underlying_price"])
    assert record["underlying_price"] == pytest.approx(float(frame["close"].dropna().iloc[-1]))
    for key, value in record.items():
        if key == "symbol":
            continue
        assert math.isfinite(value), f"{key} was non-finite: {value}"


def test_scan_skips_symbol_with_all_nan_history(monkeypatch):
    frame = _real_history(n_days=90, trailing_nan_rows=0)
    frame["close"] = math.nan
    monkeypatch.setattr(yf, "Ticker", lambda symbol: _FakeTicker(frame))

    records = scan(["BROKEN"])

    assert records == []


def test_scan_skips_symbol_with_too_few_real_sessions_after_dropping_nans(monkeypatch):
    # Only 40 real sessions plus a trailing NaN bar — below the 60-session
    # floor once the placeholder row is dropped, so it must be skipped
    # rather than computing features off a too-short window.
    frame = _real_history(n_days=40, trailing_nan_rows=1)
    monkeypatch.setattr(yf, "Ticker", lambda symbol: _FakeTicker(frame))

    records = scan(["THIN"])

    assert records == []


def test_decide_skips_a_record_whose_route_strategy_raises_but_keeps_others(monkeypatch):
    good_record = {
        "symbol": "GOOD",
        "underlying_price": 450.0,
        "realised_vol": 0.15,
        "implied_vol": 0.18,
        "iv_rank": 0.5,
        "vol_risk_premium": 0.03,
        "trend_strength": 30.0,
        "range_probability": 0.4,
    }
    bad_record = {
        "symbol": "BAD",
        "underlying_price": math.nan,  # would trigger route_strategy's ValueError
        "realised_vol": 0.15,
        "implied_vol": 0.18,
        "iv_rank": 0.5,
        "vol_risk_premium": 0.03,
        "trend_strength": 30.0,
        "range_probability": 0.4,
    }

    specs = decide([bad_record, good_record])

    symbols = [spec["symbol"] for spec in specs]
    assert "BAD" not in symbols
    assert "GOOD" in symbols
