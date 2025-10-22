"""
Historical Trade Data Storage

Manages SQLite database for storing historical Polymarket trade data
for backtesting purposes.
"""

import sqlite3
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class HistoricalTradeStorage:
    """SQLite storage for historical trade data"""

    def __init__(self, db_path: str = "backtesting_data.db"):
        """
        Initialize storage with SQLite database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self._init_database()

    def _init_database(self):
        """Create database and tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name

        cursor = self.conn.cursor()

        # Historical trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_trades (
                id TEXT PRIMARY KEY,
                transaction_hash TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                order_hash TEXT NOT NULL,
                maker TEXT NOT NULL,
                taker TEXT NOT NULL,
                maker_asset_id TEXT NOT NULL,
                taker_asset_id TEXT NOT NULL,
                maker_amount_filled INTEGER NOT NULL,
                taker_amount_filled INTEGER NOT NULL,
                fee INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(transaction_hash, order_hash)
            )
        """)

        # Indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON historical_trades(timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_maker_asset
            ON historical_trades(maker_asset_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_taker_asset
            ON historical_trades(taker_asset_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_maker
            ON historical_trades(maker)
        """)

        # Metadata table for tracking data collection
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_timestamp INTEGER NOT NULL,
                end_timestamp INTEGER NOT NULL,
                trades_collected INTEGER NOT NULL,
                collection_date INTEGER NOT NULL,
                notes TEXT
            )
        """)

        self.conn.commit()
        logger.info(f"📦 Database initialized: {self.db_path}")

    def insert_trade(self, trade: Dict) -> bool:
        """
        Insert a single trade into the database.

        Args:
            trade: Trade dictionary from Graph API

        Returns:
            True if inserted, False if duplicate
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                INSERT INTO historical_trades (
                    id, transaction_hash, timestamp, order_hash,
                    maker, taker, maker_asset_id, taker_asset_id,
                    maker_amount_filled, taker_amount_filled, fee,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade['id'],
                trade['transactionHash'],
                int(trade['timestamp']),
                trade['orderHash'],
                trade['maker'],
                trade['taker'],
                trade['makerAssetId'],
                trade['takerAssetId'],
                int(trade['makerAmountFilled']),
                int(trade['takerAmountFilled']),
                int(trade['fee']),
                int(datetime.now(timezone.utc).timestamp())
            ))

            self.conn.commit()
            return True

        except sqlite3.IntegrityError:
            # Duplicate trade - already exists
            return False

        except Exception as e:
            logger.error(f"Error inserting trade: {e}")
            self.conn.rollback()
            raise

    def insert_trades_batch(self, trades: List[Dict]) -> Tuple[int, int]:
        """
        Insert multiple trades efficiently.

        Args:
            trades: List of trade dictionaries

        Returns:
            Tuple of (inserted_count, duplicate_count)
        """
        inserted = 0
        duplicates = 0

        cursor = self.conn.cursor()
        created_at = int(datetime.now(timezone.utc).timestamp())

        for trade in trades:
            try:
                cursor.execute("""
                    INSERT INTO historical_trades (
                        id, transaction_hash, timestamp, order_hash,
                        maker, taker, maker_asset_id, taker_asset_id,
                        maker_amount_filled, taker_amount_filled, fee,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade['id'],
                    trade['transactionHash'],
                    int(trade['timestamp']),
                    trade['orderHash'],
                    trade['maker'],
                    trade['taker'],
                    trade['makerAssetId'],
                    trade['takerAssetId'],
                    int(trade['makerAmountFilled']),
                    int(trade['takerAmountFilled']),
                    int(trade['fee']),
                    created_at
                ))
                inserted += 1

            except sqlite3.IntegrityError:
                duplicates += 1
                continue

        self.conn.commit()

        logger.debug(
            f"Batch insert: {inserted} new, {duplicates} duplicates"
        )

        return inserted, duplicates

    def get_trade_by_id(self, trade_id: str) -> Optional[Dict]:
        """
        Retrieve a trade by its ID.

        Args:
            trade_id: Trade ID

        Returns:
            Trade dictionary or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM historical_trades WHERE id = ?
        """, (trade_id,))

        row = cursor.fetchone()

        if row:
            return dict(row)

        return None

    def get_trades_by_time_range(
        self,
        start_timestamp: int,
        end_timestamp: int,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict]:
        """
        Retrieve trades within a time range.

        Args:
            start_timestamp: Start of range (unix timestamp)
            end_timestamp: End of range (unix timestamp)
            limit: Maximum number of trades to return
            offset: Number of trades to skip

        Returns:
            List of trade dictionaries
        """
        cursor = self.conn.cursor()

        query = """
            SELECT * FROM historical_trades
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """

        params = [start_timestamp, end_timestamp]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        if offset:
            query += " OFFSET ?"
            params.append(offset)

        cursor.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def get_trades_by_asset(
        self,
        asset_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get trades for a specific asset (either maker or taker side).

        Args:
            asset_id: Asset/market ID
            limit: Maximum number of trades to return

        Returns:
            List of trade dictionaries
        """
        cursor = self.conn.cursor()

        query = """
            SELECT * FROM historical_trades
            WHERE maker_asset_id = ? OR taker_asset_id = ?
            ORDER BY timestamp DESC
        """

        params = [asset_id, asset_id]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def get_trade_count(
        self,
        start_timestamp: Optional[int] = None,
        end_timestamp: Optional[int] = None
    ) -> int:
        """
        Get count of trades in database.

        Args:
            start_timestamp: Optional start time filter
            end_timestamp: Optional end time filter

        Returns:
            Number of trades
        """
        cursor = self.conn.cursor()

        if start_timestamp and end_timestamp:
            cursor.execute("""
                SELECT COUNT(*) FROM historical_trades
                WHERE timestamp >= ? AND timestamp <= ?
            """, (start_timestamp, end_timestamp))
        else:
            cursor.execute("SELECT COUNT(*) FROM historical_trades")

        return cursor.fetchone()[0]

    def get_time_range(self) -> Optional[Tuple[int, int]]:
        """
        Get the time range of stored trades.

        Returns:
            Tuple of (oldest_timestamp, newest_timestamp) or None if empty
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM historical_trades
        """)

        row = cursor.fetchone()

        if row[0] and row[1]:
            return (row[0], row[1])

        return None

    def record_collection(
        self,
        start_timestamp: int,
        end_timestamp: int,
        trades_collected: int,
        notes: Optional[str] = None
    ):
        """
        Record metadata about a data collection run.

        Args:
            start_timestamp: Start of collection range
            end_timestamp: End of collection range
            trades_collected: Number of trades collected
            notes: Optional notes about this collection
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO collection_metadata (
                start_timestamp, end_timestamp, trades_collected,
                collection_date, notes
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            start_timestamp,
            end_timestamp,
            trades_collected,
            int(datetime.now(timezone.utc).timestamp()),
            notes
        ))

        self.conn.commit()

    def get_collection_history(self) -> List[Dict]:
        """
        Get history of data collections.

        Returns:
            List of collection metadata dictionaries
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM collection_metadata
            ORDER BY collection_date DESC
        """)

        return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict:
        """
        Get database statistics.

        Returns:
            Dictionary with various statistics
        """
        cursor = self.conn.cursor()

        stats = {}

        # Total trades
        stats['total_trades'] = self.get_trade_count()

        # Time range
        time_range = self.get_time_range()
        if time_range:
            stats['oldest_timestamp'] = time_range[0]
            stats['newest_timestamp'] = time_range[1]
            stats['time_span_days'] = (time_range[1] - time_range[0]) / 86400

        # Unique assets
        cursor.execute("""
            SELECT COUNT(DISTINCT maker_asset_id) FROM historical_trades
        """)
        stats['unique_maker_assets'] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT taker_asset_id) FROM historical_trades
        """)
        stats['unique_taker_assets'] = cursor.fetchone()[0]

        # Unique traders
        cursor.execute("""
            SELECT COUNT(DISTINCT maker) FROM historical_trades
        """)
        stats['unique_makers'] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT taker) FROM historical_trades
        """)
        stats['unique_takers'] = cursor.fetchone()[0]

        # Database size
        stats['database_size_mb'] = Path(self.db_path).stat().st_size / (1024 * 1024)

        return stats

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("📦 Database connection closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
