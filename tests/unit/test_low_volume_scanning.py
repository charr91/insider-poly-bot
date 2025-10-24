"""
Comprehensive unit tests for low-volume market scanning functionality.

Tests all configuration states, edge cases, and boundary values for the hybrid
monitoring system that detects insider whales in illiquid markets.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from typing import Dict, List

from market_monitor import MarketMonitor
from config.settings import Settings
from common.enums import AlertType


def get_complete_test_config(**overrides):
    """
    Helper function to create complete test configuration.
    Ensures all detector sections are present to avoid ValueError.

    Args:
        **overrides: Any config values to override

    Returns:
        Complete config dict
    """
    config = {
        'monitoring': {
            'volume_threshold': 1000,
            'max_markets': 50,
            'enable_low_volume_scanning': True,
            'max_low_volume_markets': 200,
            'whale_escalation_enabled': True,
            'monitor_all_markets': False,
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
                'whale_threshold_usd': 2000,
                'coordination_threshold': 0.7,
                'min_whales_for_coordination': 3
            },
            'price_thresholds': {
                'rapid_movement_pct': 15,
                'price_movement_std': 2.5,
                'volatility_spike_multiplier': 3.0,
                'momentum_threshold': 0.8
            },
            'coordination_thresholds': {
                'min_coordinated_wallets': 5,
                'coordination_time_window': 30,
                'directional_bias_threshold': 0.8,
                'burst_intensity_threshold': 3.0
            },
            'fresh_wallet_thresholds': {
                'min_bet_size_usd': 2000,
                'api_lookback_limit': 100,
                'max_previous_trades': 0
            }
        },
        'alerts': {
            'discord_webhook': '',
            'min_severity': 'MEDIUM',
            'discord_min_severity': 'MEDIUM',
            'max_alerts_per_hour': 10
        },
        'api': {
            'simulation_mode': True,
            'data_api_base_url': 'https://data-api.polymarket.com',
            'websocket_url': 'wss://ws-subscriptions-clob.polymarket.com/ws/market',
            'websocket_enabled': True
        }
    }

    # Apply overrides
    for key, value in overrides.items():
        if '.' in key:  # Nested key like 'monitoring.max_markets'
            parts = key.split('.')
            target = config
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
        else:
            config[key] = value

    return config


class TestLowVolumeConfiguration:
    """Test configuration loading and validation for low-volume scanning"""

    @pytest.mark.parametrize("enable_low_volume,max_low_volume,whale_escalation,monitor_all,expected_mode", [
        (True, 200, True, False, "hybrid_with_escalation"),
        (True, 200, False, False, "hybrid_no_escalation"),
        (True, None, True, False, "hybrid_unlimited"),
        (True, 0, True, False, "no_low_volume"),
        (False, 200, True, False, "high_volume_only"),
        (True, 200, True, True, "monitor_all_markets"),
    ])
    def test_configuration_loading(self, enable_low_volume, max_low_volume, whale_escalation, monitor_all, expected_mode):
        """Test Settings correctly loads all low-volume config combinations"""
        config = get_complete_test_config(
            **{
                'monitoring.enable_low_volume_scanning': enable_low_volume,
                'monitoring.max_low_volume_markets': max_low_volume,
                'monitoring.whale_escalation_enabled': whale_escalation,
                'monitoring.monitor_all_markets': monitor_all
            }
        )

        settings = Settings(config)

        assert settings.monitoring.enable_low_volume_scanning == enable_low_volume
        assert settings.monitoring.max_low_volume_markets == max_low_volume
        assert settings.monitoring.whale_escalation_enabled == whale_escalation
        assert settings.monitoring.monitor_all_markets == monitor_all

    @pytest.mark.parametrize("max_markets,max_low_volume", [
        (None, None),  # Both unlimited
        (None, 200),   # High unlimited, low limited
        (50, None),    # High limited, low unlimited
        (0, 0),        # Both zero (edge case - valid, means don't monitor)
        (1, 1),        # Minimum values
    ])
    def test_null_and_boundary_values(self, max_markets, max_low_volume):
        """Test configuration handles null/None and boundary values correctly"""
        config = get_complete_test_config(
            **{
                'monitoring.max_markets': max_markets,
                'monitoring.max_low_volume_markets': max_low_volume
            }
        )

        settings = Settings(config)

        assert settings.monitoring.max_markets == max_markets
        assert settings.monitoring.max_low_volume_markets == max_low_volume

        # Validation should pass for None and non-negative integers
        issues = settings.validate_settings()
        # Filter out the "private key" issue which is expected in test mode
        non_private_key_issues = [i for i in issues if 'private key' not in i.lower()]
        assert len(non_private_key_issues) == 0

    @pytest.mark.parametrize("invalid_value", [-1, -100])
    def test_negative_values_rejected(self, invalid_value):
        """Test that negative max_markets values fail validation"""
        config = get_complete_test_config(
            **{'monitoring.max_markets': invalid_value}
        )

        settings = Settings(config)
        issues = settings.validate_settings()

        # Should have validation issue about negative value
        assert any('non-negative' in issue.lower() for issue in issues)

    def test_config_summary_includes_new_fields(self):
        """Test get_config_summary includes all new monitoring fields"""
        config = get_complete_test_config()

        settings = Settings(config)
        summary = settings.get_config_summary()

        assert 'enable_low_volume_scanning' in summary['monitoring']
        assert 'max_low_volume_markets' in summary['monitoring']
        assert 'whale_escalation_enabled' in summary['monitoring']
        assert 'monitor_all_markets' in summary['monitoring']
        assert summary['monitoring']['enable_low_volume_scanning'] is True
        assert summary['monitoring']['max_low_volume_markets'] == 200


class TestMarketCategorization:
    """Test markets are correctly categorized into high/low volume"""

    @pytest.fixture
    def mock_markets(self):
        """Generate mock market data with varying volumes"""
        return [
            {'conditionId': 'high_vol_1', 'volume24hr': 5000, 'question': 'High Volume Market 1', 'clobTokenIds': []},
            {'conditionId': 'high_vol_2', 'volume24hr': 2000, 'question': 'High Volume Market 2', 'clobTokenIds': []},
            {'conditionId': 'threshold', 'volume24hr': 1000, 'question': 'Exactly at Threshold', 'clobTokenIds': []},
            {'conditionId': 'low_vol_1', 'volume24hr': 999, 'question': 'Low Volume Market 1', 'clobTokenIds': []},
            {'conditionId': 'low_vol_2', 'volume24hr': 500, 'question': 'Low Volume Market 2', 'clobTokenIds': []},
            {'conditionId': 'low_vol_3', 'volume24hr': 100, 'question': 'Low Volume Market 3', 'clobTokenIds': []},
        ]

    @pytest.mark.asyncio
    async def test_markets_categorized_by_volume_threshold(self, mock_markets):
        """Test markets split into high/low based on volume_threshold"""
        config = get_complete_test_config(
            **{
                'monitoring.volume_threshold': 1000,
                'monitoring.max_markets': 50,
                'monitoring.enable_low_volume_scanning': True,
                'monitoring.max_low_volume_markets': 200
            }
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    # Mock the HTTP response
                    mock_resp = AsyncMock()
                    mock_resp.status = 200
                    mock_resp.json = AsyncMock(return_value=mock_markets)

                    await monitor._process_markets_response(mock_resp, 1000, 50, True)

                    # High-volume: >= 1000 (should include 'high_vol_1', 'high_vol_2', 'threshold')
                    assert len(monitor.monitored_markets) == 3
                    assert 'high_vol_1' in monitor.monitored_markets
                    assert 'high_vol_2' in monitor.monitored_markets
                    assert 'threshold' in monitor.monitored_markets

                    # Low-volume: < 1000 (should include 'low_vol_1', 'low_vol_2', 'low_vol_3')
                    assert len(monitor.low_volume_markets) == 3
                    assert 'low_vol_1' in monitor.low_volume_markets
                    assert 'low_vol_2' in monitor.low_volume_markets
                    assert 'low_vol_3' in monitor.low_volume_markets

    @pytest.mark.asyncio
    async def test_max_markets_limit_enforced(self, mock_markets):
        """Test max_markets limits high-volume markets"""
        config = get_complete_test_config(
            **{
                'monitoring.volume_threshold': 1000,
                'monitoring.max_markets': 2,  # Limit to 2 high-volume
                'monitoring.enable_low_volume_scanning': True,
                'monitoring.max_low_volume_markets': 200
            }
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    mock_resp = AsyncMock()
                    mock_resp.status = 200
                    mock_resp.json = AsyncMock(return_value=mock_markets)

                    await monitor._process_markets_response(mock_resp, 1000, 2, True)

                    # Should be limited to 2 high-volume markets
                    assert len(monitor.monitored_markets) == 2

    @pytest.mark.asyncio
    async def test_max_low_volume_markets_limit_enforced(self, mock_markets):
        """Test max_low_volume_markets limits low-volume markets"""
        config = get_complete_test_config(
            **{
                'monitoring.volume_threshold': 1000,
                'monitoring.max_markets': 50,
                'monitoring.enable_low_volume_scanning': True,
                'monitoring.max_low_volume_markets': 2  # Limit to 2 low-volume
            }
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    mock_resp = AsyncMock()
                    mock_resp.status = 200
                    mock_resp.json = AsyncMock(return_value=mock_markets)

                    await monitor._process_markets_response(mock_resp, 1000, 50, True)

                    # Should be limited to 2 low-volume markets
                    assert len(monitor.low_volume_markets) == 2

    @pytest.mark.asyncio
    async def test_unlimited_markets_when_null(self, mock_markets):
        """Test null max values allow unlimited markets"""
        config = get_complete_test_config(
            **{
                'monitoring.volume_threshold': 1000,
                'monitoring.max_markets': None,  # Unlimited
                'monitoring.enable_low_volume_scanning': True,
                'monitoring.max_low_volume_markets': None  # Unlimited
            }
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    mock_resp = AsyncMock()
                    mock_resp.status = 200
                    mock_resp.json = AsyncMock(return_value=mock_markets)

                    await monitor._process_markets_response(mock_resp, 1000, None, True)

                    # Should include all markets without limits
                    assert len(monitor.monitored_markets) == 3  # All high-volume
                    assert len(monitor.low_volume_markets) == 3  # All low-volume

    @pytest.mark.asyncio
    async def test_monitor_all_markets_ignores_volume_threshold(self, mock_markets):
        """Test monitor_all_markets mode treats all markets as high-volume"""
        config = get_complete_test_config(
            **{
                'monitoring.volume_threshold': 1000,
                'monitoring.max_markets': None,
                'monitoring.monitor_all_markets': True,  # Override mode
                'monitoring.enable_low_volume_scanning': False
            }
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    mock_resp = AsyncMock()
                    mock_resp.status = 200
                    mock_resp.json = AsyncMock(return_value=mock_markets)

                    await monitor._process_markets_response(mock_resp, 1000, None, True)

                    # ALL markets should be in monitored_markets
                    assert len(monitor.monitored_markets) == len(mock_markets)
                    assert len(monitor.low_volume_markets) == 0

    @pytest.mark.asyncio
    async def test_low_volume_scanning_disabled(self, mock_markets):
        """Test enable_low_volume_scanning=false ignores low-volume markets"""
        config = get_complete_test_config(
            **{
                'monitoring.volume_threshold': 1000,
                'monitoring.max_markets': 50,
                'monitoring.enable_low_volume_scanning': False,  # Disabled
                'monitoring.max_low_volume_markets': 200
            }
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    mock_resp = AsyncMock()
                    mock_resp.status = 200
                    mock_resp.json = AsyncMock(return_value=mock_markets)

                    await monitor._process_markets_response(mock_resp, 1000, 50, True)

                    # Only high-volume markets
                    assert len(monitor.monitored_markets) == 3
                    assert len(monitor.low_volume_markets) == 0


class TestWhaleEscalation:
    """Test whale escalation logic and permanence"""

    @pytest.mark.asyncio
    async def test_escalate_market_moves_to_monitored(self):
        """Test _escalate_market() moves market from low to monitored_markets"""
        config = get_complete_test_config(
            **{
                'monitoring.whale_escalation_enabled': True,
                'monitoring.enable_low_volume_scanning': True
            }
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    # Add test low-volume market
                    market_id = 'test_market'
                    market_data = {
                        'conditionId': market_id,
                        'question': 'Test Low Volume Market',
                        'volume24hr': 500
                    }
                    monitor.low_volume_markets[market_id] = market_data

                    # Mock baseline initialization
                    monitor._initialize_market_baseline = AsyncMock()

                    await monitor._escalate_market(market_id, market_data)

                    # Market should be moved
                    assert market_id in monitor.monitored_markets
                    assert market_id not in monitor.low_volume_markets
                    assert market_id in monitor.escalated_markets

                    # Baseline should be initialized
                    monitor._initialize_market_baseline.assert_called_once()

    @pytest.mark.asyncio
    async def test_escalated_market_tracked_permanently(self):
        """Test escalated markets are tracked in escalated_markets set"""
        config = get_complete_test_config(
            **{'monitoring.whale_escalation_enabled': True}
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    market_id = 'test_market'
                    market_data = {'conditionId': market_id, 'question': 'Test', 'volume24hr': 500}
                    monitor.low_volume_markets[market_id] = market_data

                    monitor._initialize_market_baseline = AsyncMock()

                    await monitor._escalate_market(market_id, market_data)

                    assert market_id in monitor.escalated_markets
                    assert isinstance(monitor.escalated_markets, set)

    @pytest.mark.asyncio
    async def test_duplicate_escalation_handled_gracefully(self):
        """Test escalating already-escalated market doesn't cause errors"""
        config = get_complete_test_config()

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    market_id = 'test_market'
                    market_data = {'conditionId': market_id, 'question': 'Test', 'volume24hr': 500}
                    monitor.low_volume_markets[market_id] = market_data

                    monitor._initialize_market_baseline = AsyncMock()

                    # First escalation
                    await monitor._escalate_market(market_id, market_data)

                    # Second escalation (market already moved)
                    await monitor._escalate_market(market_id, market_data)

                    # Should handle gracefully
                    assert market_id in monitor.monitored_markets
                    assert market_id in monitor.escalated_markets


class TestLowVolumeAnalysis:
    """Test whale-only detection on low-volume markets"""

    @pytest.mark.asyncio
    async def test_analyze_market_for_whales_runs_whale_detector(self):
        """Test _analyze_market_for_whales runs whale detector"""
        config = get_complete_test_config(
            **{
                'monitoring.whale_escalation_enabled': True,
                'monitoring.enable_low_volume_scanning': True
            }
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    # Mock detectors and methods
                    monitor.whale_detector.detect_whale_activity = Mock(return_value={'anomaly': False})
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(return_value=[])
                    monitor._get_market_trades = AsyncMock(return_value=[{'price': 0.5, 'size': 1000}])

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    await monitor._analyze_market_for_whales('test', market_data)

                    monitor.whale_detector.detect_whale_activity.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_market_for_whales_runs_fresh_wallet_detector(self):
        """Test _analyze_market_for_whales runs fresh wallet detector"""
        config = get_complete_test_config()

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    monitor.whale_detector.detect_whale_activity = Mock(return_value={'anomaly': False})
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(return_value=[])
                    monitor._get_market_trades = AsyncMock(return_value=[{'price': 0.5, 'size': 1000}])

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    await monitor._analyze_market_for_whales('test', market_data)

                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity.assert_called_once()

    @pytest.mark.asyncio
    async def test_whale_detected_triggers_escalation(self):
        """Test whale detection triggers escalation when enabled"""
        config = get_complete_test_config(
            **{'monitoring.whale_escalation_enabled': True}
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    monitor.whale_detector.detect_whale_activity = Mock(return_value={'anomaly': True, 'whale_count': 2})
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(return_value=[])
                    monitor._get_market_trades = AsyncMock(return_value=[{'price': 0.5, 'size': 1000}])
                    monitor._escalate_market = AsyncMock()
                    monitor._determine_severity = Mock(return_value=Mock(value='HIGH'))
                    monitor._create_alert = AsyncMock(return_value={'market_id': 'test', 'alert_type': 'WHALE_ACTIVITY'})
                    monitor._calculate_anomaly_confidence = Mock(return_value=8.0)
                    monitor.alert_manager.send_alert = AsyncMock(return_value=True)
                    monitor._track_whales_from_alert = AsyncMock()
                    monitor._initialize_outcome_tracking = AsyncMock()

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    await monitor._analyze_market_for_whales('test', market_data)

                    monitor._escalate_market.assert_called_once_with('test', market_data)

    @pytest.mark.asyncio
    async def test_whale_detected_no_escalation_when_disabled(self):
        """Test whale detection doesn't escalate when whale_escalation_enabled=false"""
        config = get_complete_test_config(
            **{'monitoring.whale_escalation_enabled': False}
        )

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    monitor.whale_detector.detect_whale_activity = Mock(return_value={'anomaly': True, 'whale_count': 2})
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(return_value=[])
                    monitor._get_market_trades = AsyncMock(return_value=[{'price': 0.5, 'size': 1000}])
                    monitor._escalate_market = AsyncMock()
                    monitor._determine_severity = Mock(return_value=Mock(value='HIGH'))
                    monitor._create_alert = AsyncMock(return_value={'market_id': 'test', 'alert_type': 'WHALE_ACTIVITY'})
                    monitor._calculate_anomaly_confidence = Mock(return_value=8.0)
                    monitor.alert_manager.send_alert = AsyncMock(return_value=True)
                    monitor._track_whales_from_alert = AsyncMock()
                    monitor._initialize_outcome_tracking = AsyncMock()

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    await monitor._analyze_market_for_whales('test', market_data)

                    monitor._escalate_market.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_metadata_includes_source(self):
        """Test alerts from low-volume scan include source='low_volume_scan'"""
        config = get_complete_test_config()

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    monitor.whale_detector.detect_whale_activity = Mock(return_value={'anomaly': True, 'whale_count': 2})
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(return_value=[])
                    monitor._get_market_trades = AsyncMock(return_value=[{'price': 0.5, 'size': 1000}])
                    monitor._escalate_market = AsyncMock()
                    monitor._determine_severity = Mock(return_value=Mock(value='HIGH'))
                    monitor._create_alert = AsyncMock(return_value={'market_id': 'test', 'alert_type': 'WHALE_ACTIVITY'})
                    monitor._calculate_anomaly_confidence = Mock(return_value=8.0)
                    monitor.alert_manager.send_alert = AsyncMock(return_value=True)
                    monitor._track_whales_from_alert = AsyncMock()
                    monitor._initialize_outcome_tracking = AsyncMock()

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    await monitor._analyze_market_for_whales('test', market_data)

                    # Check alert was sent with correct source
                    calls = monitor.alert_manager.send_alert.call_args_list
                    assert len(calls) > 0
                    alert = calls[0][0][0]
                    assert alert.get('source') == 'low_volume_scan'


class TestMonitoringModes:
    """Test different monitoring mode combinations"""

    @pytest.mark.parametrize("config_overrides,expected_high,expected_low,expected_all", [
        # Hybrid mode
        ({'monitoring.enable_low_volume_scanning': True, 'monitoring.monitor_all_markets': False}, True, True, False),
        # High-volume only
        ({'monitoring.enable_low_volume_scanning': False, 'monitoring.monitor_all_markets': False}, True, False, False),
        # All markets mode
        ({'monitoring.enable_low_volume_scanning': False, 'monitoring.monitor_all_markets': True}, False, False, True),
    ])
    def test_monitoring_mode_combinations(self, config_overrides, expected_high, expected_low, expected_all):
        """Test different monitoring mode combinations produce expected behavior"""
        config = get_complete_test_config(**config_overrides)

        settings = Settings(config)

        if expected_all:
            assert settings.monitoring.monitor_all_markets is True
        elif expected_low:
            assert settings.monitoring.enable_low_volume_scanning is True
            assert settings.monitoring.monitor_all_markets is False
        else:  # expected_high only
            assert settings.monitoring.enable_low_volume_scanning is False
            assert settings.monitoring.monitor_all_markets is False


class TestWhaleTradeFiltering:
    """Test whale detector properly filters trades by whale_threshold_usd"""

    def create_trade(self, price: float, size: float, side: str = 'BUY', maker: str = '0xABCD') -> Dict:
        """Helper to create a trade with specific USD volume"""
        return {
            'price': price,
            'size': size,
            'side': side,
            'maker': maker,
            'timestamp': '2024-01-01T12:00:00Z',
            'tx_hash': f'0x{hash(f"{price}{size}")}'
        }

    def test_trade_exactly_at_threshold_triggers_detection(self):
        """Test trade exactly at whale_threshold_usd is detected as whale trade"""
        from detection.whale_detector import WhaleDetector

        config = get_complete_test_config(**{'detection.whale_thresholds.whale_threshold_usd': 10000})
        detector = WhaleDetector(config)

        # Create 3 whales on same side for significant activity
        trades = [
            self.create_trade(price=0.5, size=20000, maker='0xWHALE1'),   # $10k
            self.create_trade(price=0.5, size=20000, maker='0xWHALE2'),   # $10k
            self.create_trade(price=0.5, size=20000, maker='0xWHALE3'),   # $10k
        ]

        result = detector.detect_whale_activity(trades)

        assert result['anomaly'] is True
        assert result['whale_count'] == 3
        assert result['largest_whale_volume'] >= 10000

    def test_trade_below_threshold_ignored(self):
        """Test trade $1 below threshold is ignored"""
        from detection.whale_detector import WhaleDetector

        config = get_complete_test_config(**{'detection.whale_thresholds.whale_threshold_usd': 10000})
        detector = WhaleDetector(config)

        # Create trade worth $9,999 (just below threshold)
        trades = [self.create_trade(price=0.5, size=19998)]  # 0.5 * 19998 = $9,999

        result = detector.detect_whale_activity(trades)

        assert result['anomaly'] is False
        assert result['whale_count'] == 0

    def test_trade_well_above_threshold_triggers_detection(self):
        """Test trade well above threshold triggers detection"""
        from detection.whale_detector import WhaleDetector

        config = get_complete_test_config(**{'detection.whale_thresholds.whale_threshold_usd': 10000})
        detector = WhaleDetector(config)

        # Create 3 whales for significant activity
        trades = [
            self.create_trade(price=0.5, size=100000, maker='0xBIGWHALE1'),  # $50k
            self.create_trade(price=0.5, size=100000, maker='0xBIGWHALE2'),  # $50k
            self.create_trade(price=0.5, size=100000, maker='0xBIGWHALE3'),  # $50k
        ]

        result = detector.detect_whale_activity(trades)

        assert result['anomaly'] is True
        assert result['whale_count'] == 3
        assert result['largest_whale_volume'] >= 50000

    def test_mixed_trades_only_analyzes_whales(self):
        """Test mixed trades (some above/below threshold) only counts whales"""
        from detection.whale_detector import WhaleDetector

        config = get_complete_test_config(**{'detection.whale_thresholds.whale_threshold_usd': 10000})
        detector = WhaleDetector(config)

        trades = [
            self.create_trade(price=0.5, size=100000, maker='0xWHALE1'),  # $50k - whale
            self.create_trade(price=0.5, size=2000, maker='0xSMALL1'),    # $1k - not whale
            self.create_trade(price=0.5, size=40000, maker='0xWHALE2'),   # $20k - whale
            self.create_trade(price=0.5, size=500, maker='0xSMALL2'),     # $250 - not whale
            self.create_trade(price=0.5, size=50000, maker='0xWHALE3'),   # $25k - whale (3rd for anomaly)
        ]

        result = detector.detect_whale_activity(trades)

        assert result['anomaly'] is True
        assert result['whale_count'] == 3  # Only 3 whales
        assert result['total_whale_volume'] >= 95000  # $50k + $20k + $25k

    def test_different_threshold_values_respected(self):
        """Test detector respects different whale_threshold_usd config values"""
        from detection.whale_detector import WhaleDetector

        # Test with $5,000 threshold - $6,000 trades should be whales
        config_5k = get_complete_test_config(**{'detection.whale_thresholds.whale_threshold_usd': 5000})
        detector_5k = WhaleDetector(config_5k)

        trades = [
            self.create_trade(price=0.5, size=12000, maker='0xW1'),  # $6k
            self.create_trade(price=0.5, size=12000, maker='0xW2'),  # $6k
            self.create_trade(price=0.5, size=12000, maker='0xW3'),  # $6k
        ]

        result_5k = detector_5k.detect_whale_activity(trades)
        assert result_5k['anomaly'] is True  # Above $5k threshold
        assert result_5k['whale_count'] == 3

        # Test with $25,000 threshold - same trades should NOT be whales
        config_25k = get_complete_test_config(**{'detection.whale_thresholds.whale_threshold_usd': 25000})
        detector_25k = WhaleDetector(config_25k)

        result_25k = detector_25k.detect_whale_activity(trades)
        assert result_25k['anomaly'] is False  # Below $25k threshold
        assert result_25k['whale_count'] == 0

    def test_whale_count_matches_trades_above_threshold(self):
        """Verify whale_count matches number of unique wallets above threshold"""
        from detection.whale_detector import WhaleDetector

        config = get_complete_test_config(**{'detection.whale_thresholds.whale_threshold_usd': 10000})
        detector = WhaleDetector(config)

        trades = [
            self.create_trade(price=0.5, size=50000, maker='0xWHALE1'),   # $25k
            self.create_trade(price=0.5, size=30000, maker='0xWHALE1'),   # $15k (same wallet)
            self.create_trade(price=0.5, size=40000, maker='0xWHALE2'),   # $20k
            self.create_trade(price=0.5, size=60000, maker='0xWHALE3'),   # $30k
        ]

        result = detector.detect_whale_activity(trades)

        assert result['whale_count'] == 3  # 3 unique whale wallets


class TestLowVolumeWithRealTradeData:
    """Integration tests with realistic trade data through the full analysis pipeline"""

    def create_trade(self, price: float, size: float, maker: str, side: str = 'BUY') -> Dict:
        """Helper to create realistic trade data"""
        return {
            'price': price,
            'size': size,
            'side': side,
            'maker': maker,
            'timestamp': '2024-01-01T12:00:00Z',
            'tx_hash': f'0x{hash(f"{price}{size}{maker}")}'
        }

    @pytest.mark.asyncio
    async def test_low_volume_whale_above_threshold_creates_alert(self):
        """Test whale trade above threshold in low-volume market creates alert"""
        config = get_complete_test_config(**{
            'monitoring.whale_escalation_enabled': True,
            'detection.whale_thresholds.whale_threshold_usd': 10000
        })

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    # Mock whale detector to return anomaly
                    monitor.whale_detector.detect_whale_activity = Mock(return_value={
                        'anomaly': True,
                        'whale_count': 3,
                        'total_whale_volume': 75000
                    })

                    monitor._get_market_trades = AsyncMock(return_value=[
                        self.create_trade(price=0.5, size=50000, maker='0xWHALE1'),
                        self.create_trade(price=0.5, size=50000, maker='0xWHALE2'),
                        self.create_trade(price=0.5, size=50000, maker='0xWHALE3'),
                    ])
                    monitor._escalate_market = AsyncMock()
                    monitor._determine_severity = Mock(return_value=Mock(value='HIGH'))
                    monitor._create_alert = AsyncMock(return_value={
                        'market_id': 'test',
                        'alert_type': 'WHALE_ACTIVITY',
                        'source': 'low_volume_scan'
                    })
                    monitor._calculate_anomaly_confidence = Mock(return_value=8.0)
                    monitor.alert_manager.send_alert = AsyncMock(return_value=True)
                    monitor._track_whales_from_alert = AsyncMock()
                    monitor._initialize_outcome_tracking = AsyncMock()
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(return_value=[])

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    alerts_sent = await monitor._analyze_market_for_whales('test', market_data)

                    assert alerts_sent == 1
                    monitor.alert_manager.send_alert.assert_called_once()
                    monitor._escalate_market.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_volume_whale_below_threshold_no_alert(self):
        """Test whale trade below threshold in low-volume market creates no alert"""
        config = get_complete_test_config(**{
            'monitoring.whale_escalation_enabled': True,
            'detection.whale_thresholds.whale_threshold_usd': 10000
        })

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    # Mock dependencies
                    monitor._get_market_trades = AsyncMock(return_value=[
                        self.create_trade(price=0.5, size=15000, maker='0xSMALL')  # $7.5k - below threshold
                    ])
                    monitor._escalate_market = AsyncMock()
                    monitor.alert_manager.send_alert = AsyncMock(return_value=True)
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(return_value=[])

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    alerts_sent = await monitor._analyze_market_for_whales('test', market_data)

                    assert alerts_sent == 0
                    monitor.alert_manager.send_alert.assert_not_called()
                    monitor._escalate_market.assert_not_called()

    @pytest.mark.asyncio
    async def test_low_volume_fresh_wallet_large_bet_creates_alert(self):
        """Test fresh wallet with large bet in low-volume market creates alert"""
        config = get_complete_test_config(**{
            'monitoring.whale_escalation_enabled': True,
            'detection.fresh_wallet_thresholds.min_bet_size_usd': 2000
        })

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    # Mock fresh wallet detection
                    fresh_wallet_result = {
                        'anomaly': True,
                        'wallet_address': '0xFRESH',
                        'bet_size': 5000,
                        'side': 'BUY',
                        'previous_trade_count': 0
                    }

                    monitor._get_market_trades = AsyncMock(return_value=[
                        self.create_trade(price=0.5, size=10000, maker='0xFRESH')  # $5k
                    ])
                    monitor._escalate_market = AsyncMock()
                    monitor.whale_detector.detect_whale_activity = Mock(return_value={'anomaly': False})
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(
                        return_value=[fresh_wallet_result]
                    )
                    monitor._create_fresh_wallet_alert = AsyncMock(return_value={
                        'alert_type': 'FRESH_WALLET',
                        'source': 'low_volume_scan'
                    })
                    monitor.alert_manager.send_alert = AsyncMock(return_value=True)
                    monitor._track_whales_from_alert = AsyncMock()
                    monitor._initialize_outcome_tracking = AsyncMock()

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    alerts_sent = await monitor._analyze_market_for_whales('test', market_data)

                    assert alerts_sent == 1
                    monitor.alert_manager.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_volume_fresh_wallet_small_bet_no_alert(self):
        """Test fresh wallet with small bet in low-volume market creates no alert"""
        config = get_complete_test_config(**{
            'monitoring.whale_escalation_enabled': True,
            'detection.fresh_wallet_thresholds.min_bet_size_usd': 2000
        })

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    monitor._get_market_trades = AsyncMock(return_value=[
                        self.create_trade(price=0.5, size=3000, maker='0xFRESH')  # $1.5k - below threshold
                    ])
                    monitor.whale_detector.detect_whale_activity = Mock(return_value={'anomaly': False})
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(return_value=[])
                    monitor.alert_manager.send_alert = AsyncMock()

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    alerts_sent = await monitor._analyze_market_for_whales('test', market_data)

                    assert alerts_sent == 0
                    monitor.alert_manager.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_low_volume_established_whale_only_whale_alert(self):
        """Test established wallet large bet only triggers whale alert, not fresh wallet"""
        config = get_complete_test_config(**{
            'monitoring.whale_escalation_enabled': True,
            'detection.whale_thresholds.whale_threshold_usd': 10000,
            'detection.fresh_wallet_thresholds.min_bet_size_usd': 2000
        })

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    # Mock whale detector to return anomaly
                    monitor.whale_detector.detect_whale_activity = Mock(return_value={
                        'anomaly': True,
                        'whale_count': 3,
                        'total_whale_volume': 150000
                    })

                    monitor._get_market_trades = AsyncMock(return_value=[
                        self.create_trade(price=0.5, size=100000, maker='0xESTABLISHED1'),
                        self.create_trade(price=0.5, size=100000, maker='0xESTABLISHED2'),
                        self.create_trade(price=0.5, size=100000, maker='0xESTABLISHED3'),
                    ])
                    monitor._escalate_market = AsyncMock()
                    monitor._determine_severity = Mock(return_value=Mock(value='HIGH'))
                    monitor._create_alert = AsyncMock(return_value={
                        'market_id': 'test',
                        'alert_type': 'WHALE_ACTIVITY'
                    })
                    monitor._calculate_anomaly_confidence = Mock(return_value=8.0)
                    monitor.alert_manager.send_alert = AsyncMock(return_value=True)
                    monitor._track_whales_from_alert = AsyncMock()
                    monitor._initialize_outcome_tracking = AsyncMock()
                    # Fresh wallet detector returns empty (wallets have history)
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(return_value=[])

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    alerts_sent = await monitor._analyze_market_for_whales('test', market_data)

                    # Should have 1 alert (whale only, not fresh wallet)
                    assert alerts_sent == 1
                    assert monitor.alert_manager.send_alert.call_count == 1

    @pytest.mark.asyncio
    async def test_low_volume_whale_and_fresh_wallet_both_detected(self):
        """Test market with both whale and fresh wallet generates 2 alerts"""
        config = get_complete_test_config(**{
            'monitoring.whale_escalation_enabled': True,
            'detection.whale_thresholds.whale_threshold_usd': 10000,
            'detection.fresh_wallet_thresholds.min_bet_size_usd': 2000
        })

        with patch('market_monitor.MarketMonitor._load_config') as mock_load:
            with patch('market_monitor.DatabaseManager'):
                with patch('market_monitor.DataAPIClient'):
                    mock_load.return_value = config
                    monitor = MarketMonitor()

                    trades = [
                        self.create_trade(price=0.5, size=100000, maker='0xFRESHWHALE1'),
                        self.create_trade(price=0.5, size=100000, maker='0xFRESHWHALE2'),
                        self.create_trade(price=0.5, size=100000, maker='0xFRESHWHALE3'),
                    ]

                    # Mock whale detector to return anomaly
                    monitor.whale_detector.detect_whale_activity = Mock(return_value={
                        'anomaly': True,
                        'whale_count': 3,
                        'total_whale_volume': 150000
                    })

                    monitor._get_market_trades = AsyncMock(return_value=trades)
                    monitor._escalate_market = AsyncMock()
                    monitor._determine_severity = Mock(return_value=Mock(value='HIGH'))
                    monitor._create_alert = AsyncMock(return_value={
                        'market_id': 'test',
                        'alert_type': 'WHALE_ACTIVITY'
                    })
                    monitor._calculate_anomaly_confidence = Mock(return_value=8.0)
                    monitor._create_fresh_wallet_alert = AsyncMock(return_value={
                        'alert_type': 'FRESH_WALLET'
                    })
                    monitor.alert_manager.send_alert = AsyncMock(return_value=True)
                    monitor._track_whales_from_alert = AsyncMock()
                    monitor._initialize_outcome_tracking = AsyncMock()
                    # Fresh wallet detector finds the wallet is fresh
                    monitor.fresh_wallet_detector.detect_fresh_wallet_activity = AsyncMock(return_value=[{
                        'anomaly': True,
                        'wallet_address': '0xFRESHWHALE1',
                        'bet_size': 50000,
                        'previous_trade_count': 0
                    }])

                    market_data = {'conditionId': 'test', 'question': 'Test Market'}

                    alerts_sent = await monitor._analyze_market_for_whales('test', market_data)

                    # Should have 2 alerts (whale + fresh wallet)
                    assert alerts_sent == 2
                    assert monitor.alert_manager.send_alert.call_count == 2
