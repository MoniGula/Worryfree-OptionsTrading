"""
Iron butterfly strike and wing selection logic.

An iron butterfly is deployed in low-trend, high-IV environments where the
underlying is expected to pin near the current price at expiration.
"""

from __future__ import annotations


def select_strikes(
    underlying_price: float,
    expiry_dte: int,
    implied_vol: float,
    wing_delta: float = 0.10,
) -> dict:
    """
    Select all four strikes for an iron butterfly.

    The body strikes (ATM short call and short put) are placed at the
    nearest available strike to ``underlying_price``.  The wings are placed
    at the strike corresponding to ``wing_delta``.

    Parameters
    ----------
    underlying_price:
        Current mid-price of the underlying asset.
    expiry_dte:
        Days to expiration of the target contract.
    implied_vol:
        Current at-the-money implied volatility (decimal).
    wing_delta:
        Absolute delta value used to position the long wings.

    Returns
    -------
    dict
        Keys: ``short_put``, ``short_call``, ``long_put``, ``long_call``,
        ``body_strike``, ``wing_width``.
    """
    pass


def select_wing_width(
    underlying_price: float,
    implied_vol: float,
    expiry_dte: int,
    target_credit_ratio: float = 0.33,
) -> float:
    """
    Determine wing width to achieve a target credit-to-width ratio.

    Parameters
    ----------
    underlying_price:
        Current mid-price of the underlying.
    implied_vol:
        Current implied volatility (decimal).
    expiry_dte:
        Days to expiration.
    target_credit_ratio:
        Desired ratio of net credit received to total wing width
        (e.g. 0.33 means collect at least 1/3 of the wing width).

    Returns
    -------
    float
        Recommended wing width in strike-price points.
    """
    pass
