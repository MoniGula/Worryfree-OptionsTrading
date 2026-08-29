"""
Volatility feature engineering for the WorryFree options-trading agent.

Functions here produce the volatility-related inputs consumed by the
strategy decision engine.
"""

from __future__ import annotations

import pandas as pd


def realized_volatility(prices: pd.Series, window: int = 20) -> float:
    """
    Estimate annualised realised volatility from a price series.

    Parameters
    ----------
    prices:
        Time-ordered closing prices for a single underlying.
    window:
        Number of trading days used for the rolling log-return window.

    Returns
    -------
    float
        Annualised realised volatility as a decimal (e.g. 0.18 for 18 %).
    """
    pass


def iv_rank(current_iv: float, iv_high: float, iv_low: float) -> float:
    """
    Compute the IV Rank (IVR) for the current implied-volatility level.

    IVR = (current_iv - iv_low) / (iv_high - iv_low)

    Parameters
    ----------
    current_iv:
        Current at-the-money implied volatility (decimal).
    iv_high:
        52-week high implied volatility (decimal).
    iv_low:
        52-week low implied volatility (decimal).

    Returns
    -------
    float
        IV Rank in the range [0.0, 1.0].
    """
    pass


def vol_risk_premium(implied_vol: float, realised_vol: float) -> float:
    """
    Calculate the volatility risk premium (VRP).

    VRP = implied_vol - realised_vol

    A positive VRP indicates that options are priced above historical
    realised volatility, which is the primary signal for premium-selling
    strategies.

    Parameters
    ----------
    implied_vol:
        Current implied volatility of the front-month ATM option (decimal).
    realised_vol:
        Realised volatility over the matching trailing window (decimal).

    Returns
    -------
    float
        Volatility risk premium as a decimal.
    """
    pass
