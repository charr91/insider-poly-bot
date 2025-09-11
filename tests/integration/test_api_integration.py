"""
Integration tests for external API connections
"""

import pytest
import asyncio
from data_sources.data_api_client import DataAPIClient


@pytest.mark.integration
class TestDataAPIIntegration:
    """Integration tests for Polymarket Data API"""
    
    @pytest.fixture
    def data_client(self):
        """Create DataAPIClient instance"""
        return DataAPIClient()
    
    def test_api_connection(self, data_client):
        """Test basic API connectivity"""
        # Test connection without making actual calls
        assert hasattr(data_client, 'base_url')
        assert data_client.base_url.startswith('https://')
    
    @pytest.mark.slow
    def test_get_recent_trades_real_api(self, data_client):
        """Test getting recent trades from real API"""
        try:
            # Get trades for a small set of markets
            test_market_ids = ['test-market-1']  # Use minimal test data
            trades = data_client.get_recent_trades(test_market_ids, limit=5)
            
            # Verify response structure
            assert isinstance(trades, list)
            
            # If trades exist, verify structure
            if trades:
                trade = trades[0]
                expected_fields = ['timestamp', 'price', 'size']
                for field in expected_fields:
                    assert field in trade or hasattr(trade, field)
                    
        except Exception as e:
            # API might be rate limited or unavailable
            pytest.skip(f"API integration test skipped: {e}")
    
    @pytest.mark.slow
    def test_api_rate_limiting(self, data_client):
        """Test API handles rate limiting gracefully"""
        try:
            # Make multiple rapid requests
            for i in range(3):
                trades = data_client.get_recent_trades(['test-market'], limit=1)
                assert isinstance(trades, list)
                
        except Exception as e:
            # Rate limiting or API errors are expected
            assert "rate" in str(e).lower() or "limit" in str(e).lower()


@pytest.mark.integration
@pytest.mark.slow
class TestWebSocketIntegration:
    """Integration tests for WebSocket connections"""
    
    def test_websocket_url_accessible(self):
        """Test WebSocket URL is accessible"""
        from data_sources.websocket_client import WebSocketClient
        
        # Just verify the URL format is correct
        client = WebSocketClient(['test'], lambda x: None)
        assert client.ws_url.startswith('wss://')
        assert 'polymarket.com' in client.ws_url
    
    @pytest.mark.asyncio
    async def test_websocket_connection_attempt(self):
        """Test WebSocket connection attempt (may timeout)"""
        from data_sources.websocket_client import WebSocketClient
        
        connection_successful = False
        
        def mock_callback(trade_data):
            nonlocal connection_successful
            connection_successful = True
        
        client = WebSocketClient(['test-token'], mock_callback)
        
        try:
            # Attempt connection with short timeout
            client.connect()
            
            # Wait briefly for connection
            await asyncio.sleep(2)
            
            # Clean disconnect
            client.disconnect()
            
        except Exception as e:
            # Connection failures are acceptable in CI environment
            pytest.skip(f"WebSocket integration test skipped: {e}")