"""
Shared test fixtures for detector tests.
Provides common fixtures to eliminate duplication across test files.
"""

import pytest
from tests.fixtures.data_generators import MockDataGenerator
from detection.whale_detector import WhaleDetector
from detection.volume_detector import VolumeDetector
from detection.price_detector import PriceDetector
from detection.coordination_detector import CoordinationDetector


class DetectorFactory:
    """Factory for creating detector instances with standardized configurations."""
    
    @staticmethod
    def create_whale_detector(
        whale_threshold_usd: int = 15000,
        coordination_threshold: float = 0.8,
        min_whales_for_coordination: int = 3
    ) -> WhaleDetector:
        """Create WhaleDetector with specified thresholds."""
        config = {
            'detection': {
                'whale_thresholds': {
                    'whale_threshold_usd': whale_threshold_usd,
                    'coordination_threshold': coordination_threshold,
                    'min_whales_for_coordination': min_whales_for_coordination
                }
            }
        }
        return WhaleDetector(config)
    
    @staticmethod
    def create_volume_detector(
        volume_spike_multiplier: float = 4.0,
        z_score_threshold: float = 3.0
    ) -> VolumeDetector:
        """Create VolumeDetector with specified thresholds."""
        config = {
            'detection': {
                'volume_thresholds': {
                    'volume_spike_multiplier': volume_spike_multiplier,
                    'z_score_threshold': z_score_threshold
                }
            }
        }
        return VolumeDetector(config)
    
    @staticmethod
    def create_price_detector(
        rapid_movement_pct: int = 15,
        price_movement_std: float = 2.5,
        volatility_spike_multiplier: float = 3.0,
        momentum_threshold: float = 0.8
    ) -> PriceDetector:
        """Create PriceDetector with specified thresholds."""
        config = {
            'detection': {
                'price_thresholds': {
                    'rapid_movement_pct': rapid_movement_pct,
                    'price_movement_std': price_movement_std,
                    'volatility_spike_multiplier': volatility_spike_multiplier,
                    'momentum_threshold': momentum_threshold
                }
            }
        }
        return PriceDetector(config)
    
    @staticmethod
    def create_coordination_detector(
        coordination_threshold: float = 0.7,
        min_coordinated_wallets: int = 3,
        timing_window_seconds: int = 300,
        coordination_strength: float = 0.8
    ) -> CoordinationDetector:
        """Create CoordinationDetector with specified thresholds."""
        config = {
            'detection': {
                'coordination_thresholds': {
                    'coordination_threshold': coordination_threshold,
                    'min_coordinated_wallets': min_coordinated_wallets,
                    'timing_window_seconds': timing_window_seconds,
                    'coordination_strength': coordination_strength
                }
            }
        }
        return CoordinationDetector(config)


class TradeDataFactory:
    """Factory for creating standardized test trade data."""
    
    def __init__(self):
        self.generator = MockDataGenerator()
    
    def create_normal_trades(self, count: int = 50, time_span_hours: int = 12):
        """Generate normal trade data without anomalies."""
        return self.generator.generate_normal_trades(count=count, time_span_hours=time_span_hours)
    
    def create_whale_trades(self, accumulation_count: int = 8, time_span_hours: int = 6):
        """Generate whale trading data."""
        return self.generator.generate_whale_accumulation_pattern(
            accumulation_count=accumulation_count,
            time_span_hours=time_span_hours
        )
    
    def create_coordinated_trades(self, wallet_count: int = 5, coordination_window: int = 300):
        """Generate coordinated whale trading data."""
        return self.generator.generate_coordinated_trading_pattern(
            wallet_count=wallet_count,
            coordination_window=coordination_window
        )
    
    def create_volume_spike_trades(self, spike_multiplier: float = 8.0):
        """Generate trades with volume spike."""
        return self.generator.generate_volume_spike_pattern(spike_multiplier=spike_multiplier)
    
    def create_pump_dump_trades(self):
        """Generate pump and dump pattern trades."""
        return self.generator.generate_pump_and_dump_pattern()


# Global fixtures that can be used across all test files
@pytest.fixture(scope="session")
def detector_factory():
    """Provides DetectorFactory instance for creating test detectors."""
    return DetectorFactory()


@pytest.fixture(scope="session") 
def trade_data_factory():
    """Provides TradeDataFactory instance for creating test data."""
    return TradeDataFactory()


# Common detector fixtures with standard configurations
@pytest.fixture
def standard_whale_detector(detector_factory):
    """Standard WhaleDetector configuration for most tests."""
    return detector_factory.create_whale_detector()


@pytest.fixture
def standard_volume_detector(detector_factory):
    """Standard VolumeDetector configuration for most tests."""
    return detector_factory.create_volume_detector()


@pytest.fixture
def standard_price_detector(detector_factory):
    """Standard PriceDetector configuration for most tests."""
    return detector_factory.create_price_detector()


@pytest.fixture
def standard_coordination_detector(detector_factory):
    """Standard CoordinationDetector configuration for most tests."""
    return detector_factory.create_coordination_detector()


# Common trade data fixtures
@pytest.fixture
def normal_trades(trade_data_factory):
    """Normal trade data without anomalies."""
    return trade_data_factory.create_normal_trades()


@pytest.fixture
def whale_trades(trade_data_factory):
    """Whale trading data."""
    return trade_data_factory.create_whale_trades()


@pytest.fixture
def coordinated_trades(trade_data_factory):
    """Coordinated whale trading data."""
    return trade_data_factory.create_coordinated_trades()


@pytest.fixture
def volume_spike_trades(trade_data_factory):
    """Trades with volume spike pattern."""
    return trade_data_factory.create_volume_spike_trades()


@pytest.fixture
def pump_dump_trades(trade_data_factory):
    """Pump and dump pattern trades."""
    return trade_data_factory.create_pump_dump_trades()