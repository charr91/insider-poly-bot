#!/usr/bin/env python
"""
End-to-End Backtesting Demo

Comprehensive demonstration of the backtesting framework:
1. Load historical trade data from The Graph
2. Run simulation through detection algorithms
3. Analyze and display results
4. Generate validation report

Usage:
    python backtesting/demo_end_to_end.py [--days DAYS] [--db PATH] [--detectors NAMES]
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtesting import (
    HistoricalDataLoader,
    HistoricalTradeStorage,
    SimulationEngine,
    VirtualAlert
)
from config.settings import Settings

logger = logging.getLogger(__name__)


class BacktestingDemo:
    """End-to-end backtesting demonstration"""

    def __init__(self, db_path: str = "demo_backtest.db"):
        self.db_path = db_path
        self.settings = Settings()
        self.loader = None
        self.storage = None
        self.engine = None
        self.alerts: List[VirtualAlert] = []

    def print_header(self, title: str):
        """Print formatted section header"""
        print("\n" + "=" * 80)
        print(f" {title}")
        print("=" * 80)

    def print_subheader(self, title: str):
        """Print formatted subsection header"""
        print(f"\n--- {title} ---")

    def step_1_load_data(self, days: int = 7, skip_prompt: bool = False):
        """Step 1: Load historical trade data"""
        self.print_header("STEP 1: Loading Historical Trade Data")

        print(f"\n📊 Data Source: The Graph - Polymarket Orderbook Subgraph")
        print(f"📅 Time Range: Last {days} days")
        print(f"💾 Database: {self.db_path}")

        # Create loader
        self.loader = HistoricalDataLoader(db_path=self.db_path)

        # Check existing data
        stats = self.loader.get_storage_stats()
        if stats['total_trades'] > 0:
            print(f"\n✅ Found existing data: {stats['total_trades']:,} trades")
            if not skip_prompt:
                try:
                    user_input = input("Load more data? (y/N): ").strip().lower()
                    if user_input != 'y':
                        print("Using existing data.")
                        return
                except EOFError:
                    print("Using existing data.")
                    return
            else:
                print("Using existing data (--yes flag)")
                return

        # Progress callback
        def progress(fetched, inserted, duplicates):
            if fetched % 1000 == 0 and fetched > 0:
                print(f"  Progress: {fetched:,} fetched, {inserted:,} inserted, {duplicates:,} duplicates")

        # Load data
        print(f"\n🔄 Fetching trades from The Graph (this may take a few minutes)...")
        load_stats = self.loader.load_days_back(days=days, progress_callback=progress)

        # Display load statistics
        self.print_subheader("Load Statistics")
        print(f"  Total Fetched:    {load_stats['total_fetched']:,}")
        print(f"  Total Inserted:   {load_stats['total_inserted']:,}")
        print(f"  Total Duplicates: {load_stats['total_duplicates']:,}")
        print(f"  Time Taken:       {load_stats['time_taken']:.1f}s")
        if load_stats['time_taken'] > 0:
            print(f"  Fetch Rate:       {load_stats['total_fetched'] / load_stats['time_taken']:.0f} trades/sec")

        # Display database statistics
        storage_stats = self.loader.get_storage_stats()
        self.print_subheader("Database Statistics")
        print(f"  Total Trades:     {storage_stats['total_trades']:,}")

        if 'oldest_timestamp' in storage_stats:
            oldest = datetime.fromtimestamp(storage_stats['oldest_timestamp'], timezone.utc)
            newest = datetime.fromtimestamp(storage_stats['newest_timestamp'], timezone.utc)
            print(f"  Date Range:       {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}")
            print(f"  Time Span:        {storage_stats['time_span_days']:.1f} days")

        print(f"  Unique Makers:    {storage_stats.get('unique_makers', 0):,}")
        print(f"  Unique Takers:    {storage_stats.get('unique_takers', 0):,}")
        print(f"  Database Size:    {storage_stats['database_size_mb']:.2f} MB")

        print("\n✅ Data loading complete!")

    def step_2_run_simulation(
        self,
        detector_names: List[str] = None,
        limit: int = 10000,
        batch_mode: bool = False
    ):
        """Step 2: Run simulation with detectors"""
        self.print_header("STEP 2: Running Detection Simulation")

        mode_name = "Batch" if batch_mode else "Sequential"
        print(f"\n⚙️  Mode: {mode_name} processing")

        # Default to all detectors if none specified
        if detector_names is None:
            detector_names = ['volume', 'whale']

        print(f"\n🔍 Detectors: {', '.join(detector_names)}")
        print(f"📊 Trade Limit: {limit:,} trades")

        # Load configuration - detectors expect nested threshold sections (matches market_monitor.py)
        config = {
            'detection': {
                'volume_thresholds': {
                    'volume_spike_multiplier': self.settings.detection.volume_spike_multiplier,
                    'z_score_threshold': self.settings.detection.z_score_threshold
                },
                'whale_thresholds': {
                    'whale_threshold_usd': self.settings.detection.whale_threshold_usd,
                    'coordination_threshold': self.settings.detection.coordination_threshold,
                    'min_whales_for_coordination': self.settings.detection.min_whales_for_coordination
                },
                'price_thresholds': {
                    'rapid_movement_pct': self.settings.detection.rapid_movement_pct,
                    'price_movement_std': self.settings.detection.price_movement_std,
                    'volatility_spike_multiplier': self.settings.detection.volatility_spike_multiplier,
                    'momentum_threshold': self.settings.detection.momentum_threshold
                },
                'coordination_thresholds': {
                    'min_coordinated_wallets': self.settings.detection.min_coordinated_wallets,
                    'coordination_time_window': self.settings.detection.coordination_time_window,
                    'directional_bias_threshold': self.settings.detection.directional_bias_threshold,
                    'burst_intensity_threshold': self.settings.detection.burst_intensity_threshold
                }
            }
        }

        # Load detectors
        detectors = {}
        try:
            if 'volume' in detector_names:
                from detection.volume_detector import VolumeDetector
                detectors['volume'] = VolumeDetector(config)
                print("  ✓ Volume detector loaded")
        except ImportError:
            logger.warning("VolumeDetector not available")

        try:
            if 'whale' in detector_names:
                from detection.whale_detector import WhaleDetector
                detectors['whale'] = WhaleDetector(config)
                print("  ✓ Whale detector loaded")
        except ImportError:
            logger.warning("WhaleDetector not available")

        try:
            if 'price' in detector_names:
                from detection.price_detector import PriceDetector
                detectors['price'] = PriceDetector(config)
                print("  ✓ Price detector loaded")
        except ImportError:
            logger.warning("PriceDetector not available")

        try:
            if 'coordination' in detector_names:
                from detection.coordination_detector import CoordinationDetector
                detectors['coordination'] = CoordinationDetector(config)
                print("  ✓ Coordination detector loaded")
        except ImportError:
            logger.warning("CoordinationDetector not available")

        if not detectors:
            print("  ⚠️  No detectors available, running simulation without detection")

        # Create simulation engine
        self.engine = SimulationEngine(config=config, detectors=detectors)

        # Load trades from database
        print(f"\n📖 Loading trades from database...")
        with HistoricalTradeStorage(self.db_path) as storage:
            time_range = storage.get_time_range()

            if not time_range:
                print("❌ No trades found in database. Run step 1 first.")
                sys.exit(1)

            trades = storage.get_trades_by_time_range(
                start_timestamp=time_range[0],
                end_timestamp=time_range[1],
                limit=limit
            )

            print(f"  Loaded {len(trades):,} trades for simulation")

        # Enhanced progress callback with ETA
        start_time = datetime.now()

        def progress(processed, alerts):
            if processed > 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = (len(trades) - processed) / rate if rate > 0 else 0
                pct = (processed / len(trades)) * 100

                print(
                    f"  Progress: {processed:,}/{len(trades):,} ({pct:.1f}%) | "
                    f"{rate:.0f} trades/sec | "
                    f"ETA: {int(remaining)}s | "
                    f"Alerts: {alerts:,}"
                )

        # Run simulation
        print(f"\n🚀 Running simulation...")
        if batch_mode:
            # Batch mode: faster, processes each market completely
            def batch_progress(markets_done, alerts):
                pct = (markets_done / stats['unique_markets'] * 100) if 'unique_markets' in locals() else 0
                print(f"  Progress: Market {markets_done}/{total_markets} | Alerts: {alerts:,}")

            # Pre-count markets for progress
            from collections import defaultdict
            markets_temp = defaultdict(int)
            for t in trades:
                markets_temp[t.get('maker_asset_id', 'unknown')] += 1
            total_markets = len(markets_temp)

            stats = self.engine.simulate_trades_batch(trades, progress_callback=batch_progress)
        else:
            # Sequential mode: maintains chronological order
            stats = self.engine.simulate_trades(trades, progress_callback=progress)

        # Store alerts for analysis
        self.alerts = self.engine.virtual_alerts

        # Display simulation results
        self.print_subheader("Simulation Results")
        print(f"  Mode:             {stats.get('mode', 'sequential').title()}")
        print(f"  Trades Processed: {stats['total_trades']:,}")
        print(f"  Unique Markets:   {stats['unique_markets']:,}")
        print(f"  Total Alerts:     {stats['total_alerts']:,}")
        if stats['total_trades'] > 0:
            print(f"  Alert Rate:       {stats['total_alerts'] / stats['total_trades'] * 100:.2f}%")
        print(f"  Simulation Time:  {stats['simulation_time']:.1f}s")
        if stats['simulation_time'] > 0:
            print(f"  Processing Speed: {stats['trades_per_second']:.0f} trades/sec")

        if stats['alerts_by_detector']:
            self.print_subheader("Alerts by Detector")
            for detector, count in stats['alerts_by_detector'].items():
                print(f"  {detector:12s}: {count:,}")

        if stats['alerts_by_severity']:
            self.print_subheader("Alerts by Severity")
            for severity, count in stats['alerts_by_severity'].items():
                print(f"  {severity:8s}: {count:,}")

        print("\n✅ Simulation complete!")

    def step_3_analyze_results(self):
        """Step 3: Analyze and display alert details"""
        self.print_header("STEP 3: Alert Analysis")

        if not self.alerts:
            print("\n⚠️  No alerts generated during simulation")
            return

        # Sort alerts by confidence score
        sorted_alerts = sorted(
            self.alerts,
            key=lambda a: a.confidence_score,
            reverse=True
        )

        # Display top 10 alerts
        self.print_subheader(f"Top 10 Alerts by Confidence Score")
        print(f"\n{'#':<4} {'Market':<12} {'Detector':<12} {'Severity':<8} {'Confidence':<10} {'Time'}")
        print("-" * 80)

        for i, alert in enumerate(sorted_alerts[:10], 1):
            market_short = alert.market_id[:10] + "..." if len(alert.market_id) > 10 else alert.market_id
            time_str = alert.timestamp.strftime("%Y-%m-%d %H:%M")
            print(
                f"{i:<4} {market_short:<12} {alert.detector_type:<12} "
                f"{alert.severity:<8} {alert.confidence_score:<10.2f} {time_str}"
            )

        # Show detailed example of highest confidence alert
        if sorted_alerts:
            self.print_subheader("Highest Confidence Alert Details")
            top_alert = sorted_alerts[0]
            print(f"\n  Alert ID:         {top_alert.alert_id}")
            print(f"  Market ID:        {top_alert.market_id}")
            print(f"  Detector:         {top_alert.detector_type}")
            print(f"  Severity:         {top_alert.severity}")
            print(f"  Confidence:       {top_alert.confidence_score:.2f}")
            print(f"  Timestamp:        {top_alert.timestamp}")
            if top_alert.price_at_alert:
                print(f"  Price at Alert:   ${top_alert.price_at_alert:.4f}")
            if top_alert.predicted_direction:
                print(f"  Predicted Move:   {top_alert.predicted_direction}")

            print(f"\n  Analysis Details:")
            for key, value in top_alert.analysis.items():
                if isinstance(value, float):
                    print(f"    {key}: {value:.4f}")
                else:
                    print(f"    {key}: {value}")

        # Market activity summary
        self.print_subheader("Market Activity Summary")
        market_alert_counts = {}
        for alert in self.alerts:
            market_alert_counts[alert.market_id] = market_alert_counts.get(alert.market_id, 0) + 1

        top_markets = sorted(market_alert_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"\n  Top 5 Markets by Alert Count:")
        for market, count in top_markets:
            market_short = market[:20] + "..." if len(market) > 20 else market
            print(f"    {market_short:<25} {count:,} alerts")

    def step_4_validation_report(self):
        """Step 4: Generate validation report and performance metrics"""
        self.print_header("STEP 4: Performance Metrics & Validation")

        if not self.alerts:
            print("\n⚠️  No alerts generated, skipping metrics calculation")
            return

        # Calculate alert outcomes
        print("\n📊 Calculating alert outcomes...")
        self.engine.calculate_alert_outcomes(interval_hours=[1, 4, 24])

        # Get completed outcomes count
        if self.engine.outcome_tracker:
            completed = len(self.engine.outcome_tracker.get_completed_outcomes())
            print(f"  ✓ Processed {completed} completed outcomes")

        # Calculate metrics
        print("\n📈 Calculating performance metrics...")
        metrics = self.engine.calculate_metrics(interval='24h')

        if metrics:
            # Display metrics report
            self.engine.metrics_calculator.print_metrics_report(metrics)

            # Export everything
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Export alerts
            alerts_file = f"backtesting/results/alerts_{timestamp}.json"
            self.engine.export_alerts_to_json(alerts_file)
            print(f"\n  ✓ Alerts exported to: {alerts_file}")

            # Export outcomes
            outcomes_file = f"backtesting/results/outcomes_{timestamp}.json"
            self.engine.export_outcomes_to_json(outcomes_file)
            print(f"  ✓ Outcomes exported to: {outcomes_file}")

            # Export metrics
            metrics_file = f"backtesting/results/metrics_{timestamp}.json"
            self.engine.export_metrics_to_json(metrics_file, interval='24h')
            print(f"  ✓ Metrics exported to: {metrics_file}")

            # Summary recommendations
            print("\n💡 Analysis Summary:")
            if metrics.precision >= 0.7:
                print(f"  ✅ High precision ({metrics.precision:.1%}) - alerts are reliable")
            elif metrics.precision >= 0.5:
                print(f"  ⚠️  Moderate precision ({metrics.precision:.1%}) - some false positives")
            else:
                print(f"  ❌ Low precision ({metrics.precision:.1%}) - many false positives")

            if metrics.win_rate >= 0.6:
                print(f"  ✅ Good win rate ({metrics.win_rate:.1%}) - profitable strategy")
            elif metrics.win_rate >= 0.5:
                print(f"  ⚠️  Break-even win rate ({metrics.win_rate:.1%})")
            else:
                print(f"  ❌ Low win rate ({metrics.win_rate:.1%}) - losing strategy")

            if metrics.f1_score >= 0.7:
                print(f"  ✅ Strong F1 score ({metrics.f1_score:.1%}) - balanced performance")
            else:
                print(f"  ⚠️  F1 score ({metrics.f1_score:.1%}) - room for improvement")

        else:
            print("\n⚠️  Could not calculate metrics - insufficient outcome data")
            print("  This may happen if:")
            print("    - Trade data doesn't cover full intervals (1h, 4h, 24h)")
            print("    - Markets don't have price movement data")
            print("    - No alerts were generated")

            # Still export alerts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            alerts_file = f"backtesting/results/alerts_{timestamp}.json"
            self.engine.export_alerts_to_json(alerts_file)
            print(f"\n  ✓ Alerts exported to: {alerts_file}")

        print("\n📚 Next Steps:")
        print("  - Review exported JSON files for detailed data")
        print("  - Adjust detector thresholds to improve precision/recall")
        print("  - Run with longer time ranges for more data")
        print("  - Test different confidence thresholds")

    def run(
        self,
        days: int = 7,
        limit: int = 10000,
        detectors: List[str] = None,
        batch_mode: bool = False,
        skip_prompt: bool = False
    ):
        """Run complete end-to-end demo"""
        self.print_header("🎬 Polymarket Backtesting Framework - End-to-End Demo")

        print("\n📋 Demo Pipeline:")
        print("   1. Load historical trade data from The Graph")
        print("   2. Run simulation with detection algorithms")
        print("   3. Analyze and display results")
        print("   4. Generate validation report")

        try:
            # Step 1: Load data
            self.step_1_load_data(days=days, skip_prompt=skip_prompt)

            # Step 2: Run simulation
            self.step_2_run_simulation(
                detector_names=detectors,
                limit=limit,
                batch_mode=batch_mode
            )

            # Step 3: Analyze results
            self.step_3_analyze_results()

            # Step 4: Validation report
            self.step_4_validation_report()

            # Final summary
            self.print_header("✅ Demo Complete!")
            print("\n🎉 All steps completed successfully!")
            print("\n📚 Next steps:")
            print("   - Review the exported JSON file for detailed alert data")
            print("   - Adjust detector thresholds in config/settings.py")
            print("   - Run again with different time ranges or detectors")
            print("   - Implement metrics collector for performance validation")

        except KeyboardInterrupt:
            print("\n\n⚠️  Demo interrupted by user")
            sys.exit(0)
        except Exception as e:
            print(f"\n\n❌ Error: {e}")
            logger.exception("Demo failed")
            sys.exit(1)
        finally:
            # Cleanup
            if self.loader:
                self.loader.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="End-to-end backtesting demonstration",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days of historical data to load (default: 7)'
    )

    parser.add_argument(
        '--db',
        type=str,
        default='demo_backtest.db',
        help='Database path (default: demo_backtest.db)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=10000,
        help='Maximum number of trades to simulate (default: 10000)'
    )

    parser.add_argument(
        '--detectors',
        type=str,
        nargs='+',
        default=['volume', 'whale'],
        help='Detectors to use (default: volume whale)'
    )

    parser.add_argument(
        '--batch',
        action='store_true',
        help='Use batch processing mode (faster, groups by market)'
    )

    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip prompts and use existing data'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run demo
    demo = BacktestingDemo(db_path=args.db)
    demo.run(
        days=args.days,
        limit=args.limit,
        detectors=args.detectors,
        batch_mode=args.batch,
        skip_prompt=args.yes
    )


if __name__ == "__main__":
    main()
