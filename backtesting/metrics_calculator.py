"""
Metrics Calculator

Calculates comprehensive performance metrics for detection algorithms.
Includes precision, recall, F1 score, ROI, and other evaluation metrics.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

from backtesting.outcome_tracker import (
    AlertOutcome,
    OutcomeResult,
    OutcomeDirection
)

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for all performance metrics"""

    # Basic counts
    total_alerts: int
    completed_outcomes: int

    # Classification metrics
    precision: float
    recall: float
    f1_score: float
    accuracy: float

    # Confusion matrix
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int

    # Financial metrics
    roi: float  # Return on investment
    win_rate: float
    average_return: float
    total_return: float
    sharpe_ratio: Optional[float] = None

    # Time interval metrics
    accuracy_1h: Optional[float] = None
    accuracy_4h: Optional[float] = None
    accuracy_24h: Optional[float] = None

    # By detector type
    by_detector: Dict[str, Dict] = None

    # By confidence threshold
    by_confidence: Dict[str, Dict] = None

    # Additional metadata
    interval: str = '24h'
    timestamp: datetime = None


class MetricsCalculator:
    """
    Calculates performance metrics from alert outcomes.

    Provides comprehensive analysis including:
    - Classification metrics (precision, recall, F1)
    - Financial metrics (ROI, win rate, returns)
    - Detector-specific performance
    - Confidence threshold analysis
    """

    def __init__(self):
        logger.info("📊 MetricsCalculator initialized")

    def calculate_metrics(
        self,
        outcomes: List[AlertOutcome],
        interval: str = '24h',
        min_confidence: Optional[float] = None
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.

        Args:
            outcomes: List of alert outcomes to analyze
            interval: Time interval to use ('1h', '4h', '24h')
            min_confidence: Optional minimum confidence filter

        Returns:
            PerformanceMetrics with all calculated metrics
        """
        logger.info(f"📈 Calculating metrics for {len(outcomes)} outcomes (interval: {interval})")

        # Filter by confidence if specified
        if min_confidence is not None:
            outcomes = [o for o in outcomes if o.confidence_score >= min_confidence]
            logger.info(f"  Filtered to {len(outcomes)} outcomes with confidence >= {min_confidence}")

        # Filter to completed outcomes only
        completed = self._filter_completed_outcomes(outcomes, interval)
        logger.info(f"  {len(completed)} completed outcomes available")

        if not completed:
            logger.warning("No completed outcomes available for metrics calculation")
            return self._empty_metrics(len(outcomes), interval)

        # Calculate confusion matrix
        confusion = self._calculate_confusion_matrix(completed)

        # Calculate classification metrics
        precision = self._calculate_precision(confusion)
        recall = self._calculate_recall(confusion)
        f1_score = self._calculate_f1_score(precision, recall)
        accuracy = self._calculate_accuracy(confusion)

        # Calculate financial metrics
        financial = self._calculate_financial_metrics(completed, interval)

        # Calculate time-specific accuracy
        time_metrics = self._calculate_time_interval_metrics(completed)

        # Calculate detector-specific metrics
        detector_metrics = self._calculate_detector_metrics(completed, interval)

        # Calculate confidence threshold analysis
        confidence_metrics = self._calculate_confidence_metrics(outcomes, interval)

        metrics = PerformanceMetrics(
            total_alerts=len(outcomes),
            completed_outcomes=len(completed),
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy,
            true_positives=confusion['true_positives'],
            false_positives=confusion['false_positives'],
            true_negatives=confusion['true_negatives'],
            false_negatives=confusion['false_negatives'],
            roi=financial['roi'],
            win_rate=financial['win_rate'],
            average_return=financial['average_return'],
            total_return=financial['total_return'],
            sharpe_ratio=financial.get('sharpe_ratio'),
            accuracy_1h=time_metrics.get('accuracy_1h'),
            accuracy_4h=time_metrics.get('accuracy_4h'),
            accuracy_24h=time_metrics.get('accuracy_24h'),
            by_detector=detector_metrics,
            by_confidence=confidence_metrics,
            interval=interval,
            timestamp=datetime.now()
        )

        logger.info(f"✅ Metrics calculated: P={precision:.2%}, R={recall:.2%}, F1={f1_score:.2%}, ROI={financial['roi']:.2%}")

        return metrics

    def _filter_completed_outcomes(
        self,
        outcomes: List[AlertOutcome],
        interval: str
    ) -> List[AlertOutcome]:
        """Filter to outcomes with data at specified interval"""
        if interval == '1h':
            return [o for o in outcomes if o.price_1h_after is not None]
        elif interval == '4h':
            return [o for o in outcomes if o.price_4h_after is not None]
        else:  # 24h
            return [o for o in outcomes if o.price_24h_after is not None]

    def _calculate_confusion_matrix(self, outcomes: List[AlertOutcome]) -> Dict:
        """Calculate confusion matrix from outcomes"""
        tp = sum(1 for o in outcomes if o.outcome_result == OutcomeResult.TRUE_POSITIVE)
        fp = sum(1 for o in outcomes if o.outcome_result == OutcomeResult.FALSE_POSITIVE)
        tn = sum(1 for o in outcomes if o.outcome_result == OutcomeResult.TRUE_NEGATIVE)
        fn = sum(1 for o in outcomes if o.outcome_result == OutcomeResult.FALSE_NEGATIVE)

        return {
            'true_positives': tp,
            'false_positives': fp,
            'true_negatives': tn,
            'false_negatives': fn
        }

    def _calculate_precision(self, confusion: Dict) -> float:
        """
        Calculate precision: TP / (TP + FP)
        What percentage of alerts were correct?
        """
        tp = confusion['true_positives']
        fp = confusion['false_positives']

        if tp + fp == 0:
            return 0.0

        return tp / (tp + fp)

    def _calculate_recall(self, confusion: Dict) -> float:
        """
        Calculate recall: TP / (TP + FN)
        What percentage of actual events did we detect?
        """
        tp = confusion['true_positives']
        fn = confusion['false_negatives']

        if tp + fn == 0:
            return 0.0

        return tp / (tp + fn)

    def _calculate_f1_score(self, precision: float, recall: float) -> float:
        """
        Calculate F1 score: 2 * (precision * recall) / (precision + recall)
        Balanced metric between precision and recall
        """
        if precision + recall == 0:
            return 0.0

        return 2 * (precision * recall) / (precision + recall)

    def _calculate_accuracy(self, confusion: Dict) -> float:
        """
        Calculate accuracy: (TP + TN) / (TP + TN + FP + FN)
        Overall correctness rate
        """
        tp = confusion['true_positives']
        tn = confusion['true_negatives']
        fp = confusion['false_positives']
        fn = confusion['false_negatives']

        total = tp + tn + fp + fn

        if total == 0:
            return 0.0

        return (tp + tn) / total

    def _calculate_financial_metrics(
        self,
        outcomes: List[AlertOutcome],
        interval: str
    ) -> Dict:
        """Calculate financial performance metrics"""

        # Get returns for interval
        returns = self._get_returns_for_interval(outcomes, interval)

        if not returns:
            return {
                'roi': 0.0,
                'win_rate': 0.0,
                'average_return': 0.0,
                'total_return': 0.0
            }

        # Calculate metrics
        total_return = sum(returns)
        average_return = total_return / len(returns)
        positive_returns = sum(1 for r in returns if r > 0)
        win_rate = positive_returns / len(returns)

        # ROI (assuming equal investment in each alert)
        # Simplified: cumulative return
        roi = total_return

        # Sharpe ratio (risk-adjusted return)
        sharpe_ratio = self._calculate_sharpe_ratio(returns)

        return {
            'roi': roi,
            'win_rate': win_rate,
            'average_return': average_return,
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'num_trades': len(returns)
        }

    def _get_returns_for_interval(
        self,
        outcomes: List[AlertOutcome],
        interval: str
    ) -> List[float]:
        """Get returns for specified interval"""
        if interval == '1h':
            return [o.return_1h for o in outcomes if o.return_1h is not None]
        elif interval == '4h':
            return [o.return_4h for o in outcomes if o.return_4h is not None]
        else:  # 24h
            return [o.return_24h for o in outcomes if o.return_24h is not None]

    def _calculate_sharpe_ratio(self, returns: List[float]) -> Optional[float]:
        """
        Calculate Sharpe ratio (risk-adjusted return).

        Sharpe = (mean return - risk_free_rate) / std_dev of returns
        Assumes risk_free_rate = 0 for simplicity
        """
        if len(returns) < 2:
            return None

        mean_return = sum(returns) / len(returns)

        # Calculate standard deviation
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return None

        return mean_return / std_dev

    def _calculate_time_interval_metrics(self, outcomes: List[AlertOutcome]) -> Dict:
        """Calculate accuracy at different time intervals"""
        metrics = {}

        # 1h accuracy
        outcomes_1h = [o for o in outcomes if o.prediction_correct_1h is not None]
        if outcomes_1h:
            correct_1h = sum(1 for o in outcomes_1h if o.prediction_correct_1h)
            metrics['accuracy_1h'] = correct_1h / len(outcomes_1h)

        # 4h accuracy
        outcomes_4h = [o for o in outcomes if o.prediction_correct_4h is not None]
        if outcomes_4h:
            correct_4h = sum(1 for o in outcomes_4h if o.prediction_correct_4h)
            metrics['accuracy_4h'] = correct_4h / len(outcomes_4h)

        # 24h accuracy
        outcomes_24h = [o for o in outcomes if o.prediction_correct_24h is not None]
        if outcomes_24h:
            correct_24h = sum(1 for o in outcomes_24h if o.prediction_correct_24h)
            metrics['accuracy_24h'] = correct_24h / len(outcomes_24h)

        return metrics

    def _calculate_detector_metrics(
        self,
        outcomes: List[AlertOutcome],
        interval: str
    ) -> Dict[str, Dict]:
        """Calculate metrics broken down by detector type"""
        by_detector = {}

        for outcome in outcomes:
            detector = outcome.detector_type or 'unknown'

            if detector not in by_detector:
                by_detector[detector] = {
                    'outcomes': [],
                    'returns': []
                }

            by_detector[detector]['outcomes'].append(outcome)

            # Add return if available
            returns = self._get_returns_for_interval([outcome], interval)
            if returns:
                by_detector[detector]['returns'].extend(returns)

        # Calculate metrics for each detector
        detector_metrics = {}
        for detector, data in by_detector.items():
            outcomes_list = data['outcomes']
            confusion = self._calculate_confusion_matrix(outcomes_list)

            precision = self._calculate_precision(confusion)
            recall = self._calculate_recall(confusion)
            f1 = self._calculate_f1_score(precision, recall)

            returns = data['returns']
            avg_return = sum(returns) / len(returns) if returns else 0.0
            win_rate = sum(1 for r in returns if r > 0) / len(returns) if returns else 0.0

            detector_metrics[detector] = {
                'count': len(outcomes_list),
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'average_return': avg_return,
                'win_rate': win_rate,
                'confusion_matrix': confusion
            }

        return detector_metrics

    def _calculate_confidence_metrics(
        self,
        outcomes: List[AlertOutcome],
        interval: str
    ) -> Dict[str, Dict]:
        """Calculate metrics at different confidence thresholds"""
        thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]
        confidence_metrics = {}

        for threshold in thresholds:
            filtered = [o for o in outcomes if o.confidence_score >= threshold]
            completed = self._filter_completed_outcomes(filtered, interval)

            if not completed:
                continue

            confusion = self._calculate_confusion_matrix(completed)
            precision = self._calculate_precision(confusion)
            recall = self._calculate_recall(confusion)
            f1 = self._calculate_f1_score(precision, recall)

            financial = self._calculate_financial_metrics(completed, interval)

            confidence_metrics[f'>={threshold:.1f}'] = {
                'count': len(completed),
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'roi': financial['roi'],
                'win_rate': financial['win_rate']
            }

        return confidence_metrics

    def _empty_metrics(self, total_alerts: int, interval: str) -> PerformanceMetrics:
        """Return empty metrics when no data available"""
        return PerformanceMetrics(
            total_alerts=total_alerts,
            completed_outcomes=0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            accuracy=0.0,
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
            roi=0.0,
            win_rate=0.0,
            average_return=0.0,
            total_return=0.0,
            interval=interval,
            timestamp=datetime.now()
        )

    def export_metrics_to_dict(self, metrics: PerformanceMetrics) -> Dict:
        """Export metrics to dictionary for JSON serialization"""
        return {
            'total_alerts': metrics.total_alerts,
            'completed_outcomes': metrics.completed_outcomes,
            'interval': metrics.interval,
            'timestamp': metrics.timestamp.isoformat() if metrics.timestamp else None,
            'classification_metrics': {
                'precision': metrics.precision,
                'recall': metrics.recall,
                'f1_score': metrics.f1_score,
                'accuracy': metrics.accuracy
            },
            'confusion_matrix': {
                'true_positives': metrics.true_positives,
                'false_positives': metrics.false_positives,
                'true_negatives': metrics.true_negatives,
                'false_negatives': metrics.false_negatives
            },
            'financial_metrics': {
                'roi': metrics.roi,
                'win_rate': metrics.win_rate,
                'average_return': metrics.average_return,
                'total_return': metrics.total_return,
                'sharpe_ratio': metrics.sharpe_ratio
            },
            'time_interval_accuracy': {
                '1h': metrics.accuracy_1h,
                '4h': metrics.accuracy_4h,
                '24h': metrics.accuracy_24h
            },
            'by_detector': metrics.by_detector,
            'by_confidence': metrics.by_confidence
        }

    def print_metrics_report(self, metrics: PerformanceMetrics):
        """Print formatted metrics report to console"""
        print("\n" + "=" * 80)
        print(f"  PERFORMANCE METRICS REPORT - {metrics.interval.upper()} Interval")
        print("=" * 80)

        print(f"\n📊 Overview:")
        print(f"  Total Alerts:        {metrics.total_alerts:,}")
        print(f"  Completed Outcomes:  {metrics.completed_outcomes:,}")

        print(f"\n🎯 Classification Metrics:")
        print(f"  Precision:           {metrics.precision:6.2%}  (correct alerts / total alerts)")
        print(f"  Recall:              {metrics.recall:6.2%}  (detected events / total events)")
        print(f"  F1 Score:            {metrics.f1_score:6.2%}  (balanced accuracy)")
        print(f"  Accuracy:            {metrics.accuracy:6.2%}  (overall correctness)")

        print(f"\n📈 Confusion Matrix:")
        print(f"  True Positives:      {metrics.true_positives:,}")
        print(f"  False Positives:     {metrics.false_positives:,}")
        print(f"  True Negatives:      {metrics.true_negatives:,}")
        print(f"  False Negatives:     {metrics.false_negatives:,}")

        print(f"\n💰 Financial Metrics:")
        print(f"  ROI:                 {metrics.roi:+6.2%}")
        print(f"  Win Rate:            {metrics.win_rate:6.2%}")
        print(f"  Average Return:      {metrics.average_return:+6.2%}")
        print(f"  Total Return:        {metrics.total_return:+6.2%}")
        if metrics.sharpe_ratio is not None:
            print(f"  Sharpe Ratio:        {metrics.sharpe_ratio:6.2f}")

        if metrics.accuracy_1h or metrics.accuracy_4h or metrics.accuracy_24h:
            print(f"\n⏱️  Time Interval Accuracy:")
            if metrics.accuracy_1h is not None:
                print(f"  1 Hour:              {metrics.accuracy_1h:6.2%}")
            if metrics.accuracy_4h is not None:
                print(f"  4 Hours:             {metrics.accuracy_4h:6.2%}")
            if metrics.accuracy_24h is not None:
                print(f"  24 Hours:            {metrics.accuracy_24h:6.2%}")

        if metrics.by_detector:
            print(f"\n🔍 By Detector Type:")
            for detector, detector_metrics in metrics.by_detector.items():
                print(f"\n  {detector.upper()}:")
                print(f"    Count:       {detector_metrics['count']:,}")
                print(f"    Precision:   {detector_metrics['precision']:6.2%}")
                print(f"    F1 Score:    {detector_metrics['f1_score']:6.2%}")
                print(f"    Avg Return:  {detector_metrics['average_return']:+6.2%}")
                print(f"    Win Rate:    {detector_metrics['win_rate']:6.2%}")

        if metrics.by_confidence:
            print(f"\n🎚️  By Confidence Threshold:")
            for threshold, conf_metrics in metrics.by_confidence.items():
                print(f"\n  Confidence {threshold}:")
                print(f"    Count:       {conf_metrics['count']:,}")
                print(f"    Precision:   {conf_metrics['precision']:6.2%}")
                print(f"    F1 Score:    {conf_metrics['f1_score']:6.2%}")
                print(f"    ROI:         {conf_metrics['roi']:+6.2%}")

        print("\n" + "=" * 80)
