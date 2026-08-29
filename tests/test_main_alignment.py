"""Unit tests for src.main._align_spec_to_real_chain — the logic that
snaps model-derived theoretical strikes/expirations onto real, listed
Alpaca option contracts before an order is built. Uses a fake client
(no live network calls to Alpaca)."""

import pytest

from src.main import _align_spec_to_real_chain


def _contract(strike, option_type):
    return {"strike_price": strike, "type": option_type}


class FakeAlpacaClient:
    """Duck-typed stand-in for AlpacaClient exposing only the two methods
    _align_spec_to_real_chain calls."""

    def __init__(self, chains_by_expiry, expirations=None):
        self._chains_by_expiry = chains_by_expiry
        self._expirations = expirations or []

    def get_option_chain(self, symbol, expiry_date):
        return self._chains_by_expiry.get(expiry_date, [])

    def list_expirations(self, symbol, expiration_date_gte, expiration_date_lte):
        return [
            d
            for d in self._expirations
            if expiration_date_gte <= d <= expiration_date_lte
        ]


SPARSE_CHAIN = [
    _contract(300.0, "put"),
    _contract(310.0, "put"),
    _contract(320.0, "put"),
    _contract(300.0, "call"),
    _contract(310.0, "call"),
    _contract(320.0, "call"),
]


def test_credit_spread_snaps_to_real_put_strikes():
    client = FakeAlpacaClient({"2026-09-04": SPARSE_CHAIN})
    spec = {
        "strategy": "credit_spread",
        "direction": "put",
        "symbol": "TEST",
        "expiry_date": "2026-09-04",
        "strikes": {"short_strike": 308.0, "long_strike": 297.0, "max_profit": 1.5},
    }

    aligned = _align_spec_to_real_chain(client, spec)

    assert aligned["strikes"]["short_strike"] in {300.0, 310.0, 320.0}
    assert aligned["strikes"]["long_strike"] in {300.0, 310.0, 320.0}
    assert aligned["strikes"]["short_strike"] != aligned["strikes"]["long_strike"]


def test_credit_spread_widens_when_both_legs_collapse_to_same_strike():
    # Both theoretical strikes are close enough to 310 that a naive
    # independent snap would collapse the spread to zero width.
    client = FakeAlpacaClient({"2026-09-04": SPARSE_CHAIN})
    spec = {
        "strategy": "credit_spread",
        "direction": "put",
        "symbol": "TEST",
        "expiry_date": "2026-09-04",
        "strikes": {"short_strike": 311.0, "long_strike": 309.0, "max_profit": 1.5},
    }

    aligned = _align_spec_to_real_chain(client, spec)

    assert aligned["strikes"]["short_strike"] != aligned["strikes"]["long_strike"]
    # long leg should have been pushed further away (below the short leg,
    # matching the original direction of the spread), not collapsed.
    assert aligned["strikes"]["long_strike"] < aligned["strikes"]["short_strike"]


def test_iron_butterfly_body_uses_strike_common_to_puts_and_calls():
    client = FakeAlpacaClient({"2026-09-04": SPARSE_CHAIN})
    spec = {
        "strategy": "iron_butterfly",
        "symbol": "TEST",
        "expiry_date": "2026-09-04",
        "strikes": {
            "short_put": 311.0,
            "short_call": 311.0,
            "long_put": 295.0,
            "long_call": 325.0,
            "body_strike": 311.0,
            "wing_width": 15.0,
        },
    }

    aligned = _align_spec_to_real_chain(client, spec)
    strikes = aligned["strikes"]

    assert strikes["short_put"] == strikes["short_call"]
    assert strikes["long_put"] < strikes["short_put"]
    assert strikes["long_call"] > strikes["short_call"]


def test_falls_back_to_nearest_real_expiration_when_target_not_listed():
    client = FakeAlpacaClient(
        chains_by_expiry={"2026-09-06": SPARSE_CHAIN},
        expirations=["2026-08-28", "2026-09-06", "2026-09-13"],
    )
    spec = {
        "strategy": "credit_spread",
        "direction": "put",
        "symbol": "TEST",
        "expiry_date": "2026-09-04",  # not directly listed
        "strikes": {"short_strike": 308.0, "long_strike": 297.0, "max_profit": 1.5},
    }

    aligned = _align_spec_to_real_chain(client, spec)

    assert aligned["expiry_date"] == "2026-09-06"


def test_falls_back_only_to_a_future_expiration_never_an_already_closed_one():
    # 2026-08-28 is in the list but is today/in the past relative to the
    # frozen "now" below, so it must never be selected even though it is
    # numerically closer to the (also past) target than the future date.
    client = FakeAlpacaClient(
        chains_by_expiry={"2026-09-04": SPARSE_CHAIN},
        expirations=["2026-08-21", "2026-08-28", "2026-09-04", "2026-09-11"],
    )
    spec = {
        "strategy": "credit_spread",
        "direction": "put",
        "symbol": "TEST",
        "expiry_date": "2026-08-29",  # closest listed date is 2026-08-28, but that's already past
        "strikes": {"short_strike": 308.0, "long_strike": 297.0, "max_profit": 1.5},
    }

    import src.main as main_module

    class FrozenDatetime(main_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return main_module.datetime(2026, 8, 29, 3, 59, tzinfo=tz)

    original_datetime = main_module.datetime
    main_module.datetime = FrozenDatetime
    try:
        aligned = _align_spec_to_real_chain(client, spec)
    finally:
        main_module.datetime = original_datetime

    assert aligned["expiry_date"] == "2026-09-04"


def test_raises_when_no_expirations_available_at_all():
    client = FakeAlpacaClient(chains_by_expiry={}, expirations=[])
    spec = {
        "strategy": "credit_spread",
        "direction": "put",
        "symbol": "TEST",
        "expiry_date": "2026-09-04",
        "strikes": {"short_strike": 308.0, "long_strike": 297.0, "max_profit": 1.5},
    }

    with pytest.raises(ValueError):
        _align_spec_to_real_chain(client, spec)
