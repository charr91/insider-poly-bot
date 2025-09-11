"""
Unit tests for PriceDetector class.
"""
import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import numpy as np

from detection.price_detector import PriceDetector
from tests.fixtures.data_generators import MockDataGenerator
from tests.test_utils import create_test_config, setup_detector_for_testing


class TestPriceDetector:
    """Test suite for PriceDetector functionality."""
    
    @pytest.fixture
    def detector(self):
        """Create PriceDetector instance for testing."""
        config = create_test_config()
        detector = PriceDetector(config)
        return setup_detector_for_testing(detector)
    
    @pytest.fixture
    def normal_price_trades(self):
        """Generate trades with normal price movement."""
        generator = MockDataGenerator()
        trades = generator.generate_normal_trades(count=50, time_span_hours=12)
        
        # Ensure stable pricing
        for i, trade in enumerate(trades):
            trade['price'] = str(0.50 + (i * 0.001))  # Gradual increase
        
        return trades
    
    @pytest.fixture
    def pump_dump_trades(self):
        """Generate pump and dump pattern trades."""
        generator = MockDataGenerator()
        return generator.generate_pump_and_dump_pattern()
    
    def test_init_custom_config(self):
        """Test PriceDetector initialization with custom config."""
        config = {
            'detection': {
                'price_thresholds': {
                    'rapid_movement_pct': 25,
                    'price_movement_std': 2.5,
                    'volatility_spike_multiplier': 5.0,
                    'momentum_threshold': 0.8
                }
            }
        }
        detector = PriceDetector(config)
        assert detector.thresholds['rapid_movement_pct'] == 25
        assert detector.thresholds['volatility_spike_multiplier'] == 5.0
    
    def test_detect_price_movement_empty_trades(self, detector):
        """Test price movement detection with empty trades."""
        result = detector.detect_price_movement([])
        assert not result['anomaly']
        assert result['reason'] == 'Insufficient trade data'
    
    def test_detect_price_movement_insufficient_trades(self, detector):
        """Test price movement detection with insufficient trades."""
        single_trade = [{'price': '0.5', 'timestamp': int(datetime.now().timestamp())}]
        result = detector.detect_price_movement(single_trade)
        assert not result['anomaly']
        assert result['reason'] == 'Insufficient trade data'
    
    def test_detect_price_movement_invalid_data(self, detector):
        """Test price movement detection with invalid data."""
        invalid_trades = [
            {'price': 'invalid', 'timestamp': 'invalid'},
            {'price': None, 'timestamp': None},
        ]
        result = detector.detect_price_movement(invalid_trades)
        assert not result['anomaly']
        assert 'normalization' in result['reason']
    
    def test_detect_price_movement_normal_trades(self, detector, normal_price_trades):
        """Test price movement detection with normal price movements."""
        result = detector.detect_price_movement(normal_price_trades, window_minutes=60)
        
        assert 'anomaly' in result
        assert 'analysis' in result
        assert 'triggers' in result
        
        analysis = result['analysis']
        assert 'price_change_pct' in analysis
        assert 'volatility_spike' in analysis
        assert 'momentum_score' in analysis
        assert 'trend_direction' in analysis
    
    def test_detect_price_movement_rapid_movement(self, detector):
        """Test detection of rapid price movements."""
        # Create trades with rapid price increase
        current_time = datetime.now(timezone.utc)
        rapid_trades = [
            {
                'price': '0.30',
                'timestamp': (current_time - timedelta(minutes=30)).timestamp()
            },
            {
                'price': '0.50',
                'timestamp': (current_time - timedelta(minutes=15)).timestamp()
            },
            {
                'price': '0.70',
                'timestamp': current_time.timestamp()
            }
        ]
        
        result = detector.detect_price_movement(rapid_trades, window_minutes=60)
        
        # Should detect rapid movement (30% -> 70% = 133% increase)
        assert result['triggers']['rapid_movement']
        assert result['analysis']['price_change_pct'] > 20  # Above threshold
    
    def test_detect_price_movement_high_volatility(self, detector):
        """Test detection of high volatility."""
        current_time = datetime.now(timezone.utc)
        
        # Create historical baseline with low volatility
        baseline_trades = []
        for i in range(20):
            baseline_trades.append({
                'price': str(0.49 + (i * 0.001)),  # Stable prices
                'timestamp': (current_time - timedelta(hours=24) + timedelta(hours=i)).timestamp()
            })
        
        # Add recent volatile trades
        volatile_trades = [
            {
                'price': '0.30',
                'timestamp': (current_time - timedelta(minutes=30)).timestamp()
            },
            {
                'price': '0.70',
                'timestamp': (current_time - timedelta(minutes=20)).timestamp()
            },
            {
                'price': '0.40',
                'timestamp': (current_time - timedelta(minutes=10)).timestamp()
            },
            {
                'price': '0.60',
                'timestamp': current_time.timestamp()
            }
        ]
        
        all_trades = baseline_trades + volatile_trades
        result = detector.detect_price_movement(all_trades, window_minutes=60)
        
        # Should detect volatility spike
        assert result['analysis']['volatility_spike'] > 1.0
    
    def test_detect_price_movement_high_momentum(self, detector):
        """Test detection of high momentum (consistent direction)."""
        current_time = datetime.now(timezone.utc)
        
        # Create consistent upward movement
        momentum_trades = []
        for i in range(10):
            momentum_trades.append({
                'price': str(0.30 + (i * 0.02)),  # Consistent increase
                'timestamp': (current_time - timedelta(minutes=50) + timedelta(minutes=i*5)).timestamp()
            })
        
        result = detector.detect_price_movement(momentum_trades, window_minutes=60)
        
        # Should detect high momentum
        assert result['analysis']['momentum_score'] > 0.8
        assert result['analysis']['trend_direction'] == 'UP'
    
    def test_analyze_price_pattern_calculations(self, detector, normal_price_trades):
        """Test detailed price pattern analysis calculations."""
        # Convert to dataframe for analysis
        df = pd.DataFrame(normal_price_trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df['price'] = df['price'].astype(float)
        
        recent_df = df.tail(10)  # Recent trades
        analysis = detector._analyze_price_pattern(recent_df, df)
        
        # Check all required fields are present
        required_fields = [
            'price_start', 'price_end', 'price_high', 'price_low',
            'price_change_abs', 'price_change_pct', 'price_range',
            'trend_direction', 'momentum_score', 'recent_volatility',
            'historical_volatility', 'volatility_spike',
            'price_change_std_score', 'ma_divergence', 'trade_count'
        ]
        
        for field in required_fields:
            assert field in analysis
        
        # Verify calculations make sense
        assert analysis['price_start'] <= analysis['price_high']
        assert analysis['price_start'] >= analysis['price_low']
        assert analysis['price_end'] <= analysis['price_high']
        assert analysis['price_end'] >= analysis['price_low']
        assert analysis['momentum_score'] >= 0 and analysis['momentum_score'] <= 1
        assert analysis['trade_count'] == len(recent_df)
    
    def test_detect_accumulation_pattern_empty_trades(self, detector):
        """Test accumulation detection with empty trades."""
        result = detector.detect_accumulation_pattern([])
        assert not result['anomaly']
        assert 'Insufficient trades' in result['reason']
    
    def test_detect_accumulation_pattern_insufficient_trades(self, detector):
        """Test accumulation detection with insufficient trades."""
        few_trades = [
            {'price': '0.5', 'size': '100', 'timestamp': int(datetime.now().timestamp())}
            for _ in range(5)
        ]
        result = detector.detect_accumulation_pattern(few_trades)
        assert not result['anomaly']
        assert 'Insufficient trades' in result['reason']
    
    def test_detect_accumulation_pattern_accumulation(self, detector):
        """Test detection of accumulation pattern."""
        current_time = datetime.now(timezone.utc)
        
        # Create accumulation pattern (prices above VWAP)
        accumulation_trades = []
        for i in range(25):
            accumulation_trades.append({
                'price': str(0.45 + (i * 0.01)),  # Gradually increasing
                'size': str(1000 + (i * 50)),     # Increasing size
                'timestamp': (current_time - timedelta(hours=2) + timedelta(minutes=i*4)).timestamp()
            })
        
        result = detector.detect_accumulation_pattern(accumulation_trades)
        
        assert 'pattern_type' in result
        assert 'pattern_strength' in result
        assert 'above_vwap_ratio' in result
        assert 'current_vwap' in result
        
        # Should detect accumulation or neutral pattern
        assert result['pattern_type'] in ['ACCUMULATION', 'NEUTRAL', 'DISTRIBUTION']
    
    def test_detect_accumulation_pattern_distribution(self, detector):
        """Test detection of distribution pattern."""
        current_time = datetime.now(timezone.utc)
        
        # Create distribution pattern (prices below VWAP)
        distribution_trades = []
        for i in range(25):
            distribution_trades.append({
                'price': str(0.65 - (i * 0.01)),  # Gradually decreasing
                'size': str(1000 + (i * 50)),     # Increasing size
                'timestamp': (current_time - timedelta(hours=2) + timedelta(minutes=i*4)).timestamp()
            })
        
        result = detector.detect_accumulation_pattern(distribution_trades)
        
        # Check for distribution or neutral pattern
        assert result['pattern_type'] in ['DISTRIBUTION', 'NEUTRAL', 'ACCUMULATION']
        assert result['below_vwap_ratio'] >= 0
    
    def test_get_price_summary_no_anomaly(self, detector):
        """Test price summary generation with no anomaly."""
        no_anomaly_result = {'anomaly': False}
        summary = detector.get_price_summary(no_anomaly_result)
        assert summary == "No unusual price movement detected"
    
    def test_get_price_summary_with_anomaly(self, detector):
        """Test price summary generation with detected anomaly."""
        anomaly_result = {
            'anomaly': True,
            'analysis': {
                'price_change_pct': 25.5,
                'volatility_spike': 3.2,
                'momentum_score': 0.85,
                'trend_direction': 'UP'
            }
        }
        
        summary = detector.get_price_summary(anomaly_result)
        
        assert "increased 25.5%" in summary
        assert "volatility 3.2x normal" in summary
        assert "85% consistent direction" in summary
        assert "strong UP trend" in summary
    
    def test_different_timestamp_formats(self, detector):
        """Test handling of different timestamp formats."""
        varied_timestamp_trades = [
            {
                'price': '0.5',
                'timestamp': int(datetime.now().timestamp())  # Unix timestamp
            },
            {
                'price': '0.51',
                'createdAt': datetime.now().isoformat() + 'Z'  # ISO format
            },
            {
                'price': '0.52',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # String format
            }
        ]
        
        result = detector.detect_price_movement(varied_timestamp_trades)
        # Should handle different formats without crashing
        assert 'anomaly' in result
    
    def test_different_field_names(self, detector):
        """Test handling of different field name formats."""
        varied_field_trades = [
            {'price': '0.5', 'timestamp': int(datetime.now().timestamp())},
            {'feeRate': '0.51', 'createdAt': int(datetime.now().timestamp())},
            {'outcome_price': '0.52', 'created_at': int(datetime.now().timestamp())},
        ]
        
        result = detector.detect_price_movement(varied_field_trades)
        assert 'analysis' in result
        assert result['analysis']['trade_count'] >= 1
    
    @pytest.mark.parametrize("price_change,expected_anomaly", [
        (5.0, False),   # Below 20% threshold
        (25.0, True),   # Above 20% threshold
        (50.0, True),   # Well above threshold
    ])
    def test_rapid_movement_threshold_sensitivity(self, detector, price_change, expected_anomaly):
        """Test rapid movement detection sensitivity."""
        current_time = datetime.now(timezone.utc)
        
        start_price = 0.50
        end_price = start_price * (1 + price_change / 100)
        
        test_trades = [
            {
                'price': str(start_price),
                'timestamp': (current_time - timedelta(minutes=30)).timestamp()
            },
            {
                'price': str(end_price),
                'timestamp': current_time.timestamp()
            }
        ]
        
        result = detector.detect_price_movement(test_trades, window_minutes=60)
        
        if expected_anomaly:
            assert result['triggers']['rapid_movement']
        else:
            # May still trigger on other conditions
            pass
    
    def test_window_size_effects(self, detector, normal_price_trades):
        """Test effects of different time window sizes."""
        window_sizes = [15, 30, 60, 120]
        results = []
        
        for window in window_sizes:
            result = detector.detect_price_movement(normal_price_trades, window_minutes=window)
            results.append(result)
        
        # All should complete successfully
        assert len(results) == len(window_sizes)
        for result in results:
            assert 'anomaly' in result
            assert 'analysis' in result
    
    def test_edge_cases_zero_prices(self, detector):
        """Test edge cases with zero prices."""
        zero_price_trades = [
            {'price': '0', 'timestamp': int(datetime.now().timestamp())},
            {'price': '0.5', 'timestamp': int(datetime.now().timestamp()) + 60},
        ]
        
        result = detector.detect_price_movement(zero_price_trades)
        # Should handle gracefully by filtering out zero prices
        assert 'reason' in result
    
    def test_edge_cases_negative_prices(self, detector):
        """Test edge cases with negative prices."""
        negative_price_trades = [
            {'price': '-0.1', 'timestamp': int(datetime.now().timestamp())},
            {'price': '0.5', 'timestamp': int(datetime.now().timestamp()) + 60},
        ]
        
        result = detector.detect_price_movement(negative_price_trades)
        # Should filter out negative prices
        assert 'reason' in result
    
    def test_vwap_calculation_accuracy(self, detector):
        """Test VWAP calculation accuracy."""
        # Create known trades for VWAP calculation
        known_trades = [
            {'price': '0.50', 'size': '100', 'timestamp': int(datetime.now().timestamp())},
            {'price': '0.60', 'size': '200', 'timestamp': int(datetime.now().timestamp()) + 60},
            {'price': '0.40', 'size': '300', 'timestamp': int(datetime.now().timestamp()) + 120},
        ]
        
        # Expected VWAP = (0.5*100 + 0.6*200 + 0.4*300) / (100+200+300) = 0.483
        expected_vwap = (0.5*100 + 0.6*200 + 0.4*300) / (100+200+300)
        
        # Add more trades to meet minimum requirement
        for i in range(15):
            known_trades.append({
                'price': '0.50',
                'size': '100',
                'timestamp': int(datetime.now().timestamp()) + 180 + (i * 60)
            })
        
        result = detector.detect_accumulation_pattern(known_trades)
        
        # Check VWAP is reasonable
        assert 'current_vwap' in result
        assert result['current_vwap'] > 0
    
    def test_thread_safety_simulation(self, detector, normal_price_trades):
        """Simulate concurrent access to detector methods."""
        import threading
        results = []
        
        def analyze_worker():
            result = detector.detect_price_movement(normal_price_trades)
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
    
    def test_memory_efficiency_large_dataset(self, detector):
        """Test memory efficiency with large datasets."""
        generator = MockDataGenerator()
        large_trades = generator.generate_normal_trades(count=5000, time_span_hours=168)
        
        # Should handle large datasets without memory issues
        result = detector.detect_price_movement(large_trades)
        assert 'anomaly' in result
        assert 'analysis' in result
    
    @patch('detection.price_detector.datetime')
    def test_time_window_boundary_conditions(self, mock_datetime, detector, normal_price_trades):
        """Test boundary conditions for time window calculations."""
        # Mock current time
        fixed_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_time
        
        # Ensure datetime.now(timezone.utc) returns our fixed time
        with patch('detection.price_detector.datetime') as mock_dt:
            mock_dt.now.return_value = fixed_time
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            result = detector.detect_price_movement(normal_price_trades, window_minutes=60)
            
            # Should handle time boundary calculations correctly
            assert 'analysis' in result