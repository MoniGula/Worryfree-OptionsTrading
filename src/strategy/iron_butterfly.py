"""
Iron butterfly strike and wing selection logic.

An iron butterfly is deployed in low-trend, high-IV environments where the
underlying is expected to pin near the current price at expiration.
"""

from __future__ import annotations

from math import sqrt

from src.strategy.credit_spread import _delta_to_strike_distance, _round_to_strike_increment


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
    if underlying_price <= 0 or implied_vol <= 0 or expiry_dte <= 0:
        raise ValueError("underlying_price, implied_vol, and expiry_dte must be positive.")

    increment = 1.0 if underlying_price < 200 else 5.0
    body_strike = _round_to_strike_increment(underlying_price, increment)

    put_wing_distance = _delta_to_strike_distance(
        underlying_price, wing_delta, implied_vol, expiry_dte, "put"
    )
    call_wing_distance = _delta_to_strike_distance(
        underlying_price, wing_delta, implied_vol, expiry_dte, "call"
    )

    long_put = _round_to_strike_increment(body_strike - put_wing_distance, increment)
    long_call = _round_to_strike_increment(body_strike + call_wing_distance, increment)

    # Symmetric wing width: use the wider of the two sides so both wings
    # have equal, defined risk (a standard/"iron" butterfly convention).
    wing_width = max(body_strike - long_put, long_call - body_strike)
    wing_width = max(wing_width, increment)

    long_put = body_strike - wing_width
    long_call = body_strike + wing_width

    return {
        "short_put": float(body_strike),
        "short_call": float(body_strike),
        "long_put": float(long_put),
        "long_call": float(long_call),
        "body_strike": float(body_strike),
        "wing_width": float(wing_width),
    }


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
    if underlying_price <= 0 or implied_vol <= 0 or expiry_dte <= 0:
        raise ValueError("underlying_price, implied_vol, and expiry_dte must be positive.")
    if not (0 < target_credit_ratio < 1):
        raise ValueError("target_credit_ratio must be between 0 and 1.")

    # Expected 1-sigma move over the expiry window sets a baseline for how
    # much premium the ATM straddle is likely worth; wider wings are needed
    # to hit a given credit ratio when IV (and therefore straddle value) is
    # higher relative to price.
    t = expiry_dte / 365.0
    expected_move = underlying_price * implied_vol * sqrt(t)

    # A body (ATM short straddle) is roughly worth ~0.8x the expected move
    # for near-dated, near-ATM options (a standard rule-of-thumb approx).
    approx_straddle_value = 0.8 * expected_move

    # width * target_credit_ratio ~= straddle credit collected -> solve width.
    width = approx_straddle_value / target_credit_ratio

    increment = 1.0 if underlying_price < 200 else 5.0
    width = _round_to_strike_increment(width, increment)

    lower_bound = increment
    upper_bound = max(underlying_price * 0.15, increment)
    return float(min(max(width, lower_bound), upper_bound))
