"""
Telegram Alert Formatter
Formats alerts as HTML messages for Telegram following the PoliWhale Alerts design
"""

from typing import Dict, Optional
from datetime import datetime
import html
import logging

logger = logging.getLogger(__name__)


class TelegramFormatter:
    """Formats alerts for Telegram Bot API using HTML"""

    # Severity emoji mapping
    SEVERITY_EMOJIS = {
        'CRITICAL': '🔴',
        'HIGH': '🟠',
        'MEDIUM': '🟡',
        'LOW': '🟢'
    }

    def __init__(self):
        pass

    def format_alert(self, alert: Dict, recommendation: Dict, market_url: Optional[str] = None) -> str:
        """
        Format alert as HTML message for Telegram

        Args:
            alert: Alert data including market info, analysis, etc.
            recommendation: Recommendation dict from RecommendationEngine
            market_url: URL to Polymarket market page

        Returns:
            HTML-formatted string ready to send to Telegram
        """
        severity = alert.get('severity', 'UNKNOWN')
        market_question = alert.get('market_question', 'Unknown Market')
        alert_type = alert.get('alert_type')
        alert_type_str = alert_type.value if hasattr(alert_type, 'value') else str(alert_type)
        confidence_score = alert.get('confidence_score', 0)
        analysis = alert.get('analysis', {})

        # Get emoji for severity
        emoji = self.SEVERITY_EMOJIS.get(severity, '⚪')

        # Build message sections
        sections = []

        # Header with severity
        severity_line = f"{emoji} <b>{severity} SIGNAL</b>"
        sections.append(severity_line)
        sections.append("")  # Blank line

        # Recommendation section
        if recommendation:
            sections.append(self._format_recommendation(recommendation))
            sections.append("")

        # Market section
        sections.append(self._format_market_info(alert, market_question))
        sections.append("")

        # Detected section
        sections.append(self._format_detected_info(alert_type_str, analysis, alert))
        sections.append("")

        # Trade details if available
        if alert_type_str in ['WHALE_ACTIVITY', 'COORDINATED_TRADING']:
            trade_details = self._format_trade_details(analysis)
            if trade_details:
                sections.append(trade_details)
                sections.append("")

        # Confidence score (cap at 100)
        confidence_pct = min(int((confidence_score / 10) * 100), 100)
        sections.append(f"📈 <b>CONFIDENCE:</b> {confidence_pct}/100")

        # Latency (time since alert was created)
        alert_time = alert.get('timestamp')
        if isinstance(alert_time, datetime):
            time_diff = (datetime.now() - alert_time).total_seconds()
            latency_str = self._format_latency(time_diff)
            sections.append(f"⏱️ <b>Latency:</b> {latency_str}")

        sections.append("")

        # View market link
        if market_url:
            sections.append(f'<a href="{html.escape(market_url)}">View Market</a>')

        # Join all sections with newlines
        return "\n".join(sections)

    def _format_recommendation(self, recommendation: Dict) -> str:
        """Format recommendation section"""
        action = recommendation.get('action', 'MONITOR')
        text = recommendation.get('text', 'Monitor activity')
        reasoning = recommendation.get('reasoning', '')

        # Get emoji for action
        if action == 'BUY':
            emoji = '💚'
        elif action == 'SELL':
            emoji = '❤️'
        else:
            emoji = '👁️'

        lines = [
            f"⚡ <b>RECOMMENDATION:</b>",
            f"{emoji} <b>{html.escape(text)}</b>"
        ]

        if reasoning:
            lines.append(f"<i>{html.escape(reasoning)}</i>")

        return "\n".join(lines)

    def _format_market_info(self, alert: Dict, market_question: str) -> str:
        """Format market information section"""
        market_data = alert.get('market_data', {})
        volume_24hr = market_data.get('volume24hr', 0)
        last_price = market_data.get('lastTradePrice', 0)

        # Format volume
        if volume_24hr >= 1000000:
            volume_str = f"${volume_24hr/1000000:.1f}M"
        elif volume_24hr >= 1000:
            volume_str = f"${volume_24hr/1000:.0f}K"
        else:
            volume_str = f"${volume_24hr:.0f}"

        lines = [
            "🎯 <b>MARKET:</b>",
            html.escape(market_question),
            f"Current: {last_price:.2f}¢ YES",  # Simplified for now
            f"Volume: {volume_str}"
        ]

        return "\n".join(lines)

    def _format_detected_info(self, alert_type_str: str, analysis: Dict, alert: Dict) -> str:
        """Format detection information section"""
        lines = [
            "📊 <b>DETECTED:</b>",
            f"<b>Alert:</b> {alert_type_str.replace('_', ' ').title()}"
        ]

        # Add type-specific metrics
        if alert_type_str == 'VOLUME_SPIKE':
            anomaly_score = analysis.get('max_anomaly_score', 0)
            lines.append(f"<b>Score:</b> {anomaly_score:.1f}x normal")

        elif alert_type_str == 'WHALE_ACTIVITY':
            total_volume = analysis.get('total_whale_volume', 0)
            whale_count = analysis.get('whale_count', 0)
            dominant_side = analysis.get('dominant_side', 'N/A')
            direction_imbalance = analysis.get('direction_imbalance', 0)

            volume_str = f"${total_volume/1000:.0f}K" if total_volume >= 1000 else f"${total_volume:.0f}"
            lines.append(f"<b>Whales:</b> {volume_str} from {whale_count} wallet{'s' if whale_count != 1 else ''}")
            lines.append(f"<b>Direction:</b> {direction_imbalance*100:.0f}% {dominant_side} bias")

        elif alert_type_str == 'UNUSUAL_PRICE_MOVEMENT':
            price_analysis = analysis.get('analysis', {})
            price_change_pct = price_analysis.get('price_change_pct', 0)
            volatility_spike = price_analysis.get('volatility_spike', 1)

            lines.append(f"<b>Change:</b> {price_change_pct:+.1f}%")
            lines.append(f"<b>Volatility:</b> {volatility_spike:.1f}x normal")

        elif alert_type_str == 'COORDINATED_TRADING':
            coord_score = analysis.get('coordination_score', 0)
            unique_wallets = analysis.get('unique_wallets', 0)

            lines.append(f"<b>Coordination:</b> {coord_score:.2f} score")
            lines.append(f"<b>Wallets:</b> {unique_wallets} coordinated")

        # Add timestamp
        alert_time = alert.get('timestamp')
        if isinstance(alert_time, datetime):
            time_diff = (datetime.now() - alert_time).total_seconds()
            time_str = self._format_latency(time_diff)
            lines.append(f"<b>Detected:</b> {time_str} ago")

        return "\n".join(lines)

    def _format_trade_details(self, analysis: Dict) -> Optional[str]:
        """Format trade details for whale/coordination alerts"""
        whale_breakdown = analysis.get('whale_breakdown', {})

        if not whale_breakdown:
            return None

        # Get top whale (largest volume)
        top_whale = None
        max_volume = 0

        for wallet, data in whale_breakdown.items():
            if isinstance(data, dict):
                volume = data.get('total_volume', 0)
                if volume > max_volume:
                    max_volume = volume
                    top_whale = {
                        'wallet': wallet,
                        'volume': volume,
                        'side': data.get('dominant_side', 'UNKNOWN'),
                        'avg_price': data.get('avg_price', 0),
                        'tx_hash': data.get('tx_hash')  # If available
                    }

        if not top_whale:
            return None

        volume_str = f"${top_whale['volume']/1000:.1f}K" if top_whale['volume'] >= 1000 else f"${top_whale['volume']:.0f}"

        lines = [
            "💰 <b>TRADE DETAILS:</b>",
            f"<b>Top Whale:</b> {volume_str} {top_whale['side']} @ ${top_whale['avg_price']:.2f}"
        ]

        # Add wallet address (shortened with link) - skip if unknown
        if top_whale['wallet'] and top_whale['wallet'] != 'unknown':
            wallet_short = f"{top_whale['wallet'][:6]}...{top_whale['wallet'][-4:]}"
            wallet_url = f"https://polygonscan.com/address/{top_whale['wallet']}"
            lines.append(f'<b>Wallet:</b> <a href="{wallet_url}">{html.escape(wallet_short)}</a>')

        # Add transaction link if available
        if top_whale.get('tx_hash') and top_whale['tx_hash'] != 'unknown':
            tx_short = f"{top_whale['tx_hash'][:6]}...{top_whale['tx_hash'][-4:]}"
            tx_url = f"https://polygonscan.com/tx/{top_whale['tx_hash']}"
            lines.append(f'<b>Tx:</b> <a href="{tx_url}">{html.escape(tx_short)}</a>')

        return "\n".join(lines)

    def _format_latency(self, seconds: float) -> str:
        """Format time difference as human-readable string"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
