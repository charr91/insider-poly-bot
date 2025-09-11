"""
Price Movement Detection Module
Identifies unusual price movements and trends
"""

import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime, timedelta, timezone
import logging
from .utils import TradeNormalizer, ThresholdValidator, create_consistent_early_return

logger = logging.getLogger(__name__)

class PriceDetector:
    """Detects unusual price movements and volatility patterns"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.thresholds = {
            'rapid_movement_pct': 15,  # 15% price move threshold
            'price_movement_std': 2.5,  # 2.5 standard deviations
            'volatility_spike_multiplier': 3.0,  # 3x normal volatility
            'momentum_threshold': 0.8  # Momentum consistency threshold
        }
        
        # Update thresholds from config
        if config and 'detection' in config:
            detection_config = config['detection']
            if 'price_thresholds' in detection_config:
                self.thresholds.update(detection_config['price_thresholds'])
    
    def _create_price_early_return(self, reason: str, window_minutes: int) -> Dict:
        """Create consistent early return structure for price detection"""
        empty_analysis = {
            'price_start': 0, 'price_end': 0, 'price_high': 0, 'price_low': 0,
            'price_change_abs': 0, 'price_change_pct': 0, 'price_range': 0,
            'trend_direction': 'neutral', 'momentum_score': 0,
            'recent_volatility': 0, 'historical_volatility': 0, 'volatility_spike': 0,
            'price_change_std_score': 0, 'ma_divergence': 0, 'trade_count': 0
        }
        
        return create_consistent_early_return(
            anomaly=False,
            reason=reason,
            additional_fields={
                'window_minutes': window_minutes,
                'triggers': {'rapid_movement': False, 'volatility_spike': False, 'high_momentum': False},
                'analysis': empty_analysis
            }
        )
    
    def detect_price_movement(self, trades: List[Dict], window_minutes: int = 60) -> Dict:
        """Detect unusual price movements within a time window"""
        if not trades or len(trades) < 2:
            return self._create_price_early_return(
                'Insufficient trade data', window_minutes
            )
        
        # Normalize trade data using utility
        normalized_trades = TradeNormalizer.normalize_trades(trades)
        
        if len(normalized_trades) < 2:
            return self._create_price_early_return(
                'Insufficient valid trades after normalization', window_minutes
            )
        
        df = pd.DataFrame(normalized_trades)
        df['price'] = df['price'].astype(float)
        df = df.sort_values('timestamp')
        
        # Get trades from specified time window
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        recent = df[df['timestamp'] > cutoff]
        
        if len(recent) < 2:
            return self._create_price_early_return(
                f'Less than 2 trades in last {window_minutes} minutes', window_minutes
            )
        
        # Analyze price movement
        analysis = self._analyze_price_pattern(recent, df)
        
        # Check for anomalies using threshold validator
        rapid_movement = ThresholdValidator.meets_threshold(
            abs(analysis['price_change_pct']), self.thresholds['rapid_movement_pct'], inclusive=False
        )
        unusual_volatility = ThresholdValidator.meets_threshold(
            analysis['volatility_spike'], self.thresholds['volatility_spike_multiplier'], inclusive=False
        )
        high_momentum = ThresholdValidator.meets_threshold(
            analysis['momentum_score'], self.thresholds['momentum_threshold'], inclusive=False
        )
        
        anomaly_detected = rapid_movement or unusual_volatility or high_momentum
        
        return {
            'anomaly': anomaly_detected,
            'window_minutes': window_minutes,
            'analysis': analysis,
            'triggers': {
                'rapid_movement': rapid_movement,
                'unusual_volatility': unusual_volatility,
                'high_momentum': high_momentum
            },
            'thresholds': self.thresholds
        }
    
    def _analyze_price_pattern(self, recent_trades: pd.DataFrame, all_trades: pd.DataFrame) -> Dict:
        """Analyze detailed price movement patterns"""
        # Basic price movement
        price_start = recent_trades['price'].iloc[0]
        price_end = recent_trades['price'].iloc[-1]
        price_change_abs = price_end - price_start
        price_change_pct = (price_change_abs / price_start) * 100
        
        # Price extremes in window
        price_high = recent_trades['price'].max()
        price_low = recent_trades['price'].min()
        price_range = price_high - price_low
        
        # Volatility analysis
        recent_volatility = recent_trades['price'].std()
        historical_volatility = all_trades['price'].std()
        volatility_spike = recent_volatility / (historical_volatility + 1e-8)
        
        # Trend analysis
        trend_direction = 'UP' if price_change_pct > 1 else 'DOWN' if price_change_pct < -1 else 'FLAT'
        
        # Momentum calculation (consistency of direction)
        price_changes = recent_trades['price'].diff().dropna()
        if len(price_changes) > 0:
            positive_changes = (price_changes > 0).sum()
            negative_changes = (price_changes < 0).sum()
            total_changes = len(price_changes)
            
            if total_changes > 0:
                momentum_score = max(positive_changes, negative_changes) / total_changes
            else:
                momentum_score = 0
        else:
            momentum_score = 0
        
        # Statistical significance
        if len(all_trades) > 10:
            historical_std = all_trades['price'].std()
            price_change_std_score = abs(price_change_abs) / (historical_std + 1e-8)
        else:
            price_change_std_score = 0
        
        # Calculate moving averages for trend confirmation
        if len(recent_trades) >= 5:
            recent_ma = recent_trades['price'].tail(5).mean()
            if len(all_trades) >= 20:
                long_term_ma = all_trades['price'].tail(20).mean()
                ma_divergence = (recent_ma - long_term_ma) / long_term_ma * 100
            else:
                ma_divergence = 0
        else:
            ma_divergence = 0
        
        return {
            'price_start': price_start,
            'price_end': price_end,
            'price_high': price_high,
            'price_low': price_low,
            'price_change_abs': price_change_abs,
            'price_change_pct': price_change_pct,
            'price_range': price_range,
            'trend_direction': trend_direction,
            'momentum_score': momentum_score,
            'recent_volatility': recent_volatility,
            'historical_volatility': historical_volatility,
            'volatility_spike': volatility_spike,
            'price_change_std_score': price_change_std_score,
            'ma_divergence': ma_divergence,
            'trade_count': len(recent_trades)
        }
    
    def detect_accumulation_pattern(self, trades: List[Dict]) -> Dict:
        """Detect price accumulation/distribution patterns"""
        if not trades or len(trades) < 10:
            return create_consistent_early_return(
                anomaly=False, 
                reason='Insufficient trades for pattern analysis'
            )
        
        # Normalize trades using utility
        normalized_trades = TradeNormalizer.normalize_trades(trades)
        
        if len(normalized_trades) < 10:
            return create_consistent_early_return(
                anomaly=False, 
                reason='Insufficient valid trades'
            )
        
        df = pd.DataFrame(normalized_trades)
        df = df.sort_values('timestamp')
        
        # Calculate volume-weighted average price (VWAP)
        df['volume'] = df['volume_usd']  # Already calculated in normalization
        cumulative_volume = df['volume'].cumsum()
        cumulative_size = df['size'].cumsum()
        df['vwap'] = cumulative_volume / cumulative_size
        
        # Analyze price vs VWAP
        df['price_vs_vwap'] = (df['price'] - df['vwap']) / df['vwap'] * 100
        
        # Look for sustained patterns
        recent_trades = df.tail(20)  # Last 20 trades
        
        above_vwap = (recent_trades['price_vs_vwap'] > 0).sum()
        below_vwap = (recent_trades['price_vs_vwap'] < 0).sum()
        
        # Pattern classification
        if above_vwap > 15:  # 75% of trades above VWAP
            pattern_type = 'ACCUMULATION'
            pattern_strength = above_vwap / len(recent_trades)
        elif below_vwap > 15:  # 75% of trades below VWAP
            pattern_type = 'DISTRIBUTION'
            pattern_strength = below_vwap / len(recent_trades)
        else:
            pattern_type = 'NEUTRAL'
            pattern_strength = 0.5
        
        # Check for anomalous patterns
        anomaly = pattern_strength > 0.8 and pattern_type != 'NEUTRAL'
        
        return {
            'anomaly': anomaly,
            'pattern_type': pattern_type,
            'pattern_strength': pattern_strength,
            'above_vwap_ratio': above_vwap / len(recent_trades),
            'below_vwap_ratio': below_vwap / len(recent_trades),
            'current_vwap': df['vwap'].iloc[-1],
            'current_price': df['price'].iloc[-1],
            'vwap_divergence': df['price_vs_vwap'].iloc[-1]
        }
    
    def get_price_summary(self, analysis: Dict) -> str:
        """Generate human-readable summary of price analysis"""
        if not analysis['anomaly']:
            return "No unusual price movement detected"
        
        movement_analysis = analysis['analysis']
        summary_parts = []
        
        # Price change
        change_pct = movement_analysis['price_change_pct']
        direction = "increased" if change_pct > 0 else "decreased"
        summary_parts.append(f"Price {direction} {abs(change_pct):.1f}%")
        
        # Volatility
        if movement_analysis['volatility_spike'] > 2:
            vol_spike = movement_analysis['volatility_spike']
            summary_parts.append(f"volatility {vol_spike:.1f}x normal")
        
        # Momentum
        if movement_analysis['momentum_score'] > 0.8:
            momentum = movement_analysis['momentum_score'] * 100
            summary_parts.append(f"{momentum:.0f}% consistent direction")
        
        # Trend
        if movement_analysis['trend_direction'] != 'FLAT':
            trend = movement_analysis['trend_direction']
            summary_parts.append(f"strong {trend} trend")
        
        return "; ".join(summary_parts)