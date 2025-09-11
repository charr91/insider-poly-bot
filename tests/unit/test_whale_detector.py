"""
Unit tests for WhaleDetector class.
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch
import numpy as np

from detection.whale_detector import WhaleDetector
from tests.fixtures.data_generators import MockDataGenerator
from tests.test_utils import create_test_config, setup_detector_for_testing


class TestWhaleDetector:
    """Test suite for WhaleDetector functionality."""
    
    @pytest.fixture
    def detector(self):
        """Create WhaleDetector instance for testing."""
        config = create_test_config()
        detector = WhaleDetector(config)
        return setup_detector_for_testing(detector)
    
    @pytest.fixture
    def normal_trades(self):
        """Generate normal trade data without whales."""
        generator = MockDataGenerator()
        return generator.generate_normal_trades(count=50, time_span_hours=12)
    
    @pytest.fixture
    def whale_trades(self):
        """Generate whale trading data."""
        generator = MockDataGenerator()
        return generator.generate_whale_accumulation_pattern(
            accumulation_count=8,
            time_span_hours=6
        )
    
    @pytest.fixture
    def coordinated_trades(self):
        """Generate coordinated whale trading data."""
        generator = MockDataGenerator()
        return generator.generate_coordinated_trading_pattern(
            wallet_count=5,
            coordination_window=300
        )
    
    def test_init_custom_config(self):
        """Test WhaleDetector initialization with custom config."""
        config = {
            'detection': {
                'whale_thresholds': {
                    'whale_threshold_usd': 50000,
                    'coordination_threshold': 0.9,
                    'min_whales_for_coordination': 5
                }
            }
        }
        detector = WhaleDetector(config)
        assert detector.thresholds['whale_threshold_usd'] == 50000
        assert detector.thresholds['coordination_threshold'] == 0.9
        assert detector.thresholds['min_whales_for_coordination'] == 5
    
    def test_detect_whale_activity_empty_trades(self, detector):
        """Test whale detection with empty trades list."""
        result = detector.detect_whale_activity([])
        assert not result['anomaly']
        assert result['reason'] == 'No trades available'
    
    def test_detect_whale_activity_invalid_trades(self, detector):
        """Test whale detection with invalid trade data."""
        invalid_trades = [
            {'price': 'invalid', 'size': 'invalid'},
            {'price': None, 'size': None},
            {},
        ]
        result = detector.detect_whale_activity(invalid_trades)
        assert not result['anomaly']
        assert 'No valid trades after normalization' in result['reason']
    
    def test_detect_whale_activity_no_whales(self, detector, normal_trades):
        """Test whale detection with normal-sized trades."""
        result = detector.detect_whale_activity(normal_trades)
        
        assert not result['anomaly']
        assert '$10000 threshold' in result['reason']
        assert result['total_trades'] > 0
        assert result['largest_trade'] > 0
    
    def test_detect_whale_activity_single_whale(self, detector):
        """Test detection of single whale trade."""
        whale_trade = [{
            'price': '0.5',
            'size': '40000',  # $20k trade
            'side': 'BUY',
            'maker': '0xwhale123'
        }]
        
        result = detector.detect_whale_activity(whale_trade)
        
        assert 'whale_count' in result
        assert 'total_whale_volume' in result
        assert 'largest_whale_volume' in result
        assert result['total_whale_volume'] > 15000
    
    def test_detect_whale_activity_multiple_whales(self, detector, whale_trades):
        """Test detection of multiple whale trades."""
        result = detector.detect_whale_activity(whale_trades)
        
        assert result['whale_count'] > 0
        assert result['total_whale_volume'] > 0
        assert result['largest_whale_volume'] > 0
        assert 'whale_breakdown' in result
        assert 'market_impact' in result
    
    def test_analyze_whale_patterns_directional_bias(self, detector):
        """Test analysis of directional bias in whale trading."""
        # Create trades with strong BUY bias
        biased_trades = []
        for i in range(5):
            biased_trades.append({
                'price': '0.5',
                'size': '30000',  # Whale size
                'side': 'BUY',
                'maker': f'0xwhale{i}'
            })
        
        result = detector.detect_whale_activity(biased_trades)
        
        assert result['dominant_side'] == 'BUY'
        assert result['direction_imbalance'] > 0.9  # Strong bias
    
    def test_analyze_whale_patterns_market_impact(self, detector):
        """Test calculation of whale market impact."""
        # Mix of whale and normal trades
        mixed_trades = [
            {'price': '0.5', 'size': '50000', 'side': 'BUY', 'maker': '0xwhale1'},
            {'price': '0.5', 'size': '1000', 'side': 'SELL', 'maker': '0xnormal1'},
            {'price': '0.5', 'size': '1000', 'side': 'BUY', 'maker': '0xnormal2'},
        ]
        
        result = detector.detect_whale_activity(mixed_trades)
        
        market_impact = result['market_impact']
        assert 'whale_market_share' in market_impact
        assert 'total_market_volume' in market_impact
        assert 'whale_dominance' in market_impact
        
        # Whale should dominate this small market
        assert market_impact['whale_market_share'] > 0.8
        assert market_impact['whale_dominance']
    
    def test_detect_coordination_insufficient_trades(self, detector):
        """Test coordination detection with insufficient whale trades."""
        small_whale_data = pd.DataFrame([
            {'price': 0.5, 'size': 20000, 'side': 'BUY', 'maker': '0xwhale1', 'volume_usd': 10000}
        ])
        
        result = detector._detect_coordination(small_whale_data)
        
        assert not result['coordinated']
        assert 'Insufficient whale trades' in result['reason']
    
    def test_detect_coordination_same_direction(self, detector):
        """Test coordination detection with same-direction trades."""
        coordinated_data = pd.DataFrame([
            {'price': 0.5, 'size': 20000, 'side': 'BUY', 'maker': '0xwhale1', 'volume_usd': 10000},
            {'price': 0.5, 'size': 22000, 'side': 'BUY', 'maker': '0xwhale2', 'volume_usd': 11000},
            {'price': 0.5, 'size': 21000, 'side': 'BUY', 'maker': '0xwhale3', 'volume_usd': 10500},
            {'price': 0.5, 'size': 20500, 'side': 'BUY', 'maker': '0xwhale4', 'volume_usd': 10250},
        ])
        
        result = detector._detect_coordination(coordinated_data)
        
        assert result['same_direction']
        assert result['unique_whales'] >= 3
        assert result['coordination_score'] >= 4
        assert result['coordinated']
    
    def test_detect_coordination_with_timestamps(self, detector):
        """Test coordination detection with timestamp clustering."""
        import datetime
        base_time = datetime.datetime.now()
        
        timestamped_data = pd.DataFrame([
            {
                'price': 0.5, 'size': 20000, 'side': 'BUY', 'maker': '0xwhale1',
                'volume_usd': 10000, 'timestamp': base_time
            },
            {
                'price': 0.5, 'size': 22000, 'side': 'BUY', 'maker': '0xwhale2',
                'volume_usd': 11000, 'timestamp': base_time + datetime.timedelta(minutes=2)
            },
            {
                'price': 0.5, 'size': 21000, 'side': 'BUY', 'maker': '0xwhale3',
                'volume_usd': 10500, 'timestamp': base_time + datetime.timedelta(minutes=3)
            },
            {
                'price': 0.5, 'size': 20500, 'side': 'BUY', 'maker': '0xwhale4',
                'volume_usd': 10250, 'timestamp': base_time + datetime.timedelta(minutes=4)
            },
        ])
        
        result = detector._detect_coordination(timestamped_data)
        
        assert result['clustered_timing']
        assert result['avg_time_gap'] is not None
        assert result['coordination_score'] > 0
    
    def test_detect_coordination_similar_sizes(self, detector):
        """Test coordination detection with similar trade sizes."""
        similar_size_data = pd.DataFrame([
            {'price': 0.5, 'size': 20000, 'side': 'BUY', 'maker': '0xwhale1', 'volume_usd': 10000},
            {'price': 0.5, 'size': 20100, 'side': 'BUY', 'maker': '0xwhale2', 'volume_usd': 10050},
            {'price': 0.5, 'size': 19900, 'side': 'BUY', 'maker': '0xwhale3', 'volume_usd': 9950},
            {'price': 0.5, 'size': 20050, 'side': 'BUY', 'maker': '0xwhale4', 'volume_usd': 10025},
        ])
        
        result = detector._detect_coordination(similar_size_data)
        
        assert result['similar_sizes']
        assert result['size_variance'] < 0.5
    
    def test_get_whale_summary_no_activity(self, detector):
        """Test whale summary generation with no activity."""
        no_activity_result = {'anomaly': False}
        summary = detector.get_whale_summary(no_activity_result)
        assert summary == "No significant whale activity detected"
    
    def test_get_whale_summary_with_activity(self, detector):
        """Test whale summary generation with detected activity."""
        activity_result = {
            'anomaly': True,
            'whale_count': 5,
            'total_whale_volume': 125000,
            'direction_imbalance': 0.8,
            'dominant_side': 'BUY',
            'coordination': {'coordinated': True, 'coordination_score': 6},
            'market_impact': {'whale_dominance': True, 'whale_market_share': 0.45}
        }
        
        summary = detector.get_whale_summary(activity_result)
        
        assert "5 whales traded $125,000" in summary
        assert "80% BUY bias" in summary
        assert "coordination detected" in summary
        assert "45.0% of market volume" in summary
    
    def test_different_field_names(self, detector):
        """Test handling of different field name formats."""
        varied_field_trades = [
            {'price': '100', 'size': '200', 'side': 'BUY', 'maker': '0xwhale1'},
            {'feeRate': '100', 'amount': '200', 'type': 'SELL', 'trader': '0xwhale2'},
            {'outcome_price': '100', 'shares': '200', 'side': 'BUY', 'user': '0xwhale3'},
        ]
        
        result = detector.detect_whale_activity(varied_field_trades)
        
        # Should normalize and process all trades
        assert 'whale_count' in result
        assert 'total_whale_volume' in result
    
    @pytest.mark.parametrize("threshold,expected_whales", [
        (5000, 3),   # Lower threshold, more whales
        (25000, 1),  # Higher threshold, fewer whales
        (100000, 0), # Very high threshold, no whales
    ])
    def test_whale_threshold_sensitivity(self, detector, threshold, expected_whales):
        """Test whale detection sensitivity to different thresholds."""
        # Override threshold
        detector.thresholds['whale_threshold_usd'] = threshold
        
        test_trades = [
            {'price': '0.5', 'size': '20000', 'side': 'BUY', 'maker': '0xwhale1'},  # $10k
            {'price': '0.6', 'size': '50000', 'side': 'BUY', 'maker': '0xwhale2'},  # $30k
            {'price': '0.4', 'size': '25000', 'side': 'SELL', 'maker': '0xwhale3'}, # $10k
        ]
        
        result = detector.detect_whale_activity(test_trades)
        
        if expected_whales > 0:
            assert result['whale_count'] >= expected_whales
        else:
            assert not result['anomaly']
    
    def test_edge_cases_zero_volume_trades(self, detector):
        """Test edge cases with zero volume trades."""
        zero_volume_trades = [
            {'price': '0', 'size': '1000', 'side': 'BUY', 'maker': '0xtrader1'},
            {'price': '100', 'size': '0', 'side': 'SELL', 'maker': '0xtrader2'},
        ]
        
        result = detector.detect_whale_activity(zero_volume_trades)
        # Should handle gracefully without crashing
        assert 'anomaly' in result
    
    def test_edge_cases_negative_values(self, detector):
        """Test edge cases with negative price/size values."""
        negative_trades = [
            {'price': '-100', 'size': '1000', 'side': 'BUY', 'maker': '0xtrader1'},
            {'price': '100', 'size': '-1000', 'side': 'SELL', 'maker': '0xtrader2'},
        ]
        
        result = detector.detect_whale_activity(negative_trades)
        # Should filter out invalid trades
        assert not result['anomaly']
    
    def test_whale_breakdown_sorting(self, detector):
        """Test that whale breakdown is properly sorted by volume."""
        whale_trades_data = [
            {'price': '0.5', 'size': '20000', 'side': 'BUY', 'maker': '0xsmall'},   # $10k
            {'price': '0.5', 'size': '80000', 'side': 'BUY', 'maker': '0xlarge'},   # $40k
            {'price': '0.5', 'size': '50000', 'side': 'BUY', 'maker': '0xmedium'},  # $25k
        ]
        
        result = detector.detect_whale_activity(whale_trades_data)
        
        breakdown = result['whale_breakdown']
        volumes = [data['total_volume'] for data in breakdown.values()]
        
        # Should be sorted in descending order
        assert volumes == sorted(volumes, reverse=True)
        assert list(breakdown.keys())[0] == '0xlarge'  # Largest should be first
    
    def test_memory_efficiency_large_dataset(self, detector):
        """Test memory efficiency with large whale datasets."""
        # Create large dataset with many whale trades
        large_whale_trades = []
        for i in range(1000):
            large_whale_trades.append({
                'price': '0.5',
                'size': str(50000 + i),  # Varying whale sizes, all well above threshold
                'side': 'BUY' if i % 2 == 0 else 'SELL',
                'maker': f'0xwhale{i}'
            })
        
        result = detector.detect_whale_activity(large_whale_trades)
        
        # Should handle large datasets without memory issues
        assert result['whale_count'] == 1000
        assert 'whale_breakdown' in result
        assert len(result['whale_breakdown']) <= 10  # Top 10 limited
    
    def test_coordination_score_calculation(self, detector):
        """Test coordination score calculation with various scenarios."""
        # Perfect coordination scenario
        perfect_coord_data = pd.DataFrame([
            {'price': 0.5, 'size': 20000, 'side': 'BUY', 'maker': '0xwhale1', 'volume_usd': 10000},
            {'price': 0.5, 'size': 20000, 'side': 'BUY', 'maker': '0xwhale2', 'volume_usd': 10000},
            {'price': 0.5, 'size': 20000, 'side': 'BUY', 'maker': '0xwhale3', 'volume_usd': 10000},
            {'price': 0.5, 'size': 20000, 'side': 'BUY', 'maker': '0xwhale4', 'volume_usd': 10000},
        ])
        
        result = detector._detect_coordination(perfect_coord_data)
        
        # Should have high coordination score
        assert result['coordination_score'] >= 5
        assert result['same_direction']
        assert result['similar_sizes']
        assert result['coordinated']
    
    def test_thread_safety_simulation(self, detector, whale_trades):
        """Simulate concurrent access to detector methods."""
        import threading
        results = []
        
        def analyze_worker():
            result = detector.detect_whale_activity(whale_trades)
            results.append(result['anomaly'])
        
        threads = [threading.Thread(target=analyze_worker) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All threads should complete successfully
        assert len(results) == 5
        # Results should be consistent
        assert all(isinstance(result, bool) for result in results)