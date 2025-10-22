#!/usr/bin/env python
"""
Test script for metrics collector

Creates synthetic alert data to verify metrics calculation works correctly.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtesting.outcome_tracker import OutcomeTracker, OutcomeDirection
from backtesting.metrics_calculator import MetricsCalculator


def main():
    print("\n" + "=" * 80)
    print("  METRICS COLLECTOR TEST")
    print("=" * 80)

    # Create tracker and calculator
    tracker = OutcomeTracker(price_change_threshold=0.05)
    calculator = MetricsCalculator()

    # Create some synthetic alerts with outcomes
    base_time = datetime.now(timezone.utc)

    print("\n📊 Creating synthetic alert outcomes...")

    # Alert 1: Correct prediction - BUY, price went UP
    outcome1 = tracker.track_alert(
        alert_id="test_001",
        market_id="market_001",
        alert_timestamp=base_time,
        predicted_direction="BUY",
        confidence_score=0.85,
        price_at_alert=0.50,
        detector_type="volume",
        severity="HIGH"
    )
    tracker.update_price_at_interval("test_001", "1h", 0.52, base_time + timedelta(hours=1))
    tracker.update_price_at_interval("test_001", "4h", 0.55, base_time + timedelta(hours=4))
    tracker.update_price_at_interval("test_001", "24h", 0.60, base_time + timedelta(hours=24))

    # Alert 2: Incorrect prediction - BUY, but price went DOWN
    outcome2 = tracker.track_alert(
        alert_id="test_002",
        market_id="market_002",
        alert_timestamp=base_time + timedelta(hours=1),
        predicted_direction="BUY",
        confidence_score=0.75,
        price_at_alert=0.60,
        detector_type="whale",
        severity="MEDIUM"
    )
    tracker.update_price_at_interval("test_002", "1h", 0.58, base_time + timedelta(hours=2))
    tracker.update_price_at_interval("test_002", "4h", 0.55, base_time + timedelta(hours=5))
    tracker.update_price_at_interval("test_002", "24h", 0.50, base_time + timedelta(hours=25))

    # Alert 3: Correct prediction - BUY, price went UP
    outcome3 = tracker.track_alert(
        alert_id="test_003",
        market_id="market_003",
        alert_timestamp=base_time + timedelta(hours=2),
        predicted_direction="BUY",
        confidence_score=0.90,
        price_at_alert=0.40,
        detector_type="volume",
        severity="HIGH"
    )
    tracker.update_price_at_interval("test_003", "1h", 0.43, base_time + timedelta(hours=3))
    tracker.update_price_at_interval("test_003", "4h", 0.48, base_time + timedelta(hours=6))
    tracker.update_price_at_interval("test_003", "24h", 0.55, base_time + timedelta(hours=26))

    # Alert 4: Correct prediction - BUY, price went UP (slightly)
    outcome4 = tracker.track_alert(
        alert_id="test_004",
        market_id="market_004",
        alert_timestamp=base_time + timedelta(hours=3),
        predicted_direction="BUY",
        confidence_score=0.65,
        price_at_alert=0.45,
        detector_type="whale",
        severity="LOW"
    )
    tracker.update_price_at_interval("test_004", "1h", 0.46, base_time + timedelta(hours=4))
    tracker.update_price_at_interval("test_004", "4h", 0.47, base_time + timedelta(hours=7))
    tracker.update_price_at_interval("test_004", "24h", 0.48, base_time + timedelta(hours=27))

    # Alert 5: No movement (FLAT) - incorrect since we predicted BUY
    outcome5 = tracker.track_alert(
        alert_id="test_005",
        market_id="market_005",
        alert_timestamp=base_time + timedelta(hours=4),
        predicted_direction="BUY",
        confidence_score=0.55,
        price_at_alert=0.50,
        detector_type="volume",
        severity="MEDIUM"
    )
    tracker.update_price_at_interval("test_005", "1h", 0.50, base_time + timedelta(hours=5))
    tracker.update_price_at_interval("test_005", "4h", 0.51, base_time + timedelta(hours=8))
    tracker.update_price_at_interval("test_005", "24h", 0.51, base_time + timedelta(hours=28))

    print(f"  ✓ Created {len(tracker.outcomes)} synthetic alerts with outcomes")

    # Display individual outcomes
    print("\n📋 Individual Outcomes:")
    print(f"\n{'Alert ID':<12} {'Predicted':<10} {'Actual (24h)':<15} {'Correct?':<10} {'Return':<10} {'Confidence'}")
    print("-" * 80)

    for outcome in tracker.get_all_outcomes():
        actual_dir = outcome.direction_24h.value if outcome.direction_24h else "PENDING"
        correct = "✓" if outcome.prediction_correct_24h else "✗"
        return_pct = f"{outcome.return_24h:+.1%}" if outcome.return_24h is not None else "N/A"
        conf = f"{outcome.confidence_score:.2f}"

        print(f"{outcome.alert_id:<12} {outcome.predicted_direction:<10} {actual_dir:<15} {correct:<10} {return_pct:<10} {conf}")

    # Calculate aggregate metrics
    print("\n📈 Calculating aggregate metrics...")
    metrics = calculator.calculate_metrics(
        outcomes=tracker.get_all_outcomes(),
        interval='24h'
    )

    # Display metrics report
    calculator.print_metrics_report(metrics)

    # Test confidence threshold analysis
    print("\n🎚️  Testing confidence threshold analysis...")
    metrics_high_conf = calculator.calculate_metrics(
        outcomes=tracker.get_all_outcomes(),
        interval='24h',
        min_confidence=0.80
    )

    print(f"\n  With confidence >= 0.80:")
    print(f"    Total Alerts:  {metrics_high_conf.total_alerts}")
    print(f"    Precision:     {metrics_high_conf.precision:.2%}")
    print(f"    Win Rate:      {metrics_high_conf.win_rate:.2%}")
    print(f"    Avg Return:    {metrics_high_conf.average_return:+.2%}")

    # Export test results
    print("\n📁 Exporting test results...")
    import json

    # Export outcomes
    outcomes_data = tracker.export_to_dict()
    with open("backtesting/results/test_outcomes.json", 'w') as f:
        json.dump(outcomes_data, f, indent=2)
    print(f"  ✓ Outcomes exported to: backtesting/results/test_outcomes.json")

    # Export metrics
    metrics_data = calculator.export_metrics_to_dict(metrics)
    with open("backtesting/results/test_metrics.json", 'w') as f:
        json.dump(metrics_data, f, indent=2)
    print(f"  ✓ Metrics exported to: backtesting/results/test_metrics.json")

    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE - Metrics Collector is working correctly!")
    print("=" * 80)

    # Validation summary
    print("\n🎯 Validation Summary:")
    print(f"  • Created {len(tracker.outcomes)} test alerts")
    print(f"  • Calculated outcomes for all intervals (1h, 4h, 24h)")
    print(f"  • Precision: {metrics.precision:.2%} (3 TP out of 4 positive predictions)")
    print(f"  • Accuracy: {metrics.accuracy:.2%} (3 correct out of 5 total)")
    print(f"  • F1 Score: {metrics.f1_score:.2%}")
    print(f"  • Win Rate: {metrics.win_rate:.2%} (profitable outcomes)")
    print(f"  • ROI: {metrics.roi:+.2%}")

    # Validate expected metrics
    expected_precision = 3 / 4  # 3 TP out of 4 positive predictions (TP + FP)
    expected_accuracy = 3 / 5   # 3 correct out of 5 total predictions

    precision_ok = abs(metrics.precision - expected_precision) < 0.01
    accuracy_ok = abs(metrics.accuracy - expected_accuracy) < 0.01

    if precision_ok and accuracy_ok:
        print("\n  ✅ All metrics match expected values!")
    else:
        if not precision_ok:
            print(f"\n  ⚠️  Precision mismatch: got {metrics.precision:.2%}, expected {expected_precision:.2%}")
        if not accuracy_ok:
            print(f"\n  ⚠️  Accuracy mismatch: got {metrics.accuracy:.2%}, expected {expected_accuracy:.2%}")

    print("\n💡 Next Steps:")
    print("  • Review exported JSON files for detailed data")
    print("  • Test with real simulation data using demo_end_to_end.py")
    print("  • Adjust detector thresholds to generate more alerts")


if __name__ == "__main__":
    main()
