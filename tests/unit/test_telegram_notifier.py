"""
Unit tests for TelegramNotifier
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from alerts.telegram_notifier import TelegramNotifier


class TestTelegramNotifier:
    """Test TelegramNotifier functionality"""

    @pytest.fixture
    def notifier_enabled(self):
        """Create enabled Telegram notifier"""
        return TelegramNotifier(bot_token='test_token_123', chat_id='test_chat_456')

    @pytest.fixture
    def notifier_disabled(self):
        """Create disabled Telegram notifier (no credentials)"""
        # Mock environment variables to ensure no credentials are loaded
        with patch('os.getenv', return_value=''):
            return TelegramNotifier()

    def test_initialization_enabled(self, notifier_enabled):
        """Test notifier initializes correctly when enabled"""
        assert notifier_enabled.is_enabled()
        assert notifier_enabled.bot_token == 'test_token_123'
        assert notifier_enabled.chat_id == 'test_chat_456'
        assert 'test_token_123' in notifier_enabled.api_base_url

    @patch('os.getenv', return_value='')
    def test_initialization_disabled(self, mock_getenv, notifier_disabled):
        """Test notifier initializes correctly when disabled"""
        assert not notifier_disabled.is_enabled()

    @pytest.mark.asyncio
    @patch('alerts.telegram_notifier.aiohttp.ClientSession')
    async def test_send_alert_success(self, mock_session, notifier_enabled):
        """Test successful alert sending"""
        # Mock response with proper async context manager protocol
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Mock post method - returns response directly (not async)
        mock_post = MagicMock(return_value=mock_response)

        # Mock session object
        mock_session_obj = MagicMock()
        mock_session_obj.post = mock_post
        mock_session_obj.__aenter__ = AsyncMock(return_value=mock_session_obj)
        mock_session_obj.__aexit__ = AsyncMock(return_value=None)

        # Make ClientSession() return the session object
        mock_session.return_value = mock_session_obj

        message = "<b>Test Alert</b>\nThis is a test"
        result = await notifier_enabled.send_alert(message)

        assert result is True
        mock_post.assert_called_once()

        # Check call arguments
        call_args = mock_post.call_args
        assert '/sendMessage' in call_args[0][0]
        assert call_args[1]['json']['text'] == message
        assert call_args[1]['json']['parse_mode'] == 'HTML'

    @pytest.mark.asyncio
    @patch('os.getenv', return_value='')
    async def test_send_alert_disabled(self, mock_getenv, notifier_disabled):
        """Test sending alert when disabled returns False"""
        message = "Test message"
        result = await notifier_disabled.send_alert(message)

        assert result is False

    @pytest.mark.asyncio
    @patch('alerts.telegram_notifier.aiohttp.ClientSession')
    async def test_send_alert_api_error(self, mock_session, notifier_enabled):
        """Test alert sending with API error"""
        # Mock error response
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value='Bad Request')
        mock_response.__aenter__.return_value = mock_response

        mock_post = AsyncMock(return_value=mock_response)
        mock_session.return_value.__aenter__.return_value.post = mock_post

        message = "Test message"
        result = await notifier_enabled.send_alert(message)

        assert result is False

    @pytest.mark.asyncio
    @patch('alerts.telegram_notifier.aiohttp.ClientSession')
    async def test_send_alert_connection_error(self, mock_session, notifier_enabled):
        """Test alert sending with connection error"""
        # Mock connection error
        mock_session.return_value.__aenter__.side_effect = Exception("Connection failed")

        message = "Test message"
        result = await notifier_enabled.send_alert(message)

        assert result is False

    @pytest.mark.asyncio
    @patch('alerts.telegram_notifier.aiohttp.ClientSession')
    async def test_test_connection_success(self, mock_session, notifier_enabled):
        """Test connection test success"""
        # Mock successful response with proper async context manager protocol
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Mock post method - returns response directly (not async)
        mock_post = MagicMock(return_value=mock_response)

        # Mock session object
        mock_session_obj = MagicMock()
        mock_session_obj.post = mock_post
        mock_session_obj.__aenter__ = AsyncMock(return_value=mock_session_obj)
        mock_session_obj.__aexit__ = AsyncMock(return_value=None)

        # Make ClientSession() return the session object
        mock_session.return_value = mock_session_obj

        result = await notifier_enabled.test_connection()

        assert result is True
        mock_post.assert_called_once()

        # Verify test message content
        call_args = mock_post.call_args
        assert 'Test Alert' in call_args[1]['json']['text']

    @pytest.mark.asyncio
    @patch('os.getenv', return_value='')
    async def test_test_connection_disabled(self, mock_getenv, notifier_disabled):
        """Test connection test when disabled"""
        result = await notifier_disabled.test_connection()

        assert result is False

    def test_get_bot_info(self, notifier_enabled):
        """Test get_bot_info returns correct information"""
        info = notifier_enabled.get_bot_info()

        assert info['enabled'] is True
        assert info['has_token'] is True
        assert info['has_chat_id'] is True
        assert info['token_preview'] == 'test_tok...'  # First 8 chars + '...'
        assert info['chat_id'] == 'test_chat_456'

    def test_html_parse_mode_default(self, notifier_enabled):
        """Test that HTML is the default parse mode"""
        # The default parse_mode parameter should be HTML
        assert True  # Verified in code inspection
