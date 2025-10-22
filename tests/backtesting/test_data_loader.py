"""
Unit tests for historical data loader
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone

from backtesting.data_loader import HistoricalDataLoader
from backtesting.graph_client import PolymarketGraphClient
from backtesting.historical_storage import HistoricalTradeStorage


@pytest.fixture
def mock_graph_client():
    """Mock Graph client"""
    return Mock(spec=PolymarketGraphClient)


@pytest.fixture
def mock_storage():
    """Mock storage"""
    return Mock(spec=HistoricalTradeStorage)


@pytest.fixture
def sample_trades():
    """Sample trade data"""
    return [
        {
            'id': f'0xtx{i}-0xorder{i}',
            'transactionHash': f'0xtx{i}',
            'timestamp': str(1700000000 + i * 100),
            'orderHash': f'0xorder{i}',
            'maker': f'0xmaker{i}',
            'taker': f'0xtaker{i}',
            'makerAssetId': f'{i}001',
            'takerAssetId': f'{i}002',
            'makerAmountFilled': str(1000000 * (i + 1)),
            'takerAmountFilled': str(2000000 * (i + 1)),
            'fee': str(10000 * (i + 1))
        }
        for i in range(10)
    ]


class TestHistoricalDataLoader:
    """Test suite for HistoricalDataLoader"""

    def test_initialization_with_provided_clients(self, mock_graph_client, mock_storage):
        """Test initialization with provided clients"""
        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        assert loader.graph_client is mock_graph_client
        assert loader.storage is mock_storage
        assert loader._owns_storage is False  # Didn't create storage

    def test_initialization_with_defaults(self):
        """Test initialization creates default clients"""
        with patch('backtesting.data_loader.PolymarketGraphClient') as MockGraph, \
             patch('backtesting.data_loader.HistoricalTradeStorage') as MockStorage:

            loader = HistoricalDataLoader(db_path="test.db")

            MockGraph.assert_called_once()
            MockStorage.assert_called_once_with("test.db")
            assert loader._owns_storage is True  # Created storage

    def test_load_time_range_single_batch(
        self,
        mock_graph_client,
        mock_storage,
        sample_trades
    ):
        """Test loading a time range that fits in one batch"""
        # Setup mocks
        mock_graph_client.get_trades.return_value = sample_trades
        mock_storage.insert_trades_batch.return_value = (10, 0)  # 10 inserted, 0 duplicates

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        # Load data
        stats = loader.load_time_range(
            start_timestamp=1700000000,
            end_timestamp=1700010000
        )

        # Verify Graph API was called correctly
        mock_graph_client.get_trades.assert_called_once_with(
            first=1000,
            skip=0,
            start_timestamp=1700000000,
            end_timestamp=1700010000,
            order_direction="asc"
        )

        # Verify storage was called
        mock_storage.insert_trades_batch.assert_called_once_with(sample_trades)

        # Verify metadata was recorded
        mock_storage.record_collection.assert_called_once()

        # Check stats
        assert stats['total_fetched'] == 10
        assert stats['total_inserted'] == 10
        assert stats['total_duplicates'] == 0
        assert 'time_taken' in stats

    def test_load_time_range_multiple_batches(
        self,
        mock_graph_client,
        mock_storage,
        sample_trades
    ):
        """Test loading data across multiple batches"""
        # Mock returns full batch first, then partial batch, then empty
        mock_graph_client.get_trades.side_effect = [
            sample_trades,  # First batch (10 trades)
            sample_trades[:5],  # Second batch (5 trades)
            []  # Third call returns empty (done)
        ]

        mock_storage.insert_trades_batch.side_effect = [
            (10, 0),  # First batch: 10 inserted
            (5, 0)    # Second batch: 5 inserted
        ]

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        stats = loader.load_time_range(
            start_timestamp=1700000000,
            end_timestamp=1700010000,
            batch_size=10
        )

        # Should have made 2 calls (stopped on partial batch)
        assert mock_graph_client.get_trades.call_count == 2

        # Check calls used correct skip values
        calls = mock_graph_client.get_trades.call_args_list
        assert calls[0][1]['skip'] == 0
        assert calls[1][1]['skip'] == 10

        # Check total stats
        assert stats['total_fetched'] == 15
        assert stats['total_inserted'] == 15
        assert stats['total_duplicates'] == 0

    def test_load_time_range_with_duplicates(
        self,
        mock_graph_client,
        mock_storage,
        sample_trades
    ):
        """Test loading handles duplicates correctly"""
        mock_graph_client.get_trades.return_value = sample_trades
        mock_storage.insert_trades_batch.return_value = (7, 3)  # 7 new, 3 duplicates

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        stats = loader.load_time_range(
            start_timestamp=1700000000,
            end_timestamp=1700010000
        )

        assert stats['total_fetched'] == 10
        assert stats['total_inserted'] == 7
        assert stats['total_duplicates'] == 3

    def test_load_time_range_with_progress_callback(
        self,
        mock_graph_client,
        mock_storage,
        sample_trades
    ):
        """Test progress callback is called"""
        mock_graph_client.get_trades.return_value = sample_trades
        mock_storage.insert_trades_batch.return_value = (10, 0)

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        # Create mock callback
        callback = Mock()

        stats = loader.load_time_range(
            start_timestamp=1700000000,
            end_timestamp=1700010000,
            progress_callback=callback
        )

        # Callback should have been called
        callback.assert_called_once_with(10, 10, 0)

    def test_load_days_back(self, mock_graph_client, mock_storage, sample_trades):
        """Test loading by number of days"""
        mock_graph_client.get_trades.return_value = sample_trades
        mock_storage.insert_trades_batch.return_value = (10, 0)

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        # Load 30 days
        with patch('backtesting.data_loader.datetime') as mock_datetime:
            # Mock current time
            mock_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            stats = loader.load_days_back(days=30)

            # Verify it calculated correct time range
            call_args = mock_graph_client.get_trades.call_args
            start_ts = call_args[1]['start_timestamp']
            end_ts = call_args[1]['end_timestamp']

            # Should be 30 days apart
            assert end_ts - start_ts == 30 * 86400

    def test_load_incremental_with_existing_data(
        self,
        mock_graph_client,
        mock_storage,
        sample_trades
    ):
        """Test incremental load when data exists"""
        # Mock existing data
        mock_storage.get_time_range.return_value = (1700000000, 1700005000)
        mock_graph_client.get_trades.return_value = sample_trades
        mock_storage.insert_trades_batch.return_value = (10, 0)

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        stats = loader.load_incremental()

        # Should start from last trade timestamp
        call_args = mock_graph_client.get_trades.call_args
        assert call_args[1]['start_timestamp'] == 1700005000

    def test_load_incremental_empty_database(
        self,
        mock_graph_client,
        mock_storage,
        sample_trades
    ):
        """Test incremental load on empty database"""
        # Mock no existing data
        mock_storage.get_time_range.return_value = None
        mock_graph_client.get_trades.return_value = sample_trades
        mock_storage.insert_trades_batch.return_value = (10, 0)

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        with patch('backtesting.data_loader.datetime') as mock_datetime:
            mock_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            stats = loader.load_incremental()

            # Should load last 30 days
            call_args = mock_graph_client.get_trades.call_args
            start_ts = call_args[1]['start_timestamp']
            end_ts = call_args[1]['end_timestamp']

            # Should be approximately 30 days
            assert end_ts - start_ts >= 29 * 86400
            assert end_ts - start_ts <= 31 * 86400

    def test_get_storage_stats(self, mock_graph_client, mock_storage):
        """Test getting storage statistics"""
        mock_storage.get_statistics.return_value = {
            'total_trades': 1000,
            'unique_makers': 50,
            'database_size_mb': 2.5
        }

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        stats = loader.get_storage_stats()

        assert stats['total_trades'] == 1000
        assert stats['unique_makers'] == 50
        assert stats['database_size_mb'] == 2.5

        mock_storage.get_statistics.assert_called_once()

    def test_close_owned_storage(self):
        """Test that close() closes storage if loader created it"""
        with patch('backtesting.data_loader.PolymarketGraphClient'), \
             patch('backtesting.data_loader.HistoricalTradeStorage') as MockStorage:

            mock_storage_instance = Mock()
            MockStorage.return_value = mock_storage_instance

            loader = HistoricalDataLoader(db_path="test.db")
            assert loader._owns_storage is True

            loader.close()

            # Should close storage
            mock_storage_instance.close.assert_called_once()

    def test_close_not_owned_storage(self, mock_graph_client, mock_storage):
        """Test that close() doesn't close storage if provided externally"""
        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        assert loader._owns_storage is False

        loader.close()

        # Should NOT close storage
        mock_storage.close.assert_not_called()

    def test_context_manager(self):
        """Test loader works as context manager"""
        with patch('backtesting.data_loader.PolymarketGraphClient'), \
             patch('backtesting.data_loader.HistoricalTradeStorage') as MockStorage:

            mock_storage_instance = Mock()
            MockStorage.return_value = mock_storage_instance

            with HistoricalDataLoader(db_path="test.db") as loader:
                assert loader is not None

            # Should have closed storage
            mock_storage_instance.close.assert_called_once()

    def test_load_time_range_stops_on_empty_result(
        self,
        mock_graph_client,
        mock_storage,
        sample_trades
    ):
        """Test loading stops when API returns empty result"""
        # First call returns empty immediately
        mock_graph_client.get_trades.return_value = []

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        stats = loader.load_time_range(
            start_timestamp=1700000000,
            end_timestamp=1700010000
        )

        # Should have made 1 call and stopped
        assert mock_graph_client.get_trades.call_count == 1
        assert stats['total_fetched'] == 0
        assert stats['total_inserted'] == 0

    def test_load_time_range_stops_on_partial_batch(
        self,
        mock_graph_client,
        mock_storage,
        sample_trades
    ):
        """Test loading stops when receiving partial batch"""
        # Returns full batch, then partial (5 < 10), which stops pagination
        mock_graph_client.get_trades.side_effect = [
            sample_trades,  # 10 trades
            sample_trades[:5]  # 5 trades (partial)
        ]

        mock_storage.insert_trades_batch.side_effect = [(10, 0), (5, 0)]

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        stats = loader.load_time_range(
            start_timestamp=1700000000,
            end_timestamp=1700010000,
            batch_size=10
        )

        # Should have made 2 calls and stopped on partial batch
        assert mock_graph_client.get_trades.call_count == 2
        assert stats['total_fetched'] == 15

    def test_custom_batch_size(self, mock_graph_client, mock_storage, sample_trades):
        """Test using custom batch size"""
        mock_graph_client.get_trades.return_value = sample_trades[:5]
        mock_storage.insert_trades_batch.return_value = (5, 0)

        loader = HistoricalDataLoader(
            graph_client=mock_graph_client,
            storage=mock_storage
        )

        stats = loader.load_time_range(
            start_timestamp=1700000000,
            end_timestamp=1700010000,
            batch_size=500
        )

        # Verify batch size was used
        call_args = mock_graph_client.get_trades.call_args
        assert call_args[1]['first'] == 500
