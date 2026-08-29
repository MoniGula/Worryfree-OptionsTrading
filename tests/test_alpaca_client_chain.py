"""Unit tests for AlpacaClient.get_option_chain / list_expirations
pagination handling (no live network calls — the underlying SDK trading
client is mocked)."""

from unittest.mock import MagicMock

from src.execution.alpaca_client import AlpacaClient


class _FakeContract(dict):
    """dict subclass so dict(contract) in the client just returns
    itself, mirroring how a real pydantic model behaves under dict()."""


def _make_client_with_mocked_sdk(pages):
    """Return an AlpacaClient whose _client() is a MagicMock whose
    get_option_contracts yields one page per call from pages."""
    client = AlpacaClient(api_key="k", api_secret="s", base_url="https://paper-api.alpaca.markets")

    mock_sdk = MagicMock()
    responses = []
    for contracts, next_token in pages:
        resp = MagicMock()
        resp.option_contracts = contracts
        resp.next_page_token = next_token
        responses.append(resp)
    mock_sdk.get_option_contracts.side_effect = responses

    client._trading_client = mock_sdk
    return client, mock_sdk


def test_get_option_chain_follows_pagination_until_exhausted():
    # Simulates a deep chain (e.g. SPY) split across two pages: first page
    # all calls, second page all puts — exactly the failure mode this
    # fixes (a single unpaginated page returning only one option type).
    page1 = ([_FakeContract(strike_price=100.0, type="call")], "token-2")
    page2 = ([_FakeContract(strike_price=100.0, type="put")], None)
    client, mock_sdk = _make_client_with_mocked_sdk([page1, page2])

    chain = client.get_option_chain("SPY", "2026-09-04")

    assert len(chain) == 2
    assert mock_sdk.get_option_contracts.call_count == 2
    types = {c["type"] for c in chain}
    assert types == {"call", "put"}


def test_get_option_chain_single_page_stops_immediately():
    page1 = ([_FakeContract(strike_price=50.0, type="put")], None)
    client, mock_sdk = _make_client_with_mocked_sdk([page1])

    chain = client.get_option_chain("AAPL", "2026-09-04")

    assert len(chain) == 1
    assert mock_sdk.get_option_contracts.call_count == 1


def test_list_expirations_follows_pagination_until_exhausted():
    page1 = ([_FakeContract(strike_price=100.0, type="call", expiration_date="2026-08-28")], "token-2")
    page2 = ([_FakeContract(strike_price=100.0, type="put", expiration_date="2026-09-04")], None)
    client, mock_sdk = _make_client_with_mocked_sdk([page1, page2])

    dates = client.list_expirations("SPY", "2026-08-20", "2026-09-17")

    assert dates == ["2026-08-28", "2026-09-04"]
    assert mock_sdk.get_option_contracts.call_count == 2
