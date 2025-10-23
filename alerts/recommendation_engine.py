"""
Recommendation Engine
Generates actionable trading recommendations based on alert analysis
"""

from typing import Dict, Optional, Tuple
from enum import Enum
from common import AlertType, AlertSeverity
import logging

logger = logging.getLogger(__name__)


class RecommendationAction(Enum):
    """Possible recommendation actions"""
    BUY = "BUY"
    SELL = "SELL"
    MONITOR = "MONITOR"


class ConfidenceLevel(Enum):
    """Confidence levels for recommendations"""
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


def format_confidence_display(confidence_score: float, is_multi_metric: bool = False) -> tuple:
    """
    Format confidence score for display with label and percentage

    Args:
        confidence_score: Raw confidence score (0-10+ scale)
        is_multi_metric: Whether this is a multi-metric alert (can have scores >10)

    Returns:
        Tuple of (label, percentage) e.g. ("Very High", 95)
    """
    # Scale multi-metric scores to 0-10 range
    if is_multi_metric and confidence_score > 10.0:
        # Scale: 15.0 → 10.0 (100%), 12.0 → 8.0 (80%), 18.0 → 10.0+ (100%)
        scaled_score = min(confidence_score / 1.5, 10.0)
    else:
        scaled_score = confidence_score

    # Convert to percentage (0-100)
    percentage = min(int((scaled_score / 10.0) * 100), 100)

    # Determine label based on scaled score
    if scaled_score >= 9.5 or (is_multi_metric and confidence_score >= 15.0):
        label = "Very High"
    elif scaled_score >= 8.5 or (is_multi_metric and confidence_score >= 12.0):
        label = "High"
    elif scaled_score >= 8.0 or (is_multi_metric and confidence_score >= 10.0):
        label = "Medium"
    else:
        label = "Low"

    return (label, percentage)


class RecommendationEngine:
    """Generates intelligent trading recommendations from alert analysis"""

    def __init__(self, token_to_outcome: Dict[str, str] = None):
        """
        Initialize recommendation engine

        Args:
            token_to_outcome: Mapping of token asset_ids to outcome names (Yes/No)
        """
        self.token_to_outcome = token_to_outcome or {}

    def generate_recommendation(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        analysis: Dict,
        market_data: Dict,
        confidence_score: float,
        multi_metric: bool = False,
        supporting_anomalies: Optional[list] = None
    ) -> Dict:
        """
        Generate actionable recommendation based on alert analysis

        Args:
            alert_type: Type of alert detected
            severity: Alert severity level
            analysis: Detailed analysis from detector
            market_data: Market information including prices
            confidence_score: Confidence score (0-10 scale)
            multi_metric: Whether multiple metrics triggered
            supporting_anomalies: Other anomalies supporting this alert

        Returns:
            Dict containing:
                - action: BUY, SELL, or MONITOR
                - side: YES or NO (which outcome to trade)
                - price: Current market price
                - entry_price: Recommended entry (for actionable recs)
                - target_price: Target price (for high confidence)
                - risk_price: Stop loss price (for high confidence)
                - text: Display text of recommendation
                - reasoning: Context explaining the recommendation
                - confidence_level: HIGH, MEDIUM, or LOW
        """
        # Determine confidence level from score
        confidence_level = self._determine_confidence_level(confidence_score, multi_metric)

        # Get current price from market data
        current_price = market_data.get('lastTradePrice', 0)

        # Route to specific handler based on alert type
        if multi_metric and supporting_anomalies:
            return self._generate_multi_metric_recommendation(
                alert_type, severity, analysis, current_price,
                confidence_score, confidence_level, supporting_anomalies
            )
        elif alert_type == AlertType.WHALE_ACTIVITY:
            return self._generate_whale_recommendation(
                severity, analysis, current_price, confidence_level
            )
        elif alert_type == AlertType.COORDINATED_TRADING:
            return self._generate_coordination_recommendation(
                severity, analysis, current_price, confidence_level
            )
        elif alert_type == AlertType.VOLUME_SPIKE:
            return self._generate_volume_recommendation(
                severity, analysis, current_price, confidence_level
            )
        elif alert_type == AlertType.UNUSUAL_PRICE_MOVEMENT:
            return self._generate_price_movement_recommendation(
                severity, analysis, current_price, confidence_level
            )
        else:
            # Fallback for unknown alert types - format enum properly
            alert_type_formatted = (alert_type.value if hasattr(alert_type, 'value') else str(alert_type)).replace('_', ' ').title()
            return self._generate_monitor_recommendation(
                f"Unusual {alert_type_formatted} detected",
                "Verify independently before acting",
                current_price, confidence_level
            )

    def _generate_whale_recommendation(
        self,
        severity: AlertSeverity,
        analysis: Dict,
        current_price: float,
        confidence_level: ConfidenceLevel
    ) -> Dict:
        """Generate recommendation for whale activity"""
        total_volume = analysis.get('total_whale_volume', 0)
        whale_count = analysis.get('whale_count', 0)
        dominant_side = analysis.get('dominant_side', 'NEUTRAL')
        direction_imbalance = analysis.get('direction_imbalance', 0)
        coordination = analysis.get('coordination', {})
        coordinated = coordination.get('coordinated', False)

        # Determine which outcome whales are trading
        # dominant_side is 'BUY' or 'SELL', but we need to know if it's YES or NO
        # For now, we'll extract from whale_breakdown if available
        outcome = self._determine_outcome_from_whales(analysis)

        # HIGH/CRITICAL confidence with strong directional bias
        if (severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH] and
            direction_imbalance > 0.8 and
            total_volume > 50000):

            # In prediction markets, always BUY the outcome we think will happen
            action = RecommendationAction.BUY

            # Calculate price levels
            entry_price = current_price * 1.02
            risk_price = current_price * 0.95

            # Create recommendation text
            action_text = "Buy"
            whale_desc = f"{whale_count} whale{'s' if whale_count != 1 else ''}"
            coord_text = " coordinated" if coordinated else ""

            text = f"Consider {outcome} {action_text} @ ${current_price:.2f}"
            reasoning = (
                f"{whale_desc}{coord_text} {'purchased' if dominant_side == 'BUY' else 'sold'} "
                f"${total_volume/1000:.0f}K {outcome} @ ${current_price:.2f} "
                f"with {direction_imbalance*100:.0f}% {dominant_side.lower()} bias. "
                f"Strong conviction signal."
            )

            return {
                'action': action.value,
                'side': outcome,
                'price': current_price,
                'entry_price': entry_price,
                'target_price': None,  # Not calculating target for whale-only signals
                'risk_price': risk_price,
                'text': text,
                'reasoning': reasoning,
                'confidence_level': confidence_level.value
            }

        # MEDIUM confidence or moderate volume
        elif total_volume > 10000 and direction_imbalance > 0.6:
            action_text = "purchased" if dominant_side == 'BUY' else "sold"

            text = f"Monitor - Whale {action_text} ${total_volume/1000:.0f}K {outcome} @ ${current_price:.2f}"
            reasoning = (
                f"{'Coordinated ' if coordinated else ''}whale activity detected. "
                f"Verify with other signals before acting."
            )

            return {
                'action': RecommendationAction.MONITOR.value,
                'side': outcome,
                'price': current_price,
                'entry_price': None,
                'target_price': None,
                'risk_price': None,
                'text': text,
                'reasoning': reasoning,
                'confidence_level': confidence_level.value
            }

        # LOW confidence
        else:
            text = "Monitor - Unusual whale activity detected"
            reasoning = "Activity detected but low directional conviction. Monitor for confirmation."

            return self._generate_monitor_recommendation(text, reasoning, current_price, confidence_level)

    def _generate_coordination_recommendation(
        self,
        severity: AlertSeverity,
        analysis: Dict,
        current_price: float,
        confidence_level: ConfidenceLevel
    ) -> Dict:
        """Generate recommendation for coordinated trading"""
        coord_score = analysis.get('coordination_score', 0)
        unique_wallets = analysis.get('unique_wallets', 0)
        directional_bias = analysis.get('directional_bias', 0)
        dominant_direction = analysis.get('dominant_direction', 'UNKNOWN')
        wash_trading = analysis.get('wash_trading_detected', False)

        # Determine outcome from analysis
        outcome = self._determine_outcome_from_coordination(analysis)

        # CRITICAL - Very high coordination score
        if severity == AlertSeverity.CRITICAL and coord_score > 0.8 and unique_wallets >= 5:
            action = RecommendationAction.BUY if dominant_direction == 'BUY' else RecommendationAction.SELL
            action_text = "Buy" if action == RecommendationAction.BUY else "Sell"

            entry_price = current_price * 1.02 if action == RecommendationAction.BUY else current_price * 0.98
            risk_price = current_price * 0.95 if action == RecommendationAction.BUY else current_price * 1.05

            warning = " | ⚠️ Risk: Potential wash trading" if wash_trading else ""
            text = f"Strong insider signal - Consider {outcome} {action_text} @ ${current_price:.2f}{warning}"
            reasoning = (
                f"{unique_wallets} wallets coordinated ${analysis.get('total_volume', 0)/1000:.0f}K "
                f"{outcome} {'purchase' if dominant_direction == 'BUY' else 'sale'}. "
                f"Coordination score: {coord_score:.2f}. "
                f"{'High risk: potential wash trading. ' if wash_trading else ''}"
                f"Verify independently before acting."
            )

            return {
                'action': action.value,
                'side': outcome,
                'price': current_price,
                'entry_price': entry_price,
                'target_price': None,
                'risk_price': risk_price,
                'text': text,
                'reasoning': reasoning,
                'confidence_level': confidence_level.value
            }

        # HIGH - Moderate coordination
        elif coord_score > 0.6 and unique_wallets >= 3:
            text = f"Monitor - {unique_wallets} wallets coordinated on {outcome}"
            reasoning = (
                f"Coordination detected (score: {coord_score:.2f}). "
                f"Verify independently before acting."
            )

            return self._generate_monitor_recommendation(text, reasoning, current_price, confidence_level)

        # LOW confidence
        else:
            text = "Monitor - Potential coordination detected"
            reasoning = "Low coordination signal. Monitor for stronger confirmation."

            return self._generate_monitor_recommendation(text, reasoning, current_price, confidence_level)

    def _generate_multi_metric_recommendation(
        self,
        primary_alert_type: AlertType,
        severity: AlertSeverity,
        analysis: Dict,
        current_price: float,
        confidence_score: float,
        confidence_level: ConfidenceLevel,
        supporting_anomalies: list
    ) -> Dict:
        """Generate recommendation for multi-metric alerts (highest confidence)"""
        # Helper function to format alert type enums
        def format_alert_type(alert_type):
            """Format alert type enum to human-readable string"""
            type_str = alert_type.value if hasattr(alert_type, 'value') else str(alert_type)
            return type_str.replace('_', ' ').title()

        # Determine if this is a whale/coordination alert (show BUY action) or volume/price alert (show signal)
        is_actionable_alert = primary_alert_type in [AlertType.WHALE_ACTIVITY, AlertType.COORDINATED_TRADING]

        # Extract information from primary alert
        outcome = "YES"  # Default, will be overridden
        action = RecommendationAction.MONITOR

        if is_actionable_alert:
            # Whale/Coordination alerts: determine outcome and use BUY action
            if primary_alert_type == AlertType.WHALE_ACTIVITY:
                outcome = self._determine_outcome_from_whales(analysis)
            elif primary_alert_type == AlertType.COORDINATED_TRADING:
                outcome = self._determine_outcome_from_coordination(analysis)
            action = RecommendationAction.BUY
        else:
            # Volume/Price alerts: determine price direction for signal strength
            # Try to determine outcome from whale activity in supporting anomalies
            for anomaly in supporting_anomalies:
                if anomaly.get('type') == AlertType.WHALE_ACTIVITY:
                    anomaly_analysis = anomaly.get('analysis', {})
                    outcome = self._determine_outcome_from_whales(anomaly_analysis)
                    break
                elif anomaly.get('type') == AlertType.COORDINATED_TRADING:
                    anomaly_analysis = anomaly.get('analysis', {})
                    outcome = self._determine_outcome_from_coordination(anomaly_analysis)
                    break

        # Determine price direction for volume/price alerts
        price_direction = None
        if not is_actionable_alert:
            # Convert supporting_anomalies to full format for helper
            full_anomalies = []
            for anomaly in supporting_anomalies:
                if anomaly.get('type') == AlertType.UNUSUAL_PRICE_MOVEMENT:
                    # Get the full analysis from the anomaly
                    full_anomalies.append(anomaly)
            price_direction = self._determine_price_direction(analysis, full_anomalies)

        # Very high confidence (3+ signals) - threshold now 18.0
        if confidence_score >= 18 and len(supporting_anomalies) >= 2:
            if is_actionable_alert:
                # Whale/Coordination: Show BUY recommendation
                entry_price = current_price * 1.02
                target_price = current_price * 1.30
                risk_price = current_price * 0.90

                support_text = " + ".join([format_alert_type(a['type']) for a in supporting_anomalies[:2]])

                text = (
                    f"Consider {outcome} Buy @ ${current_price:.2f} | "
                    f"Entry: <${entry_price:.2f} | Target: ${target_price:.2f} | Risk: {(abs(current_price - risk_price)):.2f}¢"
                )
                reasoning = (
                    f"Very strong confluence: {format_alert_type(primary_alert_type)} + {support_text}. "
                    f"Multiple independent signals confirm buying pressure on {outcome}."
                )

                return {
                    'action': action.value,
                    'side': outcome,
                    'price': current_price,
                    'entry_price': entry_price,
                    'target_price': target_price,
                    'risk_price': risk_price,
                    'text': text,
                    'reasoning': reasoning,
                    'confidence_level': confidence_level.value
                }
            else:
                # Volume/Price: Show signal with direction
                support_text = " + ".join([format_alert_type(a['type']) for a in supporting_anomalies[:2]])
                direction_text = f" {price_direction}" if price_direction else ""

                text = f"Very Strong {outcome}{direction_text} Signal @ ${current_price:.2f}"
                reasoning = (
                    f"Very strong confluence: {format_alert_type(primary_alert_type)} + {support_text}. "
                    f"Multiple independent signals on {outcome}."
                )

                return {
                    'action': RecommendationAction.MONITOR.value,
                    'side': outcome,
                    'price': current_price,
                    'entry_price': None,
                    'target_price': None,
                    'risk_price': None,
                    'text': text,
                    'reasoning': reasoning,
                    'confidence_level': confidence_level.value
                }

        # High confidence (2 signals) - threshold now 12.0
        elif confidence_score >= 12 and len(supporting_anomalies) >= 1:
            if is_actionable_alert:
                # Whale/Coordination: Show BUY recommendation
                entry_price = current_price * 1.02

                support_text = format_alert_type(supporting_anomalies[0]['type'])

                text = f"Consider {outcome} Buy @ ${current_price:.2f}"
                reasoning = (
                    f"{format_alert_type(primary_alert_type)} + {support_text} detected. "
                    f"Dual signal confirmation on {outcome}."
                )

                return {
                    'action': action.value,
                    'side': outcome,
                    'price': current_price,
                    'entry_price': entry_price,
                    'target_price': None,
                    'risk_price': None,
                    'text': text,
                    'reasoning': reasoning,
                    'confidence_level': confidence_level.value
                }
            else:
                # Volume/Price: Show signal with direction
                support_text = format_alert_type(supporting_anomalies[0]['type'])
                direction_text = f" {price_direction} Pressure" if price_direction else " Signal"

                text = f"Strong {outcome}{direction_text} @ ${current_price:.2f}"
                reasoning = (
                    f"{format_alert_type(primary_alert_type)} + {support_text} detected. "
                    f"Dual signal confirmation on {outcome}."
                )

                return {
                    'action': RecommendationAction.MONITOR.value,
                    'side': outcome,
                    'price': current_price,
                    'entry_price': None,
                    'target_price': None,
                    'risk_price': None,
                    'text': text,
                    'reasoning': reasoning,
                    'confidence_level': confidence_level.value
                }

        # Fallback to monitor
        return self._generate_monitor_recommendation(
            f"Multi-metric signal on {outcome}",
            "Multiple signals detected. Monitor for stronger confirmation.",
            current_price, confidence_level
        )

    def _generate_volume_recommendation(
        self,
        severity: AlertSeverity,
        analysis: Dict,
        current_price: float,
        confidence_level: ConfidenceLevel
    ) -> Dict:
        """Generate recommendation for volume spikes"""
        anomaly_score = analysis.get('max_anomaly_score', 0)

        # Volume spikes alone are ambiguous - recommend monitoring
        text = f"Monitor - Volume spike {anomaly_score:.1f}x normal"
        reasoning = "High volume detected. Verify market news and confirm direction with other signals."

        return self._generate_monitor_recommendation(text, reasoning, current_price, confidence_level)

    def _generate_price_movement_recommendation(
        self,
        severity: AlertSeverity,
        analysis: Dict,
        current_price: float,
        confidence_level: ConfidenceLevel
    ) -> Dict:
        """Generate recommendation for unusual price movements"""
        price_analysis = analysis.get('analysis', {})
        price_change_pct = price_analysis.get('price_change_pct', 0)
        trend = price_analysis.get('trend', 'UNKNOWN')

        # Price movement alone could be news-driven - recommend monitoring
        text = f"Monitor - Rapid {price_change_pct:+.1f}% price movement"
        reasoning = "Significant price movement detected. Verify news catalyst before acting."

        return self._generate_monitor_recommendation(text, reasoning, current_price, confidence_level)

    def _generate_monitor_recommendation(
        self,
        text: str,
        reasoning: str,
        current_price: float,
        confidence_level: ConfidenceLevel
    ) -> Dict:
        """Generate a monitoring recommendation (no trade action)"""
        return {
            'action': RecommendationAction.MONITOR.value,
            'side': None,
            'price': current_price,
            'entry_price': None,
            'target_price': None,
            'risk_price': None,
            'text': text,
            'reasoning': reasoning,
            'confidence_level': confidence_level.value
        }

    def _determine_confidence_level(self, confidence_score: float, multi_metric: bool) -> ConfidenceLevel:
        """Determine confidence level from score"""
        if multi_metric and confidence_score >= 15:
            return ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 12:
            return ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 9:
            return ConfidenceLevel.HIGH
        elif confidence_score >= 6:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _determine_outcome_from_whales(self, analysis: Dict) -> str:
        """Determine which outcome (YES/NO) whales are trading"""
        # Try to extract from whale_breakdown
        whale_breakdown = analysis.get('whale_breakdown', {})
        if whale_breakdown:
            # Get the top whale's (highest volume) asset_id
            for whale_data in whale_breakdown.values():
                if isinstance(whale_data, dict) and 'asset_id' in whale_data:
                    asset_id = whale_data['asset_id']
                    # Return the outcome if we can determine it, otherwise try next whale
                    if asset_id and asset_id in self.token_to_outcome:
                        return self.token_to_outcome[asset_id]

        # Fallback: if we can't determine from whales, check the dominant side
        # If dominant side is SELL, assume they're selling YES (betting on NO)
        # If dominant side is BUY, assume they're buying YES
        dominant_side = analysis.get('dominant_side', 'BUY')
        return "YES" if dominant_side == "BUY" else "NO"

    def _determine_outcome_from_coordination(self, analysis: Dict) -> str:
        """Determine which outcome (YES/NO) is being coordinated"""
        # Extract asset_id from best_window (which has the highest coordination score)
        best_window = analysis.get('best_window', {})
        if best_window and 'asset_id' in best_window:
            asset_id = best_window['asset_id']
            if asset_id and asset_id in self.token_to_outcome:
                return self.token_to_outcome[asset_id]

        # Fallback: check directional_bias
        # High directional_bias towards BUY suggests coordinated YES buying
        directional_bias = best_window.get('directional_bias', 0.5) if best_window else 0.5
        return "YES" if directional_bias > 0.5 else "NO"

    def _determine_price_direction(self, analysis: Dict, supporting_anomalies: Optional[list] = None) -> Optional[str]:
        """
        Determine if price is rising (buying pressure) or falling (selling pressure)

        Args:
            analysis: Primary analysis data (may contain price info)
            supporting_anomalies: List of supporting anomalies to check for price movement data

        Returns:
            "Buying" if price trending up, "Selling" if price trending down, None if unclear
        """
        # Check if primary analysis has price movement data
        if 'analysis' in analysis and isinstance(analysis['analysis'], dict):
            price_analysis = analysis['analysis']
            price_change_pct = price_analysis.get('price_change_pct', 0)
            trend = price_analysis.get('trend', None)

            # Use trend if available (UPTREND/DOWNTREND)
            if trend == 'UPTREND':
                return "Buying"
            elif trend == 'DOWNTREND':
                return "Selling"

            # Otherwise use price change percentage (threshold: 2%)
            if price_change_pct > 2.0:
                return "Buying"
            elif price_change_pct < -2.0:
                return "Selling"

        # Check supporting anomalies for Unusual Price Movement
        if supporting_anomalies:
            for anomaly in supporting_anomalies:
                if anomaly.get('type') == AlertType.UNUSUAL_PRICE_MOVEMENT:
                    # Try to extract from the anomaly's analysis if it has one
                    anomaly_analysis = anomaly.get('analysis', {})
                    if 'analysis' in anomaly_analysis:
                        price_analysis = anomaly_analysis['analysis']
                        price_change_pct = price_analysis.get('price_change_pct', 0)
                        trend = price_analysis.get('trend', None)

                        if trend == 'UPTREND':
                            return "Buying"
                        elif trend == 'DOWNTREND':
                            return "Selling"

                        if price_change_pct > 2.0:
                            return "Buying"
                        elif price_change_pct < -2.0:
                            return "Selling"

        # If we can't determine direction, return None
        return None
