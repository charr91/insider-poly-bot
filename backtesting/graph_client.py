"""
The Graph GraphQL Client for Polymarket FPMM Subgraph

Provides access to historical trade data from Polymarket's blockchain data
indexed by The Graph protocol.
"""

import requests
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone, timedelta
import time

logger = logging.getLogger(__name__)


class PolymarketGraphClient:
    """Client for querying Polymarket data from The Graph subgraph"""

    # Goldsky public endpoint for orderbook subgraph (no API key required)
    # This contains OrderFilledEvent entities which are the actual trades
    DEFAULT_ENDPOINT = (
        "https://api.goldsky.com/api/public/"
        "project_cl6mb8i9h0003e201j6li0diw/subgraphs/"
        "orderbook-subgraph/0.0.1/gn"
    )

    # Backup endpoints
    BACKUP_ENDPOINTS = [
        # FPMM subgraph on The Graph (has FpmmTransaction)
        "https://api.thegraph.com/subgraphs/name/tokenunion/polymarket",
    ]

    def __init__(
        self,
        endpoint: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize The Graph client.

        Args:
            endpoint: GraphQL endpoint URL (uses default if not provided)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.endpoint = endpoint or self.DEFAULT_ENDPOINT
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PolymarketInsiderBot/1.0'
        })

        logger.info(f"🌐 Initialized Graph client with endpoint: {self.endpoint}")

    def query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict]:
        """
        Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            Query result data or None on error
        """
        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.endpoint,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()

                result = response.json()

                # Check for GraphQL errors
                if 'errors' in result:
                    logger.error(f"GraphQL errors: {result['errors']}")
                    return None

                return result.get('data')

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All retry attempts failed: {e}")
                    return None

        return None

    def get_trades(
        self,
        first: int = 1000,
        skip: int = 0,
        start_timestamp: Optional[int] = None,
        end_timestamp: Optional[int] = None,
        asset_id: Optional[str] = None,
        order_direction: str = "desc"
    ) -> List[Dict]:
        """
        Fetch historical trades (OrderFilledEvent entities from orderbook).

        Args:
            first: Number of trades to fetch (max 1000 per query)
            skip: Number of trades to skip (for pagination)
            start_timestamp: Unix timestamp - fetch trades after this time
            end_timestamp: Unix timestamp - fetch trades before this time
            asset_id: Filter by specific asset/market ID
            order_direction: "asc" or "desc" (default: desc = newest first)

        Returns:
            List of trade dictionaries
        """
        # Build where clause
        where_conditions = []
        if start_timestamp:
            where_conditions.append(f'timestamp_gte: {start_timestamp}')
        if end_timestamp:
            where_conditions.append(f'timestamp_lte: {end_timestamp}')
        if asset_id:
            # Can filter by maker or taker asset
            where_conditions.append(f'makerAssetId: "{asset_id}"')

        where_clause = ""
        if where_conditions:
            where_clause = f"where: {{ {', '.join(where_conditions)} }}"

        query = f"""
        {{
          orderFilledEvents(
            first: {first}
            skip: {skip}
            orderBy: timestamp
            orderDirection: {order_direction}
            {where_clause}
          ) {{
            id
            transactionHash
            timestamp
            orderHash
            maker
            taker
            makerAssetId
            takerAssetId
            makerAmountFilled
            takerAmountFilled
            fee
          }}
        }}
        """

        result = self.query(query)

        if result and 'orderFilledEvents' in result:
            trades = result['orderFilledEvents']
            logger.debug(
                f"Fetched {len(trades)} trades "
                f"(skip={skip}, first={first})"
            )
            return trades

        return []

    def get_trades_paginated(
        self,
        start_timestamp: Optional[int] = None,
        end_timestamp: Optional[int] = None,
        asset_id: Optional[str] = None,
        max_trades: Optional[int] = None,
        batch_size: int = 1000,
        progress_callback: Optional[callable] = None
    ) -> List[Dict]:
        """
        Fetch trades with automatic pagination.

        Args:
            start_timestamp: Unix timestamp - start of time range
            end_timestamp: Unix timestamp - end of time range
            asset_id: Filter by specific asset/market ID
            max_trades: Maximum number of trades to fetch (None = all)
            batch_size: Number of trades per request (max 1000)
            progress_callback: Optional function(total_fetched) for progress updates

        Returns:
            List of all fetched trades
        """
        all_trades = []
        skip = 0
        batch_size = min(batch_size, 1000)  # The Graph limit

        logger.info(
            f"📥 Starting paginated fetch: "
            f"start={start_timestamp}, end={end_timestamp}, "
            f"max={max_trades or 'unlimited'}"
        )

        while True:
            # Fetch batch
            trades = self.get_trades(
                first=batch_size,
                skip=skip,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                asset_id=asset_id,
                order_direction="desc"
            )

            if not trades:
                logger.info(f"✅ Pagination complete: {len(all_trades)} total trades")
                break

            all_trades.extend(trades)
            skip += len(trades)

            # Progress callback
            if progress_callback:
                progress_callback(len(all_trades))

            # Check limits
            if max_trades and len(all_trades) >= max_trades:
                all_trades = all_trades[:max_trades]
                logger.info(
                    f"✅ Reached max_trades limit: {len(all_trades)} trades"
                )
                break

            # If we got fewer than requested, we've reached the end
            if len(trades) < batch_size:
                logger.info(f"✅ Fetched all available trades: {len(all_trades)} total")
                break

            # Rate limiting - be nice to public endpoint
            time.sleep(0.5)

        return all_trades

    def get_markets(
        self,
        first: int = 100,
        skip: int = 0,
        min_volume: Optional[float] = None
    ) -> List[Dict]:
        """
        Fetch market information.

        Args:
            first: Number of markets to fetch
            skip: Number to skip (pagination)
            min_volume: Minimum scaled collateral volume

        Returns:
            List of market dictionaries
        """
        where_clause = ""
        if min_volume:
            where_clause = f'where: {{ scaledCollateralVolume_gte: "{min_volume}" }}'

        query = f"""
        {{
          fixedProductMarketMakers(
            first: {first}
            skip: {skip}
            orderBy: scaledCollateralVolume
            orderDirection: desc
            {where_clause}
          ) {{
            id
            creator
            creationTimestamp
            conditions
            tradesQuantity
            scaledCollateralVolume
            scaledCollateralBuyVolume
            scaledCollateralSellVolume
            outcomeTokenPrices
            outcomeSlotCount
            lastActiveDay
          }}
        }}
        """

        result = self.query(query)

        if result and 'fixedProductMarketMakers' in result:
            markets = result['fixedProductMarketMakers']
            logger.debug(f"Fetched {len(markets)} markets")
            return markets

        return []

    def get_trades_for_time_range(
        self,
        days_back: int = 30,
        progress_callback: Optional[callable] = None
    ) -> List[Dict]:
        """
        Convenience method to fetch trades for the last N days.

        Args:
            days_back: Number of days of history to fetch
            progress_callback: Optional progress callback function

        Returns:
            List of trades from the time range
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days_back)

        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())

        logger.info(
            f"📅 Fetching {days_back} days of trades: "
            f"{start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}"
        )

        return self.get_trades_paginated(
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            progress_callback=progress_callback
        )

    def test_connection(self) -> bool:
        """
        Test if the subgraph endpoint is accessible.

        Returns:
            True if connection successful
        """
        query = """
        {
          _meta {
            block {
              number
              hash
            }
          }
        }
        """

        result = self.query(query)

        if result and '_meta' in result:
            block_num = result['_meta']['block']['number']
            logger.info(f"✅ Subgraph connection successful (block: {block_num})")
            return True

        logger.error("❌ Subgraph connection failed")
        return False


def main():
    """Test the Graph client"""
    logging.basicConfig(level=logging.INFO)

    client = PolymarketGraphClient()

    # Test connection
    print("\n" + "="*60)
    print("Testing The Graph Connection")
    print("="*60)

    if not client.test_connection():
        print("❌ Failed to connect to subgraph")
        return

    # Fetch recent trades
    print("\n" + "="*60)
    print("Fetching Recent Trades (last 24 hours)")
    print("="*60)

    trades = client.get_trades_for_time_range(days_back=1)

    print(f"\n✅ Fetched {len(trades)} trades")

    if trades:
        print("\nSample trades:")
        for i, trade in enumerate(trades[:3], 1):
            print(f"\n  Trade {i}:")
            print(f"    ID: {trade['id'][:30]}...")
            print(f"    Timestamp: {datetime.fromtimestamp(int(trade['timestamp'])).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Maker: {trade['maker'][:10]}...")
            print(f"    Taker: {trade['taker'][:10]}...")
            print(f"    Maker Asset: {trade['makerAssetId'][:20]}...")
            print(f"    Maker Amount: ${int(trade['makerAmountFilled']) / 1e6:.2f}")
            print(f"    Taker Amount: ${int(trade['takerAmountFilled']) / 1e6:.2f}")
            print(f"    Fee: ${int(trade['fee']) / 1e6:.2f}")


if __name__ == "__main__":
    main()
