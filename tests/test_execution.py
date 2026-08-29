"""Unit tests for src.execution.order_builder (pure order-construction logic,
no live network calls to Alpaca)."""

import pytest

from src.execution.order_builder import (
    attach_limit_price,
    build_credit_spread_order,
    build_iron_butterfly_order,
)


def test_build_credit_spread_order_structure():
    order = build_credit_spread_order(
        symbol="SPY",
        expiry_date="2026-09-04",
        short_strike=440.0,
        long_strike=435.0,
        quantity=2,
        direction="put",
    )
    assert order["order_class"] == "mleg"
    assert order["qty"] == 2
    assert len(order["legs"]) == 2
    assert order["legs"][0]["side"] == "sell"
    assert order["legs"][1]["side"] == "buy"
    assert "SPY" in order["legs"][0]["symbol"]
    assert "P" in order["legs"][0]["symbol"]


def test_build_credit_spread_order_invalid_quantity():
    with pytest.raises(ValueError):
        build_credit_spread_order("SPY", "2026-09-04", 440.0, 435.0, quantity=0)


def test_build_iron_butterfly_order_structure():
    order = build_iron_butterfly_order(
        symbol="QQQ",
        expiry_date="2026-09-04",
        short_put=380.0,
        short_call=380.0,
        long_put=375.0,
        long_call=385.0,
        quantity=1,
    )
    assert order["order_class"] == "mleg"
    assert len(order["legs"]) == 4
    sides = [leg["side"] for leg in order["legs"]]
    assert sides.count("sell") == 2
    assert sides.count("buy") == 2


def test_attach_limit_price_sets_value_without_mutating_input():
    order = build_credit_spread_order("SPY", "2026-09-04", 440.0, 435.0, 1)
    updated = attach_limit_price(order, 1.2345)

    assert updated["limit_price"] == pytest.approx(1.23)
    assert order["limit_price"] is None  # original dict left untouched
