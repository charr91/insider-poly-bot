"""
Test utilities for creating detector instances
"""

def create_test_config():
    """Create a complete test configuration for all detectors"""
    return {
        'detection': {
            'volume_thresholds': {
                'volume_spike_multiplier': 4.0,
                'z_score_threshold': 3.0
            },
            'whale_thresholds': {
                'whale_threshold_usd': 2000,
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
            },
            'fresh_wallet_thresholds': {
                'min_bet_size_usd': 2000,
                'api_lookback_limit': 100,
                'max_previous_trades': 0
            }
        }
    }

def setup_detector_for_testing(detector):
    """Setup a detector instance for testing (no longer needed - kept for compatibility)"""
    return detector