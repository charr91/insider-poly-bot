"""
Unit tests for MarketMonitor
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from market_monitor import MarketMonitor


@pytest.fixture
def mock_config():
    """Create mock configuration"""
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
            'max_alerts_per_hour': 10
        },
        'debug': {
            'debug_mode': False,
            'show_normal_activity': False,
            'activity_report_interval': 300,
            'verbose_analysis': False
        }
    }


@pytest.fixture
def mock_market_data():
    """Create mock market data"""
    return [
        {
            'conditionId': 'test-market-1',
            'question': 'Test Market 1',
            'volume24hr': 5000,
            'clobTokenIds': '["token1", "token2"]'
        },
        {
            'conditionId': 'test-market-2', 
            'question': 'Test Market 2',
            'volume24hr': 3000,
            'clobTokenIds': '["token3", "token4"]'
        }
    ]


class TestMarketMonitorInit:
    """Test MarketMonitor initialization"""
    
    @patch('market_monitor.MarketMonitor._load_config')
    def test_init_success(self, mock_load_config, mock_config):
        """Test successful initialization"""
        mock_load_config.return_value = mock_config
        
        monitor = MarketMonitor('test_config.json')
        
        assert monitor.config == mock_config
        assert hasattr(monitor, 'settings')
        assert hasattr(monitor, 'alert_manager')
        assert hasattr(monitor, 'monitored_markets')
        assert monitor.running is False
    
    @patch('market_monitor.MarketMonitor._load_config')
    def test_init_with_detectors(self, mock_load_config, mock_config):
        """Test initialization includes all detectors"""
        mock_load_config.return_value = mock_config
        
        monitor = MarketMonitor('test_config.json')
        
        assert hasattr(monitor, 'volume_detector')
        assert hasattr(monitor, 'whale_detector')
        assert hasattr(monitor, 'price_detector')
        assert hasattr(monitor, 'coordination_detector')


class TestConfigurationLoading:
    """Test configuration loading"""
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open')
    def test_load_config_success(self, mock_open, mock_exists, mock_config):
        """Test successful config loading"""
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = '{"test": "value"}'
        
        with patch('json.load', return_value=mock_config):
            monitor = MarketMonitor('test_config.json')
            assert monitor.config == mock_config
    
    @patch('pathlib.Path.exists')
    def test_load_config_file_not_found(self, mock_exists):
        """Test config loading with missing file falls back to defaults"""
        mock_exists.return_value = False
        
        monitor = MarketMonitor('nonexistent_config.json')
        assert 'monitoring' in monitor.config
        assert 'detection' in monitor.config


class TestMarketDiscovery:
    """Test market discovery functionality"""
    
    @pytest.mark.asyncio
    @patch('market_monitor.CoordinationDetector')
    @patch('market_monitor.PriceDetector')
    @patch('market_monitor.WhaleDetector') 
    @patch('market_monitor.VolumeDetector')
    @patch('market_monitor.DataAPIClient')
    @patch('market_monitor.MarketMonitor._load_config')
    @patch('aiohttp.ClientSession.get')
    async def test_discover_markets_success(self, mock_get, mock_load_config, 
                                          mock_data_api, mock_volume_det, mock_whale_det,
                                          mock_price_det, mock_coord_det, mock_config, mock_market_data):
        """Test successful market discovery"""
        # Mock configuration loading
        mock_load_config.return_value = mock_config
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_market_data)
        mock_get.return_value.__aenter__.return_value = mock_response
        
        monitor = MarketMonitor('test_config.json')
        
        await monitor._discover_markets()
        
        assert len(monitor.monitored_markets) == 2
        assert 'test-market-1' in monitor.monitored_markets
        assert 'test-market-2' in monitor.monitored_markets
    
    @pytest.mark.asyncio
    @patch('market_monitor.CoordinationDetector')
    @patch('market_monitor.PriceDetector')
    @patch('market_monitor.WhaleDetector') 
    @patch('market_monitor.VolumeDetector')
    @patch('market_monitor.DataAPIClient')
    @patch('market_monitor.MarketMonitor._load_config')
    @patch('aiohttp.ClientSession.get')
    async def test_discover_markets_http_error(self, mock_get, mock_load_config,
                                             mock_data_api, mock_volume_det, mock_whale_det,
                                             mock_price_det, mock_coord_det, mock_config):
        """Test market discovery with HTTP error"""
        # Mock configuration loading
        mock_load_config.return_value = mock_config
        
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_get.return_value.__aenter__.return_value = mock_response
        
        monitor = MarketMonitor('test_config.json')
        
        await monitor._discover_markets()
        
        # Should handle error gracefully
        assert len(monitor.monitored_markets) == 0
    
    @pytest.mark.asyncio
    @patch('market_monitor.CoordinationDetector')
    @patch('market_monitor.PriceDetector')
    @patch('market_monitor.WhaleDetector') 
    @patch('market_monitor.VolumeDetector')
    @patch('market_monitor.DataAPIClient')
    @patch('market_monitor.MarketMonitor._load_config')
    @patch('aiohttp.ClientSession.get')
    async def test_discover_markets_volume_filtering(self, mock_get, mock_load_config,
                                                   mock_data_api, mock_volume_det, mock_whale_det,
                                                   mock_price_det, mock_coord_det, mock_config):
        """Test market discovery filters by volume threshold"""
        markets_with_different_volumes = [
            {
                'conditionId': 'high-volume',
                'question': 'High Volume Market',
                'volume24hr': 5000,  # Above threshold
                'clobTokenIds': '["token1", "token2"]'
            },
            {
                'conditionId': 'low-volume',
                'question': 'Low Volume Market', 
                'volume24hr': 500,   # Below threshold
                'clobTokenIds': '["token3", "token4"]'
            }
        ]
        
        # Mock configuration loading
        mock_load_config.return_value = mock_config
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=markets_with_different_volumes)
        mock_get.return_value.__aenter__.return_value = mock_response
        
        monitor = MarketMonitor('test_config.json')
        
        await monitor._discover_markets()
        
        # Only high volume market should be included
        assert len(monitor.monitored_markets) == 1
        assert 'high-volume' in monitor.monitored_markets
        assert 'low-volume' not in monitor.monitored_markets


class TestWebSocketIntegration:
    """Test WebSocket integration"""
    
    @pytest.mark.asyncio
    @patch('market_monitor.CoordinationDetector')
    @patch('market_monitor.PriceDetector')
    @patch('market_monitor.WhaleDetector') 
    @patch('market_monitor.VolumeDetector')
    @patch('market_monitor.DataAPIClient')
    @patch('market_monitor.MarketMonitor._load_config')
    async def test_update_websocket_subscriptions(self, mock_load_config, mock_data_api, 
                                                 mock_volume_det, mock_whale_det, mock_price_det, 
                                                 mock_coord_det, mock_config):
        """Test WebSocket subscription updates"""
        # Mock configuration loading
        mock_load_config.return_value = mock_config
        
        monitor = MarketMonitor('test_config.json')
        
        # Mock WebSocket client with existing markets
        mock_ws_client = Mock()
        mock_ws_client.market_ids = ['existing_token']  # Mock the market_ids attribute
        mock_ws_client.add_markets = Mock()
        mock_ws_client.remove_markets = Mock()
        monitor.websocket_client = mock_ws_client
        
        token_ids = ['token1', 'token2', 'token3']
        
        await monitor._update_websocket_subscriptions(token_ids)
        
        # Should call add_markets with new tokens (existing token gets removed, new ones added)
        # Order may vary due to set operations, so check that it was called with correct tokens
        mock_ws_client.add_markets.assert_called_once()
        actual_tokens = mock_ws_client.add_markets.call_args[0][0]
        assert set(actual_tokens) == set(token_ids)
        mock_ws_client.remove_markets.assert_called_once_with(['existing_token'])


class TestDataAPIIntegration:
    """Test Data API integration"""
    
    def test_data_api_initialization(self):
        """Test Data API client initialization"""
        monitor = MarketMonitor('test_config.json')
        
        assert hasattr(monitor, 'data_api')
        assert monitor.data_api is not None


class TestStatusReporting:
    """Test status reporting functionality"""
    
    @pytest.mark.asyncio
    @patch('market_monitor.CoordinationDetector')
    @patch('market_monitor.PriceDetector')
    @patch('market_monitor.WhaleDetector') 
    @patch('market_monitor.VolumeDetector')
    @patch('market_monitor.DataAPIClient')
    @patch('market_monitor.MarketMonitor._load_config')
    async def test_generate_status_report(self, mock_load_config, mock_data_api, 
                                        mock_volume_det, mock_whale_det, mock_price_det, 
                                        mock_coord_det, mock_config):
        """Test status report generation"""
        # Mock configuration loading
        mock_load_config.return_value = mock_config
        
        monitor = MarketMonitor('test_config.json')
        
        # Set up some test data
        monitor.monitored_markets = {'test-1': {}, 'test-2': {}}
        monitor.analysis_count = 5
        monitor.alerts_generated = 3
        
        # Mock WebSocket client
        mock_ws_client = Mock()
        mock_ws_client.get_activity_stats.return_value = {
            'messages_received': 100,
            'order_books_received': 95,
            'is_connected': True,
            'reconnect_attempts': 0
        }
        monitor.websocket_client = mock_ws_client
        
        # Mock data API
        monitor.data_api.test_connection = AsyncMock(return_value=True)
        
        # Capture print output
        with patch('builtins.print') as mock_print:
            await monitor._generate_status_report()
            
            # Verify status report was generated
            mock_print.assert_called()
            
            # Check for expected content in print calls
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            status_content = '\n'.join(print_calls)
            
            assert 'SYSTEM STATUS' in status_content
            # Look for individual elements separately to handle colorized output
            assert '2' in status_content and 'monitored' in status_content
            assert '5' in status_content and 'completed' in status_content
            assert '3' in status_content and 'generated' in status_content


class TestTradeHandling:
    """Test trade handling functionality"""
    
    def test_handle_realtime_trade(self):
        """Test real-time trade handling"""
        monitor = MarketMonitor('test_config.json')
        
        # Set up monitored market
        monitor.monitored_markets = {
            'test-market': {
                'question': 'Test Market',
                'volume24hr': 5000
            }
        }
        
        trade_data = {
            'market': 'test-market',
            'price': 0.75,
            'size': 100,
            'side': 'BUY',
            'timestamp': datetime.now().timestamp()
        }
        
        # Test trade handling doesn't crash
        monitor._handle_realtime_trade(trade_data)
        
        # Verify trade was stored
        assert 'test-market' in monitor.trade_history
        assert len(monitor.trade_history['test-market']) == 1


class TestErrorHandling:
    """Test error handling"""
    
    @pytest.mark.asyncio
    @patch('market_monitor.CoordinationDetector')
    @patch('market_monitor.PriceDetector')
    @patch('market_monitor.WhaleDetector') 
    @patch('market_monitor.VolumeDetector')
    @patch('market_monitor.DataAPIClient')
    @patch('market_monitor.MarketMonitor._load_config')
    async def test_discover_markets_exception_handling(self, mock_load_config, mock_data_api, 
                                                     mock_volume_det, mock_whale_det, mock_price_det, 
                                                     mock_coord_det, mock_config):
        """Test market discovery handles exceptions gracefully"""
        # Mock configuration loading
        mock_load_config.return_value = mock_config
        
        monitor = MarketMonitor('test_config.json')

        # Mock an exception during discovery
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.side_effect = Exception("Network error")

            # Should handle the error gracefully without raising
            await monitor._discover_markets()

            # Markets should remain empty
            assert len(monitor.monitored_markets) == 0
    
    def test_handle_realtime_trade_invalid_data(self):
        """Test trade handling with invalid data"""
        monitor = MarketMonitor('test_config.json')

        # Test with missing required fields
        invalid_trade = {'invalid': 'data'}

        # Should not crash
        monitor._handle_realtime_trade(invalid_trade)

        # Should not add to trade history
        assert len(monitor.trade_history) == 0


class TestOutcomeTracking:
    """Test outcome tracking initialization and direction determination"""

    @pytest.mark.asyncio
    @patch('market_monitor.MarketMonitor._load_config')
    @patch('database.AlertRepository')
    async def test_outcome_tracking_whale_activity(self, mock_alert_repo_class, mock_load_config, mock_config):
        """Test outcome tracking uses dominant_side for WHALE_ACTIVITY"""
        mock_load_config.return_value = mock_config
        monitor = MarketMonitor('test_config.json')

        # Mock AlertRepository instance
        mock_alert_repo = AsyncMock()
        mock_alert = Mock()
        mock_alert.id = 123
        mock_alert_repo.get_recent_alerts = AsyncMock(return_value=[mock_alert])
        mock_alert_repo_class.return_value = mock_alert_repo

        # Mock database session
        with patch.object(monitor.db_manager, 'session') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            # Mock outcome tracker
            monitor.outcome_tracker.create_outcome_record = AsyncMock()

            alert = {
                'alert_type': 'WHALE_ACTIVITY',
                'analysis': {'dominant_side': 'SELL'},
                'market_data': {'lastTradePrice': '0.65'}
            }

            await monitor._initialize_outcome_tracking(alert, 'test_market_id')

            # Verify outcome tracker was called with SELL (not YES/NO)
            monitor.outcome_tracker.create_outcome_record.assert_called_once()
            call_args = monitor.outcome_tracker.create_outcome_record.call_args
            assert call_args[1]['predicted_direction'] == 'SELL'

    @pytest.mark.asyncio
    @patch('market_monitor.MarketMonitor._load_config')
    @patch('database.AlertRepository')
    async def test_outcome_tracking_volume_spike_uses_side_not_outcome(self, mock_alert_repo_class, mock_load_config, mock_config):
        """Test outcome tracking uses dominant_side for VOLUME_SPIKE (not dominant_outcome)"""
        mock_load_config.return_value = mock_config
        monitor = MarketMonitor('test_config.json')

        # Mock AlertRepository instance
        mock_alert_repo = AsyncMock()
        mock_alert = Mock()
        mock_alert.id = 456
        mock_alert_repo.get_recent_alerts = AsyncMock(return_value=[mock_alert])
        mock_alert_repo_class.return_value = mock_alert_repo

        # Mock database session
        with patch.object(monitor.db_manager, 'session') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            # Mock outcome tracker
            monitor.outcome_tracker.create_outcome_record = AsyncMock()

            alert = {
                'alert_type': 'VOLUME_SPIKE',
                'analysis': {
                    'dominant_outcome': 'NO',  # This should NOT be used
                    'dominant_side': 'BUY'     # This SHOULD be used
                },
                'market_data': {'lastTradePrice': '0.45'}
            }

            await monitor._initialize_outcome_tracking(alert, 'test_market_id')

            # Verify outcome tracker was called with BUY (not NO)
            monitor.outcome_tracker.create_outcome_record.assert_called_once()
            call_args = monitor.outcome_tracker.create_outcome_record.call_args
            assert call_args[1]['predicted_direction'] == 'BUY'
            # Ensure it's NOT the outcome value
            assert call_args[1]['predicted_direction'] != 'NO'

    @pytest.mark.asyncio
    @patch('market_monitor.MarketMonitor._load_config')
    @patch('database.AlertRepository')
    async def test_outcome_tracking_coordinated_trading(self, mock_alert_repo_class, mock_load_config, mock_config):
        """Test outcome tracking uses dominant_side for COORDINATED_TRADING"""
        mock_load_config.return_value = mock_config
        monitor = MarketMonitor('test_config.json')

        # Mock AlertRepository instance
        mock_alert_repo = AsyncMock()
        mock_alert = Mock()
        mock_alert.id = 789
        mock_alert_repo.get_recent_alerts = AsyncMock(return_value=[mock_alert])
        mock_alert_repo_class.return_value = mock_alert_repo

        # Mock database session
        with patch.object(monitor.db_manager, 'session') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            # Mock outcome tracker
            monitor.outcome_tracker.create_outcome_record = AsyncMock()

            alert = {
                'alert_type': 'COORDINATED_TRADING',
                'analysis': {'dominant_side': 'BUY'},
                'market_data': {'lastTradePrice': '0.55'}
            }

            await monitor._initialize_outcome_tracking(alert, 'test_market_id')

            # Verify outcome tracker was called with BUY
            monitor.outcome_tracker.create_outcome_record.assert_called_once()
            call_args = monitor.outcome_tracker.create_outcome_record.call_args
            assert call_args[1]['predicted_direction'] == 'BUY'

    @pytest.mark.asyncio
    @patch('market_monitor.MarketMonitor._load_config')
    @patch('database.AlertRepository')
    async def test_outcome_tracking_fresh_wallet(self, mock_alert_repo_class, mock_load_config, mock_config):
        """Test outcome tracking uses side for FRESH_WALLET_LARGE_BET"""
        mock_load_config.return_value = mock_config
        monitor = MarketMonitor('test_config.json')

        # Mock AlertRepository instance
        mock_alert_repo = AsyncMock()
        mock_alert = Mock()
        mock_alert.id = 999
        mock_alert_repo.get_recent_alerts = AsyncMock(return_value=[mock_alert])
        mock_alert_repo_class.return_value = mock_alert_repo

        # Mock database session
        with patch.object(monitor.db_manager, 'session') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            # Mock outcome tracker
            monitor.outcome_tracker.create_outcome_record = AsyncMock()

            alert = {
                'alert_type': 'FRESH_WALLET_LARGE_BET',
                'analysis': {'side': 'SELL'},
                'market_data': {'lastTradePrice': '0.72'}
            }

            await monitor._initialize_outcome_tracking(alert, 'test_market_id')

            # Verify outcome tracker was called with SELL
            monitor.outcome_tracker.create_outcome_record.assert_called_once()
            call_args = monitor.outcome_tracker.create_outcome_record.call_args
            assert call_args[1]['predicted_direction'] == 'SELL'

    @pytest.mark.asyncio
    @patch('market_monitor.MarketMonitor._load_config')
    @patch('database.AlertRepository')
    async def test_outcome_tracking_default_direction(self, mock_alert_repo_class, mock_load_config, mock_config):
        """Test outcome tracking defaults to BUY when direction missing"""
        mock_load_config.return_value = mock_config
        monitor = MarketMonitor('test_config.json')

        # Mock AlertRepository instance
        mock_alert_repo = AsyncMock()
        mock_alert = Mock()
        mock_alert.id = 111
        mock_alert_repo.get_recent_alerts = AsyncMock(return_value=[mock_alert])
        mock_alert_repo_class.return_value = mock_alert_repo

        # Mock database session
        with patch.object(monitor.db_manager, 'session') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            # Mock outcome tracker
            monitor.outcome_tracker.create_outcome_record = AsyncMock()

            alert = {
                'alert_type': 'WHALE_ACTIVITY',
                'analysis': {},  # No dominant_side
                'market_data': {'lastTradePrice': '0.50'}
            }

            await monitor._initialize_outcome_tracking(alert, 'test_market_id')

            # Verify outcome tracker defaults to BUY
            monitor.outcome_tracker.create_outcome_record.assert_called_once()
            call_args = monitor.outcome_tracker.create_outcome_record.call_args
            assert call_args[1]['predicted_direction'] == 'BUY'

    @pytest.mark.asyncio
    @patch('market_monitor.MarketMonitor._load_config')
    @patch('database.AlertRepository')
    async def test_outcome_tracking_no_alert_found(self, mock_alert_repo_class, mock_load_config, mock_config):
        """Test outcome tracking handles case when alert not found in database"""
        mock_load_config.return_value = mock_config
        monitor = MarketMonitor('test_config.json')

        # Mock AlertRepository instance
        mock_alert_repo = AsyncMock()
        mock_alert_repo.get_recent_alerts = AsyncMock(return_value=[])  # No alerts
        mock_alert_repo_class.return_value = mock_alert_repo

        # Mock database session
        with patch.object(monitor.db_manager, 'session') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            # Mock outcome tracker
            monitor.outcome_tracker.create_outcome_record = AsyncMock()

            alert = {
                'alert_type': 'WHALE_ACTIVITY',
                'analysis': {'dominant_side': 'BUY'},
                'market_data': {'lastTradePrice': '0.50'}
            }

            await monitor._initialize_outcome_tracking(alert, 'test_market_id')

            # Verify outcome tracker was NOT called
            monitor.outcome_tracker.create_outcome_record.assert_not_called()