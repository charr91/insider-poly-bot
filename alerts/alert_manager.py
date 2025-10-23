"""
Alert Manager
Handles sending alerts through various channels (Discord, Telegram, console, etc.)
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from typing import Dict, List, Union, Protocol, Optional
from enum import Enum
import os
from abc import ABC, abstractmethod
from common import AlertSeverity
from alerts.recommendation_engine import RecommendationEngine
from alerts.telegram_notifier import TelegramNotifier
from alerts.formatters import DiscordFormatter, TelegramFormatter

logger = logging.getLogger(__name__)

class AlertStorage(Protocol):
    """Protocol for alert storage backends"""

    @abstractmethod
    async def save_alert(self, alert_record: Dict) -> None:
        """Save an alert record to storage"""
        pass

    @abstractmethod
    async def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Get alerts from the last N hours"""
        pass

    @abstractmethod
    async def should_send_alert(self, alert: Dict, max_per_hour: int, duplicate_window_minutes: int = 10) -> bool:
        """Check if alert should be sent based on rate limiting and deduplication"""
        pass

    @abstractmethod
    async def clear_old_alerts(self, max_age_hours: int = 48) -> None:
        """Remove alerts older than specified hours"""
        pass

class MemoryAlertStorage:
    """In-memory alert storage (current default behavior)"""

    def __init__(self):
        self.alert_history: List[Dict] = []

    async def save_alert(self, alert_record: Dict) -> None:
        """Save alert record to in-memory storage"""
        self.alert_history.append(alert_record)

    async def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Get alerts from the last N hours"""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        return [
            alert for alert in self.alert_history
            if alert['timestamp'].timestamp() > cutoff_time
        ]

    async def should_send_alert(self, alert: Dict, max_per_hour: int, duplicate_window_minutes: int = 10) -> bool:
        """Check rate limiting and deduplication"""
        now = datetime.now(timezone.utc)

        # Rate limiting - count recent alerts
        recent_alerts = []
        for a in self.alert_history:
            ts = a['timestamp']
            # Ensure timezone-aware comparison
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if (now - ts).total_seconds() < 3600:  # Last hour
                recent_alerts.append(a)

        if len(recent_alerts) >= max_per_hour:
            return False

        # Deduplication - check for same market/type in recent window
        market_id = alert.get('market_id')
        alert_type = alert.get('alert_type')
        duplicate_window = duplicate_window_minutes * 60

        for hist_alert in self.alert_history:
            ts = hist_alert['timestamp']
            # Ensure timezone-aware comparison
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if (hist_alert['market_id'] == market_id and
                hist_alert['alert_type'] == alert_type and
                (now - ts).total_seconds() < duplicate_window):
                return False

        return True

    async def clear_old_alerts(self, max_age_hours: int = 48) -> None:
        """Remove alerts older than specified hours"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        self.alert_history = [
            alert for alert in self.alert_history
            if alert['timestamp'].timestamp() > cutoff_time
        ]

class AlertManager:
    """Manages alert notifications across different channels"""

    def __init__(self, settings_or_config=None, storage: AlertStorage = None, token_to_outcome: Optional[Dict[str, str]] = None):
        # Support both old config dict format and new Settings object for backward compatibility
        if hasattr(settings_or_config, 'alerts'):
            # New Settings object format
            settings = settings_or_config
            self.discord_webhook = settings.alerts.discord_webhook
            self.min_severity = settings.alerts.min_severity
            self.discord_min_severity = settings.alerts.discord_min_severity
            self.max_alerts_per_hour = settings.alerts.max_alerts_per_hour
            # Telegram settings (with defaults)
            self.telegram_enabled = getattr(settings.alerts, 'telegram_enabled', False)
            self.telegram_min_severity = getattr(settings.alerts, 'telegram_min_severity', 'MEDIUM')
        else:
            # Old config dict format (fallback)
            config = settings_or_config or {}
            alert_config = config.get('alerts', {})
            self.discord_webhook = os.getenv('DISCORD_WEBHOOK', alert_config.get('discord_webhook', ''))
            self.min_severity = alert_config.get('min_severity', 'MEDIUM')
            self.discord_min_severity = alert_config.get('discord_min_severity', 'MEDIUM')
            self.max_alerts_per_hour = alert_config.get('max_alerts_per_hour', 10)
            # Telegram settings
            self.telegram_enabled = alert_config.get('telegram_enabled', False)
            self.telegram_min_severity = alert_config.get('telegram_min_severity', 'MEDIUM')

        # Alert filtering using enum
        self.min_severity_level = AlertSeverity.get_level(self.min_severity)
        self.discord_min_severity_level = AlertSeverity.get_level(self.discord_min_severity)
        self.telegram_min_severity_level = AlertSeverity.get_level(self.telegram_min_severity)

        # Storage backend - default to in-memory for backward compatibility
        self.storage = storage or MemoryAlertStorage()

        # For backward compatibility, maintain direct access to history
        self.alert_history = self.storage.alert_history if hasattr(self.storage, 'alert_history') else []

        # Initialize new components
        self.recommendation_engine = RecommendationEngine(token_to_outcome=token_to_outcome or {})
        self.telegram_notifier = TelegramNotifier()
        self.discord_formatter = DiscordFormatter()
        self.telegram_formatter = TelegramFormatter()

        # Log initialization status
        if self.telegram_notifier.is_enabled():
            logger.info("📱 Telegram notifications enabled")
        else:
            logger.debug("📱 Telegram notifications disabled")
        
    async def send_alert(self, alert: Dict) -> bool:
        """Send alert through configured channels

        Returns:
            bool: True if alert was successfully sent, False if skipped
        """
        try:
            # Check severity filter
            alert_severity_level = AlertSeverity.get_level(alert.get('severity', 'LOW'))
            if alert_severity_level < self.min_severity_level:
                logger.debug(f"Skipping alert - severity {alert.get('severity')} below threshold {self.min_severity}")
                return False

            # Rate limiting check
            if not await self.storage.should_send_alert(alert, self.max_alerts_per_hour):
                logger.debug("Rate limiting - skipping alert")
                return False

            # Generate recommendation using new engine
            recommendation = self.recommendation_engine.generate_recommendation(
                alert_type=alert.get('alert_type'),
                severity=AlertSeverity[alert.get('severity', 'MEDIUM')] if isinstance(alert.get('severity'), str) else alert.get('severity'),
                analysis=alert.get('analysis', {}),
                market_data=alert.get('market_data', {}),
                confidence_score=alert.get('confidence_score', 0),
                multi_metric=alert.get('multi_metric', False),
                supporting_anomalies=alert.get('supporting_anomalies', [])
            )

            # Add recommendation to alert for logging
            alert['recommendation'] = recommendation

            # Generate market URL from slug
            market_url = self._generate_market_url(alert)

            # Log alert
            self._log_alert(alert)

            # Send through channels
            await self._send_console_alert(alert)

            # Discord routing decision
            if self.discord_webhook:
                if alert_severity_level >= self.discord_min_severity_level:
                    logger.debug(f"📱 Sending to Discord: {alert.get('severity')} alert (level {alert_severity_level}) >= {self.discord_min_severity} threshold")
                    await self._send_discord_alert(alert, recommendation, market_url)
                else:
                    logger.debug(f"📱 Skipping Discord: {alert.get('severity')} alert (level {alert_severity_level}) below {self.discord_min_severity} threshold")
            else:
                logger.debug("📱 Discord webhook not configured")

            # Telegram routing decision (consistent with Discord pattern)
            if self.telegram_notifier.is_enabled():
                if alert_severity_level >= self.telegram_min_severity_level:
                    logger.debug(f"📱 Sending to Telegram: {alert.get('severity')} alert (level {alert_severity_level}) >= {self.telegram_min_severity} threshold")
                    await self._send_telegram_alert(alert, recommendation, market_url)
                else:
                    logger.debug(f"📱 Skipping Telegram: {alert.get('severity')} alert (level {alert_severity_level}) below {self.telegram_min_severity} threshold")
            else:
                logger.debug("📱 Telegram notifications disabled (bot token or chat ID not configured)")

            # Record alert using storage
            # Pass the full alert dict to capture all fields (analysis, confidence_score, etc.)
            alert_record = {
                **alert,  # Include all fields from the alert
                'timestamp': datetime.now(timezone.utc)  # Ensure timestamp is timezone-aware
            }
            await self.storage.save_alert(alert_record)

            # Update backward compatibility reference
            if hasattr(self.storage, 'alert_history'):
                self.alert_history = self.storage.alert_history

            # Clean old history
            await self.storage.clear_old_alerts()

            # Alert was successfully sent
            return True

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    
    
    def _log_alert(self, alert: Dict):
        """Log alert to console"""
        severity = alert.get('severity', 'UNKNOWN')
        market_question = alert.get('market_question', 'Unknown Market')
        alert_type = alert.get('alert_type', 'UNKNOWN')

        log_msg = f"🚨 {severity} ALERT: {market_question[:50]}..."

        if severity in ['CRITICAL', 'HIGH']:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        logger.info(f"   Type: {alert_type}")

        # Log analysis summary
        analysis = alert.get('analysis', {})
        if isinstance(analysis, dict):
            if 'max_anomaly_score' in analysis:
                logger.info(f"   Anomaly Score: {analysis['max_anomaly_score']:.2f}")

            if 'total_whale_volume' in analysis:
                logger.info(f"   Whale Volume: ${analysis['total_whale_volume']:,.0f}")

            if 'coordination_score' in analysis:
                logger.info(f"   Coordination Score: {analysis['coordination_score']:.2f}")

        # Log new recommendation
        recommendation = alert.get('recommendation')
        if recommendation:
            logger.info(f"   Recommendation: {recommendation.get('text', 'N/A')}")
    
    async def _send_console_alert(self, alert: Dict):
        """Send alert to console (already handled by _log_alert)"""
        pass  # Logging is handled in _log_alert

    async def _send_discord_alert(self, alert: Dict, recommendation: Dict, market_url: Optional[str] = None):
        """Send alert to Discord webhook using new formatter"""
        if not self.discord_webhook:
            return

        try:
            # Use new formatter to create embed
            embed = self.discord_formatter.format_alert(alert, recommendation, market_url)

            async with aiohttp.ClientSession() as session:
                payload = {"embeds": [embed]}
                async with session.post(self.discord_webhook, json=payload, timeout=10) as resp:
                    if resp.status in [200, 204]:  # Discord returns 204 for successful webhooks
                        logger.debug("Discord alert sent successfully")
                    else:
                        logger.warning(f"Discord webhook returned status {resp.status}")

        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")

    async def _send_telegram_alert(self, alert: Dict, recommendation: Dict, market_url: Optional[str] = None):
        """Send alert to Telegram using new formatter"""
        try:
            # Use new formatter to create HTML message
            message = self.telegram_formatter.format_alert(alert, recommendation, market_url)

            # Send via Telegram notifier
            success = await self.telegram_notifier.send_alert(message)

            if success:
                logger.debug("Telegram alert sent successfully")
            else:
                logger.warning("Failed to send Telegram alert")

        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    def _generate_market_url(self, alert: Dict) -> Optional[str]:
        """Generate Polymarket market URL from alert data"""
        try:
            # Try to get slug from market data
            market = alert.get('market', {})
            slug = market.get('slug')

            if slug:
                return f"https://polymarket.com/event/{slug}"

            # Fallback: try to get from market_id if it contains slug info
            market_id = alert.get('market_id')
            if market_id and isinstance(market_id, dict):
                slug = market_id.get('slug')
                if slug:
                    return f"https://polymarket.com/event/{slug}"

            logger.debug(f"No slug found for market {alert.get('market_question', 'Unknown')}")
            return None

        except Exception as e:
            logger.error(f"Error generating market URL: {e}")
            return None
    
    async def test_connections(self):
        """Test alert system connections"""
        logger.info("🔔 Testing alert systems...")

        # Test Discord webhook
        if self.discord_webhook:
            logger.info(f"🔗 Testing Discord webhook: {self.discord_webhook[:50]}...")
            try:
                test_embed = {
                    "title": "🧪 Test Alert",
                    "description": "Polymarket Insider Bot - Alert System Test",
                    "color": 0x00FF00,  # Green
                    "timestamp": datetime.now().isoformat(),
                    "footer": {"text": "This is a test message"}
                }

                async with aiohttp.ClientSession() as session:
                    payload = {"embeds": [test_embed]}
                    async with session.post(self.discord_webhook, json=payload, timeout=10) as resp:
                        response_text = await resp.text()
                        if resp.status in [200, 204]:  # Discord returns 204 for successful webhooks
                            logger.info("✅ Discord webhook test successful")
                        else:
                            logger.warning(f"⚠️ Discord webhook test failed: HTTP {resp.status}")
                            logger.warning(f"   Response: {response_text[:200]}")

            except Exception as e:
                logger.error(f"❌ Discord webhook test failed: {e}")
                import traceback
                logger.error(f"   Full error: {traceback.format_exc()}")
        else:
            logger.info("ℹ️ No Discord webhook configured")

        # Test Telegram bot
        if self.telegram_notifier.is_enabled():
            logger.info("🔗 Testing Telegram bot connection...")
            try:
                success = await self.telegram_notifier.test_connection()
                if not success:
                    logger.warning("⚠️ Telegram connection test returned False")
            except Exception as e:
                logger.error(f"❌ Telegram connection test failed: {e}")
                import traceback
                logger.error(f"   Full error: {traceback.format_exc()}")
        else:
            logger.info("ℹ️ Telegram bot not configured")

        logger.info("✅ Alert system testing complete")
    
    async def get_alert_stats(self) -> Dict:
        """Get statistics about sent alerts"""
        # Use storage interface to get recent alerts
        recent_alerts = await self.storage.get_recent_alerts(24)

        # Count by severity
        severity_counts = {}
        for alert in recent_alerts:
            severity = alert['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Check rate limit status
        recent_hour_alerts = await self.storage.get_recent_alerts(1)

        return {
            'total_alerts_24h': len(recent_alerts),
            'by_severity': severity_counts,
            'rate_limit_active': len(recent_hour_alerts) >= self.max_alerts_per_hour
        }

    async def get_statistics(self) -> Dict:
        """Alias for get_alert_stats for backward compatibility"""
        return await self.get_alert_stats()