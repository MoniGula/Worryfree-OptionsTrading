"""
Configuration loader for API keys and strategy parameters.

Reads values from environment variables (optionally via a .env file loaded
by python-dotenv).  All downstream modules should import settings from here
rather than reading os.environ directly.
"""

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_PAPER_BASE_URL = "https://paper-api.alpaca.markets"


def get_api_key() -> str:
    """Return the Alpaca API key read from the API_KEY environment variable."""
    api_key = os.environ.get("API_KEY")
    if not api_key:
        raise RuntimeError(
            "API_KEY is not set. Copy .env.example to .env and fill in your "
            "Alpaca paper-trading API key."
        )
    return api_key


def get_api_secret() -> str:
    """Return the Alpaca API secret read from the API_SECRET environment variable."""
    api_secret = os.environ.get("API_SECRET")
    if not api_secret:
        raise RuntimeError(
            "API_SECRET is not set. Copy .env.example to .env and fill in your "
            "Alpaca paper-trading API secret."
        )
    return api_secret


def get_strategy_parameters() -> dict:
    """
    Return a dictionary of strategy parameters sourced from environment variables.

    Expected keys include (but are not limited to):
        - UNDERLYING_SYMBOLS  : comma-separated list of tickers to scan
        - MAX_DAYS_TO_EXPIRY  : upper bound on DTE for new positions
        - MIN_DAYS_TO_EXPIRY  : lower bound on DTE for new positions
        - TARGET_DELTA        : absolute delta target for short strikes
        - MAX_POSITION_SIZE   : maximum notional risk per trade (USD)
    """
    symbols_raw = os.environ.get(
        "UNDERLYING_SYMBOLS", "SPY,QQQ,AAPL,MSFT,AMD,NVDA,TSLA"
    )
    symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]

    return {
        "underlying_symbols": symbols,
        "max_days_to_expiry": int(os.environ.get("MAX_DAYS_TO_EXPIRY", 5)),
        "min_days_to_expiry": int(os.environ.get("MIN_DAYS_TO_EXPIRY", 2)),
        "target_delta": float(os.environ.get("TARGET_DELTA", 0.20)),
        "max_position_size": float(os.environ.get("MAX_POSITION_SIZE", 2000.0)),
        # Fraction of total account equity that may be deployed as collateral
        # across all open positions at once (risk gate).
        "max_portfolio_collateral_pct": float(
            os.environ.get("MAX_PORTFOLIO_COLLATERAL_PCT", 0.65)
        ),
        # Fraction of max profit at which an open position should be closed
        # early to recycle capital.
        "profit_take_pct": float(os.environ.get("PROFIT_TAKE_PCT", 0.60)),
        # Minimum number of calendar days before earnings required to open
        # a new position (earnings risk gate).
        "min_days_to_earnings": int(os.environ.get("MIN_DAYS_TO_EARNINGS", 3)),
    }


def get_base_url() -> str:
    """
    Return the Alpaca base URL.

    Defaults to the paper-trading endpoint when BASE_URL is not set.
    """
    return os.environ.get("BASE_URL", DEFAULT_PAPER_BASE_URL)
