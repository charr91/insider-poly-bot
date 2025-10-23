"""
Unit tests for RecommendationEngine
"""

import pytest
from alerts.recommendation_engine import RecommendationEngine, RecommendationAction, ConfidenceLevel
from common import AlertType, AlertSeverity


class TestRecommendationEngine:
    """Test RecommendationEngine functionality"""

    @pytest.fixture
    def engine(self):
        """Create recommendation engine with test token mapping"""
        token_mapping = {
            'token_yes_123': 'YES',
            'token_no_456': 'NO'
        }
        return RecommendationEngine(token_to_outcome=token_mapping)

    @pytest.fixture
    def market_data(self):
        """Sample market data"""
        return {
            'lastTradePrice': 0.65,
            'volume24hr': 100000
        }

    def test_whale_activity_high_confidence(self, engine, market_data):
        """Test high confidence whale activity generates BUY recommendation"""
        analysis = {
            'total_whale_volume': 150000,
            'whale_count': 3,
            'dominant_side': 'BUY',
            'direction_imbalance': 0.9,
            'coordination': {'coordinated': True}
        }

        recommendation = engine.generate_recommendation(
            alert_type=AlertType.WHALE_ACTIVITY,
            severity=AlertSeverity.CRITICAL,
            analysis=analysis,
            market_data=market_data,
            confidence_score=12.0,
            multi_metric=False
        )

        assert recommendation['action'] == RecommendationAction.BUY.value
        assert 'YES' in recommendation['text']  # or 'NO', depending on outcome determination
        assert recommendation['entry_price'] is not None
        assert recommendation['risk_price'] is not None
        assert 'whale' in recommendation['reasoning'].lower()

    def test_whale_activity_medium_confidence(self, engine, market_data):
        """Test medium confidence whale activity generates MONITOR recommendation"""
        analysis = {
            'total_whale_volume': 25000,
            'whale_count': 1,
            'dominant_side': 'BUY',
            'direction_imbalance': 0.7,
            'coordination': {'coordinated': False}
        }

        recommendation = engine.generate_recommendation(
            alert_type=AlertType.WHALE_ACTIVITY,
            severity=AlertSeverity.MEDIUM,
            analysis=analysis,
            market_data=market_data,
            confidence_score=6.0,
            multi_metric=False
        )

        assert recommendation['action'] == RecommendationAction.MONITOR.value
        assert 'Monitor' in recommendation['text']
        assert recommendation['entry_price'] is None

    def test_coordinated_trading_critical(self, engine, market_data):
        """Test critical coordination generates strong recommendation"""
        analysis = {
            'coordination_score': 0.85,
            'unique_wallets': 7,
            'directional_bias': 0.9,
            'dominant_direction': 'BUY',
            'wash_trading_detected': False,
            'total_volume': 200000
        }

        recommendation = engine.generate_recommendation(
            alert_type=AlertType.COORDINATED_TRADING,
            severity=AlertSeverity.CRITICAL,
            analysis=analysis,
            market_data=market_data,
            confidence_score=14.0,
            multi_metric=False
        )

        assert recommendation['action'] in [RecommendationAction.BUY.value, RecommendationAction.SELL.value]
        assert 'insider signal' in recommendation['text'].lower()
        assert recommendation['entry_price'] is not None

    def test_volume_spike_monitor_only(self, engine, market_data):
        """Test volume spike generates MONITOR recommendation (ambiguous signal)"""
        analysis = {
            'max_anomaly_score': 5.2
        }

        recommendation = engine.generate_recommendation(
            alert_type=AlertType.VOLUME_SPIKE,
            severity=AlertSeverity.HIGH,
            analysis=analysis,
            market_data=market_data,
            confidence_score=8.0,
            multi_metric=False
        )

        assert recommendation['action'] == RecommendationAction.MONITOR.value
        assert 'volume' in recommendation['text'].lower()

    def test_multi_metric_very_high_confidence(self, engine, market_data):
        """Test multi-metric alert with very high confidence"""
        analysis = {
            'total_whale_volume': 200000,
            'whale_count': 5,
            'dominant_side': 'BUY',
            'direction_imbalance': 0.95,
            'coordination': {'coordinated': True}
        }

        supporting_anomalies = [
            {'type': AlertType.VOLUME_SPIKE, 'confidence': 8.0},
            {'type': AlertType.UNUSUAL_PRICE_MOVEMENT, 'confidence': 6.0}
        ]

        recommendation = engine.generate_recommendation(
            alert_type=AlertType.WHALE_ACTIVITY,
            severity=AlertSeverity.CRITICAL,
            analysis=analysis,
            market_data=market_data,
            confidence_score=18.0,
            multi_metric=True,
            supporting_anomalies=supporting_anomalies
        )

        assert recommendation['action'] in [RecommendationAction.BUY.value, RecommendationAction.SELL.value]
        assert recommendation['target_price'] is not None
        assert recommendation['risk_price'] is not None
        assert 'Entry:' in recommendation['text'] or 'Target:' in recommendation['text']

    def test_confidence_level_determination(self, engine, market_data):
        """Test confidence level calculation"""
        analysis = {}

        # Very high confidence
        rec = engine.generate_recommendation(
            alert_type=AlertType.VOLUME_SPIKE,
            severity=AlertSeverity.CRITICAL,
            analysis=analysis,
            market_data=market_data,
            confidence_score=15.0,
            multi_metric=True
        )
        assert rec['confidence_level'] in [ConfidenceLevel.VERY_HIGH.value, ConfidenceLevel.HIGH.value]

        # Low confidence
        rec = engine.generate_recommendation(
            alert_type=AlertType.VOLUME_SPIKE,
            severity=AlertSeverity.LOW,
            analysis=analysis,
            market_data=market_data,
            confidence_score=4.0,
            multi_metric=False
        )
        assert rec['confidence_level'] in [ConfidenceLevel.LOW.value, ConfidenceLevel.MEDIUM.value]

    def test_price_levels_calculation(self, engine, market_data):
        """Test that price levels are calculated correctly"""
        current_price = 0.65

        analysis = {
            'total_whale_volume': 100000,
            'whale_count': 3,
            'dominant_side': 'BUY',
            'direction_imbalance': 0.9,
            'coordination': {'coordinated': True}
        }

        recommendation = engine.generate_recommendation(
            alert_type=AlertType.WHALE_ACTIVITY,
            severity=AlertSeverity.CRITICAL,
            analysis=analysis,
            market_data=market_data,
            confidence_score=12.0,
            multi_metric=False
        )

        # Check price levels are reasonable
        if recommendation['entry_price']:
            assert recommendation['entry_price'] > current_price * 0.95
            assert recommendation['entry_price'] < current_price * 1.05

        if recommendation['risk_price']:
            assert recommendation['risk_price'] != current_price
