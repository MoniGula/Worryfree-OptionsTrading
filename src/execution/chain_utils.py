"""
Alignment helpers between model-derived theoretical strikes/expirations
and the real, tradable option contracts Alpaca actually lists.

src.strategy.credit_spread and src.strategy.iron_butterfly compute
strikes from a delta/volatility model with no knowledge of what strikes
and expirations are actually listed for a given underlying (each name has
its own strike increment and set of expiration dates). Submitting an OCC
symbol built from a purely theoretical strike/expiry combination fails
with asset ... not found unless it happens to coincide with a real
contract. This module snaps theoretical values onto the nearest real
contract so constructed OCC symbols always correspond to assets Alpaca
recognises.
"""

from __future__ import annotations

from datetime import date, timedelta


def available_strikes(chain: list[dict], option_type: str) -> list[float]:
    """Return the sorted list of strike prices for one contract type.

    Parameters
    ----------
    chain:
        List of option contract dicts as returned by
        AlpacaClient.get_option_chain.
    option_type:
        "put" or "call" (case-insensitive).
    """
    strikes: set[float] = set()
    for contract in chain:
        raw_type = contract.get("type", "")
        # The real Alpaca SDK returns a ContractType enum whose
        # str() is "ContractType.PUT" rather than "put";
        # prefer .value when present so this matches regardless of
        # whether chain came from the live SDK or a plain-dict fixture.
        contract_type = str(getattr(raw_type, "value", raw_type)).lower()
        if contract_type != option_type.lower():
            continue
        strike = contract.get("strike_price")
        if strike is not None:
            strikes.add(float(strike))
    return sorted(strikes)


def nearest_strike(strikes: list[float], target: float) -> float:
    """Return the strike closest to target.

    Raises
    ------
    ValueError
        If strikes is empty (no contracts of that type available).
    """
    if not strikes:
        raise ValueError("No available strikes to snap to.")
    return min(strikes, key=lambda s: abs(s - target))


def snap_strikes(
    chain: list[dict],
    strikes: dict,
    put_keys: list[str],
    call_keys: list[str],
) -> dict:
    """
    Return a copy of strikes with each listed key snapped to the
    nearest real strike of the matching option type available in
    chain.

    Parameters
    ----------
    chain:
        Contracts for a single (symbol, expiration) pair.
    strikes:
        Theoretical strike dict produced by a strategy module.
    put_keys, call_keys:
        Which keys in strikes represent put strikes vs. call strikes.
    """
    puts = available_strikes(chain, "put")
    calls = available_strikes(chain, "call")

    snapped = dict(strikes)
    for key in put_keys:
        if key in snapped:
            snapped[key] = nearest_strike(puts, snapped[key])
    for key in call_keys:
        if key in snapped:
            snapped[key] = nearest_strike(calls, snapped[key])
    return snapped


def strike_below(strikes: list[float], x: float) -> float | None:
    """Return the largest strike strictly less than x, or None."""
    candidates = [s for s in strikes if s < x]
    return max(candidates) if candidates else None


def strike_above(strikes: list[float], x: float) -> float | None:
    """Return the smallest strike strictly greater than x, or None."""
    candidates = [s for s in strikes if s > x]
    return min(candidates) if candidates else None


def nearest_expiration(available_dates: list[str], target_date: str) -> str:
    """Return the expiration date string in available_dates closest to
    target_date (both YYYY-MM-DD).

    Raises
    ------
    ValueError
        If available_dates is empty.
    """
    if not available_dates:
        raise ValueError("No available expirations to choose from.")
    target = date.fromisoformat(target_date)
    return min(
        available_dates,
        key=lambda d: abs((date.fromisoformat(d) - target).days),
    )


def expiration_window(target_date: str, window_days: int = 14) -> tuple[str, str]:
    """Return an (gte, lte) ISO date pair spanning window_days on
    either side of target_date, for use with
    AlpacaClient.list_expirations."""
    target = date.fromisoformat(target_date)
    gte = (target - timedelta(days=window_days)).isoformat()
    lte = (target + timedelta(days=window_days)).isoformat()
    return gte, lte
