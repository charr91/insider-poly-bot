"""
Global pytest configuration and fixtures.
"""
import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List
import pandas as pd
import numpy as np

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings
from detection.volume_detector import VolumeDetector
from detection.whale_detector import WhaleDetector
from detection.price_detector import PriceDetector
from detection.coordination_detector import CoordinationDetector


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings configuration for testing."""
    return Settings(
        detection_thresholds={
            "volume_spike_multiplier": 5.0,
            "whale_threshold_usd": 10000.0,
            "price_change_threshold": 0.05,
            "coordination_time_window": 300
        },
        notification_channels={
            "enabled": False  # Disable notifications in tests
        },
        polymarket_config={
            "api_base_url": "https://gamma-api.polymarket.com",
            "websocket_url": "wss://ws-subscriptions-clob.polymarket.com"
        }
    )


@pytest.fixture
def volume_detector(mock_settings):
    """Create VolumeDetector instance for testing."""
    return VolumeDetector(mock_settings)


@pytest.fixture
def whale_detector(mock_settings):
    """Create WhaleDetector instance for testing."""
    return WhaleDetector(mock_settings)


@pytest.fixture
def price_detector(mock_settings):
    """Create PriceDetector instance for testing."""
    return PriceDetector(mock_settings)


@pytest.fixture
def coordination_detector(mock_settings):
    """Create CoordinationDetector instance for testing."""
    return CoordinationDetector(mock_settings)


@pytest.fixture
def sample_trade_data():
    """Generate sample trade data for testing."""
    return {
        "market_id": "test_market_123",
        "trade_id": "trade_456",
        "maker": "0x1234567890abcdef",
        "taker": "0xfedcba0987654321",
        "size": "1000.0",
        "price": "0.55",
        "side": "BUY",
        "timestamp": 1640995200,
        "outcome": "YES",
        "asset_id": "asset_789"
    }


@pytest.fixture
def sample_trades_df():
    """Generate pandas DataFrame with sample trades."""
    trades_data = [
        {
            "market_id": "market_1",
            "trade_id": f"trade_{i}",
            "maker": f"0x{'1' * 40}",
            "taker": f"0x{'2' * 40}",
            "size": 1000.0 + i * 100,
            "price": 0.5 + i * 0.01,
            "side": "BUY" if i % 2 == 0 else "SELL",
            "timestamp": 1640995200 + i * 60,
            "outcome": "YES",
            "asset_id": "asset_1"
        }
        for i in range(10)
    ]
    return pd.DataFrame(trades_data)


@pytest.fixture
def sample_whale_trades():
    """Generate sample whale trade data."""
    return [
        {
            "market_id": "market_whale",
            "trade_id": "whale_trade_1",
            "maker": "0xwhale123",
            "taker": "0xwhale456",
            "size": "50000.0",  # Large size
            "price": "0.60",
            "side": "BUY",
            "timestamp": 1640995200,
            "outcome": "YES",
            "asset_id": "asset_whale"
        },
        {
            "market_id": "market_whale",
            "trade_id": "whale_trade_2",
            "maker": "0xwhale456",
            "taker": "0xwhale789",
            "size": "75000.0",  # Very large size
            "price": "0.62",
            "side": "BUY",
            "timestamp": 1640995260,
            "outcome": "YES",
            "asset_id": "asset_whale"
        }
    ]


@pytest.fixture
def mock_websocket_messages():
    """Mock WebSocket messages for testing."""
    return [
        {
            "type": "trade",
            "data": {
                "market_id": "ws_market_1",
                "trade_id": "ws_trade_1",
                "maker": "0xwebsocket1",
                "taker": "0xwebsocket2",
                "size": "2000.0",
                "price": "0.45",
                "side": "SELL",
                "timestamp": 1640995300,
                "outcome": "NO"
            }
        },
        {
            "type": "order",
            "data": {
                "market_id": "ws_market_1",
                "order_id": "ws_order_1",
                "maker": "0xwebsocket3",
                "size": "5000.0",
                "price": "0.50",
                "side": "BUY",
                "timestamp": 1640995350,
                "outcome": "YES"
            }
        }
    ]


@pytest.fixture
def mock_api_response():
    """Mock API response data."""
    return {
        "trades": [
            {
                "id": "api_trade_1",
                "market": "api_market_1",
                "maker": "0xapi1",
                "taker": "0xapi2",
                "size": "1500.0",
                "price": "0.48",
                "side": "BUY",
                "timestamp": 1640995400,
                "outcome": "YES"
            }
        ],
        "next_cursor": "next_page_token"
    }


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for API testing."""
    with patch('aiohttp.ClientSession') as mock_session:
        mock_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_websocket():
    """Mock websocket connection for testing."""
    with patch('websocket.WebSocket') as mock_ws:
        mock_instance = Mock()
        mock_ws.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def isolate_tests(tmp_path, monkeypatch):
    """Isolate tests by using temporary directory and environment variables."""
    # Use temporary directory for any file operations
    monkeypatch.chdir(tmp_path)
    
    # Set test environment variables
    monkeypatch.setenv("POLYMARKET_API_KEY", "test_api_key")
    monkeypatch.setenv("ENVIRONMENT", "test")
    
    # Mock any external dependencies
    with patch('alerts.alert_manager.AlertManager'):
        yield


@pytest.fixture
def performance_baseline():
    """Baseline performance metrics for regression testing."""
    return {
        "volume_detection_time": 0.001,  # 1ms
        "whale_detection_time": 0.002,   # 2ms
        "price_detection_time": 0.001,   # 1ms
        "coordination_detection_time": 0.005,  # 5ms
        "memory_usage_mb": 50.0,  # 50MB
        "cpu_usage_percent": 5.0  # 5% CPU
    }