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
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self._trading_client: Optional[Any] = None

    def _client(self) -> Any:
        """Lazily construct the underlying alpaca-py TradingClient."""
        if self._trading_client is None:
            from alpaca.trading.client import TradingClient

            paper = "paper" in self.base_url
            self._trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                paper=paper,
                url_override=self.base_url,
            )
        return self._trading_client

    def get_account(self) -> dict:
        """
        Retrieve the current account details (buying power, equity, etc.).

        Returns
        -------
        dict
            Account information as returned by the Alpaca API.
        """
        account = self._client().get_account()
        return dict(account)

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
        from alpaca.trading.requests import GetOptionContractsRequest

        request = GetOptionContractsRequest(
            underlying_symbols=[symbol.upper()],
            expiration_date=expiry_date,
        )
        response = self._client().get_option_contracts(request)
        contracts = getattr(response, "option_contracts", response)
        return [dict(contract) for contract in contracts]

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
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import (
            OptionLegRequest,
            LimitOrderRequest,
        )

        legs = [
            OptionLegRequest(
                symbol=leg["symbol"],
                side=OrderSide.BUY if leg["side"] == "buy" else OrderSide.SELL,
                ratio_qty=leg.get("ratio_qty", 1),
            )
            for leg in order["legs"]
        ]

        request = LimitOrderRequest(
            qty=order["qty"],
            order_class=OrderClass.MLEG,
            time_in_force=TimeInForce.DAY,
            limit_price=order.get("limit_price"),
            legs=legs,
        )

        submitted = self._client().submit_order(request)
        return dict(submitted)

    def get_positions(self) -> list[dict]:
        """
        Retrieve all open options positions for the account.

        Returns
        -------
        list[dict]
            List of open position records.
        """
        positions = self._client().get_all_positions()
        return [dict(position) for position in positions]

    def cancel_order(self, order_id: str) -> None:
        """
        Cancel an open order by its order ID.

        Parameters
        ----------
        order_id:
            Unique identifier of the order to cancel.
        """
        self._client().cancel_order_by_id(order_id)
