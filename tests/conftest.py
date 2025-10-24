"""
Pytest configuration and shared fixtures
"""

import pytest
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test configuration
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (may require external services)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (may take several seconds)"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Add integration marker to integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add slow marker to tests that might be slow
        if any(keyword in item.name for keyword in ["api", "websocket", "connection"]):
            item.add_marker(pytest.mark.slow)


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration"""
    return {
        'monitoring': {
            'max_markets': 5,
            'volume_threshold': 1000,
            'check_interval': 60,
            'sort_by_volume': True,
            'market_discovery_interval': 300,
            'analysis_interval': 60
        },
        'detection': {
            'volume_thresholds': {
                'volume_spike_multiplier': 3.0,
                'z_score_threshold': 3.0
            },
            'whale_thresholds': {
                'whale_threshold_usd': 10000,
                'coordination_threshold': 0.7,
                'min_whales_for_coordination': 3
            }
        },
        'alerts': {
            'discord_webhook': '',
            'min_severity': 'MEDIUM',
            'discord_min_severity': 'MEDIUM',
            'max_alerts_per_hour': 10
        },
        'debug': {
            'debug_mode': False,
            'show_normal_activity': False,
            'activity_report_interval': 300,
            'verbose_analysis': False,
            'websocket_activity_logging': False
        },
        'api': {
            'simulation_mode': True,
            'data_api_base_url': 'https://data-api.polymarket.com',
            'websocket_url': 'wss://ws-subscriptions-clob.polymarket.com/ws/market',
            'websocket_enabled': True
        }
    }


@pytest.fixture
def clean_environment():
    """Ensure clean test environment"""
    # Store original environment
    original_env = dict(os.environ)

    # Set test environment variables
    test_env = {
        'DISCORD_WEBHOOK': '',
        'CLOB_API_KEY': 'test_key',
        'CLOB_API_SECRET': 'test_secret',
        'CLOB_API_PASSPHRASE': 'test_pass',
        'POLYGON_PRIVATE_KEY': '0x' + '0' * 64,
        'FUNDER_ADDRESS': '0x' + '0' * 40
    }

    os.environ.update(test_env)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def test_database_path(tmp_path):
    """
    Provide temporary database path for testing.

    Returns absolute path to a temporary database file that will be
    cleaned up after the test completes.

    Usage:
        def test_something(test_database_path):
            db_path = test_database_path
            # Use db_path for testing
    """
    return str(tmp_path / "test_insider.db")


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Setup logging for tests"""
    import logging
    
    # Reduce log level for external libraries during tests
    logging.getLogger('websocket').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


# Integration tests now use mocked HTTP, so they can run by default without external services
# The --run-integration flag is kept for backwards compatibility but is no longer required
def pytest_addoption(parser):
    """Add command line options"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="(Deprecated) Integration tests now use mocked HTTP by default"
    )