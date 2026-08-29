"""Unit tests for src.features.volatility."""

import numpy as np
import pandas as pd
import pytest

from src.features.volatility import iv_rank, realized_volatility, vol_risk_premium


def _synthetic_prices(n: int = 120, daily_vol: float = 0.01, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    returns = rng.normal(loc=0.0, scale=daily_vol, size=n)
    prices = 100 * np.exp(np.cumsum(returns))
    return pd.Series(prices)


def test_realized_volatility_is_positive_and_annualised():
    prices = _synthetic_prices()
    vol = realized_volatility(prices, window=20)
    assert vol > 0
    # Annualised vol from a ~1% daily-vol series should land in a sane band.
    assert 0.05 < vol < 0.60


def test_realized_volatility_raises_on_insufficient_data():
    prices = pd.Series([100, 101, 102])
    with pytest.raises(ValueError):
        realized_volatility(prices, window=20)


def test_realized_volatility_uses_only_trailing_window():
    """
    Changing prices *before* the trailing window must not change the
    computed volatility — this is the core no-look-ahead guarantee.
    """
    prices = _synthetic_prices(n=100)
    window = 20

    vol_before = realized_volatility(prices, window=window)

    # Mutate history far outside the trailing window.
    mutated = prices.copy()
    mutated.iloc[:50] = mutated.iloc[:50] * 5

    vol_after = realized_volatility(mutated, window=window)
    assert vol_before == pytest.approx(vol_after)


def test_iv_rank_bounds():
    assert iv_rank(current_iv=0.30, iv_high=0.40, iv_low=0.20) == pytest.approx(0.5)
    assert iv_rank(current_iv=0.50, iv_high=0.40, iv_low=0.20) == 1.0  # clamped
    assert iv_rank(current_iv=0.10, iv_high=0.40, iv_low=0.20) == 0.0  # clamped


def test_iv_rank_invalid_range_raises():
    with pytest.raises(ValueError):
        iv_rank(current_iv=0.3, iv_high=0.2, iv_low=0.2)


def test_vol_risk_premium_sign():
    assert vol_risk_premium(implied_vol=0.25, realised_vol=0.18) == pytest.approx(0.07)
    assert vol_risk_premium(implied_vol=0.15, realised_vol=0.18) == pytest.approx(-0.03)
