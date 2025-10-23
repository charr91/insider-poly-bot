"""
Whale Activity Detection Module
Identifies large orders and coordinated whale activity
"""

import pandas as pd
from typing import Dict, List, Tuple
import logging
from .base_detector import DetectorBase
from .utils import TradeNormalizer, ThresholdValidator, create_consistent_early_return

logger = logging.getLogger(__name__)

class WhaleDetector(DetectorBase):
    """Detects whale trading activity and coordination patterns"""
    
    def __init__(self, config: Dict):
        # Initialize base detector
        super().__init__(config, 'whale')
    
    def _load_detector_config(self):
        """Load whale-specific configuration from config dict"""
        # Validate and load whale thresholds from config (no hardcoded fallbacks)
        self.thresholds = self._validate_config_section(
            'whale_thresholds', 
            ['whale_threshold_usd', 'coordination_threshold', 'min_whales_for_coordination']
        )
    
    def detect_whale_activity(self, trades: List[Dict]) -> Dict:
        """Detect large orders from single or coordinated wallets"""
        if not trades:
            return create_consistent_early_return(
                anomaly=False, 
                reason='No trades available'
            )
        
        # Normalize trade data using utility (timestamps not required for whale detection)
        normalized_trades = TradeNormalizer.normalize_trades(trades, require_timestamp=False)
        
        if not normalized_trades:
            return create_consistent_early_return(
                anomaly=False, 
                reason='No valid trades after normalization'
            )
        
        df = pd.DataFrame(normalized_trades)
        # volume_usd already calculated in normalization
        
        # Find whale trades using threshold utility
        whale_trades = df[df['volume_usd'] >= self.thresholds['whale_threshold_usd']]
        
        if len(whale_trades) == 0:
            return create_consistent_early_return(
                anomaly=False,
                reason=f'No trades above ${self.thresholds["whale_threshold_usd"]} threshold',
                additional_fields={
                    'whale_count': 0,
                    'total_trades': len(df),
                    'largest_trade': df['volume_usd'].max() if len(df) > 0 else 0
                }
            )
        
        # Analyze whale patterns
        analysis = self._analyze_whale_patterns(whale_trades, df)
        
        # Check for coordination
        coordination_detected = self._detect_coordination(whale_trades)
        
        return {
            'anomaly': analysis['significant_activity'] or coordination_detected['coordinated'],
            'whale_count': analysis['unique_whales'],
            'total_whale_volume': analysis['total_whale_volume'],
            'largest_whale_volume': analysis['largest_whale_volume'],
            'direction_imbalance': analysis['direction_imbalance'],
            'dominant_side': analysis['dominant_side'],
            'coordination': coordination_detected,
            'whale_breakdown': analysis['whale_breakdown'],
            'market_impact': analysis['market_impact'],
            'details': analysis
        }
    
    def _analyze_whale_patterns(self, whale_trades: pd.DataFrame, all_trades: pd.DataFrame) -> Dict:
        """Analyze patterns in whale trading activity"""
        # Build aggregation dict
        agg_dict = {
            'volume_usd': ['sum', 'count', 'mean'],
            'side': lambda x: x.mode().iloc[0] if len(x) > 0 else 'BUY'
        }

        # Add asset_id aggregation only if it exists in the data
        if 'asset_id' in whale_trades.columns:
            agg_dict['asset_id'] = lambda x: x.mode().iloc[0] if len(x) > 0 else (x.iloc[0] if len(x) > 0 else None)

        # Group by wallet address
        whale_breakdown = whale_trades.groupby('maker').agg(agg_dict).round(2)

        # Flatten column names
        if 'asset_id' in whale_trades.columns:
            whale_breakdown.columns = ['total_volume', 'trade_count', 'avg_trade_size', 'preferred_side', 'asset_id']
        else:
            whale_breakdown.columns = ['total_volume', 'trade_count', 'avg_trade_size', 'preferred_side']
        
        # Sort by total volume
        top_whales = whale_breakdown.nlargest(10, 'total_volume')
        
        # Analyze directional bias
        whale_sides = whale_trades.groupby('side')['volume_usd'].sum()
        
        buy_volume = whale_sides.get('BUY', 0)
        sell_volume = whale_sides.get('SELL', 0)
        total_whale_volume = buy_volume + sell_volume
        
        if total_whale_volume > 0:
            direction_imbalance = abs(buy_volume - sell_volume) / total_whale_volume
            dominant_side = 'BUY' if buy_volume > sell_volume else 'SELL'
        else:
            direction_imbalance = 0
            dominant_side = 'NEUTRAL'
        
        # Calculate market impact
        total_market_volume = all_trades['volume_usd'].sum()
        whale_market_share = total_whale_volume / max(total_market_volume, 1)
        
        # Check for significant activity using threshold validator
        significant_activity = (
            ThresholdValidator.meets_threshold(
                direction_imbalance, self.thresholds['coordination_threshold'], inclusive=False
            ) and
            ThresholdValidator.meets_threshold(
                len(top_whales), self.thresholds['min_whales_for_coordination'], inclusive=True
            )
        )
        
        return {
            'unique_whales': len(whale_breakdown),
            'total_whale_volume': total_whale_volume,
            'largest_whale_volume': whale_breakdown['total_volume'].max(),
            'direction_imbalance': direction_imbalance,
            'dominant_side': dominant_side,
            'whale_market_share': whale_market_share,
            'significant_activity': significant_activity,
            'whale_breakdown': top_whales.to_dict('index'),
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'market_impact': {
                'whale_market_share': whale_market_share,
                'total_market_volume': total_market_volume,
                'whale_dominance': whale_market_share > 0.3  # 30% of market volume
            }
        }
    
    def _detect_coordination(self, whale_trades: pd.DataFrame) -> Dict:
        """Detect coordinated whale activity patterns"""
        if len(whale_trades) < self.thresholds['min_whales_for_coordination']:
            return {
                'coordinated': False,
                'reason': f'Insufficient whale trades ({len(whale_trades)} < {self.thresholds["min_whales_for_coordination"]})'
            }
        
        # Analyze timing patterns
        whale_trades_sorted = whale_trades.sort_values('volume_usd', ascending=False)
        
        # Check for similar trade sizes (potential coordination indicator)
        sizes = whale_trades['volume_usd'].values
        size_variance = pd.Series(sizes).std() / pd.Series(sizes).mean() if pd.Series(sizes).mean() > 0 else float('inf')
        
        # Check for timing clusters
        if 'timestamp' in whale_trades.columns:
            # Create a copy to avoid SettingWithCopyWarning
            whale_trades_copy = whale_trades.copy()
            whale_trades_copy['timestamp'] = pd.to_datetime(whale_trades_copy['timestamp'])
            time_diff = whale_trades_copy['timestamp'].diff().dt.total_seconds().fillna(0)
            avg_time_gap = time_diff.mean()
            clustered_timing = (time_diff < 300).sum() / len(time_diff) > 0.5  # 50% within 5 minutes
        else:
            avg_time_gap = None
            clustered_timing = False
        
        # Coordination indicators
        same_direction = len(whale_trades['side'].unique()) == 1  # All same direction
        multiple_whales = ThresholdValidator.meets_threshold(
            whale_trades['maker'].nunique(), self.thresholds['min_whales_for_coordination'], inclusive=True
        )
        similar_sizes = size_variance < 0.5  # Low variance in trade sizes
        
        coordination_score = sum([
            same_direction * 3,  # Strongest indicator
            clustered_timing * 2,
            similar_sizes * 1,
            multiple_whales * 1
        ])
        
        coordinated = coordination_score >= 4  # Threshold for coordination
        
        return {
            'coordinated': coordinated,
            'coordination_score': coordination_score,
            'same_direction': same_direction,
            'clustered_timing': clustered_timing,
            'similar_sizes': similar_sizes,
            'size_variance': size_variance,
            'avg_time_gap': avg_time_gap,
            'unique_whales': whale_trades['maker'].nunique(),
            'indicators': {
                'directional_alignment': same_direction,
                'timing_clusters': clustered_timing,
                'size_similarity': similar_sizes,
                'sufficient_participants': multiple_whales
            }
        }
    
    def get_whale_summary(self, analysis: Dict) -> str:
        """Generate human-readable summary of whale activity"""
        if not analysis['anomaly']:
            return "No significant whale activity detected"
        
        summary_parts = []
        
        # Whale count and volume
        whale_count = analysis['whale_count']
        total_volume = analysis['total_whale_volume']
        summary_parts.append(f"{whale_count} whales traded ${total_volume:,.0f}")
        
        # Direction
        if analysis['direction_imbalance'] > 0.7:
            side = analysis['dominant_side']
            imbalance = analysis['direction_imbalance'] * 100
            summary_parts.append(f"{imbalance:.0f}% {side} bias")
        
        # Coordination
        if analysis['coordination']['coordinated']:
            coord_score = analysis['coordination']['coordination_score']
            summary_parts.append(f"coordination detected (score: {coord_score})")
        
        # Market impact
        if analysis['market_impact']['whale_dominance']:
            share = analysis['market_impact']['whale_market_share'] * 100
            summary_parts.append(f"{share:.1f}% of market volume")
        
        return "; ".join(summary_parts)