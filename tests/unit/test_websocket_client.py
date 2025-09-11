"""
Unit tests for WebSocketClient
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from data_sources.websocket_client import WebSocketClient


@pytest.fixture
def mock_debug_config():
    """Create mock debug configuration"""
    return {
        'debug_mode': False,
        'websocket_activity_logging': False,
        'activity_report_interval': 30
    }


@pytest.fixture
def mock_trade_callback():
    """Create mock trade callback function"""
    return Mock()


@pytest.fixture
def sample_trade_data():
    """Create sample trade data"""
    return {
        'market': 'test-market-123',
        'price': 0.75,
        'size': 100,
        'side': 'BUY',
        'maker': 'maker_address',
        'taker': 'taker_address',
        'timestamp': datetime.now().timestamp()
    }


@pytest.fixture
def sample_order_book_data():
    """Create sample order book data"""
    return {
        'market': 'test-market-123',
        'asset_id': 'asset-123',
        'timestamp': datetime.now().timestamp(),
        'bids': [['0.75', '100'], ['0.74', '200']],
        'asks': [['0.76', '150'], ['0.77', '300']],
        'event_type': 'book'
    }


class TestWebSocketClientInit:
    """Test WebSocketClient initialization"""
    
    def test_init_success(self, mock_trade_callback, mock_debug_config):
        """Test successful initialization"""
        market_ids = ['token1', 'token2']
        
        client = WebSocketClient(market_ids, mock_trade_callback, mock_debug_config)
        
        assert client.market_ids == market_ids
        assert client.on_trade_callback == mock_trade_callback
        assert client.ws_url == "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        assert client.is_connected is False
        assert client.reconnect_attempts == 0
        assert client.max_reconnect_attempts == 10
    
    def test_init_with_debug_config(self, mock_trade_callback):
        """Test initialization with debug configuration"""
        debug_config = {
            'debug_mode': True,
            'websocket_activity_logging': True,
            'activity_report_interval': 60
        }
        
        client = WebSocketClient(['token1'], mock_trade_callback, debug_config)
        
        assert client.debug_mode is True
        assert client.show_activity is True
        assert client.activity_report_interval == 60


class TestActivityTracking:
    """Test activity tracking functionality"""
    
    def test_activity_stats_initial_state(self, mock_trade_callback, mock_debug_config):
        """Test initial activity statistics"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        
        stats = client.get_activity_stats()
        
        assert stats['messages_received'] == 0
        assert stats['order_books_received'] == 0
        assert stats['is_connected'] is False
        assert stats['reconnect_attempts'] == 0
    
    def test_activity_stats_after_processing(self, mock_trade_callback, mock_debug_config):
        """Test activity statistics after processing messages"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        
        # Simulate processing messages
        client.messages_received = 10
        client.order_books_received = 8
        client.is_connected = True
        
        stats = client.get_activity_stats()
        
        assert stats['messages_received'] == 10
        assert stats['order_books_received'] == 8
        assert stats['is_connected'] is True


class TestMessageProcessing:
    """Test WebSocket message processing"""
    
    
    def test_process_order_book_event(self, mock_trade_callback, mock_debug_config, sample_order_book_data):
        """Test processing order book event"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        
        client._process_trade_event(sample_order_book_data)
        
        # Should not call trade callback for order book
        mock_trade_callback.assert_not_called()
        assert client.order_books_received == 1
    
    def test_process_subscription_confirmation(self, mock_trade_callback, mock_debug_config):
        """Test processing subscription confirmation"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        
        subscription_msg = {
            'type': 'subscribed',
            'channel': 'trades',
            'status': 'success'
        }
        
        with patch('data_sources.websocket_client.logger') as mock_logger:
            client._process_trade_event(subscription_msg)
            
            mock_logger.info.assert_called_once()
            mock_trade_callback.assert_not_called()
    
    def test_process_error_message(self, mock_trade_callback, mock_debug_config):
        """Test processing error message"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        
        error_msg = {
            'type': 'error',
            'message': 'Subscription failed',
            'code': 400
        }
        
        with patch('data_sources.websocket_client.logger') as mock_logger:
            client._process_trade_event(error_msg)
            
            mock_logger.error.assert_called_once()
            mock_trade_callback.assert_not_called()



class TestWebSocketHandlers:
    """Test WebSocket event handlers"""
    
    def test_on_open_handler(self, mock_trade_callback, mock_debug_config):
        """Test WebSocket open handler"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        
        mock_ws = Mock()
        
        with patch.object(client, '_subscribe_to_markets') as mock_subscribe:
            with patch.object(client, '_start_heartbeat') as mock_heartbeat:
                client._on_open(mock_ws)
                
                assert client.is_connected is True
                assert client.reconnect_attempts == 0
                mock_subscribe.assert_called_once()
                mock_heartbeat.assert_called_once()
    
    def test_on_error_handler(self, mock_trade_callback, mock_debug_config):
        """Test WebSocket error handler"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        
        mock_ws = Mock()
        error = Exception("Connection error")
        
        with patch('data_sources.websocket_client.logger') as mock_logger:
            client._on_error(mock_ws, error)
            
            assert client.is_connected is False
            mock_logger.error.assert_called_once()
    
    def test_on_close_handler(self, mock_trade_callback, mock_debug_config):
        """Test WebSocket close handler"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        client.should_reconnect = True
        
        mock_ws = Mock()
        
        with patch.object(client, '_stop_heartbeat') as mock_stop_heartbeat:
            with patch.object(client, '_schedule_reconnect') as mock_schedule:
                client._on_close(mock_ws, 1000, "Normal closure")
                
                assert client.is_connected is False
                mock_stop_heartbeat.assert_called_once()
                mock_schedule.assert_called_once()


class TestSubscriptionManagement:
    """Test subscription management"""
    
    @patch('time.sleep')
    def test_subscribe_to_markets(self, mock_sleep, mock_trade_callback, mock_debug_config):
        """Test market subscription"""
        market_ids = ['token1', 'token2']
        client = WebSocketClient(market_ids, mock_trade_callback, mock_debug_config)
        
        mock_ws = Mock()
        client.ws = mock_ws
        
        client._subscribe_to_markets()
        
        # Should send 1 market subscription
        assert mock_ws.send.call_count == 1
    
    def test_add_markets(self, mock_trade_callback, mock_debug_config):
        """Test adding new markets"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        client.is_connected = True
        
        new_markets = ['token2', 'token3']
        
        with patch.object(client, '_subscribe_to_markets') as mock_subscribe:
            client.add_markets(new_markets)
            
            assert 'token2' in client.market_ids
            assert 'token3' in client.market_ids
            mock_subscribe.assert_called_once()
    
    def test_remove_markets(self, mock_trade_callback, mock_debug_config):
        """Test removing markets"""
        client = WebSocketClient(['token1', 'token2', 'token3'], mock_trade_callback, mock_debug_config)
        
        markets_to_remove = ['token2']
        
        client.remove_markets(markets_to_remove)
        
        assert 'token1' in client.market_ids
        assert 'token2' not in client.market_ids
        assert 'token3' in client.market_ids


class TestReconnectionLogic:
    """Test reconnection logic"""
    
    def test_schedule_reconnect_under_limit(self, mock_trade_callback, mock_debug_config):
        """Test reconnection scheduling under attempt limit"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        client.reconnect_attempts = 3
        client.should_reconnect = True
        
        with patch('threading.Thread') as mock_thread:
            client._schedule_reconnect()
            
            assert client.reconnect_attempts == 4
            mock_thread.assert_called_once()
    
    def test_schedule_reconnect_over_limit(self, mock_trade_callback, mock_debug_config):
        """Test reconnection gives up after max attempts"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        client.reconnect_attempts = 10  # At max limit
        
        with patch('threading.Thread') as mock_thread:
            with patch('data_sources.websocket_client.logger') as mock_logger:
                client._schedule_reconnect()
                
                mock_thread.assert_not_called()
                mock_logger.error.assert_called_once()


class TestConnectionManagement:
    """Test connection management"""
    
    @patch('websocket.WebSocketApp')
    @patch('threading.Thread')
    def test_connect_success(self, mock_thread, mock_websocket_app, mock_trade_callback, mock_debug_config):
        """Test successful connection"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        
        client.connect()
        
        mock_websocket_app.assert_called_once()
        mock_thread.assert_called_once()
    
    def test_disconnect(self, mock_trade_callback, mock_debug_config):
        """Test graceful disconnection"""
        client = WebSocketClient(['token1'], mock_trade_callback, mock_debug_config)
        client.is_connected = True
        client.should_reconnect = True
        
        mock_ws = Mock()
        client.ws = mock_ws
        
        with patch.object(client, '_stop_heartbeat') as mock_stop_heartbeat:
            client.disconnect()
            
            assert client.should_reconnect is False
            assert client.is_connected is False
            mock_ws.close.assert_called_once()
            mock_stop_heartbeat.assert_called_once()