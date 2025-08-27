"""
Alert Manager
Handles sending alerts through various channels (Discord, console, etc.)
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Dict, List
import os

logger = logging.getLogger(__name__)

class AlertManager:
    """Manages alert notifications across different channels"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.alert_config = self.config.get('alerts', {})
        
        # Discord configuration
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK', self.alert_config.get('discord_webhook', ''))
        
        # Alert filtering
        self.min_severity = self.alert_config.get('min_severity', 'MEDIUM')
        self.severity_levels = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}
        self.min_severity_level = self.severity_levels.get(self.min_severity, 2)
        
        # Rate limiting
        self.alert_history = []
        self.max_alerts_per_hour = 10
        
    async def send_alert(self, alert: Dict):
        """Send alert through configured channels"""
        try:
            # Check severity filter
            alert_severity_level = self.severity_levels.get(alert.get('severity', 'LOW'), 1)
            if alert_severity_level < self.min_severity_level:
                logger.debug(f"Skipping alert - severity {alert.get('severity')} below threshold {self.min_severity}")
                return
            
            # Rate limiting check
            if not self._should_send_alert(alert):
                logger.debug("Rate limiting - skipping alert")
                return
            
            # Log alert
            self._log_alert(alert)
            
            # Send through channels
            await self._send_console_alert(alert)
            
            if self.discord_webhook and alert_severity_level >= 3:  # HIGH and CRITICAL only
                await self._send_discord_alert(alert)
            
            # Record alert
            self.alert_history.append({
                'timestamp': datetime.now(),
                'market_id': alert.get('market_id'),
                'alert_type': alert.get('alert_type'),
                'severity': alert.get('severity')
            })
            
            # Clean old history
            self._clean_alert_history()
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    def _should_send_alert(self, alert: Dict) -> bool:
        """Check if alert should be sent based on rate limiting"""
        # Count recent alerts
        now = datetime.now()
        recent_alerts = [
            a for a in self.alert_history 
            if (now - a['timestamp']).total_seconds() < 3600  # Last hour
        ]
        
        if len(recent_alerts) >= self.max_alerts_per_hour:
            return False
        
        # Check for duplicate alerts (same market, same type in last 10 minutes)
        market_id = alert.get('market_id')
        alert_type = alert.get('alert_type')
        
        duplicate_window = 600  # 10 minutes
        for hist_alert in self.alert_history:
            if (hist_alert['market_id'] == market_id and 
                hist_alert['alert_type'] == alert_type and
                (now - hist_alert['timestamp']).total_seconds() < duplicate_window):
                return False
        
        return True
    
    def _clean_alert_history(self):
        """Remove old alerts from history"""
        now = datetime.now()
        # Keep only last 24 hours
        self.alert_history = [
            a for a in self.alert_history 
            if (now - a['timestamp']).total_seconds() < 86400
        ]
    
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
                    if resp.status == 200:
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
        embed = {
            "title": f"🚨 {severity}: {alert_type.replace('_', ' ').title()}",
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
                        if resp.status == 200:
                            logger.info("✅ Discord webhook test successful")
                        else:
                            logger.warning(f"⚠️ Discord webhook test failed: HTTP {resp.status}")
            
            except Exception as e:
                logger.error(f"❌ Discord webhook test failed: {e}")
        else:
            logger.info("ℹ️ No Discord webhook configured")
        
        logger.info("✅ Alert system testing complete")
    
    def get_alert_stats(self) -> Dict:
        """Get statistics about sent alerts"""
        now = datetime.now()
        
        # Last 24 hours
        recent_alerts = [
            a for a in self.alert_history 
            if (now - a['timestamp']).total_seconds() < 86400
        ]
        
        # Count by severity
        severity_counts = {}
        for alert in recent_alerts:
            severity = alert['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Count by type
        type_counts = {}
        for alert in recent_alerts:
            alert_type = alert['alert_type']
            type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
        
        return {
            'total_alerts_24h': len(recent_alerts),
            'by_severity': severity_counts,
            'by_type': type_counts,
            'rate_limit_active': len([
                a for a in recent_alerts 
                if (now - a['timestamp']).total_seconds() < 3600
            ]) >= self.max_alerts_per_hour
        }