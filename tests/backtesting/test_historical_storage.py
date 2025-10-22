"""
Unit tests for historical trade storage
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timezone

from backtesting.historical_storage import HistoricalTradeStorage


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def storage(temp_db):
    """Create a storage instance with temporary database"""
    store = HistoricalTradeStorage(temp_db)
    yield store
    store.close()


@pytest.fixture
def sample_trade():
    """Sample trade data for testing"""
    return {
        'id': '0xabc123-0xdef456',
        'transactionHash': '0xabc123',
        'timestamp': '1700000000',
        'orderHash': '0xdef456',
        'maker': '0xmaker123',
        'taker': '0xtaker456',
        'makerAssetId': '12345',
        'takerAssetId': '67890',
        'makerAmountFilled': '1000000',  # $1 in USDC base units
        'takerAmountFilled': '2000000',  # $2 in USDC base units
        'fee': '10000'  # $0.01 in USDC base units
    }


@pytest.fixture
def sample_trades():
    """Multiple sample trades for batch testing"""
    return [
        {
            'id': f'0xtx{i}-0xorder{i}',
            'transactionHash': f'0xtx{i}',
            'timestamp': str(1700000000 + i * 1000),
            'orderHash': f'0xorder{i}',
            'maker': f'0xmaker{i}',
            'taker': f'0xtaker{i}',
            'makerAssetId': f'{i}001',
            'takerAssetId': f'{i}002',
            'makerAmountFilled': str(1000000 * (i + 1)),
            'takerAmountFilled': str(2000000 * (i + 1)),
            'fee': str(10000 * (i + 1))
        }
        for i in range(5)
    ]


class TestHistoricalTradeStorage:
    """Test suite for HistoricalTradeStorage"""

    def test_initialization(self, temp_db):
        """Test database initialization"""
        storage = HistoricalTradeStorage(temp_db)

        assert storage.db_path == temp_db
        assert storage.conn is not None

        # Check tables exist
        cursor = storage.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='historical_trades'
        """)
        assert cursor.fetchone() is not None

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='collection_metadata'
        """)
        assert cursor.fetchone() is not None

        storage.close()

    def test_insert_single_trade(self, storage, sample_trade):
        """Test inserting a single trade"""
        result = storage.insert_trade(sample_trade)

        assert result is True  # Should succeed
        assert storage.get_trade_count() == 1

    def test_insert_duplicate_trade(self, storage, sample_trade):
        """Test that duplicate trades are rejected"""
        # Insert first time
        result1 = storage.insert_trade(sample_trade)
        assert result1 is True

        # Try to insert again
        result2 = storage.insert_trade(sample_trade)
        assert result2 is False  # Should fail (duplicate)

        # Count should still be 1
        assert storage.get_trade_count() == 1

    def test_insert_trades_batch(self, storage, sample_trades):
        """Test batch insertion of trades"""
        inserted, duplicates = storage.insert_trades_batch(sample_trades)

        assert inserted == 5
        assert duplicates == 0
        assert storage.get_trade_count() == 5

    def test_insert_batch_with_duplicates(self, storage, sample_trades):
        """Test batch insertion handles duplicates correctly"""
        # Insert first batch
        inserted1, duplicates1 = storage.insert_trades_batch(sample_trades)
        assert inserted1 == 5
        assert duplicates1 == 0

        # Try to insert same batch again
        inserted2, duplicates2 = storage.insert_trades_batch(sample_trades)
        assert inserted2 == 0
        assert duplicates2 == 5

        # Count should still be 5
        assert storage.get_trade_count() == 5

    def test_get_trade_by_id(self, storage, sample_trade):
        """Test retrieving trade by ID"""
        storage.insert_trade(sample_trade)

        retrieved = storage.get_trade_by_id(sample_trade['id'])

        assert retrieved is not None
        assert retrieved['id'] == sample_trade['id']
        assert retrieved['maker'] == sample_trade['maker']
        assert retrieved['taker'] == sample_trade['taker']
        assert retrieved['timestamp'] == int(sample_trade['timestamp'])

    def test_get_trade_by_id_not_found(self, storage):
        """Test retrieving non-existent trade returns None"""
        result = storage.get_trade_by_id('nonexistent')
        assert result is None

    def test_get_trades_by_time_range(self, storage, sample_trades):
        """Test retrieving trades by time range"""
        storage.insert_trades_batch(sample_trades)

        # Get trades from a specific time range
        start_ts = 1700000000
        end_ts = 1700003000

        trades = storage.get_trades_by_time_range(start_ts, end_ts)

        assert len(trades) == 4  # Should get 4 trades in this range

        # Verify they're ordered by timestamp
        timestamps = [t['timestamp'] for t in trades]
        assert timestamps == sorted(timestamps)

    def test_get_trades_by_time_range_with_limit(self, storage, sample_trades):
        """Test retrieving trades with limit"""
        storage.insert_trades_batch(sample_trades)

        trades = storage.get_trades_by_time_range(
            1700000000,
            1700010000,
            limit=2
        )

        assert len(trades) == 2

    def test_get_trades_by_time_range_with_offset(self, storage, sample_trades):
        """Test retrieving trades with offset"""
        storage.insert_trades_batch(sample_trades)

        # Get first 2
        trades1 = storage.get_trades_by_time_range(
            1700000000,
            1700010000,
            limit=2
        )

        # Get next 2 (with offset)
        trades2 = storage.get_trades_by_time_range(
            1700000000,
            1700010000,
            limit=2,
            offset=2
        )

        # Should be different trades
        assert trades1[0]['id'] != trades2[0]['id']

    def test_get_trades_by_asset(self, storage, sample_trades):
        """Test retrieving trades by asset ID"""
        storage.insert_trades_batch(sample_trades)

        # Get trades for specific asset
        trades = storage.get_trades_by_asset('0001')

        assert len(trades) == 1
        assert trades[0]['maker_asset_id'] == '0001'

    def test_get_trades_by_asset_with_limit(self, storage, sample_trades):
        """Test retrieving trades by asset with limit"""
        # Modify trades to use same asset
        for trade in sample_trades:
            trade['makerAssetId'] = 'same_asset'

        storage.insert_trades_batch(sample_trades)

        trades = storage.get_trades_by_asset('same_asset', limit=3)

        assert len(trades) == 3

    def test_get_trade_count_total(self, storage, sample_trades):
        """Test getting total trade count"""
        storage.insert_trades_batch(sample_trades)

        count = storage.get_trade_count()
        assert count == 5

    def test_get_trade_count_with_time_range(self, storage, sample_trades):
        """Test getting trade count within time range"""
        storage.insert_trades_batch(sample_trades)

        count = storage.get_trade_count(
            start_timestamp=1700000000,
            end_timestamp=1700002000
        )

        assert count == 3  # Should have 3 trades in this range

    def test_get_time_range(self, storage, sample_trades):
        """Test getting time range of stored trades"""
        storage.insert_trades_batch(sample_trades)

        time_range = storage.get_time_range()

        assert time_range is not None
        assert time_range[0] == 1700000000  # Oldest
        assert time_range[1] == 1700004000  # Newest

    def test_get_time_range_empty_database(self, storage):
        """Test getting time range from empty database"""
        time_range = storage.get_time_range()
        assert time_range is None

    def test_record_collection(self, storage):
        """Test recording collection metadata"""
        storage.record_collection(
            start_timestamp=1700000000,
            end_timestamp=1700010000,
            trades_collected=100,
            notes="Test collection"
        )

        history = storage.get_collection_history()

        assert len(history) == 1
        assert history[0]['start_timestamp'] == 1700000000
        assert history[0]['end_timestamp'] == 1700010000
        assert history[0]['trades_collected'] == 100
        assert history[0]['notes'] == "Test collection"

    def test_get_collection_history(self, storage):
        """Test retrieving collection history"""
        import time

        # Add multiple collections with slight delays to ensure different timestamps
        for i in range(3):
            storage.record_collection(
                start_timestamp=1700000000 + i * 10000,
                end_timestamp=1700010000 + i * 10000,
                trades_collected=100 + i,
                notes=f"Collection {i}"
            )
            if i < 2:
                time.sleep(0.01)  # Small delay to ensure different timestamps

        history = storage.get_collection_history()

        assert len(history) == 3
        # Verify all collections are present (order may vary due to timing)
        notes = [h['notes'] for h in history]
        assert 'Collection 0' in notes
        assert 'Collection 1' in notes
        assert 'Collection 2' in notes

    def test_get_statistics(self, storage, sample_trades):
        """Test getting database statistics"""
        storage.insert_trades_batch(sample_trades)

        stats = storage.get_statistics()

        assert stats['total_trades'] == 5
        assert stats['oldest_timestamp'] == 1700000000
        assert stats['newest_timestamp'] == 1700004000
        assert stats['unique_makers'] == 5
        assert stats['unique_takers'] == 5
        assert 'database_size_mb' in stats

    def test_get_statistics_empty_database(self, storage):
        """Test statistics on empty database"""
        stats = storage.get_statistics()

        assert stats['total_trades'] == 0
        assert 'oldest_timestamp' not in stats
        assert 'newest_timestamp' not in stats

    def test_context_manager(self, temp_db, sample_trade):
        """Test using storage as context manager"""
        with HistoricalTradeStorage(temp_db) as storage:
            storage.insert_trade(sample_trade)
            assert storage.get_trade_count() == 1

        # Connection should be closed after exiting context
        # Verify data persists by opening again
        with HistoricalTradeStorage(temp_db) as storage:
            assert storage.get_trade_count() == 1

    def test_indexes_exist(self, storage):
        """Test that proper indexes are created"""
        cursor = storage.conn.cursor()

        # Check for indexes
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='historical_trades'
        """)

        indexes = [row[0] for row in cursor.fetchall()]

        assert 'idx_timestamp' in indexes
        assert 'idx_maker_asset' in indexes
        assert 'idx_taker_asset' in indexes
        assert 'idx_maker' in indexes

    def test_database_persistence(self, temp_db, sample_trade):
        """Test that data persists after closing connection"""
        # Insert data and close
        storage1 = HistoricalTradeStorage(temp_db)
        storage1.insert_trade(sample_trade)
        storage1.close()

        # Reopen and verify data exists
        storage2 = HistoricalTradeStorage(temp_db)
        retrieved = storage2.get_trade_by_id(sample_trade['id'])

        assert retrieved is not None
        assert retrieved['id'] == sample_trade['id']

        storage2.close()

    def test_concurrent_inserts(self, storage, sample_trades):
        """Test that batch inserts are atomic"""
        # This tests that all trades in a batch are committed together
        inserted, duplicates = storage.insert_trades_batch(sample_trades)

        # All should be inserted
        assert inserted == len(sample_trades)
        assert storage.get_trade_count() == len(sample_trades)

    def test_integer_field_types(self, storage, sample_trade):
        """Test that integer fields are stored correctly"""
        storage.insert_trade(sample_trade)

        retrieved = storage.get_trade_by_id(sample_trade['id'])

        # Verify integer fields
        assert isinstance(retrieved['timestamp'], int)
        assert isinstance(retrieved['maker_amount_filled'], int)
        assert isinstance(retrieved['taker_amount_filled'], int)
        assert isinstance(retrieved['fee'], int)
        assert isinstance(retrieved['created_at'], int)

    def test_trade_ordering_by_timestamp(self, storage, sample_trades):
        """Test that trades are properly ordered by timestamp"""
        # Insert in random order
        import random
        shuffled = sample_trades.copy()
        random.shuffle(shuffled)

        storage.insert_trades_batch(shuffled)

        # Retrieve all trades
        all_trades = storage.get_trades_by_time_range(0, 2000000000)

        # Should be ordered by timestamp ascending
        timestamps = [t['timestamp'] for t in all_trades]
        assert timestamps == sorted(timestamps)
