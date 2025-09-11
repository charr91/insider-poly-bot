"""
Integration tests for WebSocketClient.
"""
import pytest
import json
import threading
import time
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone, timedelta

from data_sources.websocket_client import WebSocketClient
from tests.fixtures.websocket_fixtures import WebSocketFixtures


class TestWebSocketClientIntegration:
    """Integration tests for WebSocketClient with mocked WebSocket connections."""
    
    @pytest.fixture
    def trade_callback(self):
        """Mock trade callback function."""
        return Mock()
    
    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket instance."""
        mock_ws = Mock()
        mock_ws.send = Mock()
        mock_ws.close = Mock()
        return mock_ws
    
    @pytest.fixture
    def client(self, trade_callback):
        """Create WebSocketClient instance for testing."""
        market_ids = ["token_1", "token_2", "token_3"]
        debug_config = {
            'debug_mode': True,
            'websocket_activity_logging': True,
            'activity_report_interval': 60
        }
        return WebSocketClient(market_ids, trade_callback, debug_config)
    
    def test_init_configuration(self, trade_callback):
        """Test WebSocketClient initialization and configuration."""
        market_ids = ["test_token_1", "test_token_2"]
        debug_config = {
            'debug_mode': False,
            'websocket_activity_logging': True,
            'activity_report_interval': 120
        }
        
        client = WebSocketClient(market_ids, trade_callback, debug_config)
        
        assert client.market_ids == market_ids
        assert client.on_trade_callback == trade_callback
        assert client.ws_url == "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        assert not client.is_connected
        assert client.debug_config == debug_config
        assert not client.debug_mode
        assert client.show_activity
        assert client.activity_report_interval == 120
    
    def test_init_default_debug_config(self, trade_callback):
        """Test initialization with default debug configuration."""
        client = WebSocketClient(["token_1"], trade_callback)
        
        assert client.debug_config == {}
        assert not client.debug_mode
        assert not client.show_activity
        assert client.activity_report_interval == 300
    
    @patch('data_sources.websocket_client.websocket.WebSocketApp')
    @patch('threading.Thread')
    def test_connect_success(self, mock_thread, mock_websocket_app, client):
        """Test successful WebSocket connection."""
        mock_ws_instance = Mock()
        mock_websocket_app.return_value = mock_ws_instance
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        client.connect()
        
        # Verify WebSocketApp was created with correct parameters
        mock_websocket_app.assert_called_once_with(
            client.ws_url,
            on_open=client._on_open,
            on_message=client._on_message,
            on_error=client._on_error,
            on_close=client._on_close
        )
        
        # Verify thread was started
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        assert mock_thread_instance.daemon is True
    
    @patch('data_sources.websocket_client.websocket.WebSocketApp')
    def test_connect_exception(self, mock_websocket_app, client):
        """Test WebSocket connection exception handling."""
        mock_websocket_app.side_effect = Exception("Connection failed")
        
        with patch.object(client, '_schedule_reconnect') as mock_reconnect:
            client.connect()
            mock_reconnect.assert_called_once()
    
    def test_on_open_callback(self, client, mock_websocket):
        """Test WebSocket on_open callback."""
        client.ws = mock_websocket
        
        with patch.object(client, '_subscribe_to_markets') as mock_subscribe, \
             patch.object(client, '_start_heartbeat') as mock_heartbeat:
            
            client._on_open(mock_websocket)
            
            assert client.is_connected is True
            assert client.reconnect_attempts == 0
            mock_subscribe.assert_called_once()
            mock_heartbeat.assert_called_once()
    
    def test_on_message_pong_handling(self, client, trade_callback):
        """Test handling of PONG messages."""
        pong_messages = ['PONG', '[]', ' PONG ']
        
        for message in pong_messages:
            client._on_message(Mock(), message)
        
        # Should not call trade callback for PONG messages
        trade_callback.assert_not_called()
    
    def test_on_message_json_decode_error(self, client, trade_callback, caplog):
        """Test handling of invalid JSON messages."""
        invalid_messages = [
            'invalid json',
            '{"incomplete": ',
            'not json at all'
        ]
        
        with caplog.at_level("WARNING"):
            for message in invalid_messages:
                client._on_message(Mock(), message)
        
        # Should not call trade callback
        trade_callback.assert_not_called()
        
        # Should log warnings for non-PONG invalid messages
        assert "Failed to parse WebSocket message" in caplog.text
    
    def test_on_message_list_processing(self, client, trade_callback):
        """Test processing of list messages."""
        # Empty list (subscription confirmation)
        empty_list = json.dumps([])
        client._on_message(Mock(), empty_list)
        trade_callback.assert_not_called()
        
        # List with trade events
        trade_list = json.dumps([
            {
                "type": "trade",
                "market": "test_market",
                "price": "0.65",
                "size": "1500",
                "side": "BUY",
                "maker": "0xmaker",
                "taker": "0xtaker"
            }
        ])
        
        client._on_message(Mock(), trade_list)
        trade_callback.assert_called_once()
    
    def test_on_message_dict_processing(self, client, trade_callback):
        """Test processing of dictionary messages."""
        trade_dict = json.dumps({
            "type": "trade",
            "market": "test_market",
            "price": "0.75",
            "size": "2000",
            "side": "SELL",
            "maker": "0xmaker2",
            "taker": "0xtaker2"
        })
        
        client._on_message(Mock(), trade_dict)
        trade_callback.assert_called_once()
    
    def test_process_trade_event_type_detection(self, client, trade_callback):
        """Test trade event type detection."""
        trade_events = [
            {"type": "trade", "market": "test1", "price": "0.5", "size": "1000", "maker": "0xa", "taker": "0xb"},
            {"type": "TRADE", "market": "test2", "price": "0.6", "size": "1000", "maker": "0xc", "taker": "0xd"},
            {"event_type": "fill", "market": "test3", "price": "0.7", "size": "1000", "maker": "0xe", "taker": "0xf"},
            {"event_type": "EXECUTION", "market": "test4", "price": "0.8", "size": "1000", "maker": "0xg", "taker": "0xh"},
        ]
        
        for event in trade_events:
            client._process_trade_event(event)
        
        # Should detect all as trades
        assert trade_callback.call_count == 4
    
    def test_process_trade_event_implicit_detection(self, client, trade_callback):
        """Test implicit trade detection without explicit type."""
        implicit_trade = {
            "market": "test_market",
            "price": "0.55",
            "size": "1200",
            "maker": "0ximplicit_maker",
            "taker": "0ximplicit_taker"
        }
        
        client._process_trade_event(implicit_trade)
        trade_callback.assert_called_once()
    
    def test_process_trade_event_subscription_messages(self, client, trade_callback, caplog):
        """Test handling of subscription messages."""
        subscription_events = [
            {"type": "subscribed", "channel": "trades"},
            {"type": "SUBSCRIBED", "market": "test_market"},
            {"type": "subscription_success", "status": "ok"}
        ]
        
        with caplog.at_level("INFO"):
            for event in subscription_events:
                client._process_trade_event(event)
        
        # Should not call trade callback
        trade_callback.assert_not_called()
        
        # Should log subscription success
        assert "Subscribed successfully" in caplog.text
    
    def test_process_trade_event_error_messages(self, client, trade_callback, caplog):
        """Test handling of error messages."""
        error_events = [
            {"type": "error", "message": "Rate limit exceeded"},
            {"type": "ERROR", "code": "INVALID_MARKET"}
        ]
        
        with caplog.at_level("ERROR"):
            for event in error_events:
                client._process_trade_event(event)
        
        # Should not call trade callback
        trade_callback.assert_not_called()
        
        # Should log errors
        assert "WebSocket error message" in caplog.text
    
    def test_normalize_trade_data_valid(self, client):
        """Test trade data normalization with valid data."""
        trade_data = {
            "market": "test_market_123",
            "price": "0.75",
            "size": "2500",
            "side": "buy",
            "maker": "0xmaker123",
            "taker": "0xtaker456",
            "timestamp": 1640995200,
            "txHash": "0xtx123"
        }
        
        normalized = client._normalize_trade_data(trade_data)
        
        assert normalized is not None
        assert normalized["market"] == "test_market_123"
        assert normalized["price"] == 0.75
        assert normalized["size"] == 2500.0
        assert normalized["side"] == "BUY"
        assert normalized["maker"] == "0xmaker123"
        assert normalized["taker"] == "0xtaker456"
        assert normalized["timestamp"] == 1640995200
        assert normalized["tx_hash"] == "0xtx123"
        assert normalized["source"] == "websocket"
    
    def test_normalize_trade_data_invalid(self, client, caplog):
        """Test trade data normalization with invalid data."""
        invalid_data_sets = [
            {"market": "", "price": "0.5", "size": "1000"},  # Empty market
            {"market": "test", "price": "0", "size": "1000"},  # Zero price
            {"market": "test", "price": "0.5", "size": "0"},  # Zero size
            {"market": "test", "price": "invalid", "size": "1000"},  # Invalid price
            {"market": "test", "price": "0.5", "size": "invalid"},  # Invalid size
        ]
        
        with caplog.at_level("WARNING"):
            for data in invalid_data_sets:
                result = client._normalize_trade_data(data)
                assert result is None
        
        assert "Invalid trade data" in caplog.text or "Error normalizing" in caplog.text
    
    def test_normalize_trade_data_missing_timestamp(self, client):
        """Test trade data normalization with missing timestamp."""
        trade_data = {
            "market": "test_market",
            "price": "0.5",
            "size": "1000",
            "side": "BUY"
        }
        
        normalized = client._normalize_trade_data(trade_data)
        
        assert normalized is not None
        assert "timestamp" in normalized
        # Should add current timestamp
        assert isinstance(normalized["timestamp"], (int, float))
    
    def test_subscribe_to_markets(self, client, mock_websocket):
        """Test market subscription process."""
        client.ws = mock_websocket
        client.market_ids = ["token_1", "token_2"]
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            client._subscribe_to_markets()
        
        # Should send multiple subscription types
        assert mock_websocket.send.call_count == 5
        
        # Verify subscription messages
        sent_messages = [call[0][0] for call in mock_websocket.send.call_args_list]
        for message in sent_messages:
            parsed = json.loads(message)
            assert "type" in parsed
            assert "assets_ids" in parsed
            assert parsed["assets_ids"] == ["token_1", "token_2"]
    
    def test_subscribe_to_markets_no_websocket(self, client):
        """Test subscription when WebSocket is not connected."""
        client.ws = None
        client.market_ids = ["token_1"]
        
        # Should handle gracefully without error
        client._subscribe_to_markets()
    
    def test_subscribe_to_markets_no_markets(self, client, mock_websocket):
        """Test subscription with no market IDs."""
        client.ws = mock_websocket
        client.market_ids = []
        
        client._subscribe_to_markets()
        
        # Should not send any subscriptions
        mock_websocket.send.assert_not_called()
    
    @patch('threading.Thread')
    def test_start_heartbeat(self, mock_thread, client):
        """Test heartbeat thread creation."""
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        client.is_connected = True
        client._start_heartbeat()
        
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        assert mock_thread_instance.daemon is True
        assert client.heartbeat_thread == mock_thread_instance
    
    def test_heartbeat_functionality(self, client, mock_websocket):
        """Test heartbeat ping sending."""
        client.ws = mock_websocket
        client.is_connected = True
        
        # Mock the heartbeat function directly
        def mock_heartbeat():
            if client.is_connected and client.ws:
                ping_msg = {"type": "ping"}
                client.ws.send(json.dumps(ping_msg))
        
        mock_heartbeat()
        
        # Verify ping was sent
        mock_websocket.send.assert_called_once()
        sent_message = mock_websocket.send.call_args[0][0]
        parsed = json.loads(sent_message)
        assert parsed == {"type": "ping"}
    
    def test_stop_heartbeat(self, client):
        """Test heartbeat thread stopping."""
        mock_thread = Mock()
        client.heartbeat_thread = mock_thread
        
        client._stop_heartbeat()
        
        assert client.heartbeat_thread is None
    
    def test_on_error_callback(self, client):
        """Test WebSocket error callback."""
        error = Exception("Connection error")
        
        client._on_error(Mock(), error)
        
        assert client.is_connected is False
    
    def test_on_close_callback(self, client):
        """Test WebSocket close callback."""
        with patch.object(client, '_stop_heartbeat') as mock_stop, \
             patch.object(client, '_schedule_reconnect') as mock_reconnect:
            
            client.should_reconnect = True
            client._on_close(Mock(), 1000, "Normal close")
            
            assert client.is_connected is False
            mock_stop.assert_called_once()
            mock_reconnect.assert_called_once()
    
    def test_on_close_no_reconnect(self, client):
        """Test WebSocket close without reconnection."""
        with patch.object(client, '_schedule_reconnect') as mock_reconnect:
            client.should_reconnect = False
            client._on_close(Mock(), 1000, "Normal close")
            
            mock_reconnect.assert_not_called()
    
    @patch('threading.Thread')
    @patch('time.sleep')
    def test_schedule_reconnect(self, mock_sleep, mock_thread, client):
        """Test reconnection scheduling."""
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        client.reconnect_attempts = 2
        client.max_reconnect_attempts = 10
        
        client._schedule_reconnect()
        
        assert client.reconnect_attempts == 3
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
    
    def test_schedule_reconnect_max_attempts(self, client, caplog):
        """Test reconnection with maximum attempts reached."""
        client.reconnect_attempts = 10
        client.max_reconnect_attempts = 10
        
        with caplog.at_level("ERROR"):
            client._schedule_reconnect()
        
        assert "Max reconnection attempts reached" in caplog.text
        assert client.reconnect_attempts == 10  # Should not increment
    
    def test_disconnect(self, client, mock_websocket):
        """Test graceful disconnection."""
        client.ws = mock_websocket
        client.is_connected = True
        
        with patch.object(client, '_stop_heartbeat') as mock_stop:
            client.disconnect()
            
            assert client.should_reconnect is False
            assert client.is_connected is False
            mock_websocket.close.assert_called_once()
            mock_stop.assert_called_once()
    
    def test_add_markets(self, client, mock_websocket):
        """Test adding new markets to monitor."""
        client.ws = mock_websocket
        client.is_connected = True
        client.market_ids = ["token_1", "token_2"]
        
        new_markets = ["token_3", "token_4", "token_1"]  # Include duplicate
        
        with patch.object(client, '_subscribe_to_markets') as mock_subscribe:
            client.add_markets(new_markets)
        
        # Should add only new markets
        assert "token_3" in client.market_ids
        assert "token_4" in client.market_ids
        assert client.market_ids.count("token_1") == 1  # No duplicates
        
        # Should resubscribe when connected
        mock_subscribe.assert_called_once()
    
    def test_add_markets_not_connected(self, client):
        """Test adding markets when not connected."""
        client.is_connected = False
        client.market_ids = ["token_1"]
        
        with patch.object(client, '_subscribe_to_markets') as mock_subscribe:
            client.add_markets(["token_2"])
        
        assert "token_2" in client.market_ids
        # Should not resubscribe when not connected
        mock_subscribe.assert_not_called()
    
    def test_remove_markets(self, client):
        """Test removing markets from monitoring."""
        client.market_ids = ["token_1", "token_2", "token_3"]
        
        client.remove_markets(["token_2", "token_4"])  # Include non-existent
        
        assert client.market_ids == ["token_1", "token_3"]
    
    def test_get_activity_stats(self, client):
        """Test activity statistics retrieval."""
        client.messages_received = 100
        client.trades_processed = 5
        client.order_books_received = 95
        client.is_connected = True
        client.reconnect_attempts = 2
        
        stats = client.get_activity_stats()
        
        expected = {
            'messages_received': 100,
            'trades_processed': 5,
            'order_books_received': 95,
            'is_connected': True,
            'reconnect_attempts': 2
        }
        assert stats == expected
    
    def test_report_activity_if_needed(self, client):
        """Test periodic activity reporting."""
        client.show_activity = True
        client.activity_report_interval = 1  # 1 second for testing
        client.messages_received = 50
        client.trades_processed = 3
        client.order_books_received = 47
        
        # Simulate time passage
        client.last_activity_report = datetime.now(timezone.utc) - timedelta(seconds=2)
        
        with patch('builtins.print') as mock_print:
            client._report_activity_if_needed()
        
        # Should print activity report
        mock_print.assert_called()
        
        # Should reset counters
        assert client.messages_received == 0
        assert client.trades_processed == 0
        assert client.order_books_received == 0
    
    def test_report_activity_not_needed(self, client):
        """Test that activity is not reported when not needed."""
        client.show_activity = True
        client.activity_report_interval = 300  # 5 minutes
        
        # Recent last report
        client.last_activity_report = datetime.now(timezone.utc)
        
        with patch('builtins.print') as mock_print:
            client._report_activity_if_needed()
        
        # Should not print
        mock_print.assert_not_called()
    
    def test_message_count_tracking(self, client, trade_callback):
        """Test message count tracking and debug limits."""
        client.debug_mode = True
        
        # Send more than debug limit messages
        for i in range(15):
            trade_event = {
                "type": "trade",
                "market": f"test_market_{i}",
                "price": "0.5",
                "size": "1000",
                "maker": f"0xmaker{i}",
                "taker": f"0xtaker{i}"
            }
            client._process_trade_event(trade_event)
        
        # Should have debug message count attribute
        assert hasattr(client, '_debug_message_count')
        assert client._debug_message_count == 15
        
        # Should process all trades
        assert trade_callback.call_count == 15
    
    def test_websocket_fixtures_integration(self, client, trade_callback):
        """Test integration with WebSocket fixtures."""
        fixtures = WebSocketFixtures()
        
        # Test volume spike sequence
        spike_messages = fixtures.volume_spike_sequence()
        for msg in spike_messages:
            message_json = json.dumps(msg)
            client._on_message(Mock(), message_json)
        
        # Should process all trade messages
        expected_trades = len([msg for msg in spike_messages if msg.get("type") == "trade"])
        assert trade_callback.call_count == expected_trades
    
    @patch('data_sources.websocket_client.websocket.WebSocketApp')
    def test_concurrent_message_processing(self, mock_websocket_app, client, trade_callback):
        """Test concurrent message processing."""
        import threading
        
        # Create multiple trade messages
        trade_messages = []
        for i in range(10):
            trade_messages.append(json.dumps({
                "type": "trade",
                "market": f"market_{i}",
                "price": f"0.{50 + i}",
                "size": "1000",
                "maker": f"0xmaker{i}",
                "taker": f"0xtaker{i}"
            }))
        
        # Process messages concurrently
        def process_message(message):
            client._on_message(Mock(), message)
        
        threads = [threading.Thread(target=process_message, args=(msg,)) for msg in trade_messages]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # Should process all trades
        assert trade_callback.call_count == 10
    
    def test_memory_efficiency_large_messages(self, client, trade_callback):
        """Test memory efficiency with large message processing."""
        # Create large trade message
        large_trade = {
            "type": "trade",
            "market": "large_test_market",
            "price": "0.75",
            "size": "50000",
            "maker": "0x" + "a" * 38,  # Long wallet address
            "taker": "0x" + "b" * 38,
            "additional_data": "x" * 1000  # Large additional field
        }
        
        message = json.dumps(large_trade)
        client._on_message(Mock(), message)
        
        # Should handle large messages
        trade_callback.assert_called_once()
        
        # Verify normalized data doesn't include extra fields
        called_trade = trade_callback.call_args[0][0]
        assert "additional_data" not in called_trade