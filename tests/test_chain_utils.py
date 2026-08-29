"""Unit tests for src.execution.chain_utils (strike/expiry alignment
against real, listed option contracts — pure logic, no live network
calls to Alpaca)."""

import pytest

from src.execution.chain_utils import (
    available_strikes,
    expiration_window,
    nearest_expiration,
    nearest_strike,
    snap_strikes,
    strike_above,
    strike_below,
)


def _contract(strike, option_type):
    return {"strike_price": strike, "type": option_type}


SAMPLE_CHAIN = [
    _contract(300.0, "put"),
    _contract(310.0, "put"),
    _contract(320.0, "put"),
    _contract(300.0, "call"),
    _contract(310.0, "call"),
    _contract(330.0, "call"),
]


def test_available_strikes_filters_by_type():
    assert available_strikes(SAMPLE_CHAIN, "put") == [300.0, 310.0, 320.0]
    assert available_strikes(SAMPLE_CHAIN, "call") == [300.0, 310.0, 330.0]


def test_nearest_strike_picks_closest():
    assert nearest_strike([300.0, 310.0, 320.0], 308.0) == 310.0
    assert nearest_strike([300.0, 310.0, 320.0], 301.0) == 300.0


def test_nearest_strike_raises_on_empty():
    with pytest.raises(ValueError):
        nearest_strike([], 100.0)


def test_snap_strikes_maps_put_and_call_keys_independently():
    theoretical = {"short_strike": 305.0, "long_strike": 315.0}
    snapped = snap_strikes(SAMPLE_CHAIN, theoretical, put_keys=["short_strike", "long_strike"], call_keys=[])
    assert snapped["short_strike"] == 300.0 or snapped["short_strike"] == 310.0
    # both snap onto the put grid, not the call grid
    assert snapped["short_strike"] in available_strikes(SAMPLE_CHAIN, "put")
    assert snapped["long_strike"] in available_strikes(SAMPLE_CHAIN, "put")


def test_strike_below_and_above():
    strikes = [300.0, 310.0, 320.0]
    assert strike_below(strikes, 315.0) == 310.0
    assert strike_above(strikes, 315.0) == 320.0
    assert strike_below(strikes, 300.0) is None
    assert strike_above(strikes, 320.0) is None


def test_nearest_expiration_picks_closest_date():
    available = ["2026-08-28", "2026-09-04", "2026-09-11"]
    assert nearest_expiration(available, "2026-09-03") == "2026-09-04"
    assert nearest_expiration(available, "2026-08-30") == "2026-08-28"


def test_nearest_expiration_raises_on_empty():
    with pytest.raises(ValueError):
        nearest_expiration([], "2026-09-03")


def test_expiration_window_spans_target_date():
    gte, lte = expiration_window("2026-09-03", window_days=7)
    assert gte == "2026-08-27"
    assert lte == "2026-09-10"
