"""
Discord Alert Formatter
Formats alerts as Discord embeds following the improved structure
"""

from typing import Dict, Optional
from datetime import datetime
from common import AlertSeverity
from alerts.recommendation_engine import format_confidence_display
from alerts.formatters.format_utils import format_market_price, format_volume, extract_outcome_name, _format_single_price
import logging

logger = logging.getLogger(__name__)


class DiscordFormatter:
    """Formats alerts for Discord webhooks"""

    # Severity color mapping
    SEVERITY_COLORS = {
        'CRITICAL': 0xFF0000,  # Red
        'HIGH': 0xFF8C00,      # Dark orange
        'MEDIUM': 0xFFD700,    # Gold/Yellow
        'LOW': 0x32CD32        # Lime green
    }

    # Severity emoji mapping
    SEVERITY_EMOJIS = {
        'CRITICAL': '🔴',
        'HIGH': '🟠',
        'MEDIUM': '🟡',
        'LOW': '🟢'
    }

    def __init__(self):
        pass

    def format_alert(self, alert: Dict, recommendation: Dict, market_url: Optional[str] = None) -> Dict:
        """
        Format alert as Discord embed

        Args:
            alert: Alert data including market info, analysis, etc.
            recommendation: Recommendation dict from RecommendationEngine
            market_url: URL to Polymarket market page

        Returns:
            Discord embed dict ready to send via webhook
        """
        severity = alert.get('severity', 'UNKNOWN')
        market_question = alert.get('market_question', 'Unknown Market')
        alert_type = alert.get('alert_type')
        alert_type_str = alert_type.value if hasattr(alert_type, 'value') else str(alert_type)
        timestamp = alert.get('timestamp', datetime.now().isoformat())
        confidence_score = alert.get('confidence_score', 0)
        analysis = alert.get('analysis', {})

        # Get color and emoji for severity
        color = self.SEVERITY_COLORS.get(severity, 0x808080)
        emoji = self.SEVERITY_EMOJIS.get(severity, '⚪')

        # Create base embed
        embed = {
            "title": f"{emoji} {severity} SIGNAL",
            "color": color,
            "timestamp": timestamp,
            "fields": []
        }

        # Add market info section (position 1)
        market_info = self._format_market_info(alert, market_question, market_url)
        embed["fields"].append({
            "name": "🎯 MARKET",
            "value": market_info,
            "inline": False
        })

        # Add detected section (position 2)
        detected_info = self._format_detected_info(alert_type_str, analysis, alert)
        embed["fields"].append({
            "name": "📊 DETECTED",
            "value": detected_info,
            "inline": False
        })

        # Add recommendation section (position 3)
        if recommendation:
            rec_emoji = self._get_recommendation_emoji(recommendation['action'])
            rec_text = f"{rec_emoji} **{recommendation['text']}**\n_{recommendation['reasoning']}_"
            embed["fields"].append({
                "name": "⚡ RECOMMENDATION",
                "value": rec_text,
                "inline": False
            })

        # Add trade details if available (position 4 - for whale/coordination alerts)
        if alert_type_str in ['WHALE_ACTIVITY', 'COORDINATED_TRADING']:
            trade_details = self._format_trade_details(analysis)
            if trade_details:
                embed["fields"].append({
                    "name": "💰 TRADE DETAILS",
                    "value": trade_details,
                    "inline": False
                })

        # Add related outcomes for grouped markets (position 5)
        related_markets = alert.get('related_markets', [])
        if related_markets and len(related_markets) > 0:
            related_outcomes_text = self._format_related_outcomes(related_markets)
            embed["fields"].append({
                "name": "📊 OTHER OUTCOMES",
                "value": related_outcomes_text,
                "inline": False
            })

        # Add confidence score footer with label (hybrid format)
        is_multi_metric = alert.get('multi_metric', False)
        confidence_label, confidence_pct = format_confidence_display(confidence_score, is_multi_metric)
        embed["footer"] = {
            "text": f"📈 {confidence_label} Confidence ({confidence_pct}/100)"
        }

        return embed

    def _get_recommendation_emoji(self, action: str) -> str:
        """Get emoji for recommendation action"""
        if action == 'BUY':
            return '💚'
        elif action == 'SELL':
            return '❤️'
        else:  # MONITOR
            return '👁️'

    def _format_market_info(self, alert: Dict, market_question: str, market_url: Optional[str]) -> str:
        """Format market information section"""
        market_data = alert.get('market_data', {})

        # Use shared formatting utilities
        price_str = format_market_price(market_data)
        volume_str = format_volume(market_data.get('volume24hr', 0))

        lines = [
            f"**{market_question}**",
            f"Current: {price_str}",
            f"Volume: {volume_str}"
        ]

        # Add market link if available
        if market_url:
            lines.append(f"\n[View Market]({market_url})")

        return "\n".join(lines)

    def _format_detected_info(self, alert_type_str: str, analysis: Dict, alert: Dict) -> str:
        """Format detection information section"""
        lines = [
            f"**Alert:** {alert_type_str.replace('_', ' ').title()}"
        ]

        # Add type-specific metrics
        if alert_type_str == 'VOLUME_SPIKE':
            anomaly_score = analysis.get('max_anomaly_score', 0)
            lines.append(f"**Score:** {anomaly_score:.1f}x")

            # Add directional information if available
            dominant_outcome = analysis.get('dominant_outcome', 'UNKNOWN')
            dominant_side = analysis.get('dominant_side', 'UNKNOWN')
            outcome_imbalance = analysis.get('outcome_imbalance', 0)
            side_imbalance = analysis.get('side_imbalance', 0)

            # Show outcome and pressure information
            # If we can determine outcome, show it; otherwise show pressure with note
            if dominant_outcome != 'UNKNOWN' and outcome_imbalance >= 0.10:
                # We have outcome data and clear direction
                lines.append(f"**Outcome:** {outcome_imbalance*100:.0f}% {dominant_outcome}")
                # Also show pressure
                if dominant_side != 'UNKNOWN':
                    if side_imbalance >= 0.10:
                        lines.append(f"**Pressure:** {side_imbalance*100:.0f}% {dominant_side}")
                    else:
                        lines.append(f"**Pressure:** Balanced")
            else:
                # No outcome data - show pressure with clarification
                if dominant_side != 'UNKNOWN':
                    if side_imbalance < 0.10:
                        lines.append(f"**Volume:** Balanced pressure (outcome unknown)")
                    else:
                        lines.append(f"**Volume:** {side_imbalance*100:.0f}% {dominant_side} pressure (outcome unknown)")

        elif alert_type_str == 'WHALE_ACTIVITY':
            total_volume = analysis.get('total_whale_volume', 0)
            whale_count = analysis.get('whale_count', 0)
            dominant_side = analysis.get('dominant_side', 'N/A')
            direction_imbalance = analysis.get('direction_imbalance', 0)

            lines.append(f"**Whales:** ${total_volume/1000:.0f}K from {whale_count} wallet{'s' if whale_count != 1 else ''}")
            lines.append(f"**Direction:** {direction_imbalance*100:.0f}% {dominant_side} bias")

        elif alert_type_str == 'UNUSUAL_PRICE_MOVEMENT':
            price_analysis = analysis.get('analysis', {})
            price_change_pct = price_analysis.get('price_change_pct', 0)
            volatility_spike = price_analysis.get('volatility_spike', 1)

            lines.append(f"**Change:** {price_change_pct:+.1f}%")
            lines.append(f"**Volatility:** {volatility_spike:.1f}x")

        elif alert_type_str == 'COORDINATED_TRADING':
            coord_score = analysis.get('coordination_score', 0)
            unique_wallets = analysis.get('unique_wallets', 0)

            lines.append(f"**Coordination:** {coord_score:.2f} score")
            lines.append(f"**Wallets:** {unique_wallets} coordinated")

        elif alert_type_str == 'FRESH_WALLET_LARGE_BET':
            # No aggregate stats needed - all details go in trade details section
            pass

        # Add timestamp
        alert_time = alert.get('timestamp')
        if isinstance(alert_time, datetime):
            time_diff = (datetime.now() - alert_time).total_seconds()
            if time_diff < 60:
                time_str = f"{int(time_diff)}s ago"
            elif time_diff < 3600:
                time_str = f"{int(time_diff/60)}m ago"
            else:
                time_str = f"{int(time_diff/3600)}h {int((time_diff%3600)/60)}m ago"
            lines.append(f"**Detected:** {time_str}")

        return "\n".join(lines)

    def _format_trade_details(self, analysis: Dict) -> Optional[str]:
        """Format trade details for whale/coordination/fresh wallet alerts"""
        # Check if this is a fresh wallet alert (has wallet_address field)
        if 'wallet_address' in analysis:
            return self._format_fresh_wallet_details(analysis)

        # Otherwise handle whale alerts
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

        lines = [
            f"**Top Whale:** ${top_whale['volume']/1000:.1f}K {top_whale['side']} @ ${top_whale['avg_price']:.2f}"
        ]

        # Add wallet address (shortened) - skip if unknown
        if top_whale['wallet'] and top_whale['wallet'] != 'unknown':
            wallet_short = f"{top_whale['wallet'][:6]}...{top_whale['wallet'][-4:]}"
            wallet_url = f"https://polygonscan.com/address/{top_whale['wallet']}"
            lines.append(f"**Wallet:** [{wallet_short}]({wallet_url})")

        # Add transaction link if available
        if top_whale.get('tx_hash') and top_whale['tx_hash'] != 'unknown':
            tx_short = f"{top_whale['tx_hash'][:6]}...{top_whale['tx_hash'][-4:]}"
            tx_url = f"https://polygonscan.com/tx/{top_whale['tx_hash']}"
            lines.append(f"**Tx:** [{tx_short}]({tx_url})")

        return "\n".join(lines)

    def _format_fresh_wallet_details(self, wallet_data: Dict) -> str:
        """Format trade details for fresh wallet alert"""
        bet_size = wallet_data.get('bet_size', 0)
        side = wallet_data.get('side', 'UNKNOWN')
        price = wallet_data.get('price', 0)
        outcome = wallet_data.get('outcome', 'UNKNOWN')
        wallet = wallet_data.get('wallet_address')
        tx_hash = wallet_data.get('tx_hash')

        # Format price with cents (reuse existing utility)
        price_str = _format_single_price(price)

        lines = [
            f"**Bet Size:** ${bet_size/1000:.1f}K {side} {outcome} @ {price_str}",
            f"**Fresh Wallet:** ✅ First trade on Polymarket"
        ]

        # Add wallet link
        if wallet and wallet != 'unknown':
            wallet_short = f"{wallet[:6]}...{wallet[-4:]}"
            wallet_url = f"https://polygonscan.com/address/{wallet}"
            lines.append(f"**Wallet:** [{wallet_short}]({wallet_url})")

        # Add transaction link
        if tx_hash and tx_hash != 'unknown':
            tx_short = f"{tx_hash[:6]}...{tx_hash[-4:]}"
            tx_url = f"https://polygonscan.com/tx/{tx_hash}"
            lines.append(f"**Tx:** [{tx_short}]({tx_url})")

        return "\n".join(lines)

    def _format_related_outcomes(self, related_markets: list) -> str:
        """Format related outcomes for grouped markets"""
        lines = []

        for rm in related_markets:
            # Extract short outcome name
            outcome = extract_outcome_name(rm['question'])
            # Format both YES and NO prices
            yes_str = _format_single_price(rm['yes_price'])
            no_str = _format_single_price(rm['no_price'])
            # Add bullet point with both prices
            lines.append(f"• {outcome}: {yes_str} YES / {no_str} NO")

        return "\n".join(lines)
