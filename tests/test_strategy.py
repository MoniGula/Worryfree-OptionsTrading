"""Unit tests for src.strategy.credit_spread, iron_butterfly, and decision_engine."""

import pytest

from src.strategy import credit_spread, iron_butterfly
from src.strategy.decision_engine import classify_regime, route_strategy


def test_credit_spread_select_strikes_put_below_price():
    result = credit_spread.select_strikes(
        underlying_price=450.0,
        target_delta=0.20,
        expiry_dte=3,
        implied_vol=0.18,
        direction="put",
    )
    assert result["short_strike"] < 450.0
    assert result["long_strike"] < result["short_strike"]
    assert result["spread_width"] > 0
    assert result["max_profit"] > 0
    assert result["max_loss"] > 0


def test_credit_spread_select_strikes_call_above_price():
    result = credit_spread.select_strikes(
        underlying_price=450.0,
        target_delta=0.20,
        expiry_dte=3,
        implied_vol=0.18,
        direction="call",
    )
    assert result["short_strike"] > 450.0
    assert result["long_strike"] > result["short_strike"]


def test_credit_spread_select_strikes_invalid_direction():
    with pytest.raises(ValueError):
        credit_spread.select_strikes(450.0, 0.2, 3, 0.18, direction="straddle")


def test_credit_spread_select_width_respects_risk_budget():
    width = credit_spread.select_width(
        underlying_price=450.0,
        max_risk_usd=200.0,
        short_strike=440.0,
        credit_received=1.0,
    )
    # max_loss_per_contract = (width - credit) * 100 should be <= max_risk_usd
    assert (width - 1.0) * 100 <= 200.0 + 1e-6


def test_iron_butterfly_select_strikes_symmetric_and_ordered():
    result = iron_butterfly.select_strikes(
        underlying_price=100.0, expiry_dte=3, implied_vol=0.25, wing_delta=0.10
    )
    assert result["long_put"] < result["body_strike"] < result["long_call"]
    assert result["short_put"] == result["short_call"] == result["body_strike"]
    assert result["wing_width"] > 0
    # Symmetric wings: equal distance from the body on both sides.
    assert (result["body_strike"] - result["long_put"]) == pytest.approx(
        result["long_call"] - result["body_strike"]
    )


def test_iron_butterfly_select_wing_width_positive_and_bounded():
    width = iron_butterfly.select_wing_width(
        underlying_price=100.0, implied_vol=0.30, expiry_dte=5, target_credit_ratio=0.33
    )
    assert width > 0
    assert width <= 100.0 * 0.15


def test_classify_regime_undefined_below_iv_rank_gate():
    regime = classify_regime(trend_strength=30, iv_rank=0.10, vol_risk_premium=0.05)
    assert regime == "undefined"


def test_classify_regime_undefined_on_negative_vrp():
    regime = classify_regime(trend_strength=30, iv_rank=0.50, vol_risk_premium=-0.02)
    assert regime == "undefined"


def test_classify_regime_trending_and_ranging():
    assert classify_regime(trend_strength=30, iv_rank=0.50, vol_risk_premium=0.03) == "trending"
    assert classify_regime(trend_strength=10, iv_rank=0.50, vol_risk_premium=0.03) == "ranging"


def test_route_strategy_none_for_undefined_regime():
    spec = route_strategy(
        regime="undefined",
        iv_rank=0.5,
        underlying_price=100.0,
        expiry_dte=3,
        implied_vol=0.2,
    )
    assert spec is None


def test_route_strategy_credit_spread_for_trending():
    spec = route_strategy(
        regime="trending",
        iv_rank=0.5,
        underlying_price=100.0,
        expiry_dte=3,
        implied_vol=0.2,
    )
    assert spec["strategy"] == "credit_spread"
    assert "short_strike" in spec["strikes"]


def test_route_strategy_iron_butterfly_for_ranging():
    spec = route_strategy(
        regime="ranging",
        iv_rank=0.5,
        underlying_price=100.0,
        expiry_dte=3,
        implied_vol=0.2,
    )
    assert spec["strategy"] == "iron_butterfly"
    assert "body_strike" in spec["strikes"]
