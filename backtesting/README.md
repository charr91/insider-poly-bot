# Backtesting Framework

Comprehensive framework for backtesting Polymarket insider trading detection algorithms using historical blockchain data.

## Overview

This framework enables validation and optimization of detection algorithms by replaying historical trade data through the detection system and measuring performance metrics.

## Quick Start

### End-to-End Demo (Recommended)

Run the comprehensive demo to test everything with real blockchain data:

```bash
# Run full pipeline: load data, simulate, analyze
python backtesting/demo_end_to_end.py

# Load 30 days of data and test with more trades
python backtesting/demo_end_to_end.py --days 30 --limit 50000

# Use specific detectors
python backtesting/demo_end_to_end.py --detectors volume whale price

# Adjust price validation threshold for binary markets (default: 5%)
python backtesting/demo_end_to_end.py --outcome-threshold 0.02

# See all options
python backtesting/demo_end_to_end.py --help
```

**What it does:**
1. Fetches real historical trades from The Graph (free, no API key needed)
2. Runs simulation through your detection algorithms
3. Shows detailed alert analysis with confidence scores
4. Validates alert accuracy by tracking price movements after alerts
5. Exports results to JSON for further analysis

**First run takes 1-5 minutes** to download data. Subsequent runs are instant if using existing database.

**Performance Modes:**
- **Sequential mode (default)**: Maintains chronological order, ~65 trades/sec
- **Batch mode (`--batch`)**: Groups by market, ~500-2000 trades/sec, 10-30x faster

```bash
# Fast mode for large datasets
python backtesting/demo_end_to_end.py --batch --limit 100000
```

### Individual Component Demos

Test specific components separately:

```bash
# Demo 1: Just load historical data
python backtesting/data_loader.py

# Demo 2: Run simulation on existing data
python backtesting/simulation_engine.py
```

## Components

### 1. Graph Client (`graph_client.py`)

GraphQL client for The Graph's Polymarket orderbook subgraph.

**Features:**
- Fetches historical `OrderFilledEvent` data from blockchain
- Supports pagination for large datasets
- Time-range filtered queries
- 3 years of historical data available (Nov 2022 - present)
- Free public endpoint (no API key required)

**Usage:**
```python
from backtesting import PolymarketGraphClient

client = PolymarketGraphClient()

# Fetch recent trades
trades = client.get_trades(first=100)

# Fetch specific time range
trades = client.get_trades_for_time_range(days_back=30)

# Paginated fetch
all_trades = client.get_trades_paginated(
    start_timestamp=start_ts,
    end_timestamp=end_ts,
    max_trades=10000
)
```

### 2. Historical Storage (`historical_storage.py`)

SQLite-based storage for historical trade data.

**Features:**
- Efficient indexed storage
- Duplicate detection
- Time-range queries
- Asset-based filtering
- Collection metadata tracking
- Statistics and analytics

**Database Schema:**
```sql
historical_trades:
  - id (PRIMARY KEY)
  - transaction_hash
  - timestamp (INDEXED)
  - order_hash
  - maker (INDEXED)
  - taker
  - maker_asset_id (INDEXED)
  - taker_asset_id (INDEXED)
  - maker_amount_filled
  - taker_amount_filled
  - fee
  - created_at

collection_metadata:
  - id
  - start_timestamp
  - end_timestamp
  - trades_collected
  - collection_date
  - notes
```

**Usage:**
```python
from backtesting import HistoricalTradeStorage

with HistoricalTradeStorage("backtest.db") as storage:
    # Insert trades
    storage.insert_trades_batch(trades)

    # Query by time range
    trades = storage.get_trades_by_time_range(
        start_timestamp=start_ts,
        end_timestamp=end_ts
    )

    # Get statistics
    stats = storage.get_statistics()
    print(f"Total trades: {stats['total_trades']}")
```

### 3. Data Loader (`data_loader.py`)

Orchestrates fetching and storing historical data.

**Features:**
- Batch fetching with progress tracking
- Automatic deduplication
- Incremental loading
- Load by time range or days back
- Collection metadata recording

**Usage:**
```python
from backtesting import HistoricalDataLoader

with HistoricalDataLoader(db_path="backtest.db") as loader:
    # Load last 60 days
    stats = loader.load_days_back(
        days=60,
        progress_callback=lambda f, i, d: print(f"Progress: {f} fetched")
    )

    print(f"Inserted: {stats['total_inserted']}")
    print(f"Time: {stats['time_taken']:.1f}s")

    # Load incremental updates
    stats = loader.load_incremental()

    # Get storage statistics
    storage_stats = loader.get_storage_stats()
```

### 4. Simulation Engine (`simulation_engine.py`)

Replays historical trades through detection algorithms to measure performance.

**Features:**
- Maintains market state during simulation
- Runs detectors on trade streams
- Generates virtual alerts
- Tracks comprehensive statistics
- JSON export for analysis

**Key Classes:**
```python
@dataclass
class MarketState:
    """Tracks state of a market during simulation"""
    market_id: str
    trade_history: deque  # Last 1000 trades
    total_volume: float
    trade_count: int
    unique_makers: set
    unique_takers: set

@dataclass
class VirtualAlert:
    """Alert generated during simulation"""
    alert_id: str
    timestamp: datetime
    market_id: str
    detector_type: str
    severity: str
    confidence_score: float
    price_at_alert: Optional[float]
    predicted_direction: Optional[str]

class SimulationEngine:
    def simulate_trades(
        self,
        trades: List[Dict],
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """Run simulation, returns statistics"""
```

**Usage:**
```python
from backtesting import SimulationEngine
from detection.volume_detector import VolumeDetector
from config.settings import SettingsManager

# Load config and create detectors
settings = SettingsManager()
config = settings.get_config()

detectors = {
    'volume': VolumeDetector(config),
    'whale': WhaleDetector(config)
}

# Create simulation engine
engine = SimulationEngine(config=config, detectors=detectors)

# Load historical trades from storage
with HistoricalTradeStorage("backtest.db") as storage:
    trades = storage.get_trades_by_time_range(
        start_timestamp=start_ts,
        end_timestamp=end_ts,
        limit=10000
    )

# Run simulation
stats = engine.simulate_trades(trades)

print(f"Total alerts: {stats['total_alerts']}")
print(f"Alerts by detector: {stats['alerts_by_detector']}")

# Get alerts for analysis
high_alerts = engine.get_alerts(severity='HIGH')

# Export results
engine.export_alerts_to_json("simulation_results.json")
```

### 5. Outcome Tracker (`outcome_tracker.py`)

Tracks alert outcomes to measure detection accuracy and profitability.

**Features:**
- Price movement tracking at intervals (1h, 4h, 24h)
- Direction classification (UP, DOWN, FLAT)
- Prediction correctness validation
- ROI calculation per alert
- Confusion matrix classification

**Usage:**
```python
from backtesting import OutcomeTracker

tracker = OutcomeTracker(price_change_threshold=0.05)

# Track an alert
outcome = tracker.track_alert(
    alert_id="alert_001",
    market_id="market_123",
    alert_timestamp=datetime.now(),
    predicted_direction="BUY",
    confidence_score=0.85,
    price_at_alert=0.50
)

# Update price at intervals
tracker.update_price_at_interval("alert_001", "1h", 0.52, time_1h_later)
tracker.update_price_at_interval("alert_001", "4h", 0.55, time_4h_later)
tracker.update_price_at_interval("alert_001", "24h", 0.60, time_24h_later)

# Get aggregated metrics
metrics = tracker.calculate_aggregate_metrics(interval='24h')
print(f"Accuracy: {metrics['accuracy']:.2%}")
print(f"Win Rate: {metrics['win_rate']:.2%}")
```

**Price Validation Configuration:**

The outcome tracker uses a configurable price change threshold to classify price movements:

- **Default threshold: 5%** - Price must move ±5% to be classified as UP/DOWN
- **Below threshold: FLAT** - Movements under threshold are considered no significant change
- **For binary markets: 2-3%** recommended - Polymarket binary markets have smaller price ranges

```python
# More sensitive for binary markets
tracker = OutcomeTracker(price_change_threshold=0.02)  # 2%

# Conservative for higher volatility
tracker = OutcomeTracker(price_change_threshold=0.10)  # 10%
```

**Price Data Sources:**

The system queries price data from two sources in priority order:

1. **Market's own trade history** - Prices from the alerted market
2. **Database historical trades** - Any trades near target time from all markets

This ensures accurate validation even when a specific market has low trading activity after an alert.

**CLI Usage:**

```bash
# Default 5% threshold
python backtesting/demo_end_to_end.py

# Lower threshold for binary markets
python backtesting/demo_end_to_end.py --outcome-threshold 0.02

# Higher threshold for volatile markets
python backtesting/demo_end_to_end.py --outcome-threshold 0.10
```

### 6. Metrics Calculator (`metrics_calculator.py`)

Calculates comprehensive performance metrics from alert outcomes.

**Metrics Provided:**
- **Classification**: Precision, Recall, F1 Score, Accuracy
- **Financial**: ROI, Win Rate, Average Return, Sharpe Ratio
- **Confusion Matrix**: True/False Positives/Negatives
- **By Detector**: Performance breakdown by detector type
- **By Confidence**: Threshold analysis

**Usage:**
```python
from backtesting import MetricsCalculator

calculator = MetricsCalculator()

# Calculate metrics from outcomes
metrics = calculator.calculate_metrics(
    outcomes=tracker.get_all_outcomes(),
    interval='24h',
    min_confidence=0.70  # Optional filter
)

# Display formatted report
calculator.print_metrics_report(metrics)

# Export to JSON
metrics_dict = calculator.export_metrics_to_dict(metrics)
```

**Metrics Explained:**

- **Precision**: What % of alerts were correct predictions?
  - Formula: `TP / (TP + FP)`
  - High precision = Few false alarms

- **Recall**: What % of actual events did we detect?
  - Formula: `TP / (TP + FN)`
  - High recall = Few missed opportunities

- **F1 Score**: Balanced metric between precision and recall
  - Formula: `2 * (Precision * Recall) / (Precision + Recall)`
  - Useful when you want balanced performance

- **ROI**: Total return on investment if following all alerts
  - Sum of all returns across alerts
  - Measures profitability

- **Win Rate**: Percentage of profitable predictions
  - Formula: `Profitable trades / Total trades`

- **Sharpe Ratio**: Risk-adjusted return
  - Formula: `Mean Return / Std Dev of Returns`
  - Higher is better (>1 is good, >2 is excellent)

## Integration with Simulation Engine

The simulation engine automatically tracks outcomes and calculates metrics:

```python
from backtesting import SimulationEngine

# Create engine with outcome tracking (default: enabled)
engine = SimulationEngine(
    config=config,
    detectors=detectors,
    track_outcomes=True  # Default
)

# Run simulation
stats = engine.simulate_trades(trades)

# Calculate outcomes from simulation data
engine.calculate_alert_outcomes(interval_hours=[1, 4, 24])

# Get performance metrics
metrics = engine.calculate_metrics(interval='24h')

# Export everything
engine.export_alerts_to_json("alerts.json")
engine.export_outcomes_to_json("outcomes.json")
engine.export_metrics_to_json("metrics.json")
```

## Performance Optimization

The backtesting framework supports two simulation modes:

**Sequential Mode** (default):
- Maintains chronological order
- Better for time-sensitive analysis
- Speed: ~65 trades/sec

**Batch Mode** (faster):
- Groups by market for parallel processing
- 10-30x faster than sequential
- Speed: ~500-2000 trades/sec
- Trade-off: Loses cross-market temporal context

```python
# Use batch mode for large datasets
stats = engine.simulate_trades_batch(
    trades,
    progress_callback=callback
)
```

## Testing

Comprehensive test suite with **70 passing tests**:

- **Storage Tests** (26 tests): `tests/backtesting/test_historical_storage.py`
  - Database initialization
  - CRUD operations
  - Duplicate handling
  - Time-range queries
  - Statistics and metadata

- **Data Loader Tests** (16 tests): `tests/backtesting/test_data_loader.py`
  - Initialization
  - Batch loading
  - Progress callbacks
  - Incremental updates
  - Context managers

- **Simulation Engine Tests** (28 tests): `tests/backtesting/test_simulation_engine.py`
  - MarketState tracking
  - Trade format conversion
  - Detector integration
  - Alert generation and filtering
  - Statistics and export
  - Error handling

**Run tests:**
```bash
# All backtesting tests
python -m pytest tests/backtesting/ -v

# Specific test file
python -m pytest tests/backtesting/test_simulation_engine.py -v

# With coverage
python -m pytest tests/backtesting/ --cov=backtesting --cov-report=html
```

## Data Availability

✅ **Confirmed**: 3 years of historical data available

- **Source**: The Graph - Polymarket Orderbook Subgraph
- **Endpoint**: Goldsky public API (no key required)
- **Historical Depth**: November 2022 - Present (~1,065+ days)
- **Data Completeness**: 100% (blockchain-sourced)
- **Cost**: Free

**Oldest trades confirmed:**
```
Trade 1: 2022-11-21 11:50:09 (1065 days ago)
Trade 2: 2022-11-21 11:50:09 (1065 days ago)
Trade 3: 2022-11-21 11:52:13 (1065 days ago)
```

## Storage Requirements

### For 60 Days

- **Estimated Trades**: 3M - 12M trades
- **Storage Size**: 1-3 GB (SQLite with indexes)
- **Load Time**: ~10-30 minutes (depends on network)

### For Full Historical (3 years)

- **Estimated Trades**: 50M - 200M trades
- **Storage Size**: 30-100 GB
- **Load Time**: Several hours
- **Recommendation**: Load incrementally as needed

## Example Workflow

```python
from backtesting import HistoricalDataLoader
from datetime import datetime, timedelta, timezone

# 1. Load historical data
with HistoricalDataLoader(db_path="insider_backtest.db") as loader:
    # Check existing data
    stats = loader.get_storage_stats()

    if stats['total_trades'] == 0:
        # First time - load 60 days
        print("Loading initial 60 days of data...")
        load_stats = loader.load_days_back(days=60)
        print(f"Loaded {load_stats['total_inserted']} trades")
    else:
        # Incremental update
        print("Loading new trades...")
        load_stats = loader.load_incremental()
        print(f"Loaded {load_stats['total_inserted']} new trades")

    # Display statistics
    stats = loader.get_storage_stats()
    print(f"\nDatabase Statistics:")
    print(f"  Total Trades: {stats['total_trades']:,}")
    print(f"  Date Range: {datetime.fromtimestamp(stats['oldest_timestamp']).strftime('%Y-%m-%d')} to {datetime.fromtimestamp(stats['newest_timestamp']).strftime('%Y-%m-%d')}")
    print(f"  Unique Makers: {stats['unique_makers']:,}")
    print(f"  Database Size: {stats['database_size_mb']:.2f} MB")
```

## Quick Start - Load Sample Data

```bash
# Run the data loader demo
python backtesting/data_loader.py

# This will:
# - Create demo_backtest.db
# - Load last 7 days of trades
# - Display statistics
```

### 7. Configuration Variant (`config_variant.py`)

Defines and generates configuration variants for A/B testing detector parameters.

**Features:**
- Define configuration variants with parameter overrides
- Generate systematic parameter sweeps
- Grid search across multiple parameters
- Predefined variant templates (baseline, aggressive, conservative)
- Export/import variants to JSON

**Usage:**
```python
from backtesting import ConfigurationVariant, VariantGenerator
from config.settings import Settings

# Create base configuration
settings = Settings()
base_config = {
    'whale_thresholds': {
        'whale_threshold_usd': settings.detection.whale_threshold_usd,
        'coordination_threshold': settings.detection.coordination_threshold
    },
    'volume_thresholds': {
        'volume_spike_multiplier': settings.detection.volume_spike_multiplier,
        'z_score_threshold': settings.detection.z_score_threshold
    }
}

generator = VariantGenerator(base_config)

# Generate named presets
variants = generator.create_named_variants()
# Returns: baseline, aggressive, conservative, balanced

# Parameter sweep
whale_sweep = generator.sweep_parameter(
    param_path='whale_thresholds.whale_threshold_usd',
    values=[5000, 10000, 15000, 20000],
    name_template="whale_{value}",
    description_template="Whale threshold = ${value:,}"
)

# Grid search
grid_variants = generator.grid_search(
    param_grid={
        'volume_thresholds.volume_spike_multiplier': [2.0, 3.0, 4.0],
        'volume_thresholds.z_score_threshold': [2.0, 2.5, 3.0]
    },
    name_template="volume_grid_{index}"
)

# Export for later use
generator.export_variants(variants, "my_variants.json")

# Load variants
base_config, variants = VariantGenerator.load_variants("my_variants.json")
```

### 8. Configuration Tester (`config_tester.py`)

A/B testing framework for systematically comparing detector configurations.

**Features:**
- Run simulations with multiple configurations
- Statistical comparison of performance metrics
- Ranking by precision, recall, F1, ROI, Sharpe ratio
- Detailed comparison reports
- Best configuration recommendation
- Export results to JSON

**Usage:**
```python
from backtesting import ConfigurationTester, VariantGenerator

# Initialize tester with historical data
tester = ConfigurationTester(
    db_path="backtest.db",
    interval='24h',
    interval_hours=[1, 4, 24]
)

# Create variants to test
generator = VariantGenerator(base_config)
variants = generator.create_named_variants()

# Add variants to tester
for variant in variants:
    tester.add_variant(variant)

# Run A/B tests
results = tester.run_tests(
    days_back=30,
    batch_mode=True,
    progress_callback=lambda name, cur, total: print(f"Testing {name}...")
)

# Compare results
comparison = tester.compare_results(
    rank_by='f1_score',  # Can use: precision, recall, roi, sharpe_ratio
    min_alerts=5  # Require minimum alerts for valid comparison
)

# Print detailed comparison report
tester.print_comparison_report(comparison)

# Get best configuration
best_config = tester.get_best_config(rank_by='f1_score')
print(f"Best: {best_config.name}")

# Export results
tester.export_results("config_test_results.json")
tester.export_comparison(comparison, "config_comparison.json")
```

**Quick Start:**
```bash
# Test configuration framework (no data required)
python backtesting/test_config_tester.py

# Run full A/B testing demo (requires historical data)
python backtesting/demo_config_testing.py

# Run with specific database
python backtesting/demo_config_testing.py --db my_backtest.db --days 30
```

**What the demo does:**
1. Creates multiple detector configuration variants
   - Named presets (baseline, aggressive, conservative, balanced)
   - Whale threshold sweep (5K, 7.5K, 10K, 15K, 20K)
   - Volume parameter grid search
2. Runs simulations with each configuration
3. Compares performance metrics across all variants
4. Identifies best-performing configuration
5. Exports detailed results and recommendations

**Ranking Metrics:**
- `f1_score` - Balanced precision/recall (recommended)
- `precision` - Minimize false alarms
- `recall` - Maximize detection coverage
- `roi` - Maximize profitability
- `sharpe_ratio` - Best risk-adjusted returns
- `win_rate` - Most consistent wins

## Next Steps

Core infrastructure complete! Next components to build:

1. ✅ **Simulation Engine** - COMPLETE
2. ✅ **Metrics Collector** - COMPLETE (Calculate precision, recall, F1, ROI)
3. ✅ **Configuration Tester** - COMPLETE (A/B test detector parameters)
4. **Report Generator** - Performance visualization and analysis

## Architecture

```
┌─────────────────────┐
│  The Graph API      │  (Blockchain data source)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  GraphClient        │  (Fetch historical trades)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Data Loader        │  (Orchestrate fetching)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Storage (SQLite)   │  (Historical trade database)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Simulation Engine  │  (Replay trades through detectors)
└──────────┬──────────┘
           │
           ├──► Volume Detector
           ├──► Whale Detector
           ├──► Price Detector
           └──► Coordination Detector
           │
           ▼
┌─────────────────────┐
│  Virtual Alerts     │  (Simulated detection results)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Metrics Collector  │  (Coming next...)
└─────────────────────┘
```

## Performance Notes

### Simulation Speed

**Sequential Mode** (default, maintains chronological order):
- 1,000 trades: ~15-20 seconds
- 10,000 trades: ~2-3 minutes
- 100,000 trades: ~20-30 minutes
- **Use when**: Cross-market timing matters, smaller datasets

**Batch Mode** (`--batch` flag, groups by market):
- 1,000 trades: ~2-5 seconds (5-10x faster)
- 10,000 trades: ~10-30 seconds (10-20x faster)
- 100,000 trades: ~1-2 minutes (10-15x faster)
- **Use when**: Processing large datasets, per-market analysis

**Optimization Details:**
- Detectors run every 50 trades (configurable in code)
- Batch mode: 1 detector run per market (154 runs for 10k trades)
- Sequential mode: ~200 detector runs for 10k trades
- Progress updates every 100 trades with ETA

### Data Loading

- **Graph API Rate Limits**: Public endpoint, be respectful
- **Pagination**: 1000 trades per query (Graph limit)
- **Batch Insert**: Efficient bulk inserts with duplicate detection
- **Indexes**: Optimized for time-range and asset queries
- **Progress Tracking**: Real-time callbacks with ETA

## Troubleshooting

### Import Errors

```bash
# Error: "attempted relative import with no known parent package"
# Solution: Imports are now fixed. Run scripts directly:
python backtesting/data_loader.py
python backtesting/simulation_engine.py
python backtesting/demo_end_to_end.py
```

### Connection Issues

```python
# Test Graph API connection
from backtesting import PolymarketGraphClient

client = PolymarketGraphClient()
if client.test_connection():
    print("✅ Connected!")
else:
    print("❌ Connection failed")
```

### Database Issues

```python
# Check database integrity
from backtesting import HistoricalTradeStorage

with HistoricalTradeStorage("backtest.db") as storage:
    stats = storage.get_statistics()
    print(f"Database OK: {stats['total_trades']} trades")
```

### No Alerts Generated

- **Expected behavior**: If market conditions don't meet detector thresholds, no alerts will be generated
- Try longer time range: `--days 30` or `--days 60`
- Try more trades: `--limit 50000`
- Check detector thresholds in `config/settings.py`
- Use `--debug` flag to see detector decision logs

### Slow Loading

- Reduce batch size: `loader.load_days_back(days=60, batch_size=500)`
- Load incrementally: Start with fewer days, expand as needed
- Check network connection
- The Graph API is free but rate-limited - be patient on first load

## References

- [The Graph Documentation](https://thegraph.com/docs/)
- [Polymarket Subgraph](https://github.com/Polymarket/polymarket-subgraph)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

## License

Part of the Polymarket Insider Trading Detection Bot project.
