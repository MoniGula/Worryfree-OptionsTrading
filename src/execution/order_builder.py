"""
Multi-leg options order construction for the WorryFree trading agent.

Translates a strategy specification from the decision engine into a fully
formed order dict ready for submission via ``AlpacaClient.submit_order``.
"""

from __future__ import annotations


def build_credit_spread_order(
    symbol: str,
    expiry_date: str,
    short_strike: float,
    long_strike: float,
    quantity: int,
    direction: str = "put",
) -> dict:
    """
    Construct a two-leg credit spread order.

    Parameters
    ----------
    symbol:
        Underlying ticker symbol.
    expiry_date:
        Expiration date in ``YYYY-MM-DD`` format.
    short_strike:
        Strike price of the short leg.
    long_strike:
        Strike price of the long (hedge) leg.
    quantity:
        Number of spread contracts to trade.
    direction:
        ``"put"`` for bull-put; ``"call"`` for bear-call.

    Returns
    -------
    dict
        Alpaca-compatible multi-leg order specification.
    """
    pass


def build_iron_butterfly_order(
    symbol: str,
    expiry_date: str,
    short_put: float,
    short_call: float,
    long_put: float,
    long_call: float,
    quantity: int,
) -> dict:
    """
    Construct a four-leg iron butterfly order.

    Parameters
    ----------
    symbol:
        Underlying ticker symbol.
    expiry_date:
        Expiration date in ``YYYY-MM-DD`` format.
    short_put:
        Strike of the ATM short put.
    short_call:
        Strike of the ATM short call.
    long_put:
        Strike of the OTM long put wing.
    long_call:
        Strike of the OTM long call wing.
    quantity:
        Number of butterfly contracts to trade.

    Returns
    -------
    dict
        Alpaca-compatible multi-leg order specification.
    """
    pass


def attach_limit_price(order: dict, limit_price: float) -> dict:
    """
    Attach a net-debit / net-credit limit price to an existing order dict.

    Parameters
    ----------
    order:
        An order dict produced by one of the builder functions above.
    limit_price:
        The desired net limit price per spread (positive = credit).

    Returns
    -------
    dict
        The same order dict with the ``limit_price`` field populated.
    """
    pass
