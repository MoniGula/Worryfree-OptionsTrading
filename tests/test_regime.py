"""Unit tests for src.features.regime."""

import numpy as np
import pandas as pd
import pytest

from src.features.regime import range_probability, trend_strength


def _trending_prices(n: int = 100, drift: float = 0.004, vol: float = 0.003) -> pd.Series:
    rng = np.random.default_rng(1)
    returns = rng.normal(loc=drift, scale=vol, size=n)
    return pd.Series(100 * np.exp(np.cumsum(returns)))


def _ranging_prices(n: int = 100, vol: float = 0.003) -> pd.Series:
    rng = np.random.default_rng(2)
    returns = rng.normal(loc=0.0, scale=vol, size=n)
    # Mean-revert by construction: alternate sign every few bars.
    returns = returns - np.mean(returns)
    return pd.Series(100 * np.exp(np.cumsum(returns)))


def test_trend_strength_higher_for_trending_series():
    trending = trend_strength(_trending_prices(), adx_period=14)
    ranging = trend_strength(_ranging_prices(), adx_period=14)

    assert 0 <= trending <= 100
    assert 0 <= ranging <= 100
    assert trending > ranging


def test_trend_strength_raises_on_insufficient_data():
    with pytest.raises(ValueError):
        trend_strength(pd.Series([100, 101, 102]), adx_period=14)


def test_range_probability_in_bounds():
    prob = range_probability(_ranging_prices(n=120), horizon_days=5)
    assert 0.0 <= prob <= 1.0


def test_range_probability_higher_when_short_term_vol_compressed():
    """
    A series whose most recent bars are calmer than its longer history
    should get a *higher* range-bound probability than one whose recent
    bars are choppier than its history.
    """
    rng = np.random.default_rng(3)

    calm_recent = np.concatenate(
        [
            rng.normal(0, 0.02, 80),   # choppy history
            rng.normal(0, 0.002, 20),  # calm recent window
        ]
    )
    choppy_recent = np.concatenate(
        [
            rng.normal(0, 0.002, 80),  # calm history
            rng.normal(0, 0.02, 20),   # choppy recent window
        ]
    )

    calm_prices = pd.Series(100 * np.exp(np.cumsum(calm_recent)))
    choppy_prices = pd.Series(100 * np.exp(np.cumsum(choppy_recent)))

    prob_calm = range_probability(calm_prices, horizon_days=10)
    prob_choppy = range_probability(choppy_prices, horizon_days=10)

    assert prob_calm > prob_choppy
