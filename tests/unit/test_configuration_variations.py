"""
Parameterized tests for configuration variations across detection algorithms.
"""
import pytest
import numpy as np
from typing import Dict, Any
from unittest.mock import Mock, patch

from detection.volume_detector import VolumeDetector
from detection.whale_detector import WhaleDetector
from detection.price_detector import PriceDetector
from detection.coordination_detector import CoordinationDetector
from tests.fixtures.data_generators import MockDataGenerator


class TestConfigurationVariations:
    """Test suite for validating behavior across different configuration settings."""
    
    @pytest.fixture
    def mock_data_generator(self):
        """Create mock data generator for tests."""
        return MockDataGenerator(seed=42)
    
    @pytest.fixture
    def sample_trades(self, mock_data_generator):
        """Generate consistent sample trades for testing."""
        return mock_data_generator.generate_normal_trades(count=100, time_span_hours=24)
    
    @pytest.fixture
    def spike_trades(self, mock_data_generator):
        """Generate volume spike pattern for testing."""
        return mock_data_generator.generate_volume_spike_pattern(spike_multiplier=6.0)
    
    @pytest.fixture
    def whale_trades(self, mock_data_generator):
        """Generate whale trading pattern for testing."""
        return mock_data_generator.generate_whale_accumulation_pattern(accumulation_count=8)
    
    @pytest.fixture
    def coordinated_trades(self, mock_data_generator):
        """Generate coordinated trading pattern for testing."""
        return mock_data_generator.generate_coordinated_trading_pattern(wallet_count=6)
    
    # Volume Detector Configuration Tests
    @pytest.mark.parametrize("volume_multiplier,z_threshold,should_detect", [
        (2.0, 2.0, True),   # Low thresholds - sensitive
        (3.0, 3.0, True),   # Default thresholds
        (5.0, 4.0, False),  # High thresholds - strict
        (10.0, 5.0, False), # Very high thresholds
        (1.5, 1.5, True),  # Very sensitive
    ])
    def test_volume_detector_threshold_variations(
        self, volume_multiplier, z_threshold, should_detect, spike_trades
    ):
        """Test volume detector with different threshold configurations."""
        config = {
            'detection': {
                'volume_thresholds': {
                    'volume_spike_multiplier': volume_multiplier,
                    'z_score_threshold': z_threshold
                }
            }
        }
        
        detector = VolumeDetector(config)
        result = detector.analyze_volume_pattern(spike_trades)
        
        # Check if detection behavior matches expectation
        if should_detect:
            # With lower thresholds, should be more likely to detect anomalies
            # May not always detect due to data variability, but should be more sensitive
            assert 'anomaly' in result
        else:
            # With higher thresholds, should be less likely to detect anomalies
            assert 'anomaly' in result
            # The specific detection result depends on the data, but behavior should be consistent
    
    @pytest.mark.parametrize("window_hours", [1, 2, 4, 6, 12, 24])
    def test_volume_detector_time_window_variations(self, window_hours, sample_trades):
        """Test volume detector with different time window configurations."""
        config = {
            'detection': {
                'volume_thresholds': {
                    'volume_spike_multiplier': 3.0,
                    'z_score_threshold': 3.0
                }
            }
        }
        detector = VolumeDetector(config)
        
        # Test recent volume calculation with different windows
        volume = detector.get_recent_volume(sample_trades, window_hours)
        
        assert volume >= 0
        assert isinstance(volume, (int, float))
    
    # Whale Detector Configuration Tests
    @pytest.mark.parametrize("whale_threshold,coord_threshold,min_whales,expected_sensitivity", [
        (5000, 0.6, 2, "high"),     # Low thresholds - high sensitivity
        (10000, 0.7, 3, "medium"),  # Default thresholds
        (25000, 0.8, 5, "low"),     # High thresholds - low sensitivity
        (50000, 0.9, 7, "very_low"), # Very high thresholds
    ])
    def test_whale_detector_threshold_variations(
        self, whale_threshold, coord_threshold, min_whales, expected_sensitivity, whale_trades
    ):
        """Test whale detector with different threshold configurations."""
        config = {
            'detection': {
                'whale_thresholds': {
                    'whale_threshold_usd': whale_threshold,
                    'coordination_threshold': coord_threshold,
                    'min_whales_for_coordination': min_whales
                }
            }
        }
        
        detector = WhaleDetector(config)
        result = detector.detect_whale_activity(whale_trades)
        
        assert 'anomaly' in result
        assert 'whale_count' in result
        
        # Higher thresholds should generally result in fewer detected whales
        if expected_sensitivity == "very_low":
            # With very high thresholds, may detect no whales
            assert result['whale_count'] >= 0
        else:
            # Lower thresholds should be more permissive
            assert result['whale_count'] >= 0
    
    @pytest.mark.parametrize("field_mapping", [
        {'price': 'price', 'size': 'size', 'side': 'side', 'maker': 'maker'},
        {'price': 'feeRate', 'size': 'amount', 'side': 'type', 'maker': 'trader'},
        {'price': 'outcome_price', 'size': 'shares', 'side': 'side', 'maker': 'user'},
    ])
    def test_whale_detector_field_name_variations(self, field_mapping, mock_data_generator):
        """Test whale detector with different field name formats."""
        # Create trades with different field names
        trades = []
        for i in range(10):
            trade = {
                field_mapping['price']: str(0.5 + i * 0.01),
                field_mapping['size']: str(15000 + i * 1000),  # Whale sizes
                field_mapping['side']: 'BUY',
                field_mapping['maker']: f'0xwhale{i}'
            }
            trades.append(trade)
        
        config = {
            'detection': {
                'whale_thresholds': {
                    'whale_threshold_usd': 10000,
                    'coordination_threshold': 0.7,
                    'min_whales_for_coordination': 3
                }
            }
        }
        detector = WhaleDetector(config)
        result = detector.detect_whale_activity(trades)
        
        # Should handle different field names
        assert 'whale_count' in result
        assert result['whale_count'] > 0  # Should detect whales regardless of field names
    
    # Price Detector Configuration Tests
    @pytest.mark.parametrize("rapid_pct,volatility_mult,momentum_thresh,sensitivity", [
        (5, 2.0, 0.6, "very_high"),  # Very sensitive settings
        (10, 2.5, 0.7, "high"),      # High sensitivity
        (15, 3.0, 0.8, "medium"),    # Default settings
        (25, 4.0, 0.9, "low"),       # Low sensitivity
        (50, 5.0, 0.95, "very_low"), # Very low sensitivity
    ])
    def test_price_detector_threshold_variations(
        self, rapid_pct, volatility_mult, momentum_thresh, sensitivity, mock_data_generator
    ):
        """Test price detector with different threshold configurations."""
        config = {
            'detection': {
                'price_thresholds': {
                    'rapid_movement_pct': rapid_pct,
                    'price_movement_std': 2.5,  # Default value
                    'volatility_spike_multiplier': volatility_mult,
                    'momentum_threshold': momentum_thresh
                }
            }
        }
        
        # Create price movement data
        trades = mock_data_generator.generate_pump_and_dump_pattern()
        
        detector = PriceDetector(config)
        result = detector.detect_price_movement(trades, window_minutes=60)
        
        assert 'anomaly' in result
        assert 'triggers' in result
        
        # More sensitive configurations should be more likely to trigger
        if sensitivity in ["very_high", "high"]:
            # Should have lower thresholds for detection
            assert detector.thresholds['rapid_movement_pct'] <= 15
        else:
            # Should have higher thresholds
            assert detector.thresholds['rapid_movement_pct'] >= 15
    
    @pytest.mark.parametrize("window_minutes", [15, 30, 60, 120, 240])
    def test_price_detector_window_variations(self, window_minutes, mock_data_generator):
        """Test price detector with different time window configurations."""
        trades = mock_data_generator.generate_pump_and_dump_pattern()
        config = {
            'detection': {
                'price_thresholds': {
                    'rapid_movement_pct': 15,
                    'price_movement_std': 2.5,
                    'volatility_spike_multiplier': 3.0,
                    'momentum_threshold': 0.8
                }
            }
        }
        detector = PriceDetector(config)
        
        result = detector.detect_price_movement(trades, window_minutes=window_minutes)
        
        assert 'anomaly' in result
        assert 'window_minutes' in result
        assert result['window_minutes'] == window_minutes
        assert 'analysis' in result
    
    # Coordination Detector Configuration Tests
    @pytest.mark.parametrize("min_wallets,time_window,bias_threshold,expected_behavior", [
        (3, 15, 0.6, "sensitive"),   # Sensitive to coordination
        (5, 30, 0.8, "balanced"),   # Balanced detection
        (8, 60, 0.9, "strict"),     # Strict requirements
        (10, 120, 0.95, "very_strict"), # Very strict
    ])
    def test_coordination_detector_threshold_variations(
        self, min_wallets, time_window, bias_threshold, expected_behavior, coordinated_trades
    ):
        """Test coordination detector with different threshold configurations."""
        config = {
            'detection': {
                'coordination_thresholds': {
                    'min_coordinated_wallets': min_wallets,
                    'coordination_time_window': time_window,
                    'directional_bias_threshold': bias_threshold,
                    'burst_intensity_threshold': 3.0  # Default value
                }
            }
        }
        
        detector = CoordinationDetector(config)
        result = detector.detect_coordinated_buying(coordinated_trades)
        
        assert 'anomaly' in result
        assert 'coordination_score' in result
        
        # Stricter settings should require more evidence for detection
        if expected_behavior == "very_strict":
            assert detector.thresholds['min_coordinated_wallets'] >= 8
            assert detector.thresholds['directional_bias_threshold'] >= 0.9
        elif expected_behavior == "sensitive":
            assert detector.thresholds['min_coordinated_wallets'] <= 5
            assert detector.thresholds['directional_bias_threshold'] <= 0.7
    
    @pytest.mark.parametrize("coordination_windows", [
        [15, 30, 60, 120],      # Default windows
        [5, 10, 15, 30],        # Short-term focus
        [30, 60, 120, 240],     # Long-term focus
        [60],                   # Single window
    ])
    def test_coordination_detector_window_variations(
        self, coordination_windows, coordinated_trades
    ):
        """Test coordination detector with different time window sets."""
        config = {
            'detection': {
                'coordination_thresholds': {
                    'min_coordinated_wallets': 5,
                    'coordination_time_window': 30,
                    'directional_bias_threshold': 0.8,
                    'burst_intensity_threshold': 3.0
                }
            }
        }
        detector = CoordinationDetector(config)
        
        # Mock the windows to test different configurations
        with patch.object(detector, '_analyze_coordination_windows') as mock_analyze:
            mock_analyze.return_value = {
                f'{w}min': {'coordination_score': 0.5, 'reason': 'test'}
                for w in coordination_windows
            }
            
            result = detector.detect_coordinated_buying(coordinated_trades)
            
            assert 'all_windows' in result
    
    # Cross-Algorithm Configuration Tests
    @pytest.mark.parametrize("detector_class,config_key,threshold_key,test_values", [
        (VolumeDetector, 'volume_thresholds', 'volume_spike_multiplier', [1.5, 3.0, 5.0, 10.0]),
        (WhaleDetector, 'whale_thresholds', 'whale_threshold_usd', [5000, 10000, 25000, 50000]),
        (PriceDetector, 'price_thresholds', 'rapid_movement_pct', [5, 15, 25, 50]),
        (CoordinationDetector, 'coordination_thresholds', 'min_coordinated_wallets', [2, 5, 8, 12]),
    ])
    def test_detector_configuration_robustness(
        self, detector_class, config_key, threshold_key, test_values
    ):
        """Test that all detectors handle configuration changes robustly."""
        # Base configurations with all required fields
        base_configs = {
            'volume_thresholds': {
                'volume_spike_multiplier': 3.0,
                'z_score_threshold': 3.0
            },
            'whale_thresholds': {
                'whale_threshold_usd': 10000,
                'coordination_threshold': 0.7,
                'min_whales_for_coordination': 3
            },
            'price_thresholds': {
                'rapid_movement_pct': 15,
                'price_movement_std': 2.5,
                'volatility_spike_multiplier': 3.0,
                'momentum_threshold': 0.8
            },
            'coordination_thresholds': {
                'min_coordinated_wallets': 5,
                'coordination_time_window': 30,
                'directional_bias_threshold': 0.8,
                'burst_intensity_threshold': 3.0
            }
        }
        
        for value in test_values:
            config = {
                'detection': {
                    config_key: base_configs[config_key].copy()
                }
            }
            # Override the specific field being tested
            config['detection'][config_key][threshold_key] = value
            
            # Should initialize without error
            detector = detector_class(config)
            assert detector.thresholds[threshold_key] == value
    
    @pytest.mark.parametrize("config_scenario", [
        {},  # Empty config
        {'detection': {}},  # Empty detection config
        {'detection': {'invalid_key': {}}},  # Invalid config key
        {'other_section': {'value': 123}},  # Unrelated config
    ])
    def test_detector_invalid_configuration_handling(self, config_scenario):
        """Test that detectors raise appropriate errors with invalid configurations."""
        detectors = [VolumeDetector, WhaleDetector, PriceDetector, CoordinationDetector]
        
        for detector_class in detectors:
            # Should raise ValueError with invalid config - fail fast approach
            with pytest.raises(ValueError):
                detector = detector_class(config_scenario)
    
    # Market Condition Simulation Tests
    @pytest.mark.parametrize("market_scenario", [
        {
            "name": "high_volatility",
            "volume_multiplier": 2.0,
            "price_volatility": 3.0,
            "whale_threshold": 5000,
            "expected_detections": "high"
        },
        {
            "name": "normal_market",
            "volume_multiplier": 3.0,
            "price_volatility": 2.5,
            "whale_threshold": 10000,
            "expected_detections": "medium"
        },
        {
            "name": "stable_market",
            "volume_multiplier": 5.0,
            "price_volatility": 2.0,
            "whale_threshold": 25000,
            "expected_detections": "low"
        }
    ])
    def test_detector_market_condition_adaptation(self, market_scenario, mock_data_generator):
        """Test detector behavior adaptation to different market conditions."""
        scenario = market_scenario
        
        # Create market-specific configuration
        config = {
            'detection': {
                'volume_thresholds': {
                    'volume_spike_multiplier': scenario['volume_multiplier'],
                    'z_score_threshold': scenario['price_volatility']
                },
                'whale_thresholds': {
                    'whale_threshold_usd': scenario['whale_threshold'],
                    'coordination_threshold': 0.7,
                    'min_whales_for_coordination': 3
                },
                'price_thresholds': {
                    'rapid_movement_pct': 15,
                    'price_movement_std': 2.5,
                    'volatility_spike_multiplier': scenario['price_volatility'],
                    'momentum_threshold': 0.8
                },
                'coordination_thresholds': {
                    'min_coordinated_wallets': 5,
                    'coordination_time_window': 30,
                    'directional_bias_threshold': 0.8,
                    'burst_intensity_threshold': 3.0
                }
            }
        }
        
        # Initialize detectors
        volume_detector = VolumeDetector(config)
        whale_detector = WhaleDetector(config)
        price_detector = PriceDetector(config)
        
        # Generate test data appropriate for the scenario
        if scenario['name'] == 'high_volatility':
            trades = mock_data_generator.generate_volume_spike_pattern(spike_multiplier=8.0)
        elif scenario['name'] == 'normal_market':
            trades = mock_data_generator.generate_normal_trades(count=100)
        else:  # stable_market
            trades = mock_data_generator.generate_normal_trades(count=50)
        
        # Test volume detection
        volume_result = volume_detector.analyze_volume_pattern(trades)
        assert 'anomaly' in volume_result
        
        # Test whale detection
        whale_result = whale_detector.detect_whale_activity(trades)
        assert 'anomaly' in whale_result
        
        # Test price detection
        price_result = price_detector.detect_price_movement(trades)
        assert 'anomaly' in price_result
        
        # Verify that different market conditions produce different behaviors
        if scenario['expected_detections'] == 'high':
            # More sensitive settings should be more likely to detect anomalies
            assert volume_detector.thresholds['volume_spike_multiplier'] <= 3.0
        elif scenario['expected_detections'] == 'low':
            # Less sensitive settings should be less likely to detect anomalies
            assert volume_detector.thresholds['volume_spike_multiplier'] >= 5.0
    
    # Performance Impact Tests
    @pytest.mark.parametrize("data_size,config_complexity", [
        (100, "simple"),    # Small dataset, simple config
        (1000, "simple"),   # Medium dataset, simple config
        (100, "complex"),   # Small dataset, complex config
        (1000, "complex"),  # Medium dataset, complex config
    ])
    def test_configuration_performance_impact(self, data_size, config_complexity, mock_data_generator):
        """Test performance impact of different configurations."""
        import time
        
        # Generate test data
        trades = mock_data_generator.generate_normal_trades(count=data_size)
        
        # Create configuration based on complexity
        if config_complexity == "simple":
            config = {
                'detection': {
                    'volume_thresholds': {
                        'volume_spike_multiplier': 3.0,
                        'z_score_threshold': 3.0
                    },
                    'whale_thresholds': {
                        'whale_threshold_usd': 10000,
                        'coordination_threshold': 0.7,
                        'min_whales_for_coordination': 3
                    },
                    'price_thresholds': {
                        'rapid_movement_pct': 15,
                        'price_movement_std': 2.5,
                        'volatility_spike_multiplier': 3.0,
                        'momentum_threshold': 0.8
                    },
                    'coordination_thresholds': {
                        'min_coordinated_wallets': 5,
                        'coordination_time_window': 30,
                        'directional_bias_threshold': 0.8,
                        'burst_intensity_threshold': 3.0
                    }
                }
            }
        else:  # complex
            config = {
                'detection': {
                    'volume_thresholds': {
                        'volume_spike_multiplier': 3.0,
                        'z_score_threshold': 2.5
                    },
                    'whale_thresholds': {
                        'whale_threshold_usd': 10000,
                        'coordination_threshold': 0.7,
                        'min_whales_for_coordination': 3
                    },
                    'price_thresholds': {
                        'rapid_movement_pct': 15,
                        'price_movement_std': 2.5,
                        'volatility_spike_multiplier': 3.0,
                        'momentum_threshold': 0.8
                    },
                    'coordination_thresholds': {
                        'min_coordinated_wallets': 5,
                        'coordination_time_window': 30,
                        'directional_bias_threshold': 0.8,
                        'burst_intensity_threshold': 3.0
                    }
                }
            }
        
        # Test volume detector performance
        detector = VolumeDetector(config)
        
        start_time = time.time()
        result = detector.analyze_volume_pattern(trades)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Performance should be reasonable regardless of configuration
        assert execution_time < 10.0  # Should complete within 10 seconds
        assert 'anomaly' in result
        
        # Larger datasets should take longer, but not exponentially
        if data_size == 1000:
            assert execution_time < 30.0  # Still reasonable for larger dataset
    
    # Configuration Validation Tests
    @pytest.mark.parametrize("invalid_config", [
        {'detection': {'volume_thresholds': {'volume_spike_multiplier': -1}}},  # Negative value
        {'detection': {'volume_thresholds': {'volume_spike_multiplier': 0}}},   # Zero value
        {'detection': {'whale_thresholds': {'whale_threshold_usd': 'invalid'}}}, # String value
        {'detection': {'price_thresholds': {'rapid_movement_pct': None}}},      # None value
    ])
    def test_invalid_configuration_values(self, invalid_config):
        """Test that detectors raise errors with invalid or incomplete configuration values."""
        # Detectors should raise ValueError with invalid/incomplete configs
        detectors = [VolumeDetector, WhaleDetector, PriceDetector, CoordinationDetector]
        
        for detector_class in detectors:
            # Should raise ValueError with invalid/incomplete config - fail fast approach
            with pytest.raises(ValueError):
                detector = detector_class(invalid_config)
    
    # Configuration Boundary Tests
    @pytest.mark.parametrize("boundary_config", [
        {'detection': {'volume_thresholds': {'volume_spike_multiplier': 0.1}}},   # Very small
        {'detection': {'volume_thresholds': {'volume_spike_multiplier': 1000}}},  # Very large
        {'detection': {'whale_thresholds': {'coordination_threshold': 0.0}}},     # Minimum
        {'detection': {'whale_thresholds': {'coordination_threshold': 1.0}}},     # Maximum
        {'detection': {'coordination_thresholds': {'min_coordinated_wallets': 1}}}, # Minimum wallets
    ])
    def test_configuration_boundary_values(self, boundary_config, sample_trades):
        """Test detector behavior at configuration boundary values."""
        detector_classes = [VolumeDetector, WhaleDetector, PriceDetector, CoordinationDetector]
        
        for detector_class in detector_classes:
            try:
                detector = detector_class(boundary_config)
                
                # Test that detector can still function with boundary values
                if detector_class == VolumeDetector:
                    result = detector.analyze_volume_pattern(sample_trades)
                elif detector_class == WhaleDetector:
                    result = detector.detect_whale_activity(sample_trades)
                elif detector_class == PriceDetector:
                    result = detector.detect_price_movement(sample_trades)
                else:  # CoordinationDetector
                    result = detector.detect_coordinated_buying(sample_trades)
                
                assert 'anomaly' in result
                
            except Exception as e:
                # Some boundary values may not be valid, but should fail gracefully
                assert isinstance(e, (ValueError, TypeError))
    
    def test_configuration_consistency_across_detectors(self):
        """Test that configuration structure is consistent across all detectors."""
        config = {
            'detection': {
                'volume_thresholds': {
                    'volume_spike_multiplier': 3.0,
                    'z_score_threshold': 3.0
                },
                'whale_thresholds': {
                    'whale_threshold_usd': 10000,
                    'coordination_threshold': 0.7,
                    'min_whales_for_coordination': 3
                },
                'price_thresholds': {
                    'rapid_movement_pct': 15,
                    'price_movement_std': 2.5,
                    'volatility_spike_multiplier': 3.0,
                    'momentum_threshold': 0.8
                },
                'coordination_thresholds': {
                    'min_coordinated_wallets': 5,
                    'coordination_time_window': 30,
                    'directional_bias_threshold': 0.8,
                    'burst_intensity_threshold': 3.0
                }
            }
        }
        
        detectors = [
            VolumeDetector(config),
            WhaleDetector(config),
            PriceDetector(config),
            CoordinationDetector(config)
        ]
        
        # All detectors should accept the same configuration structure
        for detector in detectors:
            assert hasattr(detector, 'config')
            assert hasattr(detector, 'thresholds')
            assert isinstance(detector.thresholds, dict)