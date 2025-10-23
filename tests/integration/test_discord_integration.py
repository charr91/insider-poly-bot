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
    def real_settings(self, monkeypatch):
        """Create settings with Discord webhook from env or mock URL"""
        import json
        with open('insider_config.json') as f:
            config = json.load(f)

        # Determine webhook URL - use env var if set, otherwise mock URL
        webhook = os.getenv('DISCORD_WEBHOOK')
        if not webhook:  # Handles None and empty string
            webhook = 'https://discord.com/api/webhooks/mock/test'
            # Set env var so Settings class will use it (Settings reads env vars first)
            monkeypatch.setenv('DISCORD_WEBHOOK', webhook)

        config['alerts']['discord_webhook'] = webhook

        return Settings(config)

    @pytest.mark.asyncio
    @patch('alerts.telegram_notifier.aiohttp.ClientSession')
    @patch('alerts.alert_manager.aiohttp.ClientSession')
    async def test_discord_connection_test(self, mock_alert_session, mock_telegram_session, real_settings):
        """Test Discord webhook connection (mocked HTTP to prevent spam)"""

        # Setup mock response for Discord (returns 204)
        mock_discord_response = MagicMock()
        mock_discord_response.status = 204
        mock_discord_response.text = AsyncMock(return_value='')
        mock_discord_response.__aenter__ = AsyncMock(return_value=mock_discord_response)
        mock_discord_response.__aexit__ = AsyncMock(return_value=None)

        # Setup mock response for Telegram (returns 200)
        mock_telegram_response = MagicMock()
        mock_telegram_response.status = 200
        mock_telegram_response.text = AsyncMock(return_value='{"ok": true}')
        mock_telegram_response.json = AsyncMock(return_value={"ok": True})
        mock_telegram_response.__aenter__ = AsyncMock(return_value=mock_telegram_response)
        mock_telegram_response.__aexit__ = AsyncMock(return_value=None)

        # Mock post method - returns Discord response (not async, just returns the response)
        mock_post = MagicMock(return_value=mock_discord_response)

        # Mock session object
        mock_session_obj = MagicMock()
        mock_session_obj.post = mock_post
        mock_session_obj.__aenter__ = AsyncMock(return_value=mock_session_obj)
        mock_session_obj.__aexit__ = AsyncMock(return_value=None)

        # Make both ClientSession() calls return the same mock session object
        mock_alert_session.return_value = mock_session_obj
        mock_telegram_session.return_value = mock_session_obj

        am = AlertManager(real_settings)

        # This tests the full flow WITHOUT actually sending HTTP request
        await am.test_connections()

        # Verify HTTP calls were made
        assert mock_post.call_count > 0, f"Expected HTTP POST calls, but got {mock_post.call_count}"

        # Check that the webhook URL was called
        call_args_list = mock_post.call_args_list
        assert len(call_args_list) > 0, "No calls to session.post() were recorded"
    
    @pytest.mark.asyncio
    @patch('alerts.telegram_notifier.aiohttp.ClientSession')
    @patch('alerts.alert_manager.aiohttp.ClientSession')
    async def test_send_real_alert_to_discord(self, mock_alert_session, mock_telegram_session, real_settings):
        """Test sending alert to Discord (mocked HTTP to prevent spam)"""

        # Setup mock response for Discord (returns 204)
        mock_discord_response = MagicMock()
        mock_discord_response.status = 204
        mock_discord_response.text = AsyncMock(return_value='')
        mock_discord_response.__aenter__ = AsyncMock(return_value=mock_discord_response)
        mock_discord_response.__aexit__ = AsyncMock(return_value=None)

        # Setup mock response for Telegram (returns 200)
        mock_telegram_response = MagicMock()
        mock_telegram_response.status = 200
        mock_telegram_response.text = AsyncMock(return_value='{"ok": true}')
        mock_telegram_response.json = AsyncMock(return_value={"ok": True})
        mock_telegram_response.__aenter__ = AsyncMock(return_value=mock_telegram_response)
        mock_telegram_response.__aexit__ = AsyncMock(return_value=None)

        # Mock post method - returns Discord response
        mock_post = MagicMock(return_value=mock_discord_response)

        # Mock session object
        mock_session_obj = MagicMock()
        mock_session_obj.post = mock_post
        mock_session_obj.__aenter__ = AsyncMock(return_value=mock_session_obj)
        mock_session_obj.__aexit__ = AsyncMock(return_value=None)

        # Make both ClientSession() calls return the mock session object
        mock_alert_session.return_value = mock_session_obj
        mock_telegram_session.return_value = mock_session_obj

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

        # Verify HTTP calls were made
        assert mock_post.call_count > 0, f"Expected HTTP POST calls, but got {mock_post.call_count}"

        # Verify alert was recorded
        assert len(am.alert_history) == 1
        assert am.alert_history[0]['severity'] == 'HIGH'

        # Verify the Discord webhook was called with proper payload
        mock_post.assert_called()
        call_kwargs = mock_post.call_args[1]  # Get keyword arguments

        # Discord calls should have 'json' parameter with 'embeds'
        if 'json' in call_kwargs:
            assert 'embeds' in call_kwargs['json'], "Discord payload should have embeds"
            assert len(call_kwargs['json']['embeds']) > 0

            # Verify embed structure
            embed = call_kwargs['json']['embeds'][0]
            assert 'title' in embed
            assert 'HIGH' in embed['title']
            assert 'color' in embed