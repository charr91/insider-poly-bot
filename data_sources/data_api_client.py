"""
Polymarket Data API Client
Fetches historical and current trade data from public API

This client uses async aiohttp for optimal performance in async contexts
and proper resource management to prevent memory leaks.
"""

import aiohttp
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class DataAPIClient:
    """
    Async client for Polymarket Data API - provides historical trade data.

    Designed for use as an async context manager to ensure proper cleanup:
        async with DataAPIClient() as client:
            trades = await client.get_market_trades(market_id)

    Or with manual lifecycle management:
        client = DataAPIClient()
        await client.__aenter__()
        try:
            trades = await client.get_market_trades(market_id)
        finally:
            await client.__aexit__(None, None, None)
    """

    def __init__(self, base_url: str = "https://data-api.polymarket.com"):
        self.base_url = base_url.rstrip('/')
        self.trades_endpoint = f"{self.base_url}/trades"
        self._session: Optional[aiohttp.ClientSession] = None
        self._owned_session = False  # Track if we created the session

    async def __aenter__(self):
        """Async context manager entry - creates session"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - closes session"""
        await self.close()
        return False

    async def _ensure_session(self):
        """Create session if it doesn't exist"""
        if self._session is None or self._session.closed:
            # Configure timeout for all requests
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)

            # Create session with proper headers
            self._session = aiohttp.ClientSession(
                headers={
                    'User-Agent': 'PolymarketInsiderBot/1.0',
                    'Accept': 'application/json'
                },
                timeout=timeout,
                connector=aiohttp.TCPConnector(
                    limit=10,  # Connection pool limit
                    limit_per_host=5,  # Per-host connection limit
                    ttl_dns_cache=300  # DNS cache TTL
                )
            )
            self._owned_session = True
            logger.debug("DataAPIClient session created")
        
    async def get_market_trades(self, market_id: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Get trades for a specific market.

        Args:
            market_id: Market condition ID
            limit: Maximum number of trades to return (capped at 500)
            offset: Pagination offset

        Returns:
            List of trade dictionaries
        """
        await self._ensure_session()

        params = {
            'market': market_id,
            'limit': min(limit, 500),  # API max is 500
            'offset': offset
        }

        try:
            async with self._session.get(self.trades_endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                trades = await response.json()
                logger.debug(f"Fetched {len(trades)} trades for market {market_id[:10]}...")
                return trades

        except aiohttp.ClientError as e:
            logger.error(f"Error fetching trades for market {market_id[:10]}...: {e}")
            return []
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing JSON for market {market_id[:10]}...: {e}")
            return []
    
    async def get_recent_trades(self, market_ids: List[str], limit: int = 100, batch_size: int = 25) -> List[Dict]:
        """
        Get recent trades across multiple markets with automatic batching.

        Batches large market lists to avoid 414 Request-URI Too Large errors.
        URL length limit ~2000 chars, batch_size=25 keeps us safely under this.

        Args:
            market_ids: List of market condition IDs to filter by (empty = all markets)
            limit: Maximum number of trades to return per request (capped at 500)
            batch_size: Number of markets per batch to avoid URI length limits

        Returns:
            List of trade dictionaries from all batches combined
        """
        # Handle empty or small lists - no batching needed
        if not market_ids or len(market_ids) <= batch_size:
            return await self._fetch_recent_trades_batch(market_ids, limit)

        # Split into batches to avoid URL length limits
        batches = [market_ids[i:i+batch_size] for i in range(0, len(market_ids), batch_size)]
        logger.debug(f"Batching {len(market_ids)} markets into {len(batches)} requests (batch_size={batch_size})")

        # Fetch all batches concurrently for performance
        tasks = [self._fetch_recent_trades_batch(batch, limit) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results from all batches, filtering out errors
        all_trades = []
        errors = 0
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.warning(f"Batch {i+1}/{len(batches)} failed: {result}")
                errors += 1
            elif isinstance(result, list):
                all_trades.extend(result)

        if errors > 0:
            logger.warning(f"Completed with {errors}/{len(batches)} batch errors, got {len(all_trades)} trades")
        else:
            logger.debug(f"Fetched {len(all_trades)} trades from {len(batches)} batches")

        return all_trades

    async def _fetch_recent_trades_batch(self, market_ids: List[str], limit: int) -> List[Dict]:
        """
        Fetch recent trades for a single batch of markets (internal helper).

        Args:
            market_ids: List of market IDs for this batch (or empty for all markets)
            limit: Maximum number of trades to return

        Returns:
            List of trade dictionaries
        """
        await self._ensure_session()

        params = {
            'limit': min(limit, 500)
        }

        # Only add market filter if market_ids provided
        if market_ids:
            market_param = ",".join(market_ids)
            params['market'] = market_param

        try:
            async with self._session.get(self.trades_endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                trades = await response.json()
                market_info = f" across {len(market_ids)} markets" if market_ids else " (all markets)"
                logger.debug(f"Fetched {len(trades)} recent trades{market_info}")
                return trades

        except aiohttp.ClientError as e:
            logger.error(f"Error fetching recent trades: {e}")
            return []
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing JSON for recent trades: {e}")
            return []
    
    async def get_historical_trades(self, market_id: str, lookback_hours: int = 24, max_trades: int = 5000) -> List[Dict]:
        """
        Get historical trades within a time window for baseline analysis.

        Args:
            market_id: Market condition ID
            lookback_hours: How many hours back to fetch data
            max_trades: Maximum number of trades to fetch (default 5000 to prevent memory issues)

        Returns:
            List of trade dictionaries within the time window (up to max_trades)
        """
        all_trades = []
        offset = 0
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        while True:
            # Stop if we've reached the max trades limit
            if len(all_trades) >= max_trades:
                logger.info(f"Reached max_trades limit ({max_trades}) for market {market_id[:10]}...")
                break

            trades = await self.get_market_trades(market_id, limit=500, offset=offset)

            if not trades:
                break

            # Filter by timestamp and add to results
            time_filtered = []
            for trade in trades:
                try:
                    # Handle different timestamp formats
                    timestamp = trade.get('timestamp')
                    if timestamp:
                        if isinstance(timestamp, (int, float)):
                            trade_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                        else:
                            # ISO format
                            trade_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

                        if trade_time > cutoff_time:
                            time_filtered.append(trade)
                        else:
                            # Reached cutoff, return what we have
                            all_trades.extend(time_filtered)
                            return all_trades
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing timestamp for trade: {e}")
                    continue

            all_trades.extend(time_filtered)

            # If we got fewer than requested, we've hit the end
            if len(trades) < 500:
                break

            offset += 500

            # Rate limiting - use asyncio.sleep instead of time.sleep
            await asyncio.sleep(0.1)

        logger.info(f"Fetched {len(all_trades)} historical trades for {market_id[:10]}... (last {lookback_hours}h)")
        return all_trades
    
    async def get_all_recent_trades(self, limit: int = 100) -> List[Dict]:
        """
        Get recent trades across all markets (no market filter).

        Args:
            limit: Maximum number of trades to return (capped at 500)

        Returns:
            List of trade dictionaries
        """
        await self._ensure_session()

        params = {'limit': min(limit, 500)}

        try:
            async with self._session.get(self.trades_endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                trades = await response.json()
                logger.debug(f"Fetched {len(trades)} recent trades across all markets")
                return trades

        except aiohttp.ClientError as e:
            logger.error(f"Error fetching all recent trades: {e}")
            return []
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing JSON for all recent trades: {e}")
            return []

    async def test_connection(self) -> bool:
        """
        Test API connectivity.

        Returns:
            True if connection successful, False otherwise
        """
        await self._ensure_session()

        try:
            async with self._session.get(self.trades_endpoint, params={'limit': 1}, timeout=aiohttp.ClientTimeout(total=5)) as response:
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Data API connection test failed: {e}")
            return False

    async def get_wallet_trades(self, wallet_address: str, limit: int = 100) -> List[Dict]:
        """
        Get trade history for a specific wallet address.

        Used to verify if wallet is fresh/first-time trader.

        Args:
            wallet_address: Wallet address to check
            limit: Maximum trades to fetch (default: 100)

        Returns:
            List of trade dictionaries for this wallet
        """
        await self._ensure_session()

        params = {
            'maker': wallet_address,
            'limit': min(limit, 500)
        }

        try:
            async with self._session.get(
                self.trades_endpoint,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                trades = await response.json()
                logger.debug(f"Fetched {len(trades)} historical trades for wallet {wallet_address[:10]}...")
                return trades

        except aiohttp.ClientError as e:
            logger.error(f"Error fetching trades for wallet {wallet_address[:10]}...: {e}")
            return []
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing JSON for wallet {wallet_address[:10]}...: {e}")
            return []

    async def close(self):
        """Close the session and clean up resources"""
        if self._session and not self._session.closed and self._owned_session:
            await self._session.close()
            logger.debug("DataAPIClient session closed")
            self._session = None