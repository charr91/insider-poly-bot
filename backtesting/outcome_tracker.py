"""
Alert Outcome Tracker

Tracks the outcomes of detection alerts to measure accuracy and profitability.
Monitors price movements and market resolutions following alerts.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class OutcomeDirection(Enum):
    """Direction of price movement after alert"""
    UP = "UP"
    DOWN = "DOWN"
    FLAT = "FLAT"


class OutcomeResult(Enum):
    """Result of alert prediction"""
    TRUE_POSITIVE = "TRUE_POSITIVE"      # Correctly predicted movement
    FALSE_POSITIVE = "FALSE_POSITIVE"    # Incorrect prediction
    TRUE_NEGATIVE = "TRUE_NEGATIVE"      # Correctly predicted no movement
    FALSE_NEGATIVE = "FALSE_NEGATIVE"    # Missed actual movement
    PENDING = "PENDING"                  # Not enough time has passed
    UNRESOLVED = "UNRESOLVED"            # Market hasn't resolved


@dataclass
class PriceSnapshot:
    """Price at a specific time"""
    timestamp: datetime
    price: float
    source: str = "simulated"


@dataclass
class AlertOutcome:
    """Tracks the outcome of a single alert"""
    alert_id: str
    market_id: str
    alert_timestamp: datetime
    predicted_direction: str
    confidence_score: float

    # Price tracking
    price_at_alert: Optional[float] = None
    price_1h_after: Optional[float] = None
    price_4h_after: Optional[float] = None
    price_24h_after: Optional[float] = None

    # Calculated outcomes
    direction_1h: Optional[OutcomeDirection] = None
    direction_4h: Optional[OutcomeDirection] = None
    direction_24h: Optional[OutcomeDirection] = None

    # Performance metrics
    return_1h: Optional[float] = None    # Percentage return if acted on alert
    return_4h: Optional[float] = None
    return_24h: Optional[float] = None

    # Validation
    prediction_correct_1h: Optional[bool] = None
    prediction_correct_4h: Optional[bool] = None
    prediction_correct_24h: Optional[bool] = None

    # Market resolution
    market_resolved: bool = False
    resolution_value: Optional[float] = None  # 0.0 or 1.0 for binary markets
    resolution_timestamp: Optional[datetime] = None

    # Classification for confusion matrix
    outcome_result: OutcomeResult = OutcomeResult.PENDING

    # Additional metadata
    detector_type: Optional[str] = None
    severity: Optional[str] = None
    notes: Dict = field(default_factory=dict)


class OutcomeTracker:
    """
    Tracks alert outcomes to measure detection accuracy and profitability.

    For backtesting: tracks price movements from historical data
    For live monitoring: tracks outcomes over time
    """

    def __init__(self, price_change_threshold: float = 0.05):
        """
        Initialize outcome tracker.

        Args:
            price_change_threshold: Minimum price change % to consider as movement (default: 5%)
        """
        self.price_change_threshold = price_change_threshold
        self.outcomes: Dict[str, AlertOutcome] = {}

        logger.info(f"🎯 OutcomeTracker initialized (threshold: {price_change_threshold*100:.1f}%)")

    def track_alert(
        self,
        alert_id: str,
        market_id: str,
        alert_timestamp: datetime,
        predicted_direction: str,
        confidence_score: float,
        price_at_alert: Optional[float] = None,
        detector_type: Optional[str] = None,
        severity: Optional[str] = None
    ) -> AlertOutcome:
        """
        Begin tracking an alert's outcome.

        Args:
            alert_id: Unique alert identifier
            market_id: Market identifier
            alert_timestamp: When alert was generated
            predicted_direction: Predicted price direction (BUY/SELL)
            confidence_score: Alert confidence score
            price_at_alert: Price at time of alert
            detector_type: Type of detector that generated alert
            severity: Alert severity level

        Returns:
            AlertOutcome instance
        """
        outcome = AlertOutcome(
            alert_id=alert_id,
            market_id=market_id,
            alert_timestamp=alert_timestamp,
            predicted_direction=predicted_direction,
            confidence_score=confidence_score,
            price_at_alert=price_at_alert,
            detector_type=detector_type,
            severity=severity
        )

        self.outcomes[alert_id] = outcome
        logger.debug(f"📊 Tracking alert: {alert_id} on {market_id[:10]}...")

        return outcome

    def update_price_at_interval(
        self,
        alert_id: str,
        interval: str,
        price: float,
        timestamp: datetime
    ):
        """
        Update price at a specific interval after alert.

        Args:
            alert_id: Alert identifier
            interval: '1h', '4h', or '24h'
            price: Price at this interval
            timestamp: Time of price snapshot
        """
        if alert_id not in self.outcomes:
            logger.warning(f"Alert {alert_id} not found in tracker")
            return

        outcome = self.outcomes[alert_id]

        # Update price at interval
        if interval == '1h':
            outcome.price_1h_after = price
        elif interval == '4h':
            outcome.price_4h_after = price
        elif interval == '24h':
            outcome.price_24h_after = price
        else:
            logger.warning(f"Unknown interval: {interval}")
            return

        # Calculate returns and direction
        self._calculate_outcome_metrics(alert_id, interval)

    def _calculate_outcome_metrics(self, alert_id: str, interval: str):
        """Calculate direction, return, and correctness for an interval"""
        outcome = self.outcomes[alert_id]

        if outcome.price_at_alert is None:
            return

        # Get price at interval
        price_after = None
        if interval == '1h':
            price_after = outcome.price_1h_after
        elif interval == '4h':
            price_after = outcome.price_4h_after
        elif interval == '24h':
            price_after = outcome.price_24h_after

        if price_after is None:
            return

        # Calculate return percentage
        price_change = (price_after - outcome.price_at_alert) / outcome.price_at_alert

        # Determine direction
        if abs(price_change) < self.price_change_threshold:
            direction = OutcomeDirection.FLAT
        elif price_change > 0:
            direction = OutcomeDirection.UP
        else:
            direction = OutcomeDirection.DOWN

        # Store results
        if interval == '1h':
            outcome.return_1h = price_change
            outcome.direction_1h = direction
            outcome.prediction_correct_1h = self._is_prediction_correct(
                outcome.predicted_direction, direction
            )
        elif interval == '4h':
            outcome.return_4h = price_change
            outcome.direction_4h = direction
            outcome.prediction_correct_4h = self._is_prediction_correct(
                outcome.predicted_direction, direction
            )
        elif interval == '24h':
            outcome.return_24h = price_change
            outcome.direction_24h = direction
            outcome.prediction_correct_24h = self._is_prediction_correct(
                outcome.predicted_direction, direction
            )

        # Update outcome result for confusion matrix (using 24h as default)
        if interval == '24h':
            outcome.outcome_result = self._classify_outcome(outcome)

    def _is_prediction_correct(
        self,
        predicted: str,
        actual: OutcomeDirection
    ) -> bool:
        """
        Check if prediction matches actual direction.

        Args:
            predicted: Predicted direction string (BUY/SELL/UP/DOWN)
            actual: Actual direction enum

        Returns:
            True if prediction was correct
        """
        predicted_upper = predicted.upper()

        # Map predictions to expected directions
        if predicted_upper in ['BUY', 'UP']:
            return actual == OutcomeDirection.UP
        elif predicted_upper in ['SELL', 'DOWN']:
            return actual == OutcomeDirection.DOWN

        # If no clear direction predicted, flat is correct
        return actual == OutcomeDirection.FLAT

    def _classify_outcome(self, outcome: AlertOutcome) -> OutcomeResult:
        """
        Classify outcome for confusion matrix.

        Returns:
            OutcomeResult classification
        """
        # Use 24h results for classification
        if outcome.direction_24h is None:
            return OutcomeResult.PENDING

        if outcome.prediction_correct_24h is True:
            if outcome.direction_24h == OutcomeDirection.FLAT:
                return OutcomeResult.TRUE_NEGATIVE
            else:
                return OutcomeResult.TRUE_POSITIVE
        else:
            if outcome.direction_24h == OutcomeDirection.FLAT:
                return OutcomeResult.FALSE_POSITIVE
            else:
                return OutcomeResult.FALSE_NEGATIVE

    def update_market_resolution(
        self,
        alert_id: str,
        resolved: bool,
        resolution_value: Optional[float] = None,
        resolution_timestamp: Optional[datetime] = None
    ):
        """
        Update market resolution information.

        Args:
            alert_id: Alert identifier
            resolved: Whether market has resolved
            resolution_value: Resolution value (0.0 or 1.0 for binary)
            resolution_timestamp: When market resolved
        """
        if alert_id not in self.outcomes:
            logger.warning(f"Alert {alert_id} not found in tracker")
            return

        outcome = self.outcomes[alert_id]
        outcome.market_resolved = resolved
        outcome.resolution_value = resolution_value
        outcome.resolution_timestamp = resolution_timestamp

        logger.debug(f"📋 Updated resolution for {alert_id}: {resolved}")

    def get_outcome(self, alert_id: str) -> Optional[AlertOutcome]:
        """Get outcome for specific alert"""
        return self.outcomes.get(alert_id)

    def get_all_outcomes(self) -> List[AlertOutcome]:
        """Get all tracked outcomes"""
        return list(self.outcomes.values())

    def get_completed_outcomes(self) -> List[AlertOutcome]:
        """Get outcomes where all intervals have been measured"""
        return [
            outcome for outcome in self.outcomes.values()
            if outcome.price_24h_after is not None
        ]

    def calculate_aggregate_metrics(
        self,
        interval: str = '24h',
        min_confidence: Optional[float] = None
    ) -> Dict:
        """
        Calculate aggregate performance metrics across all outcomes.

        Args:
            interval: Time interval to use ('1h', '4h', '24h')
            min_confidence: Optional minimum confidence score filter

        Returns:
            Dictionary with aggregate metrics
        """
        # Filter outcomes
        outcomes = self.get_completed_outcomes()

        if min_confidence is not None:
            outcomes = [o for o in outcomes if o.confidence_score >= min_confidence]

        if not outcomes:
            return {
                'total_alerts': 0,
                'error': 'No completed outcomes available'
            }

        # Get correct field based on interval
        if interval == '1h':
            correct_field = 'prediction_correct_1h'
            return_field = 'return_1h'
        elif interval == '4h':
            correct_field = 'prediction_correct_4h'
            return_field = 'return_4h'
        else:  # 24h
            correct_field = 'prediction_correct_4h'
            return_field = 'return_24h'

        # Calculate metrics
        total = len(outcomes)
        correct_predictions = sum(
            1 for o in outcomes
            if getattr(o, correct_field, None) is True
        )

        accuracy = correct_predictions / total if total > 0 else 0.0

        # Calculate returns
        returns = [getattr(o, return_field, 0.0) for o in outcomes if getattr(o, return_field) is not None]
        avg_return = sum(returns) / len(returns) if returns else 0.0
        positive_returns = sum(1 for r in returns if r > 0)

        # Win rate
        win_rate = positive_returns / len(returns) if returns else 0.0

        # By detector type
        by_detector = {}
        for outcome in outcomes:
            detector = outcome.detector_type or 'unknown'
            if detector not in by_detector:
                by_detector[detector] = {'total': 0, 'correct': 0}
            by_detector[detector]['total'] += 1
            if getattr(outcome, correct_field, None) is True:
                by_detector[detector]['correct'] += 1

        # Calculate accuracy by detector
        detector_accuracy = {
            detector: stats['correct'] / stats['total'] if stats['total'] > 0 else 0.0
            for detector, stats in by_detector.items()
        }

        return {
            'interval': interval,
            'total_alerts': total,
            'correct_predictions': correct_predictions,
            'accuracy': accuracy,
            'average_return': avg_return,
            'win_rate': win_rate,
            'positive_outcomes': positive_returns,
            'negative_outcomes': len(returns) - positive_returns,
            'by_detector': detector_accuracy,
            'min_confidence_filter': min_confidence
        }

    def calculate_confusion_matrix(self) -> Dict:
        """
        Calculate confusion matrix for classification metrics.

        Returns:
            Dictionary with TP, FP, TN, FN counts
        """
        outcomes = self.get_completed_outcomes()

        true_positives = sum(
            1 for o in outcomes
            if o.outcome_result == OutcomeResult.TRUE_POSITIVE
        )
        false_positives = sum(
            1 for o in outcomes
            if o.outcome_result == OutcomeResult.FALSE_POSITIVE
        )
        true_negatives = sum(
            1 for o in outcomes
            if o.outcome_result == OutcomeResult.TRUE_NEGATIVE
        )
        false_negatives = sum(
            1 for o in outcomes
            if o.outcome_result == OutcomeResult.FALSE_NEGATIVE
        )

        return {
            'true_positives': true_positives,
            'false_positives': false_positives,
            'true_negatives': true_negatives,
            'false_negatives': false_negatives,
            'total': len(outcomes)
        }

    def export_to_dict(self) -> List[Dict]:
        """Export all outcomes to dictionary format for JSON serialization"""
        return [
            {
                'alert_id': o.alert_id,
                'market_id': o.market_id,
                'alert_timestamp': o.alert_timestamp.isoformat(),
                'predicted_direction': o.predicted_direction,
                'confidence_score': o.confidence_score,
                'detector_type': o.detector_type,
                'severity': o.severity,
                'price_at_alert': o.price_at_alert,
                'price_1h_after': o.price_1h_after,
                'price_4h_after': o.price_4h_after,
                'price_24h_after': o.price_24h_after,
                'return_1h': o.return_1h,
                'return_4h': o.return_4h,
                'return_24h': o.return_24h,
                'direction_1h': o.direction_1h.value if o.direction_1h else None,
                'direction_4h': o.direction_4h.value if o.direction_4h else None,
                'direction_24h': o.direction_24h.value if o.direction_24h else None,
                'prediction_correct_1h': o.prediction_correct_1h,
                'prediction_correct_4h': o.prediction_correct_4h,
                'prediction_correct_24h': o.prediction_correct_24h,
                'outcome_result': o.outcome_result.value,
                'market_resolved': o.market_resolved,
                'resolution_value': o.resolution_value,
                'resolution_timestamp': o.resolution_timestamp.isoformat() if o.resolution_timestamp else None,
                'notes': o.notes
            }
            for o in self.outcomes.values()
        ]

    def reset(self):
        """Clear all tracked outcomes"""
        self.outcomes.clear()
        logger.info("🔄 Outcome tracker reset")
