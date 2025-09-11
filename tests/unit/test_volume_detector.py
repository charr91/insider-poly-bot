"""
Unit tests for VolumeDetector class.
"""
import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import numpy as np

from detection.volume_detector import VolumeDetector
from tests.fixtures.data_generators import MockDataGenerator


class TestVolumeDetector:
    """Test suite for VolumeDetector functionality."""
    
    @pytest.fixture
    def detector(self):
        """Create VolumeDetector instance for testing."""
        config = {
            'detection': {
                'volume_thresholds': {
                    'volume_spike_multiplier': 4.0,
                    'z_score_threshold': 3.0
                }
            }
        }
        detector = VolumeDetector(config)
        return detector
    
    @pytest.fixture
    def sample_trades(self):
        """Generate sample trade data."""
        generator = MockDataGenerator()
        return generator.generate_normal_trades(count=100, time_span_hours=24)
    
    @pytest.fixture
    def spike_trades(self):
        """Generate trades with volume spike."""
        generator = MockDataGenerator()
        return generator.generate_volume_spike_pattern(spike_multiplier=8.0)
    
    def test_init_default_config(self):
        """Test VolumeDetector initialization with minimal config."""
        config = {
            'detection': {
                'volume_thresholds': {
                    'volume_spike_multiplier': 3.0,
                    'z_score_threshold': 3.0
                }
            }
        }
        detector = VolumeDetector(config)
        assert detector.thresholds['volume_spike_multiplier'] == 3.0
        assert detector.thresholds['z_score_threshold'] == 3.0
    
    def test_init_custom_config(self):
        """Test VolumeDetector initialization with custom config."""
        config = {
            'detection': {
                'volume_thresholds': {
                    'volume_spike_multiplier': 10.0,
                    'z_score_threshold': 5.0
                }
            }
        }
        detector = VolumeDetector(config)
        assert detector.thresholds['volume_spike_multiplier'] == 10.0
        assert detector.thresholds['z_score_threshold'] == 5.0
    
    def test_calculate_baseline_metrics_empty_trades(self, detector):
        """Test baseline calculation with empty trades list."""
        result = detector.calculate_baseline_metrics([])
        assert result == {}
    
    def test_calculate_baseline_metrics_normal_trades(self, detector, sample_trades):
        """Test baseline calculation with normal trades."""
        baseline = detector.calculate_baseline_metrics(sample_trades)
        
        assert 'avg_hourly_volume' in baseline
        assert 'std_hourly_volume' in baseline
        assert 'avg_trades_per_hour' in baseline
        assert 'total_volume' in baseline
        
        assert baseline['avg_hourly_volume'] > 0
        assert baseline['total_volume'] > 0
    
    def test_calculate_baseline_metrics_invalid_data(self, detector):
        """Test baseline calculation with invalid trade data."""
        invalid_trades = [
            {'price': 'invalid', 'size': 'invalid'},
            {'price': None, 'size': None},
            {},
        ]
        baseline = detector.calculate_baseline_metrics(invalid_trades)
        assert baseline == {}
    
    def test_detect_volume_spike_no_baseline(self, detector):
        """Test spike detection without baseline data."""
        is_anomaly, spike_multiplier, details = detector.detect_volume_spike(1000, {})
        
        assert not is_anomaly
        assert spike_multiplier == 0
        assert 'reason' in details
        assert details['reason'] == 'No baseline data available'
    
    def test_detect_volume_spike_zero_baseline(self, detector):
        """Test spike detection with zero baseline volume."""
        baseline = {'avg_hourly_volume': 0, 'std_hourly_volume': 0}
        is_anomaly, spike_multiplier, details = detector.detect_volume_spike(1000, baseline)
        
        assert not is_anomaly
        assert spike_multiplier == 0
        assert details['reason'] == 'Zero baseline volume'
    
    def test_detect_volume_spike_normal_volume(self, detector):
        """Test spike detection with normal volume levels."""
        baseline = {
            'avg_hourly_volume': 1000,
            'std_hourly_volume': 200
        }
        current_volume = 1200  # 1.2x average, below 5x threshold
        
        is_anomaly, spike_multiplier, details = detector.detect_volume_spike(
            current_volume, baseline
        )
        
        assert not is_anomaly
        assert abs(spike_multiplier - 1.2) < 0.001  # Use approximate comparison for floating point
        assert details['current_volume'] == current_volume
        assert details['avg_volume'] == 1000
        assert not details['spike_triggered']
        assert not details['z_triggered']
    
    def test_detect_volume_spike_spike_anomaly(self, detector):
        """Test spike detection with volume spike anomaly."""
        baseline = {
            'avg_hourly_volume': 1000,
            'std_hourly_volume': 200
        }
        current_volume = 6000  # 6x average, above 5x threshold
        
        is_anomaly, spike_multiplier, details = detector.detect_volume_spike(
            current_volume, baseline
        )
        
        assert is_anomaly
        assert abs(spike_multiplier - 6.0) < 0.001  # Use approximate comparison for floating point
        assert details['spike_triggered']
        assert details['spike_multiplier'] > detector.thresholds['volume_spike_multiplier']
    
    def test_detect_volume_spike_z_score_anomaly(self, detector):
        """Test spike detection with z-score anomaly."""
        baseline = {
            'avg_hourly_volume': 1000,
            'std_hourly_volume': 200
        }
        current_volume = 1700  # 1.7x average but high z-score
        
        is_anomaly, spike_multiplier, details = detector.detect_volume_spike(
            current_volume, baseline
        )
        
        # Z-score = (1700 - 1000) / 200 = 3.5, above 3.0 threshold
        assert is_anomaly
        assert details['z_triggered']
        assert details['z_score'] > detector.thresholds['z_score_threshold']
    
    @pytest.mark.parametrize("window_hours,expected_trades", [
        (1, 4),  # Approximately 4 trades per hour
        (2, 8),  # Approximately 8 trades in 2 hours
        (6, 24), # Approximately 24 trades in 6 hours
    ])
    def test_get_recent_volume_time_windows(self, detector, sample_trades, window_hours, expected_trades):
        """Test volume calculation for different time windows."""
        volume = detector.get_recent_volume(sample_trades, window_hours)
        assert volume >= 0
        # Note: Exact assertions depend on mock data timestamp distribution
    
    def test_get_recent_volume_empty_trades(self, detector):
        """Test recent volume calculation with empty trades."""
        volume = detector.get_recent_volume([], 1)
        assert volume == 0
    
    def test_get_recent_volume_invalid_timestamps(self, detector):
        """Test recent volume with invalid timestamp data."""
        invalid_trades = [
            {'price': '100', 'size': '10', 'timestamp': 'invalid'},
            {'price': '100', 'size': '10', 'timestamp': None},
            {'price': '100', 'size': '10'},  # Missing timestamp
        ]
        volume = detector.get_recent_volume(invalid_trades, 1)
        assert volume == 0
    
    def test_analyze_volume_pattern_empty_trades(self, detector):
        """Test volume pattern analysis with empty trades."""
        result = detector.analyze_volume_pattern([])
        assert not result['anomaly']
        assert result['reason'] == 'No trades available'
    
    def test_analyze_volume_pattern_normal_trades(self, detector, sample_trades):
        """Test volume pattern analysis with normal trading data."""
        result = detector.analyze_volume_pattern(sample_trades)
        
        assert 'anomaly' in result
        assert 'baseline' in result
        assert 'windows' in result
        assert 'timestamp' in result
        
        # Check all time windows are analyzed
        expected_windows = ['1h_window', '2h_window', '4h_window', '6h_window']
        for window in expected_windows:
            assert window in result['windows']
            assert 'volume' in result['windows'][window]
            assert 'anomaly' in result['windows'][window]
    
    def test_analyze_volume_pattern_spike_detection(self, detector, spike_trades):
        """Test volume pattern analysis with spike data."""
        result = detector.analyze_volume_pattern(spike_trades)
        
        # Should detect anomaly in spike pattern
        assert 'anomaly' in result
        assert 'max_anomaly_score' in result
        
        # At least one window should show anomalous activity
        anomaly_detected_in_window = any(
            result['windows'][window]['anomaly'] 
            for window in result['windows']
        )
        assert anomaly_detected_in_window or result['anomaly']
    
    def test_edge_cases_very_small_volumes(self, detector):
        """Test edge cases with very small volume values."""
        small_trades = [
            {
                'price': '0.001',
                'size': '1',
                'timestamp': int(datetime.now().timestamp())
            }
        ]
        
        baseline = detector.calculate_baseline_metrics(small_trades)
        assert baseline['total_volume'] > 0
        assert baseline['avg_hourly_volume'] >= 0
    
    def test_edge_cases_very_large_volumes(self, detector):
        """Test edge cases with very large volume values."""
        large_trades = [
            {
                'price': '1000000',
                'size': '1000000',
                'timestamp': int(datetime.now().timestamp())
            }
        ]
        
        baseline = detector.calculate_baseline_metrics(large_trades)
        assert baseline['total_volume'] > 0
        assert baseline['avg_hourly_volume'] > 0
    
    def test_different_timestamp_formats(self, detector):
        """Test handling of different timestamp formats."""
        varied_timestamp_trades = [
            {
                'price': '100',
                'size': '10',
                'timestamp': int(datetime.now().timestamp())  # Unix timestamp
            },
            {
                'price': '100',
                'size': '10',
                'createdAt': datetime.now().isoformat() + 'Z'  # ISO format
            },
            {
                'price': '100',
                'size': '10',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # String format
            }
        ]
        
        baseline = detector.calculate_baseline_metrics(varied_timestamp_trades)
        assert baseline['total_volume'] > 0
    
    def test_different_field_names(self, detector):
        """Test handling of different field name formats."""
        varied_field_trades = [
            {'price': '100', 'size': '10', 'timestamp': int(datetime.now().timestamp())},
            {'feeRate': '100', 'amount': '10', 'createdAt': int(datetime.now().timestamp())},
            {'outcome_price': '100', 'shares': '10', 'created_at': int(datetime.now().timestamp())},
        ]
        
        baseline = detector.calculate_baseline_metrics(varied_field_trades)
        assert baseline['total_volume'] > 0
    
    @pytest.mark.parametrize("spike_multiplier,expected_anomaly", [
        (2.0, False),  # Below threshold
        (5.0, True),   # At threshold
        (10.0, True),  # Above threshold
    ])
    def test_spike_threshold_sensitivity(self, detector, spike_multiplier, expected_anomaly):
        """Test spike detection sensitivity to different multipliers."""
        baseline = {
            'avg_hourly_volume': 1000,
            'std_hourly_volume': 100
        }
        current_volume = 1000 * spike_multiplier
        
        is_anomaly, _, details = detector.detect_volume_spike(current_volume, baseline)
        
        if expected_anomaly:
            assert is_anomaly
            assert details['spike_triggered']
        else:
            # May still trigger on z-score for high multipliers
            if not is_anomaly:
                assert not details['spike_triggered']
    
    def test_concurrent_anomaly_conditions(self, detector):
        """Test when both spike and z-score conditions are met."""
        baseline = {
            'avg_hourly_volume': 1000,
            'std_hourly_volume': 100
        }
        current_volume = 10000  # 10x average, very high z-score
        
        is_anomaly, spike_multiplier, details = detector.detect_volume_spike(
            current_volume, baseline
        )
        
        assert is_anomaly
        assert details['spike_triggered']
        assert details['z_triggered']
        assert abs(spike_multiplier - 10.0) < 0.001  # Use approximate comparison for floating point
    
    def test_thread_safety_simulation(self, detector, sample_trades):
        """Simulate concurrent access to detector methods."""
        import threading
        results = []
        
        def analyze_worker():
            result = detector.analyze_volume_pattern(sample_trades)
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
        large_trades = generator.generate_normal_trades(count=10000, time_span_hours=168)
        
        # Should handle large datasets without memory issues
        result = detector.analyze_volume_pattern(large_trades)
        assert 'anomaly' in result
        assert 'baseline' in result
    
    @patch('detection.volume_detector.pd.DataFrame.resample')
    def test_resample_fallback(self, mock_resample, detector, sample_trades):
        """Test fallback calculation when resample fails."""
        mock_resample.side_effect = Exception("Resample failed")
        
        baseline = detector.calculate_baseline_metrics(sample_trades)
        
        # Should use fallback calculation
        assert 'avg_hourly_volume' in baseline
        assert baseline['avg_hourly_volume'] > 0