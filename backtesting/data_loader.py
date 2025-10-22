"""
Historical Data Loader

Fetches historical trade data from The Graph and stores it in the database.
"""

import logging
from typing import Optional, Callable
from datetime import datetime, timedelta, timezone

from .graph_client import PolymarketGraphClient
from .historical_storage import HistoricalTradeStorage

logger = logging.getLogger(__name__)


class HistoricalDataLoader:
    """
    Loads historical trade data from The Graph into local database.

    Handles pagination, progress tracking, and deduplication.
    """

    def __init__(
        self,
        graph_client: Optional[PolymarketGraphClient] = None,
        storage: Optional[HistoricalTradeStorage] = None,
        db_path: str = "backtesting_data.db"
    ):
        """
        Initialize data loader.

        Args:
            graph_client: Graph client instance (creates new if None)
            storage: Storage instance (creates new if None)
            db_path: Path to database file (used if storage is None)
        """
        self.graph_client = graph_client or PolymarketGraphClient()
        self.storage = storage or HistoricalTradeStorage(db_path)
        self._owns_storage = storage is None  # Track if we created storage

    def load_time_range(
        self,
        start_timestamp: int,
        end_timestamp: int,
        batch_size: int = 1000,
        progress_callback: Optional[Callable[[int, int, int], None]] = None
    ) -> dict:
        """
        Load trades from a specific time range.

        Args:
            start_timestamp: Start of range (unix timestamp)
            end_timestamp: End of range (unix timestamp)
            batch_size: Number of trades per Graph API query
            progress_callback: Optional callback(total_fetched, inserted, duplicates)

        Returns:
            Dictionary with statistics:
                - total_fetched: Total trades fetched from Graph
                - total_inserted: New trades inserted
                - total_duplicates: Duplicate trades skipped
                - time_taken: Seconds elapsed
        """
        logger.info(
            f"📥 Loading trades from "
            f"{datetime.fromtimestamp(start_timestamp, timezone.utc).strftime('%Y-%m-%d')} to "
            f"{datetime.fromtimestamp(end_timestamp, timezone.utc).strftime('%Y-%m-%d')}"
        )

        start_time = datetime.now()
        total_fetched = 0
        total_inserted = 0
        total_duplicates = 0

        # Fetch trades in batches
        skip = 0

        while True:
            # Fetch batch from Graph
            trades = self.graph_client.get_trades(
                first=batch_size,
                skip=skip,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                order_direction="asc"  # Oldest first for chronological loading
            )

            if not trades:
                logger.info("✅ No more trades to fetch")
                break

            # Store batch
            inserted, duplicates = self.storage.insert_trades_batch(trades)

            total_fetched += len(trades)
            total_inserted += inserted
            total_duplicates += duplicates

            logger.debug(
                f"Batch: {len(trades)} fetched, {inserted} inserted, "
                f"{duplicates} duplicates (total: {total_fetched})"
            )

            # Progress callback
            if progress_callback:
                progress_callback(total_fetched, total_inserted, total_duplicates)

            # Check if we've reached the end
            if len(trades) < batch_size:
                logger.info("✅ Fetched all available trades in range")
                break

            skip += batch_size

        # Record collection metadata
        self.storage.record_collection(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            trades_collected=total_inserted,
            notes=f"Loaded {total_inserted} new trades, {total_duplicates} duplicates"
        )

        time_taken = (datetime.now() - start_time).total_seconds()

        stats = {
            'total_fetched': total_fetched,
            'total_inserted': total_inserted,
            'total_duplicates': total_duplicates,
            'time_taken': time_taken
        }

        logger.info(
            f"✅ Load complete: {total_inserted} inserted, "
            f"{total_duplicates} duplicates, {time_taken:.1f}s"
        )

        return stats

    def load_days_back(
        self,
        days: int = 60,
        progress_callback: Optional[Callable[[int, int, int], None]] = None
    ) -> dict:
        """
        Load trades from the last N days.

        Args:
            days: Number of days of history to load
            progress_callback: Optional progress callback

        Returns:
            Statistics dictionary
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        return self.load_time_range(
            start_timestamp=int(start_time.timestamp()),
            end_timestamp=int(end_time.timestamp()),
            progress_callback=progress_callback
        )

    def load_incremental(
        self,
        progress_callback: Optional[Callable[[int, int, int], None]] = None
    ) -> dict:
        """
        Load trades since the last collection.

        Fetches only new trades since the most recent trade in the database.
        If database is empty, loads last 30 days.

        Args:
            progress_callback: Optional progress callback

        Returns:
            Statistics dictionary
        """
        # Get the most recent trade timestamp in database
        time_range = self.storage.get_time_range()

        if time_range:
            # Start from last trade
            start_timestamp = time_range[1]
            logger.info(
                f"📊 Incremental load from last trade: "
                f"{datetime.fromtimestamp(start_timestamp, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            # No existing data, load last 30 days
            logger.info("📊 No existing data, loading last 30 days")
            start_timestamp = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())

        end_timestamp = int(datetime.now(timezone.utc).timestamp())

        return self.load_time_range(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            progress_callback=progress_callback
        )

    def get_storage_stats(self) -> dict:
        """
        Get statistics about stored data.

        Returns:
            Statistics dictionary from storage
        """
        return self.storage.get_statistics()

    def close(self):
        """Close storage connection if we own it"""
        if self._owns_storage and self.storage:
            self.storage.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def main():
    """Demo/test data loader"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n" + "="*70)
    print("HISTORICAL DATA LOADER - Demo")
    print("="*70)

    # Create loader
    with HistoricalDataLoader(db_path="demo_backtest.db") as loader:

        # Progress callback
        def progress(fetched, inserted, duplicates):
            if fetched % 1000 == 0:
                print(f"  Progress: {fetched} fetched, {inserted} inserted, {duplicates} duplicates")

        # Load last 7 days
        print("\nLoading last 7 days of trade data...")
        stats = loader.load_days_back(days=7, progress_callback=progress)

        print("\n" + "="*70)
        print("LOAD STATISTICS")
        print("="*70)
        print(f"Total Fetched: {stats['total_fetched']}")
        print(f"Total Inserted: {stats['total_inserted']}")
        print(f"Total Duplicates: {stats['total_duplicates']}")
        print(f"Time Taken: {stats['time_taken']:.1f}s")
        print(f"Rate: {stats['total_fetched'] / stats['time_taken']:.0f} trades/sec")

        # Get storage stats
        print("\n" + "="*70)
        print("DATABASE STATISTICS")
        print("="*70)

        storage_stats = loader.get_storage_stats()

        print(f"Total Trades: {storage_stats['total_trades']:,}")

        if 'oldest_timestamp' in storage_stats:
            oldest = datetime.fromtimestamp(storage_stats['oldest_timestamp'], timezone.utc)
            newest = datetime.fromtimestamp(storage_stats['newest_timestamp'], timezone.utc)
            print(f"Time Range: {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}")
            print(f"Span: {storage_stats['time_span_days']:.1f} days")

        print(f"Unique Makers: {storage_stats.get('unique_makers', 0):,}")
        print(f"Unique Takers: {storage_stats.get('unique_takers', 0):,}")
        print(f"Database Size: {storage_stats['database_size_mb']:.2f} MB")

    print("\n✅ Demo complete!\n")


if __name__ == "__main__":
    main()
