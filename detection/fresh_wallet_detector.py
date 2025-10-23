"""
Fresh Wallet Detection Module
Identifies first-time wallets making large bets on Polymarket
"""

import pandas as pd
from typing import Dict, List, Optional
import logging
from .base_detector import DetectorBase
from .utils import TradeNormalizer, ThresholdValidator, create_consistent_early_return

logger = logging.getLogger(__name__)

class FreshWalletDetector(DetectorBase):
    """Detects fresh wallets making large bets (insider trading signal)"""

    def __init__(self, config: Dict, data_api_client, whale_tracker):
        """
        Initialize fresh wallet detector

        Args:
            config: Configuration dict
            data_api_client: DataAPIClient instance for wallet verification
            whale_tracker: WhaleTracker instance for database checks
        """
        super().__init__(config, 'fresh_wallet')
        self.data_api = data_api_client
        self.whale_tracker = whale_tracker
        self._verification_cache = {}  # In-memory cache for session

    def _load_detector_config(self):
        """Load fresh wallet specific configuration"""
        self.thresholds = self._validate_config_section(
            'fresh_wallet_thresholds',
            ['min_bet_size_usd', 'api_lookback_limit', 'max_previous_trades']
        )

    async def detect_fresh_wallet_activity(self, trades: List[Dict]) -> List[Dict]:
        """
        Detect fresh wallets making large bets.

        Returns one detection result per fresh wallet (not aggregated).

        Args:
            trades: List of trade dictionaries

        Returns:
            List of detection results (one per fresh wallet detected)
        """
        if not trades:
            return []

        # Normalize trades
        normalized_trades = TradeNormalizer.normalize_trades(trades, require_timestamp=False)

        if not normalized_trades:
            return []

        # Filter for large bets above threshold
        large_bets = [
            t for t in normalized_trades
            if t.get('volume_usd', 0) >= self.thresholds['min_bet_size_usd']
            and t.get('maker', 'unknown') != 'unknown'
        ]

        if not large_bets:
            return []

        # Check each wallet for freshness and create individual detection results
        fresh_wallet_detections = []

        for bet in large_bets:
            wallet_address = bet.get('maker')

            # Check if this is a fresh wallet
            is_fresh, trade_count = await self._is_fresh_wallet(wallet_address)

            if is_fresh:
                # Create individual detection for this fresh wallet
                detection = {
                    'anomaly': True,
                    'wallet_address': wallet_address,
                    'bet_size': bet.get('volume_usd'),
                    'side': bet.get('side'),
                    'price': bet.get('price'),
                    'outcome': bet.get('outcome', 'UNKNOWN'),
                    'tx_hash': bet.get('tx_hash'),
                    'timestamp': bet.get('timestamp'),
                    'previous_trade_count': trade_count
                }
                fresh_wallet_detections.append(detection)

        return fresh_wallet_detections

    async def _is_fresh_wallet(self, wallet_address: str) -> tuple[bool, int]:
        """
        Check if wallet is fresh (first-time or very new trader)

        Args:
            wallet_address: Wallet address to check

        Returns:
            Tuple of (is_fresh: bool, trade_count: int)
        """
        # Check in-memory cache first
        if wallet_address in self._verification_cache:
            cached_result = self._verification_cache[wallet_address]
            return cached_result['is_fresh'], cached_result['trade_count']

        # Check database for existing whale record
        whale = await self.whale_tracker.get_whale(wallet_address)

        if whale and whale.verified_fresh:
            # Already verified via API - use cached result
            logger.debug(f"Wallet {wallet_address[:10]}... freshness cached in DB: is_fresh={whale.is_fresh_wallet}")
            self._verification_cache[wallet_address] = {
                'is_fresh': whale.is_fresh_wallet,
                'trade_count': whale.trade_count if whale.is_fresh_wallet else whale.trade_count
            }
            return whale.is_fresh_wallet, whale.trade_count

        # Not verified yet - query Polymarket API
        logger.info(f"🔍 Verifying wallet freshness via API: {wallet_address[:10]}...")

        try:
            wallet_history = await self.data_api.get_wallet_trades(
                wallet_address,
                limit=self.thresholds['api_lookback_limit']
            )

            trade_count = len(wallet_history)
            is_fresh = trade_count <= self.thresholds['max_previous_trades']

            logger.info(
                f"✅ Wallet {wallet_address[:10]}... verification: "
                f"{trade_count} previous trades → {'FRESH' if is_fresh else 'ESTABLISHED'}"
            )

            # Cache result in memory
            self._verification_cache[wallet_address] = {
                'is_fresh': is_fresh,
                'trade_count': trade_count
            }

            # Update database with verification result
            if whale:
                await self.whale_tracker.mark_wallet_verified(wallet_address, is_fresh, trade_count)

            return is_fresh, trade_count

        except Exception as e:
            logger.error(f"Error verifying wallet {wallet_address[:10]}...: {e}")
            # On error, assume not fresh (conservative approach)
            return False, -1
