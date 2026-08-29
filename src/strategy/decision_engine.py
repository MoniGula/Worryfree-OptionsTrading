"""
Regime classification and strategy-routing decision engine.

The decision engine combines volatility and regime features to select the
most appropriate options structure (credit spread or iron butterfly) for a
given underlying on a given trading day.
"""

from __future__ import annotations

from typing import Optional


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
        ADX-style trend-strength score from ``src.features.regime``.
    iv_rank:
        Current IV Rank in [0, 1] from ``src.features.volatility``.
    vol_risk_premium:
        Volatility risk premium (IV minus realised vol) from
        ``src.features.volatility``.

    Returns
    -------
    str
        One of ``"trending"``, ``"ranging"``, or ``"undefined"``.
    """
    pass


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
        Output of ``classify_regime`` — ``"trending"``, ``"ranging"``, or
        ``"undefined"``.
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
        ``None`` if conditions do not warrant a new position.  The dict
        contains at minimum: ``strategy`` (str), ``strikes`` (dict), and
        ``direction`` (str).
    """
    pass
