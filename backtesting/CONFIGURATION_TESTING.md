# Configuration Testing Guide

## Overview

The Configuration Tester allows you to systematically A/B test different detector parameter configurations to find optimal settings for your data.

## Quick Start

```bash
# 1. Ensure you have historical data loaded
python backtesting/demo_end_to_end.py --days 30

# 2. Run configuration testing
python backtesting/demo_config_testing.py --db demo_backtest.db
```

## Understanding Results

### Zero Alerts Scenario

If all configurations produce 0 alerts, this indicates:

1. **Thresholds are too conservative** for your dataset
   - Try lowering thresholds in variant generation
   - Create more aggressive parameter sweeps

2. **Limited data** - Need more historical trades
   - Load more days: `--days 60` or `--days 90`
   - Ensure data has sufficient volume and whale activity

3. **Market conditions** - The historical period may not have had significant insider activity
   - This is actually a good validation that the system doesn't create false positives

### Successful Testing

When alerts are generated, you'll see:

```
🏆 Best by f1_score: aggressive
  1. aggressive: 75.00%
  2. balanced: 65.00%
  3. baseline: 60.00%
```

The comparison will show:
- Precision (minimize false alarms)
- Recall (maximize detection coverage)
- F1 Score (balanced metric)
- ROI (profitability)
- Win Rate (consistency)

## Creating Better Test Variants

### More Aggressive Thresholds

```python
# Lower whale thresholds significantly
whale_sweep = generator.sweep_parameter(
    param_path='whale_thresholds.whale_threshold_usd',
    values=[1000, 2500, 5000, 7500, 10000],  # Start lower
    name_template="whale_{value}"
)

# Lower volume multipliers
volume_sweep = generator.sweep_parameter(
    param_path='volume_thresholds.volume_spike_multiplier',
    values=[1.5, 2.0, 2.5, 3.0],  # Start lower
    name_template="vol_{value}x"
)
```

### Custom Aggressive Preset

```python
# Create ultra-aggressive variant
ultra_aggressive = ConfigurationVariant(
    name="ultra_aggressive",
    description="Maximum sensitivity - catch everything",
    config={
        'whale_thresholds': {
            'whale_threshold_usd': 1000,  # Very low
            'min_whales_for_coordination': 2
        },
        'volume_thresholds': {
            'volume_spike_multiplier': 1.5,  # Very low
            'z_score_threshold': 1.5
        }
    },
    tags=['preset', 'ultra_aggressive']
)

tester.add_variant(ultra_aggressive)
```

## Interpreting Exported Results

### config_test_results.json

```json
{
  "timestamp": "2025-10-22T...",
  "total_variants": 11,
  "results": {
    "aggressive": {
      "variant_name": "aggressive",
      "alert_count": 23,
      "simulation_time": 1.5,
      "metrics": {
        "precision": 0.75,
        "recall": 0.80,
        "f1_score": 0.77,
        "roi": 0.45,
        "win_rate": 0.70
      }
    }
  }
}
```

### Key Metrics

- **alert_count**: Total alerts generated (need >= 5 for valid comparison)
- **precision**: % of alerts that were correct (higher = fewer false alarms)
- **recall**: % of actual events detected (higher = catch more opportunities)
- **f1_score**: Balance between precision and recall (recommended ranking metric)
- **roi**: Total return if following all alerts
- **win_rate**: % of profitable predictions

## Recommendations

### For Production Use

1. **Start conservative**: Use baseline or balanced presets
2. **Monitor false positive rate**: High precision (>70%) is critical
3. **Balance with recall**: Don't miss too many opportunities
4. **Consider ROI**: Ultimately profitability matters most

### For Research/Development

1. **Test wide ranges**: Cast a wide net with parameter sweeps
2. **Compare multiple metrics**: Don't optimize for just one metric
3. **Use sufficient data**: 30-90 days minimum for reliable results
4. **Validate on holdout set**: Test best config on new data

## Troubleshooting

### All metrics show 0.00%

If precision, recall, F1, ROI, and win rate all show 0.00% despite generating alerts:

**Root Cause**: Price change threshold may be too high for the price movements in your data.

**Solution 1: Lower the outcome threshold**

Binary markets often have smaller price movements (<5%). Try lowering the threshold:

```bash
# Default 5% threshold - may be too high for binary markets
python backtesting/demo_config_testing.py --db demo_backtest.db

# Try 2% threshold
python backtesting/demo_config_testing.py --db demo_backtest.db --outcome-threshold 0.02

# Very sensitive 1% threshold
python backtesting/demo_config_testing.py --db demo_backtest.db --outcome-threshold 0.01
```

**Solution 2: Check price data availability**

The system needs historical trades after each alert to validate outcomes:

```python
# Check if your database has sufficient coverage
from backtesting import HistoricalTradeStorage

storage = HistoricalTradeStorage('demo_backtest.db')
time_range = storage.get_time_range()
print(f"Data range: {time_range[0]} to {time_range[1]}")

# Load more data if range is too short
python backtesting/demo_end_to_end.py --days 60 --limit 100000
```

**Solution 3: Understand the threshold**

The threshold determines what counts as price movement:

- **5% threshold (default)**: Price from 0.50 → 0.525 = FLAT (only 5% move)
- **2% threshold**: Price from 0.50 → 0.51 = UP (2% move)
- **Below threshold**: All movements classified as FLAT → predictions wrong → 0% metrics

For Polymarket binary markets (0.00-1.00 range), 2-3% is often more appropriate than 5%.

### "No variants produced at least 5 alerts"

**Solution**: Lower thresholds or load more data

```bash
# Load more historical data
python backtesting/demo_end_to_end.py --days 60 --limit 100000

# Then test with more aggressive variants
# (modify demo_config_testing.py to use lower thresholds)
```

### All variants have identical performance

**Solution**: Widen parameter ranges

The variants you're testing may be too similar. Create more extreme differences:

```python
# Bad: Too similar
values=[9000, 9500, 10000, 10500, 11000]

# Good: Clear differences
values=[1000, 5000, 10000, 20000, 50000]
```

### Tests run very slowly

**Solution**: Use batch mode and limit data

```python
# In config_tester.py run_tests() call
results = tester.run_tests(
    days_back=7,  # Limit to recent data
    batch_mode=True  # Much faster
)
```

## Advanced Usage

### Custom Ranking Function

```python
# Rank by custom metric
comparison = tester.compare_results(
    rank_by='sharpe_ratio',  # Risk-adjusted returns
    min_alerts=10  # Require more alerts
)
```

### Export Best Configuration

```python
best_config = tester.get_best_config(rank_by='f1_score')

# Apply to production
settings.detection.whale_threshold_usd = best_config.get_parameter(
    'whale_thresholds.whale_threshold_usd'
)
settings.save()
```

## Next Steps

After finding optimal configuration:

1. **Validate on new data**: Test on a different time period
2. **Monitor in production**: Track actual performance
3. **Iterate regularly**: Market conditions change
4. **A/B test in live**: Run multiple configs simultaneously

---

For more information, see:
- `backtesting/README.md` - Full backtesting documentation
- `backtesting/test_config_tester.py` - Unit tests and examples
- `backtesting/demo_config_testing.py` - Full demo source code
