"""
Whale address tracking with market maker detection.

Tracks whale wallet addresses, classifies market makers using heuristics,
and associates whales with alerts.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from database import DatabaseManager, WhaleRepository, AssociationRepository
from common import MarketMakerThresholds, WhaleRole

logger = logging.getLogger(__name__)


def calculate_mm_score(
    trade_count: int,
    buy_volume: float,
    sell_volume: float,
    markets_count: int,
    first_seen: datetime,
    last_seen: datetime
) -> int:
    """
    Calculate market maker likelihood score (0-100).

    Score >=70 indicates likely market maker.

    Factors:
    - High frequency trading (30 pts max)
    - Balanced buy/sell ratio (40 pts max)
    - Multiple markets (20 pts max)
    - Consistent activity over time (10 pts max)

    Args:
        trade_count: Total number of trades
        buy_volume: Total USD buy volume
        sell_volume: Total USD sell volume
        markets_count: Number of unique markets traded
        first_seen: First trade timestamp
        last_seen: Last trade timestamp

    Returns:
        Score from 0-100

    Examples:
        >>> from datetime import datetime
        >>> calculate_mm_score(150, 50000, 48000, 12,
        ...                     datetime(2024,1,1), datetime(2024,1,15))
        100  # Likely MM: high frequency, balanced, many markets, 14 days active

        >>> calculate_mm_score(10, 500000, 5000, 2,
        ...                     datetime(2024,1,10), datetime(2024,1,11))
        10  # Not MM: low frequency, very imbalanced, few markets
    """
    score = 0
    total_volume = buy_volume + sell_volume

    # Frequency scoring (0-30 points)
    if trade_count >= MarketMakerThresholds.HIGH_FREQUENCY_TRADES:
        score += MarketMakerThresholds.FREQUENCY_WEIGHT_MAX
    elif trade_count >= MarketMakerThresholds.MEDIUM_FREQUENCY_TRADES:
        score += 20
    elif trade_count >= MarketMakerThresholds.LOW_FREQUENCY_TRADES:
        score += 10

    # Balance scoring (0-40 points)
    if total_volume > 0:
        buy_ratio = buy_volume / total_volume

        if (MarketMakerThresholds.TIGHT_RATIO_MIN <= buy_ratio <=
                MarketMakerThresholds.TIGHT_RATIO_MAX):
            # Within 5% of 50/50 - strong MM indicator
            score += MarketMakerThresholds.BALANCE_WEIGHT_MAX
        elif (MarketMakerThresholds.LOOSE_RATIO_MIN <= buy_ratio <=
                MarketMakerThresholds.LOOSE_RATIO_MAX):
            # Within 10% of 50/50 - moderate MM indicator
            score += 20

    # Market diversity (0-20 points)
    if markets_count >= MarketMakerThresholds.MANY_MARKETS:
        score += MarketMakerThresholds.DIVERSITY_WEIGHT_MAX
    elif markets_count >= MarketMakerThresholds.SEVERAL_MARKETS:
        score += 10

    # Time consistency (0-10 points)
    # Ensure both datetimes are timezone-aware or naive for comparison
    if first_seen.tzinfo is None and last_seen.tzinfo is not None:
        first_seen = first_seen.replace(tzinfo=timezone.utc)
    elif first_seen.tzinfo is not None and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    days_active = (last_seen - first_seen).days
    if days_active >= MarketMakerThresholds.LONG_ACTIVITY_DAYS:
        score += MarketMakerThresholds.CONSISTENCY_WEIGHT_MAX
    elif days_active >= MarketMakerThresholds.MEDIUM_ACTIVITY_DAYS:
        score += 5

    return min(score, 100)


class WhaleTracker:
    """
    Track whale addresses with automatic market maker detection.

    Responsibilities:
    - Record whale trading activity from alerts
    - Classify market makers using heuristics
    - Associate whales with specific alerts
    - Provide whale analytics and queries

    The tracker maintains incremental statistics for each whale and
    automatically recalculates MM scores on updates.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize whale tracker.

        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self._logger = logging.getLogger(__name__)

    async def track_whale(
        self,
        address: str,
        trade_data: Dict[str, Any],
        alert_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
        whale_role: str = WhaleRole.PARTICIPANT
    ) -> Optional[int]:
        """
        Track or update whale address from trade data.

        Automatically recalculates MM score on each update.
        If alert_id is provided, creates whale-alert association.

        Args:
            address: Wallet address
            trade_data: Dict with keys:
                - volume_usd: Trading volume
                - side: 'BUY' or 'SELL'
                - market_id: Market identifier
                - metrics: Optional dict of additional metrics
            alert_id: Optional alert to associate with
            tags: Optional tags (e.g., ["coordination", "volume_spike"])
            whale_role: Role in alert (PRIMARY_ACTOR, COORDINATOR, PARTICIPANT)

        Returns:
            Whale ID if successful, None otherwise

        Raises:
            ValueError: If address is invalid or trade_data incomplete
        """
        # Input validation
        if not address or not isinstance(address, str):
            raise ValueError("Valid address required")

        required_fields = ['volume_usd', 'side', 'market_id']
        for field in required_fields:
            if field not in trade_data:
                raise ValueError(f"Missing required field: {field}")

        try:
            async with self.db_manager.session() as session:
                whale_repo = WhaleRepository(session)

                # Get or create whale
                whale = await whale_repo.get_by_address(address)
                now = datetime.now(timezone.utc)

                if whale is None:
                    # Create new whale
                    self._logger.info(f"Tracking new whale: {address[:10]}...")

                    whale = await whale_repo.create(
                        address=address,
                        first_seen=now,
                        last_seen=now,
                        total_volume_usd=trade_data['volume_usd'],
                        trade_count=1,
                        buy_volume_usd=trade_data['volume_usd'] if trade_data['side'] == 'BUY' else 0,
                        sell_volume_usd=trade_data['volume_usd'] if trade_data['side'] == 'SELL' else 0,
                        tags_json=tags or [],
                        metrics_json=trade_data.get('metrics', {}),
                        markets_traded_json=[trade_data['market_id']]
                    )
                else:
                    # Update existing whale
                    self._logger.debug(f"Updating whale: {address[:10]}...")

                    volume_delta = trade_data['volume_usd']
                    buy_delta = volume_delta if trade_data['side'] == 'BUY' else 0
                    sell_delta = volume_delta if trade_data['side'] == 'SELL' else 0

                    whale = await whale_repo.update_whale(
                        address=address,
                        volume_delta=volume_delta,
                        trade_count_delta=1,
                        buy_volume_delta=buy_delta,
                        sell_volume_delta=sell_delta,
                        market_id=trade_data['market_id'],
                        tags=tags,
                        metrics=trade_data.get('metrics')
                    )

                if whale is None:
                    self._logger.error(f"Failed to track whale {address}")
                    return None

                # Recalculate MM score
                mm_score = calculate_mm_score(
                    trade_count=whale.trade_count,
                    buy_volume=whale.buy_volume_usd,
                    sell_volume=whale.sell_volume_usd,
                    markets_count=len(whale.markets_traded),
                    first_seen=whale.first_seen,
                    last_seen=whale.last_seen
                )

                whale.market_maker_score = mm_score
                whale.is_market_maker = mm_score >= MarketMakerThresholds.MM_CLASSIFICATION_THRESHOLD

                # Log MM status changes
                if whale.is_market_maker:
                    self._logger.info(
                        f"Whale {address[:10]}... classified as MM (score: {mm_score})"
                    )

                # Associate with alert if provided
                if alert_id is not None:
                    assoc_repo = AssociationRepository(session)
                    await assoc_repo.link_whale_to_alert(
                        whale_id=whale.id,
                        alert_id=alert_id,
                        whale_volume=trade_data['volume_usd'],
                        whale_role=whale_role
                    )
                    self._logger.debug(f"Linked whale {whale.id} to alert {alert_id}")

                return whale.id

        except Exception as e:
            self._logger.error(f"Failed to track whale {address}: {e}", exc_info=True)
            return None

    async def get_whale_by_address(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get whale information by address.

        Args:
            address: Wallet address

        Returns:
            Whale data dict or None if not found
        """
        try:
            async with self.db_manager.session() as session:
                whale_repo = WhaleRepository(session)
                whale = await whale_repo.get_by_address(address)

                if whale is None:
                    return None

                return whale.to_dict()

        except Exception as e:
            self._logger.error(f"Failed to get whale {address}: {e}")
            return None

    async def get_top_whales(
        self,
        limit: int = 50,
        exclude_mm: bool = True,
        min_volume: float = 0,
        sort_by: str = 'total_volume_usd'
    ) -> List[Dict[str, Any]]:
        """
        Get top whales by specified metric.

        Args:
            limit: Maximum number of results
            exclude_mm: Whether to exclude market makers
            min_volume: Minimum total volume filter
            sort_by: Field to sort by (total_volume_usd, trade_count, last_seen)

        Returns:
            List of whale data dicts
        """
        try:
            async with self.db_manager.session() as session:
                whale_repo = WhaleRepository(session)
                whales = await whale_repo.get_top_whales(
                    limit=limit,
                    exclude_market_makers=exclude_mm,
                    min_volume=min_volume,
                    sort_by=sort_by
                )

                return [whale.to_dict() for whale in whales]

        except Exception as e:
            self._logger.error(f"Failed to get top whales: {e}")
            return []

    async def update_mm_classifications(
        self,
        min_trades: int = 10,
        batch_size: int = 100
    ) -> int:
        """
        Batch recalculate MM scores for all whales.

        Useful for periodic recalculation or after threshold changes.

        Args:
            min_trades: Only update whales with at least this many trades
            batch_size: Number of whales to process per batch

        Returns:
            Number of whales updated
        """
        try:
            updated_count = 0
            offset = 0

            while True:
                async with self.db_manager.session() as session:
                    whale_repo = WhaleRepository(session)

                    # Get batch of whales
                    whales = await whale_repo.get_all(limit=batch_size, offset=offset)
                    if not whales:
                        break

                    for whale in whales:
                        if whale.trade_count < min_trades:
                            continue

                        # Recalculate MM score
                        mm_score = calculate_mm_score(
                            trade_count=whale.trade_count,
                            buy_volume=whale.buy_volume_usd,
                            sell_volume=whale.sell_volume_usd,
                            markets_count=len(whale.markets_traded),
                            first_seen=whale.first_seen,
                            last_seen=whale.last_seen
                        )

                        # Update if changed
                        if whale.market_maker_score != mm_score:
                            whale.market_maker_score = mm_score
                            whale.is_market_maker = mm_score >= MarketMakerThresholds.MM_CLASSIFICATION_THRESHOLD
                            updated_count += 1

                    offset += batch_size

            self._logger.info(f"Updated MM classifications for {updated_count} whales")
            return updated_count

        except Exception as e:
            self._logger.error(f"Failed to update MM classifications: {e}")
            return 0

    async def get_whale_alerts(
        self,
        address: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get all alerts a whale participated in.

        Args:
            address: Wallet address
            limit: Maximum number of results

        Returns:
            List of alert data dicts
        """
        try:
            async with self.db_manager.session() as session:
                whale_repo = WhaleRepository(session)
                assoc_repo = AssociationRepository(session)

                # Get whale
                whale = await whale_repo.get_by_address(address)
                if whale is None:
                    return []

                # Get associated alerts
                alerts = await assoc_repo.get_alerts_for_whale(
                    whale_id=whale.id,
                    limit=limit
                )

                return [alert.to_dict() for alert in alerts]

        except Exception as e:
            self._logger.error(f"Failed to get alerts for whale {address}: {e}")
            return []

    async def add_whale_tags(
        self,
        address: str,
        tags: List[str]
    ) -> bool:
        """
        Add tags to a whale address.

        Args:
            address: Wallet address
            tags: List of tags to add

        Returns:
            True if successful, False otherwise
        """
        try:
            async with self.db_manager.session() as session:
                whale_repo = WhaleRepository(session)
                whale = await whale_repo.get_by_address(address)

                if whale is None:
                    self._logger.warning(f"Whale {address} not found")
                    return False

                # Add new tags (avoid duplicates)
                current_tags = set(whale.tags)
                current_tags.update(tags)
                whale.tags = list(current_tags)

                return True

        except Exception as e:
            self._logger.error(f"Failed to add tags to whale {address}: {e}")
            return False
