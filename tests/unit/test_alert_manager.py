"""
Unit tests for AlertManager
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from alerts.alert_manager import AlertManager
from config.settings import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing"""
    settings = Mock()
    settings.alerts = Mock()
    settings.alerts.discord_webhook = ""
    settings.alerts.min_severity = "MEDIUM"
    settings.alerts.discord_min_severity = "MEDIUM"
    settings.alerts.max_alerts_per_hour = 10
    return settings


@pytest.fixture
def mock_config():
    """Create mock config dict for legacy support"""
    return {
        'alerts': {
            'discord_webhook': '',
            'min_severity': 'MEDIUM',
            'discord_min_severity': 'MEDIUM',
            'max_alerts_per_hour': 10
        }
    }


@pytest.fixture
def sample_alert():
    """Create a sample alert for testing"""
    return {
        'severity': 'MEDIUM',
        'market_question': 'Test Market Question',
        'alert_type': 'VOLUME_SPIKE',
        'analysis': {'max_anomaly_score': 3.5},
        'market_data': {'volume24hr': 15000},
        'market_id': 'test-123',
        'recommended_action': 'Monitor closely',
        'timestamp': datetime.now().isoformat()
    }


class TestAlertManagerInit:
    """Test AlertManager initialization"""
    
    def test_init_with_settings_object(self, mock_settings):
        """Test initialization with Settings object"""
        am = AlertManager(mock_settings)
        assert am.min_severity == "MEDIUM"
        assert am.discord_min_severity == "MEDIUM"
        assert am.max_alerts_per_hour == 10
        assert am.discord_webhook == ""
    
    def test_init_with_config_dict(self, mock_config):
        """Test initialization with config dict (legacy)"""
        with patch.dict('os.environ', {'DISCORD_WEBHOOK': 'test_webhook'}):
            am = AlertManager(mock_config)
            assert am.min_severity == "MEDIUM"
            assert am.discord_min_severity == "MEDIUM"
            assert am.max_alerts_per_hour == 10
            assert am.discord_webhook == "test_webhook"
    
    def test_severity_level_mapping(self, mock_settings):
        """Test severity level mapping using AlertSeverity enum"""
        from alerts.alert_manager import AlertSeverity
        am = AlertManager(mock_settings)
        # Test enum-based severity levels
        assert AlertSeverity.get_level('LOW') == 1
        assert AlertSeverity.get_level('MEDIUM') == 2
        assert AlertSeverity.get_level('HIGH') == 3
        assert AlertSeverity.get_level('CRITICAL') == 4


class TestAlertFiltering:
    """Test alert filtering and routing"""
    
    @pytest.mark.asyncio
    async def test_send_alert_below_min_severity(self, mock_settings, sample_alert):
        """Test that alerts below min severity are filtered out"""
        am = AlertManager(mock_settings)
        
        low_alert = sample_alert.copy()
        low_alert['severity'] = 'LOW'
        
        await am.send_alert(low_alert)
        assert len(am.alert_history) == 0
    
    @pytest.mark.asyncio
    async def test_send_alert_meets_min_severity(self, mock_settings, sample_alert):
        """Test that alerts meeting min severity are processed"""
        am = AlertManager(mock_settings)
        
        await am.send_alert(sample_alert)
        assert len(am.alert_history) == 1
        assert am.alert_history[0]['severity'] == 'MEDIUM'
    
    @pytest.mark.asyncio
    async def test_discord_routing_decision(self, mock_settings, sample_alert):
        """Test Discord routing logic"""
        mock_settings.alerts.discord_webhook = "test_webhook"
        am = AlertManager(mock_settings)
        
        with patch.object(am, '_send_discord_alert', new_callable=AsyncMock) as mock_discord:
            await am.send_alert(sample_alert)
            mock_discord.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_discord_threshold_filtering(self, mock_settings, sample_alert):
        """Test Discord threshold filtering"""
        mock_settings.alerts.discord_webhook = "test_webhook"
        mock_settings.alerts.discord_min_severity = "HIGH"
        mock_settings.alerts.min_severity = "LOW"  # Ensure alerts pass general severity check
        am = AlertManager(mock_settings)
        
        # Clear alert history to prevent rate limiting interference
        am.storage.alert_history = []
        
        with patch.object(am, '_send_discord_alert', new_callable=AsyncMock) as mock_discord:
            # MEDIUM alert should not go to Discord with HIGH threshold
            await am.send_alert(sample_alert)
            mock_discord.assert_not_called()
            
            # Clear history again between tests to avoid rate limiting
            am.storage.alert_history = []
            
            # HIGH alert should go to Discord
            high_alert = sample_alert.copy()
            high_alert['severity'] = 'HIGH'
            await am.send_alert(high_alert)
            mock_discord.assert_called_once()


class TestRateLimiting:
    """Test alert rate limiting"""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_max_alerts_per_hour(self, mock_settings, sample_alert):
        """Test maximum alerts per hour rate limiting"""
        mock_settings.alerts.max_alerts_per_hour = 2
        am = AlertManager(mock_settings)
        
        # Send 3 alerts, only 2 should be processed
        for i in range(3):
            alert = sample_alert.copy()
            alert['market_id'] = f'test-{i}'
            await am.send_alert(alert)
        
        assert len(am.alert_history) == 2
    
    @pytest.mark.asyncio
    async def test_duplicate_alert_filtering(self, mock_settings, sample_alert):
        """Test duplicate alert filtering"""
        am = AlertManager(mock_settings)
        
        # Send same alert twice
        await am.send_alert(sample_alert)
        await am.send_alert(sample_alert)
        
        # Only one should be recorded
        assert len(am.alert_history) == 1


class TestDiscordIntegration:
    """Test Discord webhook integration"""
    
    @pytest.mark.asyncio
    async def test_discord_webhook_success(self, mock_settings, sample_alert):
        """Test successful Discord webhook call"""
        mock_settings.alerts.discord_webhook = "https://discord.com/api/webhooks/test"
        am = AlertManager(mock_settings)
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 204
            mock_post.return_value.__aenter__.return_value = mock_response
            
            await am._send_discord_alert(sample_alert)
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_discord_embed_creation(self, mock_settings, sample_alert):
        """Test Discord embed creation"""
        am = AlertManager(mock_settings)
        embed = am._create_discord_embed(sample_alert)
        
        assert embed['title'] == '🚨 MEDIUM: Volume Spike'
        assert embed['description'] == 'Test Market Question'
        assert embed['color'] == 0xFFD700  # Gold for MEDIUM
        assert len(embed['fields']) > 0


class TestConnectionTesting:
    """Test connection testing functionality"""
    
    @pytest.mark.asyncio
    async def test_connection_test_no_webhook(self, mock_settings):
        """Test connection test with no webhook configured"""
        am = AlertManager(mock_settings)
        
        with patch('alerts.alert_manager.logger') as mock_logger:
            await am.test_connections()
            mock_logger.info.assert_any_call("ℹ️ No Discord webhook configured")
    
    @pytest.mark.asyncio
    async def test_connection_test_with_webhook(self, mock_settings):
        """Test connection test with webhook configured"""
        mock_settings.alerts.discord_webhook = "https://discord.com/api/webhooks/test"
        am = AlertManager(mock_settings)
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 204
            mock_response.text = AsyncMock(return_value="")
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with patch('alerts.alert_manager.logger') as mock_logger:
                await am.test_connections()
                mock_logger.info.assert_any_call("✅ Discord webhook test successful")


class TestAlertStatistics:
    """Test alert statistics functionality"""
    
    def test_get_alert_stats(self, mock_settings):
        """Test alert statistics calculation"""
        am = AlertManager(mock_settings)
        
        # Add some mock alert history using storage interface
        am.storage.save_alert({
            'timestamp': datetime.now(),
            'market_id': 'test-1',
            'alert_type': 'VOLUME_SPIKE',
            'severity': 'HIGH'
        })
        am.storage.save_alert({
            'timestamp': datetime.now(),
            'market_id': 'test-2',
            'alert_type': 'WHALE_ACTIVITY',
            'severity': 'MEDIUM'
        })
        
        stats = am.get_alert_stats()
        assert stats['total_alerts_24h'] == 2
        assert 'HIGH' in stats['by_severity']
        # by_type field no longer exists
        assert 'by_type' not in stats