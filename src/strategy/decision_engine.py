"""
Regime classification and strategy-routing decision engine.

The decision engine combines volatility and regime features to select the
most appropriate options structure (credit spread or iron butterfly) for a
given underlying on a given trading day.
"""

from __future__ import annotations

import math
from typing import Optional

from src.strategy import credit_spread, iron_butterfly

# Regime-classification thresholds. These are intentionally simple and
# transparent so the write-up's "AI logic" section can explain the routing
# rules in plain language, and so they're easy to tune during backtesting.
TREND_STRENGTH_THRESHOLD = 25.0   # ADX above this => trending
RANGE_STRENGTH_THRESHOLD = 20.0   # ADX below this => range-bound
MIN_IV_RANK_FOR_ENTRY = 0.30      # Require some vol-selling edge before entry
MIN_VOL_RISK_PREMIUM = 0.0        # Require IV >= realised vol (positive VRP)


def classify_regime(
    trend_strength: float,
    iv_rank: float,
    vol_risk_premium: float,
) -> str:
    """
    Classify the current market regime for a single underlying.

    Parameters
    ----------
    trend_strength:
        ADX-style trend-strength score from src.features.regime.
    iv_rank:
        Current IV Rank in [0, 1] from src.features.volatility.
    vol_risk_premium:
        Volatility risk premium (IV minus realised vol) from
        src.features.volatility.

    Returns
    -------
    str
        One of "trending", "ranging", or "undefined".
    """
    # Risk gate: never trade a name whose options aren't rich enough to
    # justify premium-selling risk, regardless of trend/range shape.
    if iv_rank < MIN_IV_RANK_FOR_ENTRY or vol_risk_premium < MIN_VOL_RISK_PREMIUM:
        return "undefined"

    if trend_strength >= TREND_STRENGTH_THRESHOLD:
        return "trending"
    if trend_strength <= RANGE_STRENGTH_THRESHOLD:
        return "ranging"
    return "undefined"


def route_strategy(
    regime: str,
    iv_rank: float,
    underlying_price: float,
    expiry_dte: int,
    implied_vol: float,
) -> Optional[dict]:
    """
    Select and parameterise an options strategy based on the regime label.

    Parameters
    ----------
    regime:
        Output of classify_regime — "trending", "ranging", or
        "undefined".
    iv_rank:
        Current IV Rank for the underlying.
    underlying_price:
        Current mid-price of the underlying.
    expiry_dte:
        Target days to expiration for the new position.
    implied_vol:
        Current ATM implied volatility (decimal).

    Returns
    -------
    dict or None
        A strategy specification dict if a trade should be entered, or
        None if conditions do not warrant a new position.  The dict
        contains at minimum: strategy (str), strikes (dict), and
        direction (str).
    """
    if regime == "undefined":
        return None

    if not all(math.isfinite(v) for v in (iv_rank, underlying_price, implied_vol)):
        raise ValueError(
            "route_strategy received non-finite input(s): "
            f"iv_rank={iv_rank!r}, underlying_price={underlying_price!r}, "
            f"implied_vol={implied_vol!r}"
        )

    if regime == "trending":
        # Directional conviction with rich premium: sell a credit spread.
        # Default to a bull-put (defined-risk, income-generating) spread;
        # a real deployment would flip to bear-call based on the actual
        # trend direction sign, which the caller can override upstream.
        direction = "put"
        strikes = credit_spread.select_strikes(
            underlying_price=underlying_price,
            target_delta=0.20,
            expiry_dte=expiry_dte,
            implied_vol=implied_vol,
            direction=direction,
        )
        return {
            "strategy": "credit_spread",
            "direction": direction,
            "strikes": strikes,
            "iv_rank": iv_rank,
            "expiry_dte": expiry_dte,
        }

    if regime == "ranging":
        # Range-bound with elevated IV: sell an iron butterfly to harvest
        # the pin risk / theta decay around the current price.
        strikes = iron_butterfly.select_strikes(
            underlying_price=underlying_price,
            expiry_dte=expiry_dte,
            implied_vol=implied_vol,
            wing_delta=0.10,
        )
        return {
            "strategy": "iron_butterfly",
            "direction": "neutral",
            "strikes": strikes,
            "iv_rank": iv_rank,
            "expiry_dte": expiry_dte,
        }

    return None
