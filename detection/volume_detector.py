"""
Volume Spike Detection Module
Identifies unusual volume patterns that may indicate insider activity
"""

import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime, timezone, timedelta
import logging
from .base_detector import DetectorBase
from .utils import TradeNormalizer, ThresholdValidator, create_consistent_early_return

logger = logging.getLogger(__name__)

class VolumeDetector(DetectorBase):
    """Detects volume anomalies in trading data"""
    
    def __init__(self, config: Dict):
        # Initialize base detector
        super().__init__(config, 'volume')
    
    def _load_detector_config(self):
        """Load volume-specific configuration from config dict"""
        # Validate and load volume thresholds from config (no hardcoded fallbacks)
        self.thresholds = self._validate_config_section(
            'volume_thresholds', 
            ['volume_spike_multiplier', 'z_score_threshold']
        )
    
    def calculate_baseline_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate enhanced baseline trading metrics with time-aware analysis"""
        if not trades:
            return {}
        
        # Normalize trade data using utility
        normalized_trades = TradeNormalizer.normalize_trades(trades)
        
        if not normalized_trades:
            return {}
        
        df = pd.DataFrame(normalized_trades)
        # volume_usd already calculated in normalization
        
        # Calculate hourly metrics
        df.set_index('timestamp', inplace=True)
        
        # Calculate both overall and time-aware baselines
        try:
            hourly = df.resample('1h').agg({
                'volume_usd': 'sum',
                'size': 'count'  # Number of trades
            })
            
            # Overall baseline (existing logic)
            overall_baseline = {
                'avg_hourly_volume': hourly['volume_usd'].mean(),
                'std_hourly_volume': hourly['volume_usd'].std(),
                'avg_trades_per_hour': hourly['size'].mean(),
                'total_volume': df['volume_usd'].sum()
            }
            
            # Add time-aware baselines
            time_aware_baselines = self._calculate_time_aware_baselines(df, hourly)
            overall_baseline.update(time_aware_baselines)
            
            return overall_baseline
            
        except Exception as e:
            # Fallback calculation
            hours_span = max(24, len(df) / 100)  # Estimate hours based on data
            return {
                'avg_hourly_volume': df['volume_usd'].sum() / hours_span,
                'std_hourly_volume': df['volume_usd'].std(),
                'avg_trades_per_hour': len(df) / hours_span,
                'total_volume': df['volume_usd'].sum()
            }
    
    def _calculate_time_aware_baselines(self, df: pd.DataFrame, hourly: pd.DataFrame) -> Dict:
        """Calculate time-aware baselines for hour-of-day and day-of-week patterns"""
        time_baselines = {}
        
        try:
            # Hour-of-day baselines (0-23) - optimized with single copy and direct iteration
            hourly_enhanced = hourly.copy()  # Single copy for all operations
            hourly_enhanced['hour'] = hourly_enhanced.index.hour
            hour_grouped = hourly_enhanced.groupby('hour')['volume_usd'].agg(['mean', 'std'])

            # Direct iteration instead of to_dict + comprehension
            time_baselines['hourly_patterns'] = {
                str(hour): {
                    'avg_volume': row['mean'],
                    'std_volume': row['std'] if pd.notna(row['std']) else 0
                }
                for hour, row in hour_grouped.iterrows()
            }

            # Day-of-week baselines (0=Monday, 6=Sunday)
            if len(hourly) > 24:  # Need at least a day of data
                hourly_enhanced['dow'] = hourly_enhanced.index.dayofweek
                dow_grouped = hourly_enhanced.groupby('dow')['volume_usd'].agg(['mean', 'std'])

                # Direct iteration - optimized
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                time_baselines['daily_patterns'] = {
                    day_names[dow]: {
                        'avg_volume': row['mean'],
                        'std_volume': row['std'] if pd.notna(row['std']) else 0
                    }
                    for dow, row in dow_grouped.iterrows() if dow < len(day_names)
                }
            
            # Calculate percentile-based thresholds for more robust detection
            volumes = hourly['volume_usd'].dropna()
            if len(volumes) > 10:  # Need sufficient data
                time_baselines['percentile_thresholds'] = {
                    'p50': volumes.quantile(0.5),
                    'p75': volumes.quantile(0.75),
                    'p90': volumes.quantile(0.9),
                    'p95': volumes.quantile(0.95),
                    'p99': volumes.quantile(0.99)
                }
            
        except Exception as e:
            logger.warning(f"Error calculating time-aware baselines: {e}")
            # Return minimal time baseline structure
            time_baselines = {
                'hourly_patterns': {},
                'daily_patterns': {},
                'percentile_thresholds': {}
            }
        
        return time_baselines
    
    def detect_volume_spike(self, current_volume: float, baseline: Dict, current_time: datetime = None) -> Tuple[bool, float, Dict]:
        """
        Detect unusual volume spikes with time-aware comparison
        
        Args:
            current_volume: Current volume to evaluate
            baseline: Baseline metrics including time-aware patterns
            current_time: Current time for time-aware analysis (defaults to now)
        
        Returns:
            - is_anomaly: bool
            - spike_multiplier: float
            - details: Dict with analysis details
        """
        
        if not baseline or 'avg_hourly_volume' not in baseline:
            return False, 0, {'reason': 'No baseline data available'}
        
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        # Get time-aware baseline if available
        time_aware_avg, time_aware_std = self._get_time_aware_baseline(baseline, current_time)
        
        # Use time-aware baseline if available, otherwise fall back to overall
        if time_aware_avg is not None and time_aware_avg > 0:
            avg_volume = time_aware_avg
            std_volume = time_aware_std or baseline['std_hourly_volume']
            baseline_type = 'time_aware'
        else:
            avg_volume = baseline['avg_hourly_volume']
            std_volume = baseline['std_hourly_volume']
            baseline_type = 'overall'
        
        if avg_volume == 0:
            return False, 0, {'reason': 'Zero baseline volume'}
        
        # Calculate z-score using utility
        z_score = ThresholdValidator.calculate_z_score(current_volume, avg_volume, std_volume)
        
        # Calculate spike multiplier
        spike_multiplier = current_volume / (avg_volume + ThresholdValidator.FLOAT_TOLERANCE)
        
        # Also check against percentile thresholds if available
        percentile_anomaly = self._check_percentile_thresholds(current_volume, baseline)
        
        # Check if volume spike exceeds thresholds using utility
        spike_anomaly = ThresholdValidator.meets_threshold(
            spike_multiplier, self.thresholds['volume_spike_multiplier'], inclusive=True
        )
        z_anomaly = ThresholdValidator.meets_threshold(
            z_score, self.thresholds['z_score_threshold'], inclusive=True
        )
        
        # Combine all anomaly signals
        is_anomaly = spike_anomaly or z_anomaly or percentile_anomaly
        
        details = {
            'current_volume': current_volume,
            'avg_volume': avg_volume,
            'std_volume': std_volume,
            'z_score': z_score,
            'spike_multiplier': spike_multiplier,
            'spike_threshold': self.thresholds['volume_spike_multiplier'],
            'z_threshold': self.thresholds['z_score_threshold'],
            'spike_triggered': spike_anomaly,
            'z_triggered': z_anomaly,
            'percentile_triggered': percentile_anomaly,
            'baseline_type': baseline_type,
            'current_hour': current_time.hour,
            'current_dow': current_time.strftime('%A')
        }
        
        return is_anomaly, spike_multiplier, details
    
    def _get_time_aware_baseline(self, baseline: Dict, current_time: datetime) -> Tuple[float, float]:
        """Get time-aware baseline for the current time"""
        try:
            hourly_patterns = baseline.get('hourly_patterns', {})
            daily_patterns = baseline.get('daily_patterns', {})
            
            current_hour = str(current_time.hour)
            current_day = current_time.strftime('%A')
            
            # Try hourly pattern first (more specific)
            if current_hour in hourly_patterns:
                hour_data = hourly_patterns[current_hour]
                return hour_data.get('avg_volume'), hour_data.get('std_volume')
            
            # Fall back to daily pattern
            if current_day in daily_patterns:
                day_data = daily_patterns[current_day]
                return day_data.get('avg_volume'), day_data.get('std_volume')
            
            # No time-aware data available
            return None, None
            
        except Exception as e:
            logger.warning(f"Error getting time-aware baseline: {e}")
            return None, None
    
    def _check_percentile_thresholds(self, current_volume: float, baseline: Dict) -> bool:
        """Check if volume exceeds percentile-based thresholds"""
        try:
            percentiles = baseline.get('percentile_thresholds', {})
            
            # Use P95 as anomaly threshold (top 5% of historical activity)
            p95_threshold = percentiles.get('p95')
            if p95_threshold and current_volume > p95_threshold:
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking percentile thresholds: {e}")
            return False
    
    def get_recent_volume(self, trades: List[Dict], window_hours: int = 1) -> float:
        """Calculate volume in recent time window"""
        if not trades:
            return 0
        
        # Normalize all trades first
        normalized_trades = TradeNormalizer.normalize_trades(trades)
        if not normalized_trades:
            return 0
        
        # Find the most recent timestamp in the data
        latest_timestamp = max(trade['timestamp'].to_pydatetime() for trade in normalized_trades)
        
        # Use the latest timestamp from data, or current time if no valid timestamps
        reference_time = latest_timestamp if latest_timestamp else datetime.now(timezone.utc)
        cutoff_time = reference_time - timedelta(hours=window_hours)
        
        # Filter trades within time window and calculate volume
        total_volume = 0
        for trade in normalized_trades:
            if trade['timestamp'].to_pydatetime() > cutoff_time:
                total_volume += trade['volume_usd']
        
        return total_volume
    
    def analyze_volume_pattern(self, trades: List[Dict], market_id: str = None, historical_baseline: Dict = None) -> Dict:
        """Analyze volume patterns over different time windows"""
        if not trades:
            return create_consistent_early_return(
                anomaly=False, 
                reason='No trades available'
            )
        
        # Use historical baseline if available, otherwise calculate from recent trades
        if historical_baseline and len(historical_baseline) > 0:
            baseline = historical_baseline
            baseline_source = "historical"
        else:
            baseline = self.calculate_baseline_metrics(trades)
            baseline_source = "recent_trades"
        
        if not baseline:
            return create_consistent_early_return(
                anomaly=False, 
                reason='Unable to calculate baseline metrics'
            )
        
        # Check different time windows
        windows = [1, 2, 4, 6]  # hours
        results = {}
        
        max_anomaly_score = 0
        anomaly_detected = False
        
        for window in windows:
            current_volume = self.get_recent_volume(trades, window)
            is_anomaly, spike_multiplier, details = self.detect_volume_spike(
                current_volume, baseline
            )
            
            if is_anomaly:
                anomaly_detected = True
                anomaly_score = max(details['z_score'], spike_multiplier)
                if anomaly_score > max_anomaly_score:
                    max_anomaly_score = anomaly_score
            
            results[f'{window}h_window'] = {
                'volume': current_volume,
                'anomaly': is_anomaly,
                'spike_multiplier': spike_multiplier,
                'details': details
            }
        
        return {
            'anomaly': anomaly_detected,
            'max_anomaly_score': max_anomaly_score,
            'baseline': baseline,
            'baseline_source': baseline_source,
            'market_id': market_id,
            'windows': results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }