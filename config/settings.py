"""
Configuration loader for API keys and strategy parameters.

Reads values from environment variables (optionally via a .env file loaded
by python-dotenv).  All downstream modules should import settings from here
rather than reading os.environ directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def get_api_key() -> str:
    """Return the Alpaca API key read from the API_KEY environment variable."""
    pass


def get_api_secret() -> str:
    """Return the Alpaca API secret read from the API_SECRET environment variable."""
    pass


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
    pass


def get_base_url() -> str:
    """
    Return the Alpaca base URL.

    Defaults to the paper-trading endpoint when BASE_URL is not set.
    """
    pass
