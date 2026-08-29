"""
Credit spread strike and width selection logic.

A credit spread (bull-put or bear-call) is used when the regime is mildly
directional with elevated IV.  This module determines the optimal short
and long strike prices as well as the spread width.
"""

from __future__ import annotations

from math import erf, sqrt

# Default target: sell the short leg near a ~20-delta OTM strike, sized to
# risk roughly 2% of a hypothetical $100k account per trade unless the
# caller overrides via select_width.
DEFAULT_MAX_RISK_USD = 2000.0


def _norm_cdf(x: float) -> float:
    """Standard normal CDF without a scipy dependency."""
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _delta_to_strike_distance(
    underlying_price: float,
    target_delta: float,
    implied_vol: float,
    expiry_dte: int,
    option_type: str,
) -> float:
    """
    Approximate the strike distance (in price points) from ATM that
    corresponds to a target absolute delta, using a simplified
    Black-Scholes delta inversion assuming zero risk-free rate and
    zero dividend yield (adequate for short-dated, near-the-money
    approximations used in strike selection, not option pricing).
    """
    from scipy.stats import norm

    t = max(expiry_dte, 1) / 365.0
    sigma_sqrt_t = implied_vol * sqrt(t)
    if sigma_sqrt_t <= 0:
        return 0.0

    target_delta = min(max(target_delta, 0.0001), 0.9999)

    if option_type == "put":
        # Put delta = N(d1) - 1 (negative). |delta| = target_delta.
        d1 = norm.ppf(1 - target_delta)
    else:
        # Call delta = N(d1). delta = target_delta.
        d1 = norm.ppf(target_delta)

    # d1 = [ln(S/K) + 0.5*sigma^2*t] / (sigma*sqrt(t))
    # => ln(S/K) = d1*sigma*sqrt(t) - 0.5*sigma^2*t
    log_moneyness = d1 * sigma_sqrt_t - 0.5 * (implied_vol ** 2) * t
    strike = underlying_price / pow(2.718281828459045, log_moneyness)
    return abs(underlying_price - strike)


def _round_to_strike_increment(price: float, increment: float = 1.0) -> float:
    return round(price / increment) * increment


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
    if direction not in ("put", "call"):
        raise ValueError("direction must be 'put' or 'call'.")
    if underlying_price <= 0 or implied_vol <= 0 or expiry_dte <= 0:
        raise ValueError("underlying_price, implied_vol, and expiry_dte must be positive.")

    strike_distance = _delta_to_strike_distance(
        underlying_price, target_delta, implied_vol, expiry_dte, direction
    )

    # Round to a sensible strike increment relative to price level.
    increment = 1.0 if underlying_price < 200 else 5.0

    if direction == "put":
        short_strike = _round_to_strike_increment(
            underlying_price - strike_distance, increment
        )
        long_strike = short_strike - increment
    else:
        short_strike = _round_to_strike_increment(
            underlying_price + strike_distance, increment
        )
        long_strike = short_strike + increment

    spread_width = abs(short_strike - long_strike)

    # Approximate net credit as a fraction of spread width, scaled by the
    # short leg's target delta (higher delta -> richer premium).
    credit_received = spread_width * min(target_delta * 1.5, 0.9)
    max_profit = credit_received
    max_loss = spread_width - credit_received

    return {
        "short_strike": float(short_strike),
        "long_strike": float(long_strike),
        "spread_width": float(spread_width),
        "max_profit": float(max_profit),
        "max_loss": float(max_loss),
    }


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
    if max_risk_usd <= 0:
        raise ValueError("max_risk_usd must be positive.")
    if credit_received < 0:
        raise ValueError("credit_received cannot be negative.")

    # Max loss per contract (100 shares) = (width - credit) * 100.
    # Solve for width given the max risk budget in USD.
    max_loss_per_share = max_risk_usd / 100.0
    width = max_loss_per_share + credit_received

    # Never widen past a sane fraction of the underlying price, and never
    # go below a minimal 1-point width.
    upper_bound = max(underlying_price * 0.10, 1.0)
    return float(min(max(width, 1.0), upper_bound))
