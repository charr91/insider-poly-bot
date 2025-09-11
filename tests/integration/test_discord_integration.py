"""
Integration tests for Discord webhook functionality
"""

import pytest
import os
import asyncio
from alerts.alert_manager import AlertManager
from config.settings import Settings


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv('DISCORD_WEBHOOK'), reason="No Discord webhook configured")
class TestDiscordIntegration:
    """Integration tests for Discord webhook"""
    
    @pytest.fixture
    def real_settings(self):
        """Create settings with real Discord webhook"""
        import json
        with open('insider_config.json') as f:
            config = json.load(f)
        
        # Use real webhook from environment
        config['alerts']['discord_webhook'] = os.getenv('DISCORD_WEBHOOK')
        
        return Settings(config)
    
    @pytest.mark.asyncio
    async def test_discord_connection_test(self, real_settings):
        """Test actual Discord webhook connection"""
        am = AlertManager(real_settings)
        
        # This will send a real test message to Discord
        await am.test_connections()
        
        # If no exception is raised, test passed
        assert True
    
    @pytest.mark.asyncio
    async def test_send_real_alert_to_discord(self, real_settings):
        """Test sending a real alert to Discord"""
        am = AlertManager(real_settings)
        
        test_alert = {
            'severity': 'HIGH',
            'market_question': '🧪 Integration Test Alert - Please Ignore',
            'alert_type': 'TEST_INTEGRATION',
            'analysis': {
                'max_anomaly_score': 5.5,
                'whale_count': 3,
                'total_whale_volume': 25000
            },
            'market_data': {
                'volume24hr': 45000,
                'lastTradePrice': 0.85
            },
            'market_id': 'integration-test-123',
            'recommended_action': '🤖 This is an automated integration test',
            'timestamp': '2024-01-01T00:00:00Z'
        }
        
        # Send real alert to Discord
        await am.send_alert(test_alert)
        
        # Verify alert was recorded
        assert len(am.alert_history) == 1
        assert am.alert_history[0]['severity'] == 'HIGH'