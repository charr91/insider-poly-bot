"""
Integration tests for Discord webhook functionality
NOTE: These tests mock HTTP calls to prevent spamming real channels
"""

import pytest
import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from dotenv import load_dotenv
from alerts.alert_manager import AlertManager
from config.settings import Settings

# Load environment variables for integration tests
load_dotenv()


@pytest.mark.integration
class TestDiscordIntegration:
    """Integration tests for Discord webhook (with mocked HTTP calls)

    NOTE: These tests use mocked HTTP, so they will run even without a real webhook.
    In CI/CD, set DISCORD_WEBHOOK to test with actual configuration.
    """

    @pytest.fixture
    def real_settings(self):
        """Create settings with Discord webhook from env or mock URL"""
        import json
        with open('insider_config.json') as f:
            config = json.load(f)

        # Use real webhook from environment, or mock URL for testing
        webhook = os.getenv('DISCORD_WEBHOOK') or 'https://discord.com/api/webhooks/mock/test'
        config['alerts']['discord_webhook'] = webhook

        return Settings(config)

    @pytest.mark.asyncio
    @patch('alerts.alert_manager.aiohttp.ClientSession')
    async def test_discord_connection_test(self, mock_session, real_settings):
        """Test Discord webhook connection (mocked HTTP to prevent spam)"""

        # Track all post calls
        post_calls = []

        def create_mock_post(url, **kwargs):
            """Create mock response based on URL"""
            post_calls.append((url, kwargs))

            mock_response = MagicMock()
            if 'discord.com' in str(url):
                # Discord webhook response
                mock_response.status = 204
                mock_response.text = AsyncMock(return_value='')
            else:
                # Telegram API response
                mock_response.status = 200
                mock_response.text = AsyncMock(return_value='{"ok": true}')
                mock_response.json = AsyncMock(return_value={"ok": True})

            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            return mock_response

        # Mock session object
        mock_session_obj = MagicMock()
        mock_session_obj.post = MagicMock(side_effect=create_mock_post)
        mock_session_obj.__aenter__ = AsyncMock(return_value=mock_session_obj)
        mock_session_obj.__aexit__ = AsyncMock(return_value=None)

        # Make ClientSession() return the session object
        mock_session.return_value = mock_session_obj

        am = AlertManager(real_settings)

        # This tests the full flow WITHOUT actually sending HTTP request
        await am.test_connections()

        # Verify HTTP calls were made (should be at least one for Discord)
        assert len(post_calls) > 0, "No HTTP POST calls were made"

        # Check that Discord was called
        discord_called = False
        for url, kwargs in post_calls:
            if 'discord.com' in str(url):
                discord_called = True
                # Verify payload structure (should have embeds)
                if kwargs.get('json'):
                    assert 'embeds' in kwargs['json'], "Discord payload should have embeds"

        # Verify Discord webhook was called
        webhook_url = os.getenv('DISCORD_WEBHOOK', '')
        if webhook_url and 'discord.com' in webhook_url:
            assert discord_called, "Discord webhook should have been called"
    
    @pytest.mark.asyncio
    @patch('alerts.alert_manager.aiohttp.ClientSession')
    async def test_send_real_alert_to_discord(self, mock_session, real_settings):
        """Test sending alert to Discord (mocked HTTP to prevent spam)"""

        # Track all post calls
        post_calls = []

        def create_mock_post(url, **kwargs):
            """Create mock response based on URL"""
            post_calls.append((url, kwargs))

            mock_response = MagicMock()
            if 'discord.com' in str(url):
                # Discord webhook response
                mock_response.status = 204
                mock_response.text = AsyncMock(return_value='')
            else:
                # Telegram API response
                mock_response.status = 200
                mock_response.text = AsyncMock(return_value='{"ok": true}')
                mock_response.json = AsyncMock(return_value={"ok": True})

            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            return mock_response

        # Mock session object
        mock_session_obj = MagicMock()
        mock_session_obj.post = MagicMock(side_effect=create_mock_post)
        mock_session_obj.__aenter__ = AsyncMock(return_value=mock_session_obj)
        mock_session_obj.__aexit__ = AsyncMock(return_value=None)

        # Make ClientSession() return the session object
        mock_session.return_value = mock_session_obj

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

        # Send alert (HTTP call will be mocked)
        await am.send_alert(test_alert)

        # Verify HTTP calls were made (both Discord and possibly Telegram)
        assert len(post_calls) > 0, "No HTTP POST calls were made"

        # Verify alert was recorded
        assert len(am.alert_history) == 1
        assert am.alert_history[0]['severity'] == 'HIGH'

        # Find Discord call and verify payload
        discord_payload = None
        for url, kwargs in post_calls:
            if 'discord.com' in str(url):
                if 'json' in kwargs:
                    discord_payload = kwargs['json']
                    break

        # Verify Discord payload if Discord webhook is configured
        webhook_url = os.getenv('DISCORD_WEBHOOK', '')
        if webhook_url and 'discord.com' in webhook_url:
            assert discord_payload is not None, "Discord payload should exist"
            assert 'embeds' in discord_payload, "Discord payload should have embeds"
            assert len(discord_payload['embeds']) > 0

            # Verify embed has expected structure
            embed = discord_payload['embeds'][0]
            assert 'title' in embed
            assert 'HIGH' in embed['title']
            assert 'color' in embed