"""
Integration tests for DataAPIClient.
"""
import pytest
import requests
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time

from data_sources.data_api_client import DataAPIClient
from tests.fixtures.data_generators import MockDataGenerator


class TestDataAPIClientIntegration:
    """Integration tests for DataAPIClient with mocked external dependencies."""
    
    @pytest.fixture
    def client(self):
        """Create DataAPIClient instance for testing."""
        return DataAPIClient(base_url="https://test-api.polymarket.com")
    
    @pytest.fixture
    def mock_trades_response(self):
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
    
    def test_init_default_base_url(self):
        """Test DataAPIClient initialization with default URL."""
        client = DataAPIClient()
        assert client.base_url == "https://data-api.polymarket.com"
        assert client.trades_endpoint == "https://data-api.polymarket.com/trades"
        assert "User-Agent" in client.session.headers
        assert "Accept" in client.session.headers
    
    def test_init_custom_base_url(self):
        """Test DataAPIClient initialization with custom URL."""
        custom_url = "https://custom-api.example.com/"
        client = DataAPIClient(base_url=custom_url)
        assert client.base_url == "https://custom-api.example.com"
        assert client.trades_endpoint == "https://custom-api.example.com/trades"
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_get_market_trades_success(self, mock_get, client, mock_trades_response):
        """Test successful market trades retrieval."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = mock_trades_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        market_id = "test_market_123"
        trades = client.get_market_trades(market_id, limit=50, offset=10)
        
        # Verify request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == client.trades_endpoint
        assert call_args[1]['params']['market'] == market_id
        assert call_args[1]['params']['limit'] == 50
        assert call_args[1]['params']['offset'] == 10
        assert call_args[1]['timeout'] == 10
        
        # Verify response
        assert trades == mock_trades_response
        assert len(trades) == 10
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_get_market_trades_limit_enforcement(self, mock_get, client):
        """Test that API limit is enforced."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Request more than API limit
        client.get_market_trades("test_market", limit=1000)
        
        # Should cap at 500
        call_args = mock_get.call_args
        assert call_args[1]['params']['limit'] == 500
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_get_market_trades_request_exception(self, mock_get, client):
        """Test handling of request exceptions."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")
        
        trades = client.get_market_trades("test_market")
        
        # Should return empty list on error
        assert trades == []
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_get_market_trades_http_error(self, mock_get, client):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        trades = client.get_market_trades("invalid_market")
        
        # Should return empty list on HTTP error
        assert trades == []
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_get_recent_trades_with_markets(self, mock_get, client, mock_trades_response):
        """Test recent trades retrieval with specific markets."""
        mock_response = Mock()
        mock_response.json.return_value = mock_trades_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        market_ids = ["market_1", "market_2", "market_3"]
        trades = client.get_recent_trades(market_ids, limit=100)
        
        # Verify request parameters
        call_args = mock_get.call_args
        assert 'market' in call_args[1]['params']
        assert call_args[1]['params']['market'] == "market_1,market_2,market_3"
        assert call_args[1]['params']['limit'] == 100
        
        assert trades == mock_trades_response
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_get_recent_trades_no_markets(self, mock_get, client, mock_trades_response):
        """Test recent trades retrieval without market filter."""
        mock_response = Mock()
        mock_response.json.return_value = mock_trades_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        trades = client.get_recent_trades([], limit=50)
        
        # Verify no market parameter when empty list
        call_args = mock_get.call_args
        assert 'market' not in call_args[1]['params']
        assert call_args[1]['params']['limit'] == 50
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_get_all_recent_trades(self, mock_get, client, mock_trades_response):
        """Test retrieval of all recent trades."""
        mock_response = Mock()
        mock_response.json.return_value = mock_trades_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        trades = client.get_all_recent_trades(limit=200)
        
        # Verify request parameters
        call_args = mock_get.call_args
        assert call_args[1]['params'] == {'limit': 200}
        assert 'market' not in call_args[1]['params']
        
        assert trades == mock_trades_response
    
    @patch('data_sources.data_api_client.DataAPIClient.get_market_trades')
    def test_get_historical_trades_single_batch(self, mock_get_trades, client):
        """Test historical trades retrieval with single batch."""
        # Mock trades with timestamps within lookback window
        current_time = datetime.now()
        mock_trades = [
            {
                "id": f"trade_{i}",
                "timestamp": (current_time - timedelta(hours=i)).timestamp(),
                "price": "0.5",
                "size": "1000"
            }
            for i in range(5)
        ]
        
        mock_get_trades.return_value = mock_trades
        
        historical = client.get_historical_trades("test_market", lookback_hours=12)
        
        # Should call get_market_trades with correct parameters
        mock_get_trades.assert_called_with("test_market", limit=500, offset=0)
        assert len(historical) == 5
    
    @patch('data_sources.data_api_client.DataAPIClient.get_market_trades')
    def test_get_historical_trades_time_filtering(self, mock_get_trades, client):
        """Test historical trades time window filtering."""
        current_time = datetime.now()
        
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
        
        mock_get_trades.return_value = mock_trades
        
        historical = client.get_historical_trades("test_market", lookback_hours=24)
        
        # Should include only trades within 24 hours
        assert len(historical) == 2
        assert all(trade["id"].startswith("recent") for trade in historical)
    
    @patch('data_sources.data_api_client.DataAPIClient.get_market_trades')
    @patch('time.sleep')
    def test_get_historical_trades_pagination(self, mock_sleep, mock_get_trades, client):
        """Test historical trades pagination."""
        # Mock multiple pages of responses
        page_1 = [{"id": f"trade_1_{i}", "timestamp": time.time()} for i in range(500)]
        page_2 = [{"id": f"trade_2_{i}", "timestamp": time.time()} for i in range(300)]
        
        mock_get_trades.side_effect = [page_1, page_2]
        
        historical = client.get_historical_trades("test_market", lookback_hours=24)
        
        # Should make multiple requests
        assert mock_get_trades.call_count == 2
        
        # First call with offset 0, second with offset 500
        calls = mock_get_trades.call_args_list
        assert calls[0][1]['offset'] == 0
        assert calls[1][1]['offset'] == 500
        
        # Should include rate limiting
        mock_sleep.assert_called_with(0.1)
        
        # Should return all trades
        assert len(historical) == 800
    
    @patch('data_sources.data_api_client.DataAPIClient.get_market_trades')
    def test_get_historical_trades_invalid_timestamps(self, mock_get_trades, client):
        """Test handling of invalid timestamps in historical data."""
        mock_trades = [
            {"id": "valid_1", "timestamp": time.time(), "price": "0.5"},
            {"id": "invalid_1", "timestamp": "invalid_format", "price": "0.5"},
            {"id": "invalid_2", "timestamp": None, "price": "0.5"},
            {"id": "valid_2", "timestamp": time.time(), "price": "0.5"},
        ]
        
        mock_get_trades.return_value = mock_trades
        
        historical = client.get_historical_trades("test_market", lookback_hours=24)
        
        # Should skip invalid timestamps and continue
        assert len(historical) == 2
        assert all(trade["id"].startswith("valid") for trade in historical)
    
    @patch('data_sources.data_api_client.DataAPIClient.get_market_trades')
    def test_get_historical_trades_iso_timestamps(self, mock_get_trades, client):
        """Test handling of ISO format timestamps."""
        current_time = datetime.now()
        mock_trades = [
            {
                "id": "iso_trade_1",
                "timestamp": (current_time - timedelta(hours=1)).isoformat() + "Z",
                "price": "0.5"
            },
            {
                "id": "iso_trade_2",
                "timestamp": (current_time - timedelta(hours=2)).isoformat() + "+00:00",
                "price": "0.5"
            }
        ]
        
        mock_get_trades.return_value = mock_trades
        
        historical = client.get_historical_trades("test_market", lookback_hours=24)
        
        # Should successfully parse ISO timestamps
        assert len(historical) == 2
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_test_connection_success(self, mock_get, client):
        """Test successful connection test."""
        mock_response = Mock()
        mock_response.json.return_value = [{"test": "data"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = client.test_connection()
        
        assert result is True
        
        # Verify request parameters
        call_args = mock_get.call_args
        assert call_args[1]['params']['limit'] == 1
        assert call_args[1]['timeout'] == 5
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_test_connection_failure(self, mock_get, client):
        """Test connection test failure."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection failed")
        
        result = client.test_connection()
        
        assert result is False
    
    def test_session_configuration(self, client):
        """Test that session is properly configured."""
        session = client.session
        
        assert isinstance(session, requests.Session)
        assert "User-Agent" in session.headers
        assert "PolymarketInsiderBot" in session.headers["User-Agent"]
        assert session.headers["Accept"] == "application/json"
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_timeout_configuration(self, mock_get, client):
        """Test that timeouts are properly configured."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test different methods
        client.get_market_trades("test")
        client.get_recent_trades(["test"])
        client.get_all_recent_trades()
        client.test_connection()
        
        # Verify all calls include timeout
        calls = mock_get.call_args_list
        assert len(calls) == 4
        
        # First three calls should have timeout=10 (market_trades, recent_trades, all_recent_trades)
        for i in range(3):
            assert calls[i][1]['timeout'] == 10
            
        # Last call should have timeout=5 (test_connection)
        assert calls[3][1]['timeout'] == 5
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_error_logging(self, mock_get, client, caplog):
        """Test that errors are properly logged."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")
        
        with caplog.at_level("ERROR"):
            trades = client.get_market_trades("test_market")
        
        assert trades == []
        assert "Error fetching trades" in caplog.text
        assert "Network error" in caplog.text
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_json_parsing_error(self, mock_get, client):
        """Test handling of JSON parsing errors."""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        trades = client.get_market_trades("test_market")
        
        # Should handle JSON parsing error gracefully
        assert trades == []
    
    @pytest.mark.parametrize("limit,expected", [
        (10, 10),
        (500, 500),
        (1000, 500),  # Should cap at 500
        (0, 0),
        (-1, -1),  # Negative values passed through (API will handle)
    ])
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_limit_parameter_handling(self, mock_get, client, limit, expected):
        """Test limit parameter handling across different values."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client.get_market_trades("test", limit=limit)
        
        call_args = mock_get.call_args
        assert call_args[1]['params']['limit'] == expected
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_concurrent_requests(self, mock_get, client):
        """Test handling of concurrent requests."""
        import threading
        
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        results = []
        
        def make_request():
            trades = client.get_market_trades("test_market")
            results.append(len(trades))
        
        # Make concurrent requests
        threads = [threading.Thread(target=make_request) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # All requests should complete successfully
        assert len(results) == 5
        assert all(result == 0 for result in results)
        assert mock_get.call_count == 5
    
    @patch('data_sources.data_api_client.requests.Session.get')
    def test_large_response_handling(self, mock_get, client):
        """Test handling of large API responses."""
        # Create large mock response
        large_response = [
            {"id": f"trade_{i}", "market": "test", "price": "0.5", "size": "1000"}
            for i in range(1000)
        ]
        
        mock_response = Mock()
        mock_response.json.return_value = large_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        trades = client.get_market_trades("test_market", limit=500)
        
        # Should handle large responses
        assert len(trades) == 1000
        assert all("id" in trade for trade in trades)
    
    def test_url_construction(self):
        """Test proper URL construction from base URL."""
        test_cases = [
            ("https://api.example.com", "https://api.example.com/trades"),
            ("https://api.example.com/", "https://api.example.com/trades"),
            ("https://api.example.com/v1", "https://api.example.com/v1/trades"),
            ("https://api.example.com/v1/", "https://api.example.com/v1/trades"),
        ]
        
        for base_url, expected_endpoint in test_cases:
            client = DataAPIClient(base_url=base_url)
            assert client.trades_endpoint == expected_endpoint