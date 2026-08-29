"""
Alpaca Trading API wrapper for the WorryFree options-trading agent.

Provides a thin abstraction over the alpaca-py SDK and any MCP server
calls so that the rest of the codebase never imports alpaca-py directly.
"""

from __future__ import annotations

from typing import Any, Optional


class AlpacaClient:
    """Wrapper around the Alpaca broker API and MCP server interface."""

    def __init__(self, api_key: str, api_secret: str, base_url: str) -> None:
        """
        Initialise the Alpaca client with credentials.

        Parameters
        ----------
        api_key:
            Alpaca API key loaded from settings.
        api_secret:
            Alpaca API secret loaded from settings.
        base_url:
            Alpaca base URL (paper or live endpoint).
        """
        pass

    def get_account(self) -> dict:
        """
        Retrieve the current account details (buying power, equity, etc.).

        Returns
        -------
        dict
            Account information as returned by the Alpaca API.
        """
        pass

    def get_option_chain(self, symbol: str, expiry_date: str) -> list[dict]:
        """
        Fetch the full option chain for a given underlying and expiry.

        Parameters
        ----------
        symbol:
            Underlying ticker symbol (e.g. ``"SPY"``).
        expiry_date:
            Expiration date string in ``YYYY-MM-DD`` format.

        Returns
        -------
        list[dict]
            List of option contract records with strike, bid, ask, delta, etc.
        """
        pass

    def submit_order(self, order: dict) -> dict:
        """
        Submit a multi-leg options order to the Alpaca broker.

        Parameters
        ----------
        order:
            Order specification as constructed by ``order_builder``.

        Returns
        -------
        dict
            Order confirmation including order ID and status.
        """
        pass

    def get_positions(self) -> list[dict]:
        """
        Retrieve all open options positions for the account.

        Returns
        -------
        list[dict]
            List of open position records.
        """
        pass

    def cancel_order(self, order_id: str) -> None:
        """
        Cancel an open order by its order ID.

        Parameters
        ----------
        order_id:
            Unique identifier of the order to cancel.
        """
        pass
