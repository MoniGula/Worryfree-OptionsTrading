"""
WorryFree Options Trading Agent — daily entry point.

Orchestrates the scan -> decide -> execute loop once per trading day.
Run this module directly (``python -m src.main``) or invoke ``main()``
from a scheduler or cloud function.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from config import settings
from src.execution.alpaca_client import AlpacaClient
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
        List of ticker symbols to evaluate (e.g. ``["SPY", "QQQ"]``).

    Returns
    -------
    list[dict]
        One feature record per symbol, keyed by the feature names produced
        by ``src.features.volatility`` and ``src.features.regime``.
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

    Calls ``src.strategy.decision_engine.classify_regime`` and
    ``src.strategy.decision_engine.route_strategy`` for every symbol, then
    filters out ``None`` results (no-trade signals).

    Parameters
    ----------
    feature_records:
        Output of ``scan``.

    Returns
    -------
    list[dict]
        List of strategy specification dicts ready for order construction.
    """
    params = settings.get_strategy_parameters()
    expiry_dte = params["max_days_to_expiry"]
    expiry_date = (datetime.utcnow() + timedelta(days=expiry_dte)).strftime("%Y-%m-%d")

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


def execute(trade_specs: list[dict]) -> list[dict]:
    """
    Construct and submit orders for each approved trade specification.

    Uses ``src.execution.order_builder`` to build order dicts and
    ``src.execution.alpaca_client.AlpacaClient`` to submit them.

    Parameters
    ----------
    trade_specs:
        Output of ``decide``.

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

    Loads configuration via ``config.settings``, runs ``scan`` ->
    ``decide`` -> ``execute``, and logs a summary of orders submitted.
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
