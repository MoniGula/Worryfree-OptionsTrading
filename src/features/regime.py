"""
Market-regime feature engineering for the WorryFree options-trading agent.

Functions here characterise the current price-action regime (trending vs.
range-bound) so that the decision engine can route to the appropriate
options structure.
"""

from __future__ import annotations

import pandas as pd


def trend_strength(prices: pd.Series, adx_period: int = 14) -> float:
    """
    Estimate the strength of the current price trend using ADX logic.

    A value above 25 is conventionally considered a strong trend;
    below 20 indicates a ranging / sideways market.

    Parameters
    ----------
    prices:
        OHLCV DataFrame or a close-price Series for the underlying.
    adx_period:
        Look-back period for the Average Directional Index calculation.

    Returns
    -------
    float
        ADX-style trend-strength score in the range [0, 100].
    """
    pass


def range_probability(prices: pd.Series, horizon_days: int = 21) -> float:
    """
    Estimate the probability that price stays within a defined range over
    the given horizon.

    Uses a log-normal diffusion model calibrated to recent realised
    volatility to compute the probability that the underlying does not
    breach ±1 standard-deviation bands over ``horizon_days`` trading days.

    Parameters
    ----------
    prices:
        Time-ordered closing prices for the underlying.
    horizon_days:
        Forward-looking window in trading days.

    Returns
    -------
    float
        Probability in [0.0, 1.0] that the price remains range-bound.
    """
    pass
