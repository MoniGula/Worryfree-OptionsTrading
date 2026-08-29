"""
WorryFree Options Trading Agent — daily entry point.

Orchestrates the scan -> decide -> execute loop once per trading day.
Run this module directly (python -m src.main) or invoke main()
from a scheduler or cloud function.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from config import settings
from src.execution.alpaca_client import AlpacaClient
from src.execution.chain_utils import (
    available_strikes,
    expiration_window,
    nearest_expiration,
    nearest_strike,
    snap_strikes,
    strike_above,
    strike_below,
)
from src.execution.order_builder import (
    attach_limit_price,
    build_credit_spread_order,
    build_iron_butterfly_order,
)
from src.features import regime as regime_features
from src.features import volatility as volatility_features
from src.strategy.decision_engine import classify_regime, route_strategy

logger = logging.getLogger("worryfree.main")
logging.basicConfig(level=logging.INFO)


def scan(symbols: list[str]) -> list[dict]:
    """
    Scan a list of underlying symbols and compute all required features.

    For each symbol, retrieves price history and option-chain data, then
    calculates volatility (realised vol, IV rank, VRP) and regime features
    (trend strength, range probability).

    Parameters
    ----------
    symbols:
        List of ticker symbols to evaluate (e.g. ["SPY", "QQQ"]).

    Returns
    -------
    list[dict]
        One feature record per symbol, keyed by the feature names produced
        by src.features.volatility and src.features.regime.
    """
    import pandas as pd
    import yfinance as yf

    params = settings.get_strategy_parameters()
    records: list[dict] = []

    for symbol in symbols:
        try:
            history = yf.Ticker(symbol).history(period="6mo")
            if history.empty or len(history) < 60:
                logger.warning("Skipping %s: insufficient price history.", symbol)
                continue

            closes = history["close"] if "close" in history else history["Close"]
            underlying_price = float(closes.iloc[-1])

            realised_vol = volatility_features.realized_volatility(closes, window=20)

            # Without a live options-chain vendor wired in yet, approximate
            # implied vol as realised vol plus a conservative vol-risk-premium
            # cushion; the real chain-derived ATM IV should replace this once
            # get_option_chain() is backed by live/paper Alpaca data.
            implied_vol = realised_vol * 1.15
            iv_high = realised_vol * 1.6
            iv_low = realised_vol * 0.8
            ivr = volatility_features.iv_rank(implied_vol, iv_high, iv_low)
            vrp = volatility_features.vol_risk_premium(implied_vol, realised_vol)

            trend = regime_features.trend_strength(closes, adx_period=14)
            range_prob = regime_features.range_probability(
                closes, horizon_days=params["max_days_to_expiry"]
            )

            records.append(
                {
                    "symbol": symbol,
                    "underlying_price": underlying_price,
                    "realised_vol": realised_vol,
                    "implied_vol": implied_vol,
                    "iv_rank": ivr,
                    "vol_risk_premium": vrp,
                    "trend_strength": trend,
                    "range_probability": range_prob,
                }
            )
        except Exception as exc:  # noqa: BLE001 - log and continue scanning others
            logger.error("Feature computation failed for %s: %s", symbol, exc)

    return records


def decide(feature_records: list[dict]) -> list[dict]:
    """
    Run the decision engine on each feature record and return trade specs.

    Calls src.strategy.decision_engine.classify_regime and
    src.strategy.decision_engine.route_strategy for every symbol, then
    filters out None results (no-trade signals).

    Parameters
    ----------
    feature_records:
        Output of scan.

    Returns
    -------
    list[dict]
        List of strategy specification dicts ready for order construction.
    """
    params = settings.get_strategy_parameters()
    expiry_dte = params["max_days_to_expiry"]
    expiry_date = (datetime.now(UTC) + timedelta(days=expiry_dte)).strftime("%Y-%m-%d")

    trade_specs: list[dict] = []
    for record in feature_records:
        regime = classify_regime(
            trend_strength=record["trend_strength"],
            iv_rank=record["iv_rank"],
            vol_risk_premium=record["vol_risk_premium"],
        )

        spec = route_strategy(
            regime=regime,
            iv_rank=record["iv_rank"],
            underlying_price=record["underlying_price"],
            expiry_dte=expiry_dte,
            implied_vol=record["implied_vol"],
        )

        if spec is None:
            logger.info("%s: no trade (regime=%s).", record["symbol"], regime)
            continue

        spec["symbol"] = record["symbol"]
        spec["expiry_date"] = expiry_date
        trade_specs.append(spec)
        logger.info(
            "%s: routed to %s (regime=%s, iv_rank=%.2f).",
            record["symbol"],
            spec["strategy"],
            regime,
            record["iv_rank"],
        )

    return trade_specs


def _align_spec_to_real_chain(client: AlpacaClient, spec: dict) -> dict:
    """
    Snap a model-derived trade specification onto real, listed Alpaca
    option contracts.

    credit_spread.select_strikes and iron_butterfly.select_strikes
    compute strikes and a target expiry purely from a delta/volatility
    model, with no knowledge of what strikes and expirations are actually
    listed for the underlying. Submitting an OCC symbol built from a
    purely theoretical strike/expiry combination fails with
    asset ... not found unless it happens to coincide with a real
    contract. This aligns the spec to the nearest real expiration and
    strikes before order construction.

    Parameters
    ----------
    client:
        Connected AlpacaClient used to query the live option chain.
    spec:
        Trade specification produced by decide.

    Returns
    -------
    dict
        A copy of spec with expiry_date and strikes snapped to
        real listed contracts.

    Raises
    ------
    ValueError
        If the underlying has no listed options within the search window.
    """
    symbol = spec["symbol"]
    target_expiry = spec["expiry_date"]

    chain = client.get_option_chain(symbol, target_expiry)
    resolved_expiry = target_expiry

    if not chain:
        gte, lte = expiration_window(target_expiry, window_days=14)
        expirations = client.list_expirations(symbol, gte, lte)
        if not expirations:
            raise ValueError(
                f"no listed option expirations for {symbol} within "
                f"14 days of {target_expiry}"
            )
        resolved_expiry = nearest_expiration(expirations, target_expiry)
        chain = client.get_option_chain(symbol, resolved_expiry)
        if not chain:
            raise ValueError(
                f"expiration {resolved_expiry} for {symbol} returned no contracts"
            )

    aligned = dict(spec)
    aligned["expiry_date"] = resolved_expiry

    if spec["strategy"] == "credit_spread":
        put_keys = ["short_strike", "long_strike"] if spec["direction"] == "put" else []
        call_keys = ["short_strike", "long_strike"] if spec["direction"] == "call" else []
        leg_strikes = available_strikes(
            chain, "put" if spec["direction"] == "put" else "call"
        )
        snapped = snap_strikes(chain, spec["strikes"], put_keys, call_keys)

        # A sparse strike grid can snap both legs to the same real strike,
        # collapsing the spread to zero width and zero defined risk. If
        # that happens, push the long strike out to the next real strike
        # further from the short strike so the spread stays a spread.
        if snapped["short_strike"] == snapped["long_strike"]:
            short = snapped["short_strike"]
            original_long = spec["strikes"]["long_strike"]
            if original_long < spec["strikes"]["short_strike"]:
                widened = strike_below(leg_strikes, short)
            else:
                widened = strike_above(leg_strikes, short)
            if widened is None:
                raise ValueError(
                    f"only one real strike available for {symbol} at "
                    f"{resolved_expiry}, cannot form a defined-risk spread"
                )
            snapped["long_strike"] = widened

        aligned["strikes"] = snapped
    elif spec["strategy"] == "iron_butterfly":
        # The short put and short call MUST share the same strike for this
        # to remain a butterfly (not just two independently-snapped legs
        # that happen to diverge), so snap the body to a strike that is
        # actually listed for both option types before snapping the wings.
        puts = available_strikes(chain, "put")
        calls = available_strikes(chain, "call")
        common_body_strikes = sorted(set(puts) & set(calls))
        if not common_body_strikes:
            raise ValueError(
                f"no strike listed as both put and call for {symbol} at "
                f"{resolved_expiry}"
            )
        original = spec["strikes"]
        body = nearest_strike(common_body_strikes, original["short_put"])

        # Wings must sit strictly outside the body on their respective
        # side, or the position stops being a defined-risk butterfly.
        long_put = strike_below(puts, body)
        long_call = strike_above(calls, body)
        if long_put is None or long_call is None:
            raise ValueError(
                f"no real strikes available outside the body ({body}) for "
                f"{symbol} at {resolved_expiry}, cannot form defined-risk wings"
            )
        aligned["strikes"] = {
            **original,
            "short_put": body,
            "short_call": body,
            "long_put": long_put,
            "long_call": long_call,
            "body_strike": body,
        }
    else:
        aligned["strikes"] = spec["strikes"]

    if resolved_expiry != target_expiry:
        logger.info(
            "%s: target expiry %s not listed, using nearest real expiry %s.",
            symbol,
            target_expiry,
            resolved_expiry,
        )

    return aligned


def execute(trade_specs: list[dict]) -> list[dict]:
    """
    Construct and submit orders for each approved trade specification.

    Uses src.execution.order_builder to build order dicts and
    src.execution.alpaca_client.AlpacaClient to submit them.

    Parameters
    ----------
    trade_specs:
        Output of decide.

    Returns
    -------
    list[dict]
        Order confirmation records as returned by the broker API.
    """
    client = AlpacaClient(
        api_key=settings.get_api_key(),
        api_secret=settings.get_api_secret(),
        base_url=settings.get_base_url(),
    )

    confirmations: list[dict] = []
    for spec in trade_specs:
        try:
            spec = _align_spec_to_real_chain(client, spec)
        except ValueError as exc:
            logger.error(
                "%s: no listed options found near target expiry, skipping. (%s)",
                spec["symbol"],
                exc,
            )
            continue

        strikes = spec["strikes"]

        if spec["strategy"] == "credit_spread":
            order = build_credit_spread_order(
                symbol=spec["symbol"],
                expiry_date=spec["expiry_date"],
                short_strike=strikes["short_strike"],
                long_strike=strikes["long_strike"],
                quantity=1,
                direction=spec["direction"],
            )
            limit = strikes["max_profit"]
        elif spec["strategy"] == "iron_butterfly":
            order = build_iron_butterfly_order(
                symbol=spec["symbol"],
                expiry_date=spec["expiry_date"],
                short_put=strikes["short_put"],
                short_call=strikes["short_call"],
                long_put=strikes["long_put"],
                long_call=strikes["long_call"],
                quantity=1,
            )
            limit = strikes["wing_width"] * 0.33
        else:
            logger.warning("Unknown strategy %s, skipping.", spec["strategy"])
            continue

        order = attach_limit_price(order, limit)

        try:
            confirmation = client.submit_order(order)
            confirmations.append(confirmation)
            logger.info(
                "Submitted %s for %s: %s", spec["strategy"], spec["symbol"], confirmation
            )
        except Exception as exc:  # noqa: BLE001 - log and continue with other trades
            logger.error(
                "Order submission failed for %s (%s): %s",
                spec["symbol"],
                spec["strategy"],
                exc,
            )

    return confirmations


def main() -> None:
    """
    Run the full daily scan-decide-execute loop.

    Loads configuration via config.settings, runs scan ->
    decide -> execute, and logs a summary of orders submitted.
    """
    params = settings.get_strategy_parameters()
    symbols = params["underlying_symbols"]

    logger.info("Starting WorryFree daily loop for %d symbols.", len(symbols))

    feature_records = scan(symbols)
    logger.info("Scanned %d/%d symbols successfully.", len(feature_records), len(symbols))

    trade_specs = decide(feature_records)
    logger.info("Decision engine approved %d trade(s).", len(trade_specs))

    confirmations = execute(trade_specs)
    logger.info("Submitted %d order(s) this run.", len(confirmations))


if __name__ == "__main__":
    main()
