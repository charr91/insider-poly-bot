"""
Configuration Tester - A/B Testing Framework

Systematically test detector configurations and identify optimal parameters.
"""

import logging
import json
import copy
from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
import statistics

from .config_variant import ConfigurationVariant
from .simulation_engine import SimulationEngine
from .metrics_calculator import PerformanceMetrics, MetricsCalculator
from .historical_storage import HistoricalTradeStorage

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Results from testing a single configuration variant"""

    variant_name: str
    config: Dict[str, Any]
    metrics: PerformanceMetrics
    alert_count: int
    simulation_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Export test result to dictionary"""
        metrics_calc = MetricsCalculator()
        return {
            'variant_name': self.variant_name,
            'config': self.config,
            'metrics': metrics_calc.export_metrics_to_dict(self.metrics),
            'alert_count': self.alert_count,
            'simulation_time': self.simulation_time,
            'metadata': self.metadata
        }


@dataclass
class ComparisonResult:
    """Results from comparing multiple configuration variants"""

    variants_tested: int
    best_variant: str
    ranking: List[Tuple[str, float]]  # [(variant_name, score), ...]
    detailed_comparison: Dict[str, Dict[str, Any]]
    recommendation: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Export comparison result to dictionary"""
        return {
            'variants_tested': self.variants_tested,
            'best_variant': self.best_variant,
            'ranking': self.ranking,
            'detailed_comparison': self.detailed_comparison,
            'recommendation': self.recommendation,
            'timestamp': self.timestamp
        }


class ConfigurationTester:
    """
    A/B testing framework for detector configurations.

    Runs simulations with different parameter configurations and compares
    their performance using statistical metrics.
    """

    def __init__(
        self,
        db_path: str,
        detectors: Optional[Dict] = None,
        interval: str = '24h',
        interval_hours: List[int] = None,
        outcome_price_threshold: float = 0.05
    ):
        """
        Initialize configuration tester.

        Args:
            db_path: Path to historical trade database
            detectors: Optional detector instances (will be recreated for each config)
            interval: Time interval for metrics calculation ('1h', '4h', '24h')
            interval_hours: Hours to track outcomes (default: [1, 4, 24])
            outcome_price_threshold: Price change threshold for outcome validation (default: 5%)
        """
        self.db_path = db_path
        self.storage = HistoricalTradeStorage(db_path)
        self.base_detectors = detectors
        self.interval = interval
        self.interval_hours = interval_hours or [1, 4, 24]
        self.outcome_price_threshold = outcome_price_threshold

        # Test state
        self.variants: Dict[str, ConfigurationVariant] = {}
        self.results: Dict[str, TestResult] = {}

    def add_variant(self, variant: ConfigurationVariant):
        """
        Add a configuration variant to test.

        Args:
            variant: Configuration variant to test
        """
        if variant.name in self.variants:
            logger.warning(f"Variant '{variant.name}' already exists, replacing it")

        self.variants[variant.name] = variant
        logger.info(f"Added variant: {variant.name} - {variant.description}")

    def add_variants(self, variants: List[ConfigurationVariant]):
        """
        Add multiple configuration variants to test.

        Args:
            variants: List of configuration variants
        """
        for variant in variants:
            self.add_variant(variant)

    def run_tests(
        self,
        market_ids: Optional[List[str]] = None,
        days_back: Optional[int] = None,
        batch_mode: bool = True,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, TestResult]:
        """
        Run simulations for all configured variants.

        Args:
            market_ids: Optional list of specific market IDs to test
            days_back: Optional number of days to limit test data
            batch_mode: Use batch mode for faster simulation
            progress_callback: Optional callback(variant_name, current, total)

        Returns:
            Dictionary mapping variant names to test results
        """
        if not self.variants:
            raise ValueError("No variants configured. Add variants before running tests.")

        logger.info(f"Starting A/B tests for {len(self.variants)} variants...")

        total_variants = len(self.variants)
        for idx, (name, variant) in enumerate(self.variants.items(), 1):
            logger.info(f"\n[{idx}/{total_variants}] Testing variant: {name}")

            if progress_callback:
                progress_callback(name, idx, total_variants)

            # Run simulation for this variant
            result = self._run_single_test(
                variant=variant,
                market_ids=market_ids,
                days_back=days_back,
                batch_mode=batch_mode
            )

            self.results[name] = result

            # Log summary
            logger.info(f"  Alerts: {result.alert_count}")
            logger.info(f"  Precision: {result.metrics.precision:.2%}")
            logger.info(f"  ROI: {result.metrics.roi:+.2%}")
            logger.info(f"  F1 Score: {result.metrics.f1_score:.2%}")

        logger.info(f"\n✅ Completed all {total_variants} tests")
        return self.results

    def _run_single_test(
        self,
        variant: ConfigurationVariant,
        market_ids: Optional[List[str]],
        days_back: Optional[int],
        batch_mode: bool
    ) -> TestResult:
        """
        Run simulation for a single configuration variant.

        Args:
            variant: Configuration variant to test
            market_ids: Optional market IDs filter
            days_back: Optional days back limit
            batch_mode: Use batch mode

        Returns:
            Test result with metrics
        """
        start_time = datetime.now(timezone.utc)

        # Create simulation engine with variant config
        # Note: We need to merge variant config with detection config structure
        full_config = {
            'detection': variant.config
        }

        # Create detectors with the variant configuration
        from detection.whale_detector import WhaleDetector
        from detection.volume_detector import VolumeDetector
        from detection.price_detector import PriceDetector
        from detection.coordination_detector import CoordinationDetector

        variant_detectors = {}

        # Only create detectors if their config exists in variant
        if 'whale_thresholds' in variant.config:
            try:
                variant_detectors['whale'] = WhaleDetector(full_config)
            except Exception as e:
                logger.warning(f"Could not create WhaleDetector: {e}")

        if 'volume_thresholds' in variant.config:
            try:
                variant_detectors['volume'] = VolumeDetector(full_config)
            except Exception as e:
                logger.warning(f"Could not create VolumeDetector: {e}")

        if 'price_thresholds' in variant.config:
            try:
                variant_detectors['price'] = PriceDetector(full_config)
            except Exception as e:
                logger.warning(f"Could not create PriceDetector: {e}")

        if 'coordination_thresholds' in variant.config:
            try:
                variant_detectors['coordination'] = CoordinationDetector(full_config)
            except Exception as e:
                logger.warning(f"Could not create CoordinationDetector: {e}")

        engine = SimulationEngine(
            config=full_config,
            detectors=variant_detectors,
            track_outcomes=True,
            outcome_price_threshold=self.outcome_price_threshold,
            storage=self.storage
        )

        # Load trades
        time_range = self.storage.get_time_range()

        if not time_range:
            raise ValueError("No trades found in database")

        # Calculate time range if days_back is specified
        if days_back:
            import time
            end_ts = time_range[1]
            start_ts = end_ts - (days_back * 86400)  # Convert days to seconds
        else:
            start_ts, end_ts = time_range

        # Load all trades in the time range
        all_trades = self.storage.get_trades_by_time_range(
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            limit=None  # Get all trades
        )

        if not all_trades:
            raise ValueError(f"No trades found in time range")

        # Filter by market_ids if specified
        if market_ids:
            all_trades = [
                t for t in all_trades
                if t.get('maker_asset_id') in market_ids or t.get('taker_asset_id') in market_ids
            ]

        # Run simulation
        if batch_mode:
            engine.simulate_trades_batch(all_trades)
        else:
            engine.simulate_trades(all_trades)

        # Calculate outcomes and metrics
        engine.calculate_alert_outcomes(interval_hours=self.interval_hours)
        metrics = engine.calculate_metrics(interval=self.interval)

        # Calculate simulation time
        end_time = datetime.now(timezone.utc)
        simulation_time = (end_time - start_time).total_seconds()

        # Create result
        result = TestResult(
            variant_name=variant.name,
            config=variant.config,
            metrics=metrics,
            alert_count=len(engine.virtual_alerts),
            simulation_time=simulation_time,
            metadata={
                'description': variant.description,
                'tags': variant.tags,
                'total_trades': len(all_trades)
            }
        )

        return result

    def compare_results(
        self,
        rank_by: str = 'f1_score',
        min_alerts: int = 5
    ) -> ComparisonResult:
        """
        Compare results from all tested variants.

        Args:
            rank_by: Metric to rank by ('precision', 'recall', 'f1_score', 'roi', 'sharpe_ratio')
            min_alerts: Minimum alerts required for valid comparison

        Returns:
            Comparison result with ranking and recommendation
        """
        if not self.results:
            raise ValueError("No test results available. Run tests first.")

        logger.info(f"\n📊 Comparing {len(self.results)} variants (ranked by {rank_by})...")

        # Filter variants with sufficient alerts
        valid_results = {
            name: result for name, result in self.results.items()
            if result.alert_count >= min_alerts
        }

        if not valid_results:
            raise ValueError(f"No variants produced at least {min_alerts} alerts")

        if len(valid_results) < len(self.results):
            excluded = len(self.results) - len(valid_results)
            logger.warning(f"⚠️  Excluded {excluded} variants with < {min_alerts} alerts")

        # Extract metric values and rank
        metric_values = {}
        for name, result in valid_results.items():
            metric_values[name] = self._get_metric_value(result.metrics, rank_by)

        # Sort by metric (descending for most metrics)
        reverse_sort = rank_by not in ['precision', 'recall']  # Most metrics are "higher is better"
        ranked = sorted(metric_values.items(), key=lambda x: x[1], reverse=not reverse_sort)

        best_variant = ranked[0][0]
        best_score = ranked[0][1]

        # Create detailed comparison
        detailed_comparison = self._create_detailed_comparison(valid_results, ranked)

        # Generate recommendation
        recommendation = self._generate_recommendation(
            best_variant=best_variant,
            best_score=best_score,
            rank_by=rank_by,
            results=valid_results
        )

        comparison = ComparisonResult(
            variants_tested=len(valid_results),
            best_variant=best_variant,
            ranking=ranked,
            detailed_comparison=detailed_comparison,
            recommendation=recommendation
        )

        return comparison

    def _get_metric_value(self, metrics: PerformanceMetrics, metric_name: str) -> float:
        """Extract metric value by name"""
        metric_map = {
            'precision': metrics.precision,
            'recall': metrics.recall,
            'f1_score': metrics.f1_score,
            'accuracy': metrics.accuracy,
            'roi': metrics.roi,
            'win_rate': metrics.win_rate,
            'average_return': metrics.average_return,
            'sharpe_ratio': metrics.sharpe_ratio
        }

        if metric_name not in metric_map:
            raise ValueError(f"Unknown metric: {metric_name}")

        return metric_map[metric_name]

    def _create_detailed_comparison(
        self,
        results: Dict[str, TestResult],
        ranking: List[Tuple[str, float]]
    ) -> Dict[str, Dict[str, Any]]:
        """Create detailed comparison table"""
        comparison = {}

        for rank, (name, score) in enumerate(ranking, 1):
            result = results[name]
            metrics = result.metrics

            comparison[name] = {
                'rank': rank,
                'description': result.metadata.get('description', ''),
                'metrics': {
                    'precision': metrics.precision,
                    'recall': metrics.recall,
                    'f1_score': metrics.f1_score,
                    'accuracy': metrics.accuracy,
                    'roi': metrics.roi,
                    'win_rate': metrics.win_rate,
                    'average_return': metrics.average_return,
                    'sharpe_ratio': metrics.sharpe_ratio
                },
                'alert_count': result.alert_count,
                'confusion_matrix': {
                    'true_positives': metrics.true_positives,
                    'false_positives': metrics.false_positives,
                    'true_negatives': metrics.true_negatives,
                    'false_negatives': metrics.false_negatives
                },
                'simulation_time': result.simulation_time,
                'config_summary': self._summarize_config(result.config)
            }

        return comparison

    def _summarize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create human-readable config summary"""
        summary = {}

        if 'whale_thresholds' in config:
            summary['whale'] = {
                k: v for k, v in config['whale_thresholds'].items()
            }

        if 'volume_thresholds' in config:
            summary['volume'] = {
                k: v for k, v in config['volume_thresholds'].items()
            }

        if 'price_thresholds' in config:
            summary['price'] = {
                k: v for k, v in config['price_thresholds'].items()
            }

        if 'coordination_thresholds' in config:
            summary['coordination'] = {
                k: v for k, v in config['coordination_thresholds'].items()
            }

        return summary

    def _generate_recommendation(
        self,
        best_variant: str,
        best_score: float,
        rank_by: str,
        results: Dict[str, TestResult]
    ) -> str:
        """Generate recommendation text"""
        result = results[best_variant]
        metrics = result.metrics

        recommendation = f"🏆 Best Configuration: '{best_variant}'\n\n"
        recommendation += f"Ranked by: {rank_by} = {best_score:.2%}\n\n"

        recommendation += "Performance Summary:\n"
        recommendation += f"  • Precision: {metrics.precision:.2%} "
        recommendation += f"({metrics.true_positives} TP / {metrics.true_positives + metrics.false_positives} predicted positive)\n"
        recommendation += f"  • Recall: {metrics.recall:.2%} "
        recommendation += f"({metrics.true_positives} TP / {metrics.true_positives + metrics.false_negatives} actual positive)\n"
        recommendation += f"  • F1 Score: {metrics.f1_score:.2%}\n"
        recommendation += f"  • ROI: {metrics.roi:+.2%}\n"
        recommendation += f"  • Win Rate: {metrics.win_rate:.2%}\n"
        recommendation += f"  • Sharpe Ratio: {metrics.sharpe_ratio:.2f}\n"
        recommendation += f"  • Total Alerts: {result.alert_count}\n\n"

        recommendation += f"Description: {result.metadata.get('description', 'N/A')}\n"

        return recommendation

    def print_comparison_report(self, comparison: ComparisonResult):
        """Print formatted comparison report to console"""
        print("\n" + "=" * 80)
        print("  CONFIGURATION A/B TEST RESULTS")
        print("=" * 80)

        print(f"\nVariants Tested: {comparison.variants_tested}")
        print(f"Timestamp: {comparison.timestamp}")

        # Print ranking table
        print("\n" + "-" * 80)
        print("RANKING")
        print("-" * 80)

        print(f"\n{'Rank':<6} {'Variant':<20} {'Precision':<12} {'Recall':<12} {'F1 Score':<12} {'ROI':<12} {'Alerts':<8}")
        print("-" * 80)

        for rank, (name, score) in enumerate(comparison.ranking, 1):
            details = comparison.detailed_comparison[name]
            m = details['metrics']

            print(f"{rank:<6} {name:<20} {m['precision']:<12.2%} {m['recall']:<12.2%} "
                  f"{m['f1_score']:<12.2%} {m['roi']:<12.2%} {details['alert_count']:<8}")

        # Print recommendation
        print("\n" + "-" * 80)
        print("RECOMMENDATION")
        print("-" * 80)
        print(f"\n{comparison.recommendation}")

    def export_results(
        self,
        filepath: str,
        include_full_config: bool = False
    ):
        """
        Export all test results to JSON file.

        Args:
            filepath: Output file path
            include_full_config: Include full configuration in export
        """
        metrics_calc = MetricsCalculator()

        export_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'interval': self.interval,
            'total_variants': len(self.results),
            'results': {}
        }

        for name, result in self.results.items():
            export_data['results'][name] = {
                'variant_name': result.variant_name,
                'metrics': metrics_calc.export_metrics_to_dict(result.metrics),
                'alert_count': result.alert_count,
                'simulation_time': result.simulation_time,
                'metadata': result.metadata
            }

            if include_full_config:
                export_data['results'][name]['config'] = result.config
            else:
                export_data['results'][name]['config_summary'] = self._summarize_config(result.config)

        # Write to file
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"📁 Exported results to: {filepath}")

    def export_comparison(self, comparison: ComparisonResult, filepath: str):
        """
        Export comparison results to JSON file.

        Args:
            comparison: Comparison result to export
            filepath: Output file path
        """
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(comparison.to_dict(), f, indent=2)

        logger.info(f"📁 Exported comparison to: {filepath}")

    def get_best_config(self, rank_by: str = 'f1_score') -> ConfigurationVariant:
        """
        Get the best performing configuration variant.

        Args:
            rank_by: Metric to rank by

        Returns:
            Best configuration variant
        """
        if not self.results:
            raise ValueError("No test results available")

        comparison = self.compare_results(rank_by=rank_by)
        best_name = comparison.best_variant

        return self.variants[best_name]
