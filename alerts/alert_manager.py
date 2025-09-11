"""
Alert Manager
Handles sending alerts through various channels (Discord, console, etc.)
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Dict, List, Union, Protocol
from enum import Enum
import os
from abc import ABC, abstractmethod
from common import AlertSeverity

logger = logging.getLogger(__name__)

class AlertStorage(Protocol):
    """Protocol for alert storage backends"""
    
    @abstractmethod
    def save_alert(self, alert_record: Dict) -> None:
        """Save an alert record to storage"""
        pass
    
    @abstractmethod  
    def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Get alerts from the last N hours"""
        pass
    
    @abstractmethod
    def should_send_alert(self, alert: Dict, max_per_hour: int, duplicate_window_minutes: int = 10) -> bool:
        """Check if alert should be sent based on rate limiting and deduplication"""
        pass
    
    @abstractmethod
    def clear_old_alerts(self, max_age_hours: int = 48) -> None:
        """Remove alerts older than specified hours"""
        pass

class MemoryAlertStorage:
    """In-memory alert storage (current default behavior)"""
    
    def __init__(self):
        self.alert_history: List[Dict] = []
    
    def save_alert(self, alert_record: Dict) -> None:
        """Save alert record to in-memory storage"""
        self.alert_history.append(alert_record)
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Get alerts from the last N hours"""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        return [
            alert for alert in self.alert_history
            if alert['timestamp'].timestamp() > cutoff_time
        ]
    
    def should_send_alert(self, alert: Dict, max_per_hour: int, duplicate_window_minutes: int = 10) -> bool:
        """Check rate limiting and deduplication"""
        now = datetime.now()
        
        # Rate limiting - count recent alerts
        recent_alerts = [
            a for a in self.alert_history 
            if (now - a['timestamp']).total_seconds() < 3600  # Last hour
        ]
        
        if len(recent_alerts) >= max_per_hour:
            return False
        
        # Deduplication - check for same market/type in recent window
        market_id = alert.get('market_id')
        alert_type = alert.get('alert_type')
        duplicate_window = duplicate_window_minutes * 60
        
        for hist_alert in self.alert_history:
            if (hist_alert['market_id'] == market_id and 
                hist_alert['alert_type'] == alert_type and
                (now - hist_alert['timestamp']).total_seconds() < duplicate_window):
                return False
        
        return True
    
    def clear_old_alerts(self, max_age_hours: int = 48) -> None:
        """Remove alerts older than specified hours"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        self.alert_history = [
            alert for alert in self.alert_history
            if alert['timestamp'].timestamp() > cutoff_time
        ]

class AlertManager:
    """Manages alert notifications across different channels"""
    
    def __init__(self, settings_or_config=None, storage: AlertStorage = None):
        # Support both old config dict format and new Settings object for backward compatibility
        if hasattr(settings_or_config, 'alerts'):
            # New Settings object format
            settings = settings_or_config
            self.discord_webhook = settings.alerts.discord_webhook
            self.min_severity = settings.alerts.min_severity
            self.discord_min_severity = settings.alerts.discord_min_severity
            self.max_alerts_per_hour = settings.alerts.max_alerts_per_hour
        else:
            # Old config dict format (fallback)
            config = settings_or_config or {}
            alert_config = config.get('alerts', {})
            self.discord_webhook = os.getenv('DISCORD_WEBHOOK', alert_config.get('discord_webhook', ''))
            self.min_severity = alert_config.get('min_severity', 'MEDIUM')
            self.discord_min_severity = alert_config.get('discord_min_severity', 'MEDIUM')
            self.max_alerts_per_hour = alert_config.get('max_alerts_per_hour', 10)
        
        # Alert filtering using enum
        self.min_severity_level = AlertSeverity.get_level(self.min_severity)
        self.discord_min_severity_level = AlertSeverity.get_level(self.discord_min_severity)
        
        # Storage backend - default to in-memory for backward compatibility
        self.storage = storage or MemoryAlertStorage()
        
        # For backward compatibility, maintain direct access to history
        self.alert_history = self.storage.alert_history if hasattr(self.storage, 'alert_history') else []
        
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
            if not self.storage.should_send_alert(alert, self.max_alerts_per_hour):
                logger.debug("Rate limiting - skipping alert")
                return False
            
            # Log alert
            self._log_alert(alert)
            
            # Send through channels
            await self._send_console_alert(alert)
            
            # Discord routing decision
            if self.discord_webhook:
                if alert_severity_level >= self.discord_min_severity_level:
                    logger.debug(f"📱 Sending to Discord: {alert.get('severity')} alert (level {alert_severity_level}) >= {self.discord_min_severity} threshold")
                    await self._send_discord_alert(alert)
                else:
                    logger.debug(f"📱 Skipping Discord: {alert.get('severity')} alert (level {alert_severity_level}) below {self.discord_min_severity} threshold")
            else:
                logger.debug("📱 Discord webhook not configured")
            
            # Record alert using storage
            alert_record = {
                'timestamp': datetime.now(),
                'market_id': alert.get('market_id'),
                'alert_type': alert.get('alert_type'),
                'severity': alert.get('severity')
            }
            self.storage.save_alert(alert_record)
            
            # Update backward compatibility reference
            if hasattr(self.storage, 'alert_history'):
                self.alert_history = self.storage.alert_history
            
            # Clean old history
            self.storage.clear_old_alerts()
            
            # Alert was successfully sent
            return True
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
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
        
        # Log recommended action
        action = alert.get('recommended_action')
        if action:
            logger.info(f"   Action: {action}")
    
    async def _send_console_alert(self, alert: Dict):
        """Send alert to console (already handled by _log_alert)"""
        pass  # Logging is handled in _log_alert
    
    async def _send_discord_alert(self, alert: Dict):
        """Send alert to Discord webhook"""
        if not self.discord_webhook:
            return
        
        try:
            embed = self._create_discord_embed(alert)
            
            async with aiohttp.ClientSession() as session:
                payload = {"embeds": [embed]}
                async with session.post(self.discord_webhook, json=payload, timeout=10) as resp:
                    if resp.status in [200, 204]:  # Discord returns 204 for successful webhooks
                        logger.debug("Discord alert sent successfully")
                    else:
                        logger.warning(f"Discord webhook returned status {resp.status}")
        
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
    
    def _create_discord_embed(self, alert: Dict) -> Dict:
        """Create Discord embed for alert"""
        severity = alert.get('severity', 'UNKNOWN')
        market_question = alert.get('market_question', 'Unknown Market')
        alert_type = alert.get('alert_type', 'UNKNOWN')
        
        # Color based on severity
        colors = {
            'CRITICAL': 0xFF0000,  # Red
            'HIGH': 0xFF8C00,      # Dark orange
            'MEDIUM': 0xFFD700,    # Gold
            'LOW': 0x32CD32        # Lime green
        }
        color = colors.get(severity, 0x808080)  # Default gray
        
        # Create embed
        # Convert enum to string if needed, then format
        alert_type_str = alert_type.value if hasattr(alert_type, 'value') else str(alert_type)
        embed = {
            "title": f"🚨 {severity}: {alert_type_str.replace('_', ' ').title()}",
            "description": market_question,
            "color": color,
            "timestamp": alert.get('timestamp', datetime.now().isoformat()),
            "fields": []
        }
        
        # Add analysis fields
        analysis = alert.get('analysis', {})
        
        # Volume analysis
        if 'max_anomaly_score' in analysis:
            embed["fields"].append({
                "name": "Volume Anomaly",
                "value": f"Score: {analysis['max_anomaly_score']:.2f}",
                "inline": True
            })
        
        # Whale analysis
        if 'total_whale_volume' in analysis:
            whale_volume = analysis['total_whale_volume']
            whale_count = analysis.get('whale_count', 0)
            dominant_side = analysis.get('dominant_side', 'N/A')
            
            embed["fields"].append({
                "name": "Whale Activity",
                "value": f"${whale_volume:,.0f} from {whale_count} whales\nDirection: {dominant_side}",
                "inline": True
            })
        
        # Price analysis
        if 'analysis' in analysis and 'price_change_pct' in analysis['analysis']:
            price_analysis = analysis['analysis']
            price_change = price_analysis['price_change_pct']
            volatility_spike = price_analysis.get('volatility_spike', 1)
            
            embed["fields"].append({
                "name": "Price Movement",
                "value": f"Change: {price_change:+.1f}%\nVolatility: {volatility_spike:.1f}x normal",
                "inline": True
            })
        
        # Coordination analysis
        if 'coordination_score' in analysis:
            coord_score = analysis['coordination_score']
            unique_wallets = analysis.get('unique_wallets', 0)
            
            embed["fields"].append({
                "name": "Coordination",
                "value": f"Score: {coord_score:.2f}\nWallets: {unique_wallets}",
                "inline": True
            })
        
        # Market info
        market_data = alert.get('market_data', {})
        if market_data:
            volume_24hr = market_data.get('volume24hr', 0)
            last_price = market_data.get('lastTradePrice', 0)
            
            embed["fields"].append({
                "name": "Market Info",
                "value": f"24h Volume: ${volume_24hr:,.0f}\nLast Price: ${last_price:.3f}",
                "inline": True
            })
        
        # Recommended action
        action = alert.get('recommended_action')
        if action:
            embed["fields"].append({
                "name": "Recommended Action",
                "value": action,
                "inline": False
            })
        
        # Add footer
        embed["footer"] = {
            "text": f"Market ID: {alert.get('market_id', 'Unknown')[:20]}..."
        }
        
        return embed
    
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
        
        logger.info("✅ Alert system testing complete")
    
    def get_alert_stats(self) -> Dict:
        """Get statistics about sent alerts"""
        # Use storage interface to get recent alerts
        recent_alerts = self.storage.get_recent_alerts(24)
        
        # Count by severity
        severity_counts = {}
        for alert in recent_alerts:
            severity = alert['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Check rate limit status
        recent_hour_alerts = self.storage.get_recent_alerts(1)
        
        return {
            'total_alerts_24h': len(recent_alerts),
            'by_severity': severity_counts,
            'rate_limit_active': len(recent_hour_alerts) >= self.max_alerts_per_hour
        }
    
    def get_statistics(self) -> Dict:
        """Alias for get_alert_stats for backward compatibility"""
        return self.get_alert_stats()