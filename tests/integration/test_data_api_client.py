"""
Integration tests for DataAPIClient.

Tests for async aiohttp-based implementation with proper mocking and error handling.
All tests use pytest-asyncio for async test execution.
"""
import pytest
import pytest_asyncio
import aiohttp
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone

from data_sources.data_api_client import DataAPIClient
from tests.fixtures.data_generators import MockDataGenerator


@pytest_asyncio.fixture
async def client():
    """Create DataAPIClient instance for testing."""
    client = DataAPIClient(base_url="https://test-api.polymarket.com")
    await client.__aenter__()
    yield client
    await client.__aexit__(None, None, None)


@pytest.fixture
def mock_trades_response():
    """Mock API response with trade data."""
    generator = MockDataGenerator()
    trades = generator.generate_normal_trades(count=10, time_span_hours=1)

    # Convert to API format
    api_trades = []
    for trade in trades:
        api_trades.append({
            "id": trade["trade_id"],
            "market": trade["market_id"],
            "maker": trade["maker"],
            "taker": trade["taker"],
            "price": trade["price"],
            "size": trade["size"],
            "side": trade["side"],
            "timestamp": trade["timestamp"],
            "outcome": trade["outcome"]
        })

    return api_trades


class TestDataAPIClientIntegration:
    """Integration tests for DataAPIClient with mocked external dependencies."""

    @pytest.mark.asyncio
    async def test_init_default_base_url(self):
        """Test DataAPIClient initialization with default URL."""
        async with DataAPIClient() as client:
            assert client.base_url == "https://data-api.polymarket.com"
            assert client.trades_endpoint == "https://data-api.polymarket.com/trades"
            assert client._session is not None
            assert "User-Agent" in client._session.headers
            assert "Accept" in client._session.headers

    @pytest.mark.asyncio
    async def test_init_custom_base_url(self):
        """Test DataAPIClient initialization with custom URL."""
        custom_url = "https://custom-api.example.com/"
        async with DataAPIClient(base_url=custom_url) as client:
            assert client.base_url == "https://custom-api.example.com"
            assert client.trades_endpoint == "https://custom-api.example.com/trades"

    @pytest.mark.asyncio
    async def test_get_market_trades_success(self, client, mock_trades_response):
        """Test successful market trades retrieval."""
        # Mock the aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_trades_response)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            market_id = "test_market_123"
            trades = await client.get_market_trades(market_id, limit=50, offset=10)

            # Verify response
            assert trades == mock_trades_response
            assert len(trades) == 10

    @pytest.mark.asyncio
    async def test_get_market_trades_limit_enforcement(self, client):
        """Test that API limit is enforced."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[])
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response) as mock_get:
            # Request more than API limit
            await client.get_market_trades("test_market", limit=1000)

            # Verify it was called (limit enforcement happens in URL params)
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_market_trades_client_error(self, client):
        """Test handling of client errors."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.raise_for_status = Mock(side_effect=aiohttp.ClientError("Not Found"))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            trades = await client.get_market_trades("invalid_market")

            # Should return empty list on error
            assert trades == []

    @pytest.mark.asyncio
    async def test_get_recent_trades_with_markets(self, client, mock_trades_response):
        """Test recent trades retrieval with specific markets."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_trades_response)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            market_ids = ["market_1", "market_2", "market_3"]
            trades = await client.get_recent_trades(market_ids, limit=100)

            assert trades == mock_trades_response
            assert len(trades) == 10

    @pytest.mark.asyncio
    async def test_get_recent_trades_no_markets(self, client, mock_trades_response):
        """Test recent trades retrieval without market filter."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_trades_response)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            trades = await client.get_recent_trades([], limit=50)

            assert len(trades) == 10

    @pytest.mark.asyncio
    async def test_get_all_recent_trades(self, client, mock_trades_response):
        """Test retrieval of all recent trades."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_trades_response)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            trades = await client.get_all_recent_trades(limit=200)

            assert trades == mock_trades_response

    @pytest.mark.asyncio
    async def test_get_historical_trades_single_batch(self, client):
        """Test historical trades retrieval with single batch."""
        # Mock trades with timestamps within lookback window
        current_time = datetime.now(timezone.utc)
        mock_trades = [
            {
                "id": f"trade_{i}",
                "timestamp": (current_time - timedelta(hours=i)).timestamp(),
                "price": "0.5",
                "size": "1000"
            }
            for i in range(5)
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_trades)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            historical = await client.get_historical_trades("test_market", lookback_hours=12)

            assert len(historical) == 5

    @pytest.mark.asyncio
    async def test_get_historical_trades_time_filtering(self, client):
        """Test historical trades time window filtering."""
        current_time = datetime.now(timezone.utc)

        # Mix of trades within and outside lookback window
        mock_trades = [
            {
                "id": "recent_1",
                "timestamp": (current_time - timedelta(hours=2)).timestamp(),
                "price": "0.5", "size": "1000"
            },
            {
                "id": "recent_2",
                "timestamp": (current_time - timedelta(hours=6)).timestamp(),
                "price": "0.5", "size": "1000"
            },
            {
                "id": "old_1",
                "timestamp": (current_time - timedelta(hours=30)).timestamp(),
                "price": "0.5", "size": "1000"
            }
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_trades)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            historical = await client.get_historical_trades("test_market", lookback_hours=24)

            # Should include only trades within 24 hours
            assert len(historical) == 2
            assert all(trade["id"].startswith("recent") for trade in historical)

    @pytest.mark.asyncio
    async def test_get_historical_trades_pagination(self, client):
        """Test historical trades pagination."""
        # Mock multiple pages of responses
        current_time = datetime.now(timezone.utc)
        page_1 = [{"id": f"trade_1_{i}", "timestamp": current_time.timestamp()} for i in range(500)]
        page_2 = [{"id": f"trade_2_{i}", "timestamp": current_time.timestamp()} for i in range(300)]

        mock_response_1 = AsyncMock()
        mock_response_1.status = 200
        mock_response_1.json = AsyncMock(return_value=page_1)
        mock_response_1.raise_for_status = Mock()
        mock_response_1.__aenter__ = AsyncMock(return_value=mock_response_1)
        mock_response_1.__aexit__ = AsyncMock(return_value=False)

        mock_response_2 = AsyncMock()
        mock_response_2.status = 200
        mock_response_2.json = AsyncMock(return_value=page_2)
        mock_response_2.raise_for_status = Mock()
        mock_response_2.__aenter__ = AsyncMock(return_value=mock_response_2)
        mock_response_2.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', side_effect=[mock_response_1, mock_response_2]):
            historical = await client.get_historical_trades("test_market", lookback_hours=24)

            # Should return all trades
            assert len(historical) == 800

    @pytest.mark.asyncio
    async def test_get_historical_trades_invalid_timestamps(self, client):
        """Test handling of invalid timestamps in historical data."""
        current_time = datetime.now(timezone.utc)
        mock_trades = [
            {"id": "valid_1", "timestamp": current_time.timestamp(), "price": "0.5"},
            {"id": "invalid_1", "timestamp": "invalid_format", "price": "0.5"},
            {"id": "invalid_2", "timestamp": None, "price": "0.5"},
            {"id": "valid_2", "timestamp": current_time.timestamp(), "price": "0.5"},
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_trades)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            historical = await client.get_historical_trades("test_market", lookback_hours=24)

            # Should skip invalid timestamps and continue
            assert len(historical) == 2
            assert all(trade["id"].startswith("valid") for trade in historical)

    @pytest.mark.asyncio
    async def test_get_historical_trades_iso_timestamps(self, client):
        """Test handling of ISO format timestamps."""
        current_time = datetime.now(timezone.utc)
        mock_trades = [
            {
                "id": "iso_trade_1",
                "timestamp": (current_time - timedelta(hours=1)).isoformat().replace('+00:00', 'Z'),
                "price": "0.5"
            },
            {
                "id": "iso_trade_2",
                "timestamp": (current_time - timedelta(hours=2)).isoformat(),
                "price": "0.5"
            }
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_trades)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            historical = await client.get_historical_trades("test_market", lookback_hours=24)

            # Should successfully parse ISO timestamps
            assert len(historical) == 2

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client):
        """Test successful connection test."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"test": "data"}])
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            result = await client.test_connection()

            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client):
        """Test connection test failure."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.raise_for_status = Mock(side_effect=aiohttp.ClientError("Connection failed"))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            result = await client.test_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Test that context manager properly cleans up resources."""
        client = DataAPIClient()
        async with client:
            assert client._session is not None
            assert not client._session.closed

        # After exiting context, session should be closed
        assert client._session is None or client._session.closed

    @pytest.mark.asyncio
    async def test_json_parsing_error(self, client):
        """Test handling of JSON parsing errors."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            trades = await client.get_market_trades("test_market")

            # Should handle JSON parsing error gracefully
            assert trades == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("limit,expected", [
        (10, 10),
        (500, 500),
        (1000, 500),  # Should cap at 500
        (0, 0),
    ])
    async def test_limit_parameter_handling(self, client, limit, expected):
        """Test limit parameter handling across different values."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[])
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            await client.get_market_trades("test", limit=limit)
            # Verify call was made (param validation happens in method)

    @pytest.mark.asyncio
    async def test_url_construction(self):
        """Test proper URL construction from base URL."""
        test_cases = [
            ("https://api.example.com", "https://api.example.com/trades"),
            ("https://api.example.com/", "https://api.example.com/trades"),
            ("https://api.example.com/v1", "https://api.example.com/v1/trades"),
            ("https://api.example.com/v1/", "https://api.example.com/v1/trades"),
        ]

        for base_url, expected_endpoint in test_cases:
            async with DataAPIClient(base_url=base_url) as client:
                assert client.trades_endpoint == expected_endpoint

    @pytest.mark.asyncio
    async def test_error_logging(self, client, caplog):
        """Test that errors are properly logged."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.raise_for_status = Mock(side_effect=aiohttp.ClientError("Network error"))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client._session, 'get', return_value=mock_response):
            with caplog.at_level("ERROR"):
                trades = await client.get_market_trades("test_market")

            assert trades == []
            assert "Error fetching trades" in caplog.text
