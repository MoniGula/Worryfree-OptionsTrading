"""
Credit spread strike and width selection logic.

A credit spread (bull-put or bear-call) is used when the regime is mildly
directional with elevated IV.  This module determines the optimal short
and long strike prices as well as the spread width.
"""

from __future__ import annotations


def select_strikes(
    underlying_price: float,
    target_delta: float,
    expiry_dte: int,
    implied_vol: float,
    direction: str = "put",
) -> dict:
    """
    Select the short and long strikes for a credit spread.

    Parameters
    ----------
    underlying_price:
        Current mid-price of the underlying asset.
    target_delta:
        Absolute delta value for the short strike (e.g. 0.20 for a
        20-delta spread).
    expiry_dte:
        Days to expiration of the target contract.
    implied_vol:
        Current at-the-money implied volatility (decimal).
    direction:
        ``"put"`` for a bull-put spread; ``"call"`` for a bear-call spread.

    Returns
    -------
    dict
        Keys: ``short_strike``, ``long_strike``, ``spread_width``,
        ``max_profit``, ``max_loss``.
    """
    pass


def select_width(
    underlying_price: float,
    max_risk_usd: float,
    short_strike: float,
    credit_received: float,
) -> float:
    """
    Determine the spread width based on a maximum-risk-per-trade constraint.

    Parameters
    ----------
    underlying_price:
        Current mid-price of the underlying.
    max_risk_usd:
        Maximum allowable risk (loss) for the position in USD.
    short_strike:
        Strike price of the short leg as returned by ``select_strikes``.
    credit_received:
        Net premium credit collected per share (USD).

    Returns
    -------
    float
        Recommended spread width in strike-price points.
    """
    pass
