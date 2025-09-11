"""
Coordinated Trading Detection Module
Identifies patterns suggesting coordinated or insider trading
"""

import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime, timedelta, timezone
import logging
from collections import defaultdict
from .base_detector import DetectorBase

logger = logging.getLogger(__name__)

class CoordinationDetector(DetectorBase):
    """Detects coordinated trading patterns that may indicate insider activity"""
    
    def __init__(self, config: Dict):
        # Initialize base detector
        super().__init__(config, 'coordination')
    
    def _load_detector_config(self):
        """Load coordination-specific configuration from config dict"""
        # Validate and load coordination thresholds from config (no hardcoded fallbacks)
        self.thresholds = self._validate_config_section(
            'coordination_thresholds', 
            ['min_coordinated_wallets', 'coordination_time_window', 'directional_bias_threshold', 'burst_intensity_threshold']
        )
    
    def detect_coordinated_buying(self, trades: List[Dict]) -> Dict:
        """Detect multiple wallets buying in coordination"""
        if not trades or len(trades) < 10:
            return {'anomaly': False, 'reason': 'Insufficient trades for coordination analysis'}
        
        # Normalize trade data
        normalized_trades = []
        for trade in trades:
            try:
                timestamp = trade.get('timestamp', trade.get('createdAt', trade.get('created_at', '')))
                size = float(trade.get('size', trade.get('amount', trade.get('shares', 1))))
                side = trade.get('side', trade.get('type', 'BUY')).upper()
                maker = trade.get('maker', trade.get('trader', trade.get('user', 'unknown')))
                
                if timestamp and maker != 'unknown':
                    normalized_trades.append({
                        'timestamp': timestamp,
                        'size': size,
                        'side': side,
                        'maker': maker
                    })
            except (ValueError, TypeError):
                continue
        
        if len(normalized_trades) < 10:
            return {'anomaly': False, 'reason': 'Insufficient valid trades after normalization'}
        
        df = pd.DataFrame(normalized_trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values('timestamp')
        
        # Analyze different time windows
        results = self._analyze_coordination_windows(df)
        
        # Overall coordination assessment
        max_coordination_score = 0
        best_window = None
        
        for window_minutes, window_result in results.items():
            if window_result['coordination_score'] > max_coordination_score:
                max_coordination_score = window_result['coordination_score']
                best_window = window_result
        
        anomaly = max_coordination_score > 0.7  # High coordination threshold
        
        return {
            'anomaly': anomaly,
            'coordination_score': max_coordination_score,
            'best_window': best_window,
            'all_windows': results,
            'overall_analysis': self._get_overall_coordination_analysis(df)
        }
    
    def _analyze_coordination_windows(self, df: pd.DataFrame) -> Dict:
        """Analyze coordination patterns across different time windows"""
        windows = [15, 30, 60, 120]  # minutes
        results = {}
        
        for window_minutes in windows:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
            window_trades = df[df['timestamp'] > cutoff_time]
            
            if len(window_trades) < 5:
                results[f'{window_minutes}min'] = {
                    'coordination_score': 0,
                    'reason': 'Insufficient trades in window'
                }
                continue
            
            # Analyze this window
            analysis = self._analyze_window_coordination(window_trades)
            results[f'{window_minutes}min'] = analysis
        
        return results
    
    def _analyze_window_coordination(self, window_trades: pd.DataFrame) -> Dict:
        """Analyze coordination patterns within a specific time window"""
        # Basic metrics
        unique_wallets = window_trades['maker'].nunique()
        total_trades = len(window_trades)
        
        if unique_wallets < self.thresholds['min_coordinated_wallets']:
            return {
                'coordination_score': 0,
                'reason': f'Only {unique_wallets} unique wallets (need {self.thresholds["min_coordinated_wallets"]})'
            }
        
        # Directional analysis
        buy_trades = window_trades[window_trades['side'] == 'BUY']
        sell_trades = window_trades[window_trades['side'] == 'SELL']
        
        buy_wallets = buy_trades['maker'].nunique()
        sell_wallets = sell_trades['maker'].nunique()
        
        directional_bias = buy_wallets / max(buy_wallets + sell_wallets, 1)
        
        # Timing analysis
        time_clustering = self._analyze_timing_clusters(window_trades)
        
        # Size analysis
        size_analysis = self._analyze_trade_sizes(window_trades)
        
        # New wallet analysis (simplified - would need historical data)
        wallet_diversity = unique_wallets / max(total_trades, 1)
        
        # Calculate coordination score
        coordination_indicators = [
            min(directional_bias, 1 - directional_bias) < (1 - self.thresholds['directional_bias_threshold']),  # Strong directional bias
            time_clustering['clustered_ratio'] > 0.6,  # 60% of trades in clusters
            size_analysis['size_consistency'] > 0.7,  # Consistent trade sizes
            unique_wallets >= self.thresholds['min_coordinated_wallets'],  # Sufficient participants
            wallet_diversity < 0.5  # Low diversity suggests coordination
        ]
        
        coordination_score = sum(coordination_indicators) / len(coordination_indicators)
        
        return {
            'coordination_score': coordination_score,
            'unique_wallets': unique_wallets,
            'total_trades': total_trades,
            'directional_bias': directional_bias,
            'buy_wallets': buy_wallets,
            'sell_wallets': sell_wallets,
            'timing_analysis': time_clustering,
            'size_analysis': size_analysis,
            'wallet_diversity': wallet_diversity,
            'indicators': {
                'directional_alignment': coordination_indicators[0],
                'timing_clusters': coordination_indicators[1],
                'size_consistency': coordination_indicators[2],
                'sufficient_participants': coordination_indicators[3],
                'low_diversity': coordination_indicators[4]
            }
        }
    
    def _analyze_timing_clusters(self, trades: pd.DataFrame) -> Dict:
        """Analyze temporal clustering of trades"""
        if len(trades) < 2:
            return {'clustered_ratio': 0, 'avg_gap': 0}
        
        # Calculate time gaps between consecutive trades
        trades_sorted = trades.sort_values('timestamp')
        time_diffs = trades_sorted['timestamp'].diff().dt.total_seconds().fillna(0)
        
        # Find clusters (trades within 5 minutes of each other)
        cluster_threshold = 300  # 5 minutes
        clustered_trades = (time_diffs <= cluster_threshold).sum()
        clustered_ratio = clustered_trades / len(trades)
        
        avg_gap = time_diffs.mean()
        
        return {
            'clustered_ratio': clustered_ratio,
            'avg_gap': avg_gap,
            'cluster_threshold': cluster_threshold
        }
    
    def _analyze_trade_sizes(self, trades: pd.DataFrame) -> Dict:
        """Analyze consistency in trade sizes"""
        sizes = trades['size'].values
        
        if len(sizes) < 2:
            return {'size_consistency': 0, 'size_variance': float('inf')}
        
        # Calculate coefficient of variation
        mean_size = pd.Series(sizes).mean()
        std_size = pd.Series(sizes).std()
        
        if mean_size > 0:
            cv = std_size / mean_size  # Coefficient of variation
            size_consistency = max(0, 1 - cv)  # Higher consistency = lower variation
        else:
            size_consistency = 0
        
        return {
            'size_consistency': size_consistency,
            'size_variance': cv if mean_size > 0 else float('inf'),
            'mean_size': mean_size,
            'std_size': std_size
        }
    
    def _get_overall_coordination_analysis(self, df: pd.DataFrame) -> Dict:
        """Get overall coordination analysis across all trades"""
        # Wallet behavior patterns
        wallet_stats = df.groupby('maker').agg({
            'side': [lambda x: x.mode().iloc[0] if len(x) > 0 else 'BUY', 'count'],
            'size': ['mean', 'std'],
            'timestamp': ['min', 'max']
        })
        
        # Flatten column names
        wallet_stats.columns = ['preferred_side', 'trade_count', 'avg_size', 'size_std', 'first_trade', 'last_trade']
        
        # Find potential coordinated groups
        coordinated_buyers = wallet_stats[
            (wallet_stats['preferred_side'] == 'BUY') & 
            (wallet_stats['trade_count'] >= 2)
        ]
        
        coordinated_sellers = wallet_stats[
            (wallet_stats['preferred_side'] == 'SELL') & 
            (wallet_stats['trade_count'] >= 2)
        ]
        
        # Check for unusual patterns
        new_buyer_ratio = len(coordinated_buyers) / max(len(wallet_stats), 1)
        new_seller_ratio = len(coordinated_sellers) / max(len(wallet_stats), 1)
        
        return {
            'total_unique_wallets': len(wallet_stats),
            'coordinated_buyers': len(coordinated_buyers),
            'coordinated_sellers': len(coordinated_sellers),
            'new_buyer_ratio': new_buyer_ratio,
            'new_seller_ratio': new_seller_ratio,
            'dominant_pattern': 'BUY' if new_buyer_ratio > new_seller_ratio else 'SELL',
            'wallet_concentration': {
                'top_3_wallets_share': wallet_stats.nlargest(3, 'trade_count')['trade_count'].sum() / df.shape[0],
                'single_trade_wallets': (wallet_stats['trade_count'] == 1).sum()
            }
        }
    
    def detect_wash_trading(self, trades: List[Dict]) -> Dict:
        """Detect potential wash trading patterns"""
        if not trades or len(trades) < 4:
            return {'anomaly': False, 'reason': 'Insufficient trades for wash trading analysis'}
        
        # Group trades by wallet pairs
        wallet_pairs = defaultdict(list)
        
        for i, trade in enumerate(trades):
            maker = trade.get('maker', trade.get('trader', 'unknown'))
            taker = trade.get('taker', trade.get('counterparty', 'unknown'))
            
            if maker != 'unknown' and taker != 'unknown':
                pair = tuple(sorted([maker, taker]))
                wallet_pairs[pair].append({
                    'index': i,
                    'timestamp': trade.get('timestamp'),
                    'side': trade.get('side', 'BUY'),
                    'price': float(trade.get('price', 0)),
                    'size': float(trade.get('size', 0))
                })
        
        # Analyze pairs for wash trading patterns
        suspicious_pairs = []
        
        for pair, pair_trades in wallet_pairs.items():
            if len(pair_trades) >= 4:  # Need multiple trades to establish pattern
                wash_score = self._calculate_wash_trading_score(pair_trades)
                if wash_score > 0.7:
                    suspicious_pairs.append({
                        'wallets': pair,
                        'trade_count': len(pair_trades),
                        'wash_score': wash_score,
                        'trades': pair_trades
                    })
        
        return {
            'anomaly': len(suspicious_pairs) > 0,
            'suspicious_pairs': suspicious_pairs,
            'total_wallet_pairs': len(wallet_pairs),
            'analysis_summary': {
                'pairs_analyzed': len(wallet_pairs),
                'suspicious_count': len(suspicious_pairs),
                'max_wash_score': max([p['wash_score'] for p in suspicious_pairs], default=0)
            }
        }
    
    def _calculate_wash_trading_score(self, pair_trades: List[Dict]) -> float:
        """Calculate wash trading suspicion score for a wallet pair"""
        if len(pair_trades) < 4:
            return 0
        
        df = pd.DataFrame(pair_trades)
        
        # Check for alternating buy/sell pattern
        sides = df['side'].tolist()
        alternating_pattern = 0
        for i in range(1, len(sides)):
            if sides[i] != sides[i-1]:
                alternating_pattern += 1
        
        alternating_ratio = alternating_pattern / max(len(sides) - 1, 1)
        
        # Check for similar prices (minimal price impact)
        price_variance = df['price'].std() / max(df['price'].mean(), 1e-8)
        price_stability = max(0, 1 - price_variance)
        
        # Check for regular timing
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        time_diffs = df['timestamp'].diff().dt.total_seconds().fillna(0)
        time_regularity = 1 / (1 + time_diffs.std())  # More regular = higher score
        
        # Combine factors
        wash_score = (
            alternating_ratio * 0.4 +  # 40% weight on alternating pattern
            price_stability * 0.4 +    # 40% weight on price stability
            time_regularity * 0.2      # 20% weight on timing regularity
        )
        
        return min(wash_score, 1.0)
    
    def get_coordination_summary(self, analysis: Dict) -> str:
        """Generate human-readable summary of coordination analysis"""
        if not analysis['anomaly']:
            return "No coordinated trading detected"
        
        summary_parts = []
        
        # Coordination score
        score = analysis['coordination_score']
        summary_parts.append(f"Coordination score: {score:.2f}")
        
        # Best window analysis
        if analysis.get('best_window'):
            best = analysis['best_window']
            summary_parts.append(
                f"{best['unique_wallets']} wallets, "
                f"{best['directional_bias']:.0%} directional bias"
            )
        
        # Overall patterns
        if analysis.get('overall_analysis'):
            overall = analysis['overall_analysis']
            if overall['coordinated_buyers'] > overall['coordinated_sellers']:
                summary_parts.append(f"{overall['coordinated_buyers']} coordinated buyers")
            else:
                summary_parts.append(f"{overall['coordinated_sellers']} coordinated sellers")
        
        return "; ".join(summary_parts)