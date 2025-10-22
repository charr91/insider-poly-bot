#!/usr/bin/env python
"""
Configuration A/B Testing Demo

Demonstrates using the Configuration Tester to compare detector parameters
and find optimal settings.

Usage:
    python backtesting/demo_config_testing.py [--db PATH] [--days DAYS]
"""

import sys
import logging
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtesting import (
    ConfigurationVariant,
    VariantGenerator,
    ConfigurationTester
)
from config.settings import Settings

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class ConfigTestingDemo:
    """Demonstration of configuration A/B testing"""

    def __init__(self, db_path: str = "demo_backtest.db", outcome_threshold: float = 0.05):
        self.db_path = db_path
        self.outcome_threshold = outcome_threshold
        self.settings = Settings()
        self.tester = None

    def print_header(self, title: str):
        """Print formatted section header"""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)

    def print_subheader(self, title: str):
        """Print formatted subsection header"""
        print(f"\n--- {title} ---")

    def step_1_create_variants(self) -> list:
        """Step 1: Create configuration variants to test"""
        self.print_header("STEP 1: Creating Configuration Variants")

        # Create base config from current settings
        base_config = {
            'whale_thresholds': {
                'whale_threshold_usd': self.settings.detection.whale_threshold_usd,
                'coordination_threshold': self.settings.detection.coordination_threshold,
                'min_whales_for_coordination': self.settings.detection.min_whales_for_coordination
            },
            'volume_thresholds': {
                'volume_spike_multiplier': self.settings.detection.volume_spike_multiplier,
                'z_score_threshold': self.settings.detection.z_score_threshold
            },
            'price_thresholds': {
                'rapid_movement_pct': self.settings.detection.rapid_movement_pct,
                'price_movement_std': self.settings.detection.price_movement_std
            },
            'coordination_thresholds': {
                'min_coordinated_wallets': self.settings.detection.min_coordinated_wallets,
                'coordination_time_window': self.settings.detection.coordination_time_window
            }
        }

        print(f"\n📊 Base Configuration:")
        print(f"  Whale Threshold: ${base_config['whale_thresholds']['whale_threshold_usd']:,}")
        print(f"  Volume Spike Multiplier: {base_config['volume_thresholds']['volume_spike_multiplier']}x")
        print(f"  Z-Score Threshold: {base_config['volume_thresholds']['z_score_threshold']}")

        # Create variant generator
        generator = VariantGenerator(base_config)

        # Strategy 1: Named presets
        self.print_subheader("Strategy 1: Named Presets")
        named_variants = generator.create_named_variants()
        print(f"  Created {len(named_variants)} preset variants:")
        for variant in named_variants:
            print(f"    • {variant.name}: {variant.description}")

        # Strategy 2: Whale threshold sweep
        self.print_subheader("Strategy 2: Whale Threshold Sweep")
        whale_values = [5000, 7500, 10000, 15000, 20000]
        whale_sweep = generator.sweep_parameter(
            param_path='whale_thresholds.whale_threshold_usd',
            values=whale_values,
            name_template="whale_{value}",
            description_template="Whale threshold = ${value:,}"
        )
        print(f"  Created {len(whale_sweep)} variants:")
        for variant in whale_sweep:
            whale_t = variant.get_parameter('whale_thresholds.whale_threshold_usd')
            print(f"    • {variant.name}: ${whale_t:,}")

        # Strategy 3: Volume parameter grid
        self.print_subheader("Strategy 3: Volume Parameter Grid Search")
        volume_grid = generator.grid_search(
            param_grid={
                'volume_thresholds.volume_spike_multiplier': [2.0, 2.5, 3.0, 3.5],
                'volume_thresholds.z_score_threshold': [2.0, 2.5, 3.0]
            },
            name_template="vol_grid_{index}",
            description_template="Spike={params[volume_spike_multiplier]}x, Z={params[z_score_threshold]}"
        )
        print(f"  Created {len(volume_grid)} grid variants")

        # Combine all variants
        all_variants = named_variants + whale_sweep[:3] + volume_grid[:4]  # Limit for demo

        print(f"\n✅ Total variants created: {len(all_variants)}")
        return all_variants

    def step_2_run_tests(self, variants: list, days_back: int = None):
        """Step 2: Run A/B tests with all variants"""
        self.print_header("STEP 2: Running A/B Tests")

        print(f"\n🔬 Initializing Configuration Tester...")
        print(f"  Database: {self.db_path}")
        print(f"  Interval: 24h")
        print(f"  Variants to test: {len(variants)}")

        # Initialize tester
        self.tester = ConfigurationTester(
            db_path=self.db_path,
            interval='24h',
            interval_hours=[1, 4, 24],
            outcome_price_threshold=self.outcome_threshold
        )

        # Add all variants
        for variant in variants:
            self.tester.add_variant(variant)

        print(f"\n🏃 Running simulations...")
        print(f"  This may take several minutes depending on data size...\n")

        # Progress callback
        def progress(name, current, total):
            pct = (current / total) * 100
            print(f"  [{current}/{total}] ({pct:.0f}%) Testing: {name}")

        # Run all tests
        try:
            results = self.tester.run_tests(
                days_back=days_back,
                batch_mode=True,
                progress_callback=progress
            )

            print(f"\n✅ Completed {len(results)} tests")
            return results

        except Exception as e:
            print(f"\n❌ Testing failed: {e}")
            logger.exception("Test execution failed")
            return None

    def step_3_compare_results(self):
        """Step 3: Compare results and identify best configuration"""
        self.print_header("STEP 3: Comparing Results")

        if not self.tester or not self.tester.results:
            print("❌ No test results available")
            return None

        print(f"\n📊 Comparing {len(self.tester.results)} configurations...\n")

        # Compare by different metrics
        metrics_to_compare = ['f1_score', 'roi', 'precision', 'sharpe_ratio']

        comparisons = {}
        for metric in metrics_to_compare:
            try:
                comparison = self.tester.compare_results(rank_by=metric, min_alerts=3)
                comparisons[metric] = comparison

                print(f"\n🏆 Best by {metric.upper()}: {comparison.best_variant}")
                top_3 = comparison.ranking[:3]
                for rank, (name, score) in enumerate(top_3, 1):
                    print(f"  {rank}. {name}: {score:.2%}")

            except Exception as e:
                print(f"\n⚠️  Could not rank by {metric}: {e}")

        # Use F1 score as primary metric
        if 'f1_score' in comparisons:
            primary_comparison = comparisons['f1_score']
        elif comparisons:
            primary_comparison = list(comparisons.values())[0]
        else:
            print("❌ No valid comparisons available")
            return None

        # Print detailed report
        self.print_subheader("Detailed Comparison Report")
        self.tester.print_comparison_report(primary_comparison)

        return primary_comparison

    def step_4_export_results(self, comparison):
        """Step 4: Export results for analysis"""
        self.print_header("STEP 4: Exporting Results")

        results_dir = Path("backtesting/results")
        results_dir.mkdir(parents=True, exist_ok=True)

        # Export all test results
        results_file = results_dir / "config_test_results.json"
        self.tester.export_results(str(results_file), include_full_config=True)
        print(f"  ✓ Exported test results: {results_file}")

        # Export comparison
        if comparison:
            comparison_file = results_dir / "config_comparison.json"
            self.tester.export_comparison(comparison, str(comparison_file))
            print(f"  ✓ Exported comparison: {comparison_file}")

        # Get and display best config
        try:
            best_config = self.tester.get_best_config(rank_by='f1_score')
            best_file = results_dir / "best_config.json"

            import json
            with open(best_file, 'w') as f:
                json.dump({
                    'name': best_config.name,
                    'description': best_config.description,
                    'config': best_config.config,
                    'tags': best_config.tags
                }, f, indent=2)

            print(f"  ✓ Exported best config: {best_file}")

            self.print_subheader("Best Configuration")
            print(f"  Name: {best_config.name}")
            print(f"  Description: {best_config.description}")

            if 'whale_thresholds' in best_config.config:
                whale_t = best_config.config['whale_thresholds'].get('whale_threshold_usd')
                print(f"  Whale Threshold: ${whale_t:,}")

            if 'volume_thresholds' in best_config.config:
                vol_mult = best_config.config['volume_thresholds'].get('volume_spike_multiplier')
                z_score = best_config.config['volume_thresholds'].get('z_score_threshold')
                print(f"  Volume Spike Multiplier: {vol_mult}x")
                print(f"  Z-Score Threshold: {z_score}")

        except Exception as e:
            print(f"  ⚠️  Could not export best config: {e}")

        print("\n📁 All results exported to: backtesting/results/")

    def run_full_demo(self, days_back: int = None):
        """Run the complete configuration testing demo"""
        self.print_header("CONFIGURATION A/B TESTING DEMO")

        print("\nThis demo will:")
        print("  1. Create multiple detector configuration variants")
        print("  2. Run simulations with each configuration")
        print("  3. Compare performance metrics")
        print("  4. Identify the best-performing configuration")
        print("  5. Export detailed results")

        try:
            # Step 1: Create variants
            variants = self.step_1_create_variants()

            # Step 2: Run tests
            results = self.step_2_run_tests(variants, days_back=days_back)

            if not results:
                print("\n❌ Demo aborted: No test results")
                return

            # Step 3: Compare results
            comparison = self.step_3_compare_results()

            # Step 4: Export results
            self.step_4_export_results(comparison)

            # Final summary
            self.print_header("DEMO COMPLETE")
            print("\n✅ Configuration A/B testing completed successfully!")
            print("\n💡 Next Steps:")
            print("  • Review exported results in backtesting/results/")
            print("  • Apply best configuration to production settings")
            print("  • Run additional tests with different parameter ranges")
            print("  • Monitor performance with new configuration")

        except KeyboardInterrupt:
            print("\n\n⚠️  Demo interrupted by user")
        except Exception as e:
            print(f"\n\n❌ Demo failed: {e}")
            logger.exception("Demo execution failed")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Configuration A/B Testing Demo")
    parser.add_argument(
        "--db",
        default="demo_backtest.db",
        help="Path to historical trade database (default: demo_backtest.db)"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Limit test data to last N days (optional)"
    )
    parser.add_argument(
        '--outcome-threshold',
        type=float,
        default=0.05,
        help='Price change threshold for outcome validation as decimal (default: 0.05 = 5%%)'
    )

    args = parser.parse_args()

    # Check if database exists
    if not Path(args.db).exists():
        print(f"\n❌ Database not found: {args.db}")
        print("\n💡 You need historical trade data to run configuration tests.")
        print("   Run this first:")
        print(f"     python backtesting/demo_end_to_end.py --db {args.db}")
        print("\n   This will:")
        print("     • Load historical trade data from The Graph")
        print("     • Create the database file")
        print("     • Run initial simulation")
        print("\n   Then you can run configuration testing.")
        sys.exit(1)

    # Run demo
    demo = ConfigTestingDemo(db_path=args.db, outcome_threshold=args.outcome_threshold)
    demo.run_full_demo(days_back=args.days)


if __name__ == "__main__":
    main()
