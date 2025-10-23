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
    @patch('aiohttp.ClientSession.post')
    async def test_discord_connection_test(self, mock_post, real_settings):
        """Test Discord webhook connection (mocked HTTP to prevent spam)"""

        # Create mock responses for both Discord and Telegram
        def create_mock_response(url, **kwargs):
            """Create appropriate mock response based on URL"""
            mock_response = MagicMock()

            if 'discord.com' in url:
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

        # Use side_effect to return different responses based on URL
        mock_post.side_effect = create_mock_response

        am = AlertManager(real_settings)

        # This tests the full flow WITHOUT actually sending HTTP request
        await am.test_connections()

        # Verify HTTP calls were made (should be at least one for Discord)
        assert mock_post.call_count > 0

        # Check that Discord was called
        discord_called = False
        for call in mock_post.call_args_list:
            call_args_str = str(call)
            if 'discord.com' in call_args_str:
                discord_called = True
                # Verify payload structure (should have embeds)
                if call[1].get('json'):
                    assert 'embeds' in call[1]['json'], "Discord payload should have embeds"

        # Verify Discord webhook was called
        webhook_url = os.getenv('DISCORD_WEBHOOK', '')
        if webhook_url and 'discord.com' in webhook_url:
            assert discord_called, "Discord webhook should have been called"
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_send_real_alert_to_discord(self, mock_post, real_settings):
        """Test sending alert to Discord (mocked HTTP to prevent spam)"""

        # Create mock responses for both Discord and Telegram
        def create_mock_response(url, **kwargs):
            """Create appropriate mock response based on URL"""
            mock_response = MagicMock()

            if 'discord.com' in url:
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

        # Use side_effect to return different responses based on URL
        mock_post.side_effect = create_mock_response

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
        assert mock_post.call_count > 0

        # Verify alert was recorded
        assert len(am.alert_history) == 1
        assert am.alert_history[0]['severity'] == 'HIGH'

        # Find Discord call and verify payload
        discord_payload = None
        for call in mock_post.call_args_list:
            call_args_str = str(call)
            if 'discord.com' in call_args_str:
                call_kwargs = call[1]
                if 'json' in call_kwargs:
                    discord_payload = call_kwargs['json']
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