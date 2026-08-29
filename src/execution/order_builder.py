"""
Multi-leg options order construction for the WorryFree trading agent.

Translates a strategy specification from the decision engine into a fully
formed order dict ready for submission via ``AlpacaClient.submit_order``.

Order dicts follow the shape expected by Alpaca's multi-leg (MLeg) options
order endpoint: a top-level market/limit order envelope with a ``legs``
list, each leg carrying its own OCC-style option symbol, side, and ratio.
"""

from __future__ import annotations

from datetime import datetime


def _occ_option_symbol(
    symbol: str, expiry_date: str, option_type: str, strike: float
) -> str:
    """
    Build an OCC-style option symbol, e.g. ``SPY240621P00450000``.

    Parameters
    ----------
    symbol:
        Underlying ticker symbol.
    expiry_date:
        Expiration date in ``YYYY-MM-DD`` format.
    option_type:
        ``"put"`` or ``"call"``.
    strike:
        Strike price.
    """
    exp = datetime.strptime(expiry_date, "%Y-%m-%d").strftime("%y%m%d")
    type_code = "P" if option_type == "put" else "C"
    strike_code = f"{int(round(strike * 1000)):08d}"
    return f"{symbol.upper()}{exp}{type_code}{strike_code}"


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
    if direction not in ("put", "call"):
        raise ValueError("direction must be 'put' or 'call'.")
    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    short_symbol = _occ_option_symbol(symbol, expiry_date, direction, short_strike)
    long_symbol = _occ_option_symbol(symbol, expiry_date, direction, long_strike)

    return {
        "order_class": "mleg",
        "type": "limit",
        "time_in_force": "day",
        "qty": quantity,
        "strategy": "credit_spread",
        "direction": direction,
        "underlying_symbol": symbol.upper(),
        "expiry_date": expiry_date,
        "legs": [
            {
                "symbol": short_symbol,
                "side": "sell",
                "position_intent": "sell_to_open",
                "ratio_qty": 1,
            },
            {
                "symbol": long_symbol,
                "side": "buy",
                "position_intent": "buy_to_open",
                "ratio_qty": 1,
            },
        ],
        "limit_price": None,
    }


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
    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    short_put_symbol = _occ_option_symbol(symbol, expiry_date, "put", short_put)
    short_call_symbol = _occ_option_symbol(symbol, expiry_date, "call", short_call)
    long_put_symbol = _occ_option_symbol(symbol, expiry_date, "put", long_put)
    long_call_symbol = _occ_option_symbol(symbol, expiry_date, "call", long_call)

    return {
        "order_class": "mleg",
        "type": "limit",
        "time_in_force": "day",
        "qty": quantity,
        "strategy": "iron_butterfly",
        "direction": "neutral",
        "underlying_symbol": symbol.upper(),
        "expiry_date": expiry_date,
        "legs": [
            {
                "symbol": short_put_symbol,
                "side": "sell",
                "position_intent": "sell_to_open",
                "ratio_qty": 1,
            },
            {
                "symbol": short_call_symbol,
                "side": "sell",
                "position_intent": "sell_to_open",
                "ratio_qty": 1,
            },
            {
                "symbol": long_put_symbol,
                "side": "buy",
                "position_intent": "buy_to_open",
                "ratio_qty": 1,
            },
            {
                "symbol": long_call_symbol,
                "side": "buy",
                "position_intent": "buy_to_open",
                "ratio_qty": 1,
            },
        ],
        "limit_price": None,
    }


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
    order = dict(order)
    order["limit_price"] = round(float(limit_price), 2)
    return order
