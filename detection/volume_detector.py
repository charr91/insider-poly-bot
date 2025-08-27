"""
Volume Spike Detection Module
Identifies unusual volume patterns that may indicate insider activity
"""

import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

class VolumeDetector:
    """Detects volume anomalies in trading data"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.thresholds = {
            'volume_spike_multiplier': 3.0,  # 3x average volume
            'z_score_threshold': 3.0  # 3 standard deviations
        }
        
        # Update thresholds from config
        if config and 'detection' in config:
            detection_config = config['detection']
            if 'volume_thresholds' in detection_config:
                self.thresholds.update(detection_config['volume_thresholds'])
    
    def calculate_baseline_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate baseline trading metrics for comparison"""
        if not trades:
            return {}
        
        # Normalize trade data to handle different field names
        normalized_trades = []
        for trade in trades:
            try:
                normalized = {
                    'timestamp': trade.get('timestamp', trade.get('createdAt', trade.get('created_at', ''))),
                    'price': float(trade.get('price', trade.get('feeRate', trade.get('outcome_price', 0)))),
                    'size': float(trade.get('size', trade.get('amount', trade.get('shares', 1)))),
                }
                if normalized['timestamp'] and normalized['price'] > 0:
                    normalized_trades.append(normalized)
            except (ValueError, TypeError):
                continue
        
        if not normalized_trades:
            return {}
        
        df = pd.DataFrame(normalized_trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['volume_usd'] = df['price'] * df['size']
        
        # Calculate hourly metrics
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df.set_index('timestamp', inplace=True)
        
        # Calculate volume properly
        try:
            hourly = df.resample('1h').agg({
                'volume_usd': 'sum',
                'size': 'count'  # Number of trades
            })
            
            return {
                'avg_hourly_volume': hourly['volume_usd'].mean(),
                'std_hourly_volume': hourly['volume_usd'].std(),
                'avg_trades_per_hour': hourly['size'].mean(),
                'total_volume': df['volume_usd'].sum()
            }
        except Exception as e:
            # Fallback calculation
            return {
                'avg_hourly_volume': df['volume_usd'].sum() / 24,  # Rough average
                'std_hourly_volume': df['volume_usd'].std(),
                'avg_trades_per_hour': len(df) / 24,
                'total_volume': df['volume_usd'].sum()
            }
    
    def detect_volume_spike(self, current_volume: float, baseline: Dict) -> Tuple[bool, float, Dict]:
        """
        Detect unusual volume spikes
        
        Returns:
            - is_anomaly: bool
            - spike_multiplier: float
            - details: Dict with analysis details
        """
        if not baseline or 'avg_hourly_volume' not in baseline:
            return False, 0, {'reason': 'No baseline data available'}
        
        avg_volume = baseline['avg_hourly_volume']
        std_volume = baseline['std_hourly_volume']
        
        if avg_volume == 0:
            return False, 0, {'reason': 'Zero baseline volume'}
        
        # Calculate z-score
        z_score = (current_volume - avg_volume) / (std_volume + 1e-8)
        
        # Calculate spike multiplier
        spike_multiplier = current_volume / (avg_volume + 1e-8)
        
        # Check if volume spike exceeds thresholds
        spike_anomaly = spike_multiplier > self.thresholds['volume_spike_multiplier']
        z_anomaly = z_score > self.thresholds['z_score_threshold']
        
        is_anomaly = spike_anomaly or z_anomaly
        
        details = {
            'current_volume': current_volume,
            'avg_volume': avg_volume,
            'std_volume': std_volume,
            'z_score': z_score,
            'spike_multiplier': spike_multiplier,
            'spike_threshold': self.thresholds['volume_spike_multiplier'],
            'z_threshold': self.thresholds['z_score_threshold'],
            'spike_triggered': spike_anomaly,
            'z_triggered': z_anomaly
        }
        
        return is_anomaly, spike_multiplier, details
    
    def get_recent_volume(self, trades: List[Dict], window_hours: int = 1) -> float:
        """Calculate volume in recent time window"""
        if not trades:
            return 0
        
        # Normalize trade data
        recent_trades = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        
        for trade in trades:
            try:
                # Handle different timestamp formats
                ts = trade.get('timestamp', trade.get('createdAt', trade.get('created_at', '')))
                if ts:
                    # Parse timestamp
                    if 'Z' in ts:
                        ts = ts.replace('Z', '+00:00')
                    
                    if 'T' in ts:
                        trade_time = datetime.fromisoformat(ts)
                    else:
                        trade_time = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                        trade_time = trade_time.replace(tzinfo=timezone.utc)
                    
                    # Check if within time window
                    if trade_time > cutoff_time:
                        recent_trades.append(trade)
            except (ValueError, TypeError, AttributeError):
                continue
        
        # Calculate total volume
        total_volume = 0
        for trade in recent_trades:
            try:
                price = float(trade.get('price', trade.get('feeRate', trade.get('outcome_price', 0))))
                size = float(trade.get('size', trade.get('amount', trade.get('shares', 1))))
                total_volume += price * size
            except (ValueError, TypeError):
                continue
        
        return total_volume
    
    def analyze_volume_pattern(self, trades: List[Dict]) -> Dict:
        """Analyze volume patterns over different time windows"""
        if not trades:
            return {'anomaly': False, 'reason': 'No trades available'}
        
        # Calculate baseline from all available trades
        baseline = self.calculate_baseline_metrics(trades)
        
        if not baseline:
            return {'anomaly': False, 'reason': 'Unable to calculate baseline metrics'}
        
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
            'windows': results,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }