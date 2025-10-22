# Backtesting Framework

Comprehensive framework for backtesting Polymarket insider trading detection algorithms using historical blockchain data.

## Overview

This framework enables validation and optimization of detection algorithms by replaying historical trade data through the detection system and measuring performance metrics.

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

## Testing

Comprehensive test suite with **42 passing tests**:

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

**Run tests:**
```bash
# All backtesting tests
python -m pytest tests/backtesting/ -v

# Specific test file
python -m pytest tests/backtesting/test_historical_storage.py -v

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

## Next Steps

The foundation is complete! Next components to build:

1. **Simulation Engine** - Replay trades through detectors
2. **Metrics Collector** - Calculate precision, recall, F1
3. **Configuration Tester** - A/B test detector parameters
4. **Report Generator** - Performance visualization

## Architecture

```
┌─────────────────┐
│  The Graph API  │  (Blockchain data source)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GraphClient    │  (Fetch historical trades)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data Loader    │  (Orchestrate fetching)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Storage        │  (SQLite database)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Simulation     │  (Coming next...)
│  Engine         │
└─────────────────┘
```

## Performance Notes

- **Graph API Rate Limits**: Public endpoint, be respectful
- **Pagination**: 1000 trades per query (Graph limit)
- **Batch Insert**: Efficient bulk inserts with duplicate detection
- **Indexes**: Optimized for time-range and asset queries
- **Progress Tracking**: Optional callbacks for long operations

## Troubleshooting

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

### Slow Loading

- Reduce batch size: `loader.load_days_back(days=60, batch_size=500)`
- Load incrementally: Start with fewer days, expand as needed
- Check network connection

## References

- [The Graph Documentation](https://thegraph.com/docs/)
- [Polymarket Subgraph](https://github.com/Polymarket/polymarket-subgraph)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

## License

Part of the Polymarket Insider Trading Detection Bot project.
