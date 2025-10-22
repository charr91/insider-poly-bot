"""
Unit tests for market maker detection algorithm.

Tests the heuristic scoring system for identifying market makers.
"""

import pytest
from datetime import datetime, timedelta
from persistence.whale_tracker import calculate_mm_score
from common import MarketMakerThresholds


class TestMMDetectionAlgorithm:
    """Test market maker detection scoring"""

    def test_high_frequency_balanced_multi_market_mm(self):
        """High frequency + balanced ratio + many markets = likely MM"""
        score = calculate_mm_score(
            trade_count=150,
            buy_volume=50000,
            sell_volume=48000,
            markets_count=12,
            first_seen=datetime(2024, 1, 1),
            last_seen=datetime(2024, 1, 15)
        )

        # Should get maximum scores:
        # Frequency: 30 (high frequency)
        # Balance: 40 (tight ratio)
        # Markets: 20 (many markets)
        # Consistency: 10 (14 days active)
        assert score == 100
        assert score >= MarketMakerThresholds.MM_CLASSIFICATION_THRESHOLD

    def test_whale_not_mm_imbalanced(self):
        """High volume but very imbalanced = not MM"""
        score = calculate_mm_score(
            trade_count=10,
            buy_volume=500000,
            sell_volume=5000,
            markets_count=2,
            first_seen=datetime(2024, 1, 10),
            last_seen=datetime(2024, 1, 11)
        )

        # Should get low score:
        # Frequency: 0 (only 10 trades)
        # Balance: 0 (highly imbalanced: 99% buy)
        # Markets: 0 (only 2 markets)
        # Consistency: 0 (1 day = 1 day difference, which is 0 days by calculation)
        assert score == 0
        assert score < MarketMakerThresholds.MM_CLASSIFICATION_THRESHOLD

    def test_medium_frequency_balanced(self):
        """Medium frequency + balanced = borderline MM"""
        score = calculate_mm_score(
            trade_count=60,
            buy_volume=30000,
            sell_volume=28000,
            markets_count=6,
            first_seen=datetime(2024, 1, 1),
            last_seen=datetime(2024, 1, 8)
        )

        # Should get:
        # Frequency: 20 (medium frequency)
        # Balance: 40 (tight ratio)
        # Markets: 10 (several markets)
        # Consistency: 10 (7 days)
        assert score == 80
        assert score >= MarketMakerThresholds.MM_CLASSIFICATION_THRESHOLD

    def test_low_frequency_not_mm(self):
        """Low frequency even if balanced = not MM"""
        score = calculate_mm_score(
            trade_count=15,
            buy_volume=10000,
            sell_volume=9500,
            markets_count=3,
            first_seen=datetime(2024, 1, 10),
            last_seen=datetime(2024, 1, 11)
        )

        # Should get:
        # Frequency: 0 (below low threshold)
        # Balance: 40 (tight ratio)
        # Markets: 0 (few markets)
        # Consistency: 0 (1 day difference = 0 days)
        assert score == 40
        assert score < MarketMakerThresholds.MM_CLASSIFICATION_THRESHOLD

    def test_loose_balance_still_mm(self):
        """Looser balance but still within MM range"""
        score = calculate_mm_score(
            trade_count=120,
            buy_volume=60000,
            sell_volume=40000,  # 60/40 ratio
            markets_count=8,
            first_seen=datetime(2024, 1, 1),
            last_seen=datetime(2024, 1, 10)
        )

        # Should get:
        # Frequency: 30 (high frequency)
        # Balance: 20 (loose ratio, 60% buy)
        # Markets: 10 (several markets)
        # Consistency: 10 (9 days)
        assert score == 70
        assert score >= MarketMakerThresholds.MM_CLASSIFICATION_THRESHOLD

    def test_edge_case_exact_threshold(self):
        """Test exact threshold boundaries"""
        # Exactly at high frequency threshold
        score_high = calculate_mm_score(
            trade_count=MarketMakerThresholds.HIGH_FREQUENCY_TRADES,
            buy_volume=50000,
            sell_volume=50000,
            markets_count=10,
            first_seen=datetime(2024, 1, 1),
            last_seen=datetime(2024, 1, 8)
        )

        assert score_high == 100

        # Just below high frequency threshold
        score_medium = calculate_mm_score(
            trade_count=MarketMakerThresholds.HIGH_FREQUENCY_TRADES - 1,
            buy_volume=50000,
            sell_volume=50000,
            markets_count=10,
            first_seen=datetime(2024, 1, 1),
            last_seen=datetime(2024, 1, 8)
        )

        assert score_medium == 90  # 20+40+20+10

    def test_zero_volume_edge_case(self):
        """Handle zero volume gracefully"""
        score = calculate_mm_score(
            trade_count=100,
            buy_volume=0,
            sell_volume=0,
            markets_count=5,
            first_seen=datetime(2024, 1, 1),
            last_seen=datetime(2024, 1, 8)
        )

        # Should get:
        # Frequency: 30
        # Balance: 0 (no volume to calculate ratio)
        # Markets: 10
        # Consistency: 10
        assert score == 50

    def test_single_direction_trading(self):
        """All buy or all sell volume = not balanced"""
        # All buy
        score_buy = calculate_mm_score(
            trade_count=100,
            buy_volume=100000,
            sell_volume=0,
            markets_count=10,
            first_seen=datetime(2024, 1, 1),
            last_seen=datetime(2024, 1, 8)
        )

        # All sell
        score_sell = calculate_mm_score(
            trade_count=100,
            buy_volume=0,
            sell_volume=100000,
            markets_count=10,
            first_seen=datetime(2024, 1, 1),
            last_seen=datetime(2024, 1, 8)
        )

        # Both should get same score
        # Frequency: 30, Balance: 0, Markets: 20, Consistency: 10
        assert score_buy == score_sell == 60
        assert score_buy < MarketMakerThresholds.MM_CLASSIFICATION_THRESHOLD

    def test_new_whale_single_day(self):
        """New whale with single day activity"""
        score = calculate_mm_score(
            trade_count=150,
            buy_volume=50000,
            sell_volume=50000,
            markets_count=12,
            first_seen=datetime(2024, 1, 10, 10, 0),
            last_seen=datetime(2024, 1, 10, 14, 0)  # Same day, 4 hours apart
        )

        # Should get:
        # Frequency: 30
        # Balance: 40
        # Markets: 20
        # Consistency: 0 (0 days)
        assert score == 90

    def test_score_never_exceeds_100(self):
        """Score should be capped at 100"""
        # Try to create scenario that would exceed 100
        score = calculate_mm_score(
            trade_count=1000,
            buy_volume=1000000,
            sell_volume=1000000,
            markets_count=100,
            first_seen=datetime(2023, 1, 1),
            last_seen=datetime(2024, 1, 1)
        )

        assert score <= 100
        assert score == 100
