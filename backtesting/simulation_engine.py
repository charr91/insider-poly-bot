"""
Backtesting Simulation Engine

Replays historical trades through detection algorithms to measure performance.
"""

import logging
from typing import Dict, List, Optional, Callable, Tuple
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from dataclasses import dataclass, field
import json
import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@dataclass
class MarketState:
    """Tracks the state of a market during simulation"""
    market_id: str
    trade_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    total_volume: float = 0.0
    trade_count: int = 0
    first_trade_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None
    unique_makers: set = field(default_factory=set)
    unique_takers: set = field(default_factory=set)

    def add_trade(self, trade: Dict):
        """Add a trade to market history"""
        self.trade_history.append(trade)
        self.total_volume += trade.get('volume_usd', 0)
        self.trade_count += 1

        timestamp = datetime.fromtimestamp(trade['timestamp'], timezone.utc)
        if not self.first_trade_time:
            self.first_trade_time = timestamp
        self.last_trade_time = timestamp

        self.unique_makers.add(trade.get('maker', ''))
        self.unique_takers.add(trade.get('taker', ''))

    def get_recent_trades(self, window_minutes: int = 60) -> List[Dict]:
        """Get trades within the last N minutes"""
        if not self.last_trade_time:
            return []

        cutoff = self.last_trade_time - timedelta(minutes=window_minutes)
        cutoff_ts = cutoff.timestamp()

        return [
            t for t in self.trade_history
            if t['timestamp'] >= cutoff_ts
        ]


@dataclass
class VirtualAlert:
    """Represents an alert generated during simulation"""
    alert_id: str
    timestamp: datetime
    market_id: str
    detector_type: str
    severity: str
    analysis: Dict
    confidence_score: float
    price_at_alert: Optional[float] = None
    predicted_direction: Optional[str] = None


class SimulationEngine:
    """
    Replays historical trades through detection algorithms.

    Maintains market state and generates virtual alerts for performance analysis.
    """

    def __init__(
        self,
        config: Dict,
        detectors: Optional[Dict] = None,
        track_outcomes: bool = True,
        outcome_price_threshold: float = 0.05,
        storage: Optional['HistoricalTradeStorage'] = None
    ):
        """
        Initialize simulation engine.

        Args:
            config: Configuration dictionary for detectors
            detectors: Optional dict of detector instances
                      Format: {'volume': VolumeDetector(...), ...}
            track_outcomes: Whether to track alert outcomes for metrics (default: True)
            outcome_price_threshold: Price change threshold for outcome validation (default: 5%)
            storage: Optional HistoricalTradeStorage for database queries
        """
        self.config = config
        self.detectors = detectors or {}
        self.storage = storage

        # Simulation state
        self.market_states: Dict[str, MarketState] = {}
        self.virtual_alerts: List[VirtualAlert] = []
        self.current_time: Optional[datetime] = None

        # Statistics
        self.total_trades_processed = 0
        self.trades_by_market = defaultdict(int)
        self.alerts_by_detector = defaultdict(int)
        self.alerts_by_severity = defaultdict(int)

        # Outcome tracking for metrics
        self.track_outcomes = track_outcomes
        self.outcome_tracker = None
        self.metrics_calculator = None

        if track_outcomes:
            # Import here to avoid circular dependency
            from backtesting.outcome_tracker import OutcomeTracker
            from backtesting.metrics_calculator import MetricsCalculator

            self.outcome_tracker = OutcomeTracker(price_change_threshold=outcome_price_threshold)
            self.metrics_calculator = MetricsCalculator()

        logger.info("🎬 Simulation engine initialized")

    def add_detector(self, name: str, detector):
        """Add a detector to the simulation"""
        self.detectors[name] = detector
        logger.info(f"Added detector: {name}")

    def reset(self):
        """Reset simulation state"""
        self.market_states.clear()
        self.virtual_alerts.clear()
        self.current_time = None
        self.total_trades_processed = 0
        self.trades_by_market.clear()
        self.alerts_by_detector.clear()
        self.alerts_by_severity.clear()
        logger.info("🔄 Simulation state reset")

    def _convert_trade_format(self, trade: Dict) -> Dict:
        """
        Convert orderbook trade format to detector format.

        Args:
            trade: Trade from historical storage

        Returns:
            Trade in format expected by detectors
        """
        # Calculate volume in USD (assuming USDC with 6 decimals)
        maker_amount = int(trade.get('maker_amount_filled', 0))
        taker_amount = int(trade.get('taker_amount_filled', 0))

        # Use average of maker/taker amounts as trade volume
        volume_usd = (maker_amount + taker_amount) / 2 / 1e6

        # Determine side based on relative amounts
        # In Polymarket, the side isn't explicit but we can infer from asset directions
        # For now, default to BUY (doesn't affect volume-based detection)
        side = 'BUY'

        return {
            'id': trade['id'],
            'timestamp': trade['timestamp'],
            'maker': trade['maker'],
            'taker': trade['taker'],
            'makerAssetId': trade.get('maker_asset_id', ''),
            'takerAssetId': trade.get('taker_asset_id', ''),
            'size': maker_amount,  # Use maker amount as size
            'price': 0.5,  # Default price (we don't have this in orderbook data)
            'volume_usd': volume_usd,
            'side': side,  # Add side field for detector compatibility
            'fee': int(trade.get('fee', 0)) / 1e6,
            'transactionHash': trade.get('transaction_hash', ''),
        }

    def _get_or_create_market_state(self, market_id: str) -> MarketState:
        """Get existing market state or create new one"""
        if market_id not in self.market_states:
            self.market_states[market_id] = MarketState(market_id=market_id)
        return self.market_states[market_id]

    def _run_detectors(
        self,
        market_id: str,
        market_state: MarketState
    ) -> List[VirtualAlert]:
        """
        Run all detectors on current market state.

        Args:
            market_id: Market identifier
            market_state: Current market state

        Returns:
            List of virtual alerts generated
        """
        alerts = []

        # Get recent trades for detection
        recent_trades = list(market_state.trade_history)

        if not recent_trades:
            return alerts

        # Run each detector
        for detector_name, detector in self.detectors.items():
            try:
                # Different detectors have different methods
                if detector_name == 'volume':
                    result = detector.analyze_volume_pattern(
                        trades=recent_trades,
                        market_id=market_id
                    )
                elif detector_name == 'whale':
                    result = detector.detect_whale_activity(trades=recent_trades)
                elif detector_name == 'price':
                    result = detector.detect_price_movement(
                        trades=recent_trades,
                        window_minutes=60
                    )
                elif detector_name == 'coordination':
                    result = detector.detect_coordinated_buying(trades=recent_trades)
                else:
                    continue

                # Check if detection triggered
                if result and result.get('anomaly', False):
                    alert = VirtualAlert(
                        alert_id=f"sim_{market_id}_{detector_name}_{len(self.virtual_alerts)}",
                        timestamp=self.current_time,
                        market_id=market_id,
                        detector_type=detector_name,
                        severity=result.get('severity', 'MEDIUM'),
                        analysis=result,
                        confidence_score=result.get('confidence_score', 0.0),
                        price_at_alert=result.get('current_price'),
                        predicted_direction=self._infer_direction(detector_name, result)
                    )

                    alerts.append(alert)
                    self.alerts_by_detector[detector_name] += 1
                    self.alerts_by_severity[alert.severity] += 1

                    logger.debug(
                        f"🚨 Virtual alert: {detector_name} on {market_id[:10]}... "
                        f"(confidence: {alert.confidence_score:.2f})"
                    )

            except Exception as e:
                logger.warning(f"Detector {detector_name} failed: {e}")
                continue

        return alerts

    def _infer_direction(self, detector_type: str, result: Dict) -> str:
        """Infer predicted price direction from detection result"""
        # For volume spikes and whale activity, predict BUY
        if detector_type in ['volume', 'whale', 'coordination']:
            return 'BUY'

        # For price movements, use the trend
        if detector_type == 'price':
            momentum = result.get('momentum', 0)
            return 'BUY' if momentum > 0 else 'SELL'

        return 'BUY'  # Default

    def simulate_trades(
        self,
        trades: List[Dict],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict:
        """
        Simulate detection on a list of trades.

        Args:
            trades: List of trades from storage
            progress_callback: Optional callback(processed, total_alerts)

        Returns:
            Simulation statistics dictionary
        """
        logger.info(f"🎬 Starting simulation with {len(trades)} trades")

        start_time = datetime.now()
        alerts_generated = 0

        # Process trades chronologically
        for i, trade in enumerate(trades):
            # Convert trade format
            converted_trade = self._convert_trade_format(trade)

            # Update current time
            self.current_time = datetime.fromtimestamp(
                trade['timestamp'],
                timezone.utc
            )

            # Determine market ID (use maker_asset_id as market identifier)
            market_id = trade.get('maker_asset_id', 'unknown')

            # Update market state
            market_state = self._get_or_create_market_state(market_id)
            market_state.add_trade(converted_trade)

            self.total_trades_processed += 1
            self.trades_by_market[market_id] += 1

            # Run detectors periodically (not on every trade for performance)
            # For backtesting: run every 50 trades to balance speed vs granularity
            should_detect = (
                (i % 50 == 0) or
                (len(market_state.trade_history) >= 100)
            )

            if should_detect:
                new_alerts = self._run_detectors(market_id, market_state)
                self.virtual_alerts.extend(new_alerts)
                alerts_generated += len(new_alerts)

            # Progress callback with more frequent updates for better UX
            if progress_callback and (i % 100 == 0 or i == len(trades) - 1):
                progress_callback(i + 1, len(self.virtual_alerts))

        elapsed = (datetime.now() - start_time).total_seconds()

        stats = {
            'total_trades': len(trades),
            'unique_markets': len(self.market_states),
            'total_alerts': len(self.virtual_alerts),
            'alerts_by_detector': dict(self.alerts_by_detector),
            'alerts_by_severity': dict(self.alerts_by_severity),
            'simulation_time': elapsed,
            'trades_per_second': len(trades) / elapsed if elapsed > 0 else 0,
            'mode': 'sequential'
        }

        logger.info(
            f"✅ Simulation complete: {len(trades)} trades, "
            f"{len(self.virtual_alerts)} alerts, {elapsed:.1f}s"
        )

        return stats

    def get_alerts(
        self,
        detector_type: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[VirtualAlert]:
        """
        Get virtual alerts with optional filtering.

        Args:
            detector_type: Filter by detector type
            severity: Filter by severity
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            List of filtered alerts
        """
        alerts = self.virtual_alerts

        if detector_type:
            alerts = [a for a in alerts if a.detector_type == detector_type]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if start_time:
            alerts = [a for a in alerts if a.timestamp >= start_time]

        if end_time:
            alerts = [a for a in alerts if a.timestamp <= end_time]

        return alerts

    def get_market_state(self, market_id: str) -> Optional[MarketState]:
        """Get state for a specific market"""
        return self.market_states.get(market_id)

    def simulate_trades_batch(
        self,
        trades: List[Dict],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict:
        """
        Simulate detection on trades using batch processing (faster).

        Groups trades by market and processes each market completely before
        moving to the next. Much faster for large datasets but loses
        cross-market temporal context.

        Args:
            trades: List of trades from storage
            progress_callback: Optional callback(markets_processed, total_alerts)

        Returns:
            Simulation statistics dictionary
        """
        logger.info(f"🎬 Starting batch simulation with {len(trades)} trades")

        start_time = datetime.now()

        # Group trades by market
        from collections import defaultdict
        trades_by_market = defaultdict(list)

        for trade in trades:
            market_id = trade.get('maker_asset_id', 'unknown')
            trades_by_market[market_id].append(trade)

        total_markets = len(trades_by_market)
        logger.info(f"📊 Grouped into {total_markets} markets")

        # Process each market
        for market_idx, (market_id, market_trades) in enumerate(trades_by_market.items(), 1):
            # Sort trades chronologically within market
            market_trades.sort(key=lambda t: t['timestamp'])

            # Get or create market state
            market_state = self._get_or_create_market_state(market_id)

            # Add all trades to market state
            for trade in market_trades:
                converted_trade = self._convert_trade_format(trade)
                market_state.add_trade(converted_trade)
                self.total_trades_processed += 1
                self.trades_by_market[market_id] += 1

                # Update current time
                self.current_time = datetime.fromtimestamp(
                    trade['timestamp'],
                    timezone.utc
                )

            # Run detectors once for this market
            new_alerts = self._run_detectors(market_id, market_state)
            self.virtual_alerts.extend(new_alerts)

            # Progress callback
            if progress_callback:
                progress_callback(market_idx, len(self.virtual_alerts))

        elapsed = (datetime.now() - start_time).total_seconds()

        stats = {
            'total_trades': len(trades),
            'unique_markets': len(self.market_states),
            'total_alerts': len(self.virtual_alerts),
            'alerts_by_detector': dict(self.alerts_by_detector),
            'alerts_by_severity': dict(self.alerts_by_severity),
            'simulation_time': elapsed,
            'trades_per_second': len(trades) / elapsed if elapsed > 0 else 0,
            'mode': 'batch'
        }

        logger.info(
            f"✅ Batch simulation complete: {len(trades)} trades, "
            f"{len(self.virtual_alerts)} alerts, {elapsed:.1f}s"
        )

        return stats

    def get_simulation_stats(self) -> Dict:
        """Get comprehensive simulation statistics"""
        return {
            'total_trades_processed': self.total_trades_processed,
            'unique_markets': len(self.market_states),
            'total_alerts': len(self.virtual_alerts),
            'alerts_by_detector': dict(self.alerts_by_detector),
            'alerts_by_severity': dict(self.alerts_by_severity),
            'trades_by_market': dict(self.trades_by_market),
            'avg_trades_per_market': (
                self.total_trades_processed / len(self.market_states)
                if self.market_states else 0
            ),
            'alert_rate': (
                len(self.virtual_alerts) / self.total_trades_processed
                if self.total_trades_processed > 0 else 0
            )
        }

    def calculate_alert_outcomes(self, interval_hours: List[int] = [1, 4, 24]):
        """
        Calculate outcomes for all alerts by tracking price movements.

        This simulates tracking price at intervals after each alert using
        the market state data collected during simulation.

        Args:
            interval_hours: List of hours to check (default: [1, 4, 24])
        """
        if not self.track_outcomes or not self.outcome_tracker:
            logger.warning("Outcome tracking is disabled")
            return

        logger.info(f"📊 Calculating outcomes for {len(self.virtual_alerts)} alerts...")

        for alert in self.virtual_alerts:
            # Track this alert
            self.outcome_tracker.track_alert(
                alert_id=alert.alert_id,
                market_id=alert.market_id,
                alert_timestamp=alert.timestamp,
                predicted_direction=alert.predicted_direction,
                confidence_score=alert.confidence_score,
                price_at_alert=alert.price_at_alert,
                detector_type=alert.detector_type,
                severity=alert.severity
            )

            # Get market state for this alert
            market_state = self.market_states.get(alert.market_id)
            if not market_state:
                continue

            # Calculate prices at intervals
            for hours in interval_hours:
                target_time = alert.timestamp + timedelta(hours=hours)
                price = self._estimate_price_at_time(
                    market_state,
                    target_time,
                    storage=self.storage  # Pass storage for database queries
                )

                if price is not None:
                    interval_key = f"{hours}h"
                    self.outcome_tracker.update_price_at_interval(
                        alert_id=alert.alert_id,
                        interval=interval_key,
                        price=price,
                        timestamp=target_time
                    )

        logger.info(f"✅ Calculated outcomes for {len(self.outcome_tracker.outcomes)} alerts")

    def _estimate_price_at_time(
        self,
        market_state: MarketState,
        target_time: datetime,
        storage: Optional['HistoricalTradeStorage'] = None
    ) -> Optional[float]:
        """
        Estimate market price at a specific time from trade history.

        First tries market's own trade history, then queries database for
        any trades near target time if storage is provided.

        Args:
            market_state: Market state with trade history
            target_time: Time to estimate price for
            storage: Optional historical storage for database queries

        Returns:
            Estimated price or None if not enough data
        """
        target_ts = target_time.timestamp()

        # First try: Check market's own trade history
        if market_state.trade_history:
            trades_before = [
                t for t in market_state.trade_history
                if t['timestamp'] <= target_ts
            ]
            trades_after = [
                t for t in market_state.trade_history
                if t['timestamp'] > target_ts
            ]

            # If we have exact or nearby trades, use price
            if trades_after and len(trades_after) > 0:
                return trades_after[0]['price']
            elif trades_before and len(trades_before) > 0:
                return trades_before[-1]['price']

        # Second try: Query database for ANY trades near target time
        if storage:
            try:
                # Query trades within ±5 min window of target time across all markets
                window_start = target_time - timedelta(minutes=5)
                window_end = target_time + timedelta(minutes=5)

                nearby_trades = storage.get_trades_by_time_range(
                    start_timestamp=int(window_start.timestamp()),
                    end_timestamp=int(window_end.timestamp()),
                    limit=10
                )

                if nearby_trades:
                    # Use most recent trade's price
                    logger.debug(f"Found {len(nearby_trades)} trades near {target_time} from database")
                    return nearby_trades[-1].get('price', 0.5)
            except Exception as e:
                logger.debug(f"Could not query storage for price at {target_time}: {e}")

        # Last resort: Default to 0.5 (midpoint for binary markets)
        logger.debug(f"No price data found for {target_time}, using default 0.5")
        return 0.5

    def calculate_metrics(
        self,
        interval: str = '24h',
        min_confidence: Optional[float] = None
    ):
        """
        Calculate performance metrics from tracked outcomes.

        Args:
            interval: Time interval to analyze ('1h', '4h', '24h')
            min_confidence: Optional minimum confidence threshold

        Returns:
            PerformanceMetrics object with all calculated metrics
        """
        if not self.track_outcomes or not self.metrics_calculator:
            logger.warning("Metrics tracking is disabled")
            return None

        if not self.outcome_tracker:
            logger.warning("No outcome tracker available")
            return None

        outcomes = self.outcome_tracker.get_all_outcomes()
        metrics = self.metrics_calculator.calculate_metrics(
            outcomes=outcomes,
            interval=interval,
            min_confidence=min_confidence
        )

        return metrics

    def export_metrics_to_json(self, filepath: str, interval: str = '24h'):
        """
        Export performance metrics to JSON file.

        Args:
            filepath: Path to save metrics JSON
            interval: Time interval for metrics
        """
        if not self.track_outcomes:
            logger.warning("Outcome tracking is disabled, no metrics to export")
            return

        metrics = self.calculate_metrics(interval=interval)
        if not metrics:
            logger.warning("No metrics available to export")
            return

        metrics_dict = self.metrics_calculator.export_metrics_to_dict(metrics)

        with open(filepath, 'w') as f:
            json.dump(metrics_dict, f, indent=2)

        logger.info(f"📊 Exported metrics to {filepath}")

    def export_outcomes_to_json(self, filepath: str):
        """Export alert outcomes to JSON file"""
        if not self.track_outcomes or not self.outcome_tracker:
            logger.warning("Outcome tracking is disabled")
            return

        outcomes_data = self.outcome_tracker.export_to_dict()

        with open(filepath, 'w') as f:
            json.dump(outcomes_data, f, indent=2)

        logger.info(f"📊 Exported {len(outcomes_data)} outcomes to {filepath}")

    def export_alerts_to_json(self, filepath: str):
        """Export virtual alerts to JSON file"""
        import numpy as np

        def convert_numpy_types(obj):
            """Recursively convert numpy types to native Python types"""
            if isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_numpy_types(item) for item in obj]
            return obj

        alerts_data = [
            {
                'alert_id': alert.alert_id,
                'timestamp': alert.timestamp.isoformat(),
                'market_id': alert.market_id,
                'detector_type': alert.detector_type,
                'severity': alert.severity,
                'confidence_score': alert.confidence_score,
                'price_at_alert': alert.price_at_alert,
                'predicted_direction': alert.predicted_direction,
                'analysis': convert_numpy_types(alert.analysis)
            }
            for alert in self.virtual_alerts
        ]

        with open(filepath, 'w') as f:
            json.dump(alerts_data, f, indent=2)

        logger.info(f"📁 Exported {len(alerts_data)} alerts to {filepath}")


def main():
    """Demo simulation engine"""
    from backtesting import HistoricalTradeStorage
    from config.settings import Settings

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n" + "="*70)
    print("SIMULATION ENGINE - Demo")
    print("="*70)

    # Load configuration
    settings = Settings()
    # Convert settings to config dict expected by detectors (matches market_monitor.py structure)
    config = {
        'detection': {
            'volume_thresholds': {
                'volume_spike_multiplier': settings.detection.volume_spike_multiplier,
                'z_score_threshold': settings.detection.z_score_threshold
            },
            'whale_thresholds': {
                'whale_threshold_usd': settings.detection.whale_threshold_usd,
                'coordination_threshold': settings.detection.coordination_threshold,
                'min_whales_for_coordination': settings.detection.min_whales_for_coordination
            },
            'price_thresholds': {
                'rapid_movement_pct': settings.detection.rapid_movement_pct,
                'price_movement_std': settings.detection.price_movement_std,
                'volatility_spike_multiplier': settings.detection.volatility_spike_multiplier,
                'momentum_threshold': settings.detection.momentum_threshold
            },
            'coordination_thresholds': {
                'min_coordinated_wallets': settings.detection.min_coordinated_wallets,
                'coordination_time_window': settings.detection.coordination_time_window,
                'directional_bias_threshold': settings.detection.directional_bias_threshold,
                'burst_intensity_threshold': settings.detection.burst_intensity_threshold
            }
        }
    }

    # Load detectors
    from detection.volume_detector import VolumeDetector
    from detection.whale_detector import WhaleDetector

    detectors = {
        'volume': VolumeDetector(config),
        'whale': WhaleDetector(config)
    }

    # Create simulation engine
    engine = SimulationEngine(config=config, detectors=detectors)

    # Load some historical trades
    with HistoricalTradeStorage("demo_backtest.db") as storage:
        # Get last 1000 trades
        time_range = storage.get_time_range()

        if not time_range:
            print("❌ No historical data found. Run data_loader.py first.")
            return

        trades = storage.get_trades_by_time_range(
            start_timestamp=time_range[0],
            end_timestamp=time_range[1],
            limit=1000
        )

        print(f"\nLoaded {len(trades)} trades for simulation")

    # Run simulation
    def progress(processed, alerts):
        if processed % 100 == 0:
            print(f"  Processed: {processed}, Alerts: {alerts}")

    stats = engine.simulate_trades(trades, progress_callback=progress)

    # Display results
    print("\n" + "="*70)
    print("SIMULATION RESULTS")
    print("="*70)
    print(f"Trades Processed: {stats['total_trades']}")
    print(f"Unique Markets: {stats['unique_markets']}")
    print(f"Total Alerts: {stats['total_alerts']}")
    print(f"Alert Rate: {stats['total_alerts'] / stats['total_trades'] * 100:.2f}%")
    print(f"Simulation Time: {stats['simulation_time']:.1f}s")
    print(f"Speed: {stats['trades_per_second']:.0f} trades/sec")

    print("\nAlerts by Detector:")
    for detector, count in stats['alerts_by_detector'].items():
        print(f"  {detector}: {count}")

    print("\nAlerts by Severity:")
    for severity, count in stats['alerts_by_severity'].items():
        print(f"  {severity}: {count}")

    # Export alerts
    engine.export_alerts_to_json("simulation_alerts.json")
    print(f"\n✅ Alerts exported to simulation_alerts.json")


if __name__ == "__main__":
    main()
