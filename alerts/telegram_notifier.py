"""
Telegram Notifier
Sends formatted alerts to Telegram using Bot API
"""

import aiohttp
import logging
import os
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Handles sending alert notifications to Telegram"""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize Telegram notifier

        Args:
            bot_token: Telegram Bot API token (defaults to TELEGRAM_BOT_TOKEN env var)
            chat_id: Telegram chat ID to send messages to (defaults to TELEGRAM_CHAT_ID env var)
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID', '')
        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            logger.warning("Telegram notifier disabled - missing bot_token or chat_id")

    async def send_alert(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send alert message to Telegram

        Args:
            message: Formatted message text (HTML or Markdown)
            parse_mode: Parse mode for formatting (HTML or Markdown)

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled")
            return False

        try:
            url = f"{self.api_base_url}/sendMessage"

            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False  # Enable link previews
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        logger.debug("Telegram alert sent successfully")
                        return True
                    else:
                        response_text = await resp.text()
                        logger.error(f"Telegram API error: HTTP {resp.status} - {response_text}")
                        return False

        except aiohttp.ClientError as e:
            logger.error(f"Telegram connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    async def test_connection(self) -> bool:
        """
        Test Telegram bot connection

        Returns:
            bool: True if connection successful, False otherwise
        """
        if not self.enabled:
            logger.warning("Cannot test Telegram connection - bot_token or chat_id missing")
            return False

        try:
            test_message = (
                "🧪 <b>Test Alert</b>\n\n"
                "Polymarket Insider Bot - Telegram Alert System Test\n\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            result = await self.send_alert(test_message)

            if result:
                logger.info("✅ Telegram connection test successful")
            else:
                logger.warning("⚠️ Telegram connection test failed")

            return result

        except Exception as e:
            logger.error(f"❌ Telegram connection test failed: {e}")
            return False

    def is_enabled(self) -> bool:
        """Check if Telegram notifications are enabled"""
        return self.enabled

    def get_bot_info(self) -> Dict:
        """Get bot configuration info (for debugging)"""
        return {
            'enabled': self.enabled,
            'has_token': bool(self.bot_token),
            'has_chat_id': bool(self.chat_id),
            'token_preview': f"{self.bot_token[:8]}..." if self.bot_token else None,
            'chat_id': self.chat_id if self.chat_id else None
        }
