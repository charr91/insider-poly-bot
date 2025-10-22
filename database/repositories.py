"""
Repository pattern for database access.

Provides async repositories for CRUD operations and complex queries.
"""

import logging
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload

from .models import Alert, AlertOutcome, WhaleAddress, WhaleAlertAssociation

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    Base repository with common CRUD operations.

    Provides generic database operations for any model type.
    """

    def __init__(self, session: AsyncSession, model: Type[T]):
        """
        Initialize repository.

        Args:
            session: Async database session
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model

    async def create(self, **kwargs) -> T:
        """
        Create new record.

        Args:
            **kwargs: Field values for new record

        Returns:
            Created model instance

        Raises:
            Exception: If creation fails
        """
        try:
            instance = self.model(**kwargs)
            self.session.add(instance)
            await self.session.flush()  # Get ID without committing
            await self.session.refresh(instance)  # Load relationships
            return instance
        except Exception as e:
            logger.error(f"Failed to create {self.model.__name__}: {e}", exc_info=True)
            raise

    async def get_by_id(self, id: int) -> Optional[T]:
        """
        Get record by ID.

        Args:
            id: Record ID

        Returns:
            Model instance or None if not found
        """
        try:
            result = await self.session.get(self.model, id)
            return result
        except Exception as e:
            logger.error(f"Failed to get {self.model.__name__} by ID {id}: {e}")
            return None

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """
        Get all records with pagination.

        Args:
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of model instances
        """
        try:
            stmt = select(self.model).limit(limit).offset(offset)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get all {self.model.__name__}: {e}")
            return []

    async def delete(self, id: int) -> bool:
        """
        Delete record by ID.

        Args:
            id: Record ID

        Returns:
            True if deleted, False if not found
        """
        try:
            instance = await self.get_by_id(id)
            if instance is None:
                return False
            await self.session.delete(instance)
            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Failed to delete {self.model.__name__} {id}: {e}")
            return False

    async def count(self) -> int:
        """
        Count total records.

        Returns:
            Total number of records
        """
        try:
            stmt = select(func.count()).select_from(self.model)
            result = await self.session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Failed to count {self.model.__name__}: {e}")
            return 0


class AlertRepository(BaseRepository[Alert]):
    """Repository for Alert operations"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Alert)

    async def get_recent_alerts(
        self,
        hours: int = 24,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        market_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Alert]:
        """
        Get recent alerts with optional filtering.

        Args:
            hours: Number of hours to look back
            severity: Optional severity filter
            alert_type: Optional alert type filter
            market_id: Optional market ID filter
            limit: Maximum number of results

        Returns:
            List of Alert objects
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

            # Build query with filters
            conditions = [Alert.timestamp > cutoff_time]
            if severity:
                conditions.append(Alert.severity == severity)
            if alert_type:
                conditions.append(Alert.alert_type == alert_type)
            if market_id:
                conditions.append(Alert.market_id == market_id)

            stmt = (
                select(Alert)
                .where(and_(*conditions))
                .options(selectinload(Alert.outcome))  # Eager load outcomes
                .order_by(desc(Alert.timestamp))
                .limit(limit)
            )

            result = await self.session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Failed to get recent alerts: {e}")
            return []

    async def get_alerts_by_market(
        self,
        market_id: str,
        limit: int = 100
    ) -> List[Alert]:
        """
        Get all alerts for a specific market.

        Args:
            market_id: Market ID
            limit: Maximum number of results

        Returns:
            List of Alert objects
        """
        try:
            stmt = (
                select(Alert)
                .where(Alert.market_id == market_id)
                .order_by(desc(Alert.timestamp))
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get alerts for market {market_id}: {e}")
            return []

    async def get_alerts_with_outcomes(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[Alert]:
        """
        Get recent alerts with their outcomes eagerly loaded.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of results

        Returns:
            List of Alert objects with outcomes
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

            stmt = (
                select(Alert)
                .where(Alert.timestamp > cutoff_time)
                .options(selectinload(Alert.outcome))
                .order_by(desc(Alert.timestamp))
                .limit(limit)
            )

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get alerts with outcomes: {e}")
            return []


class OutcomeRepository(BaseRepository[AlertOutcome]):
    """Repository for AlertOutcome operations"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, AlertOutcome)

    async def get_by_alert_id(self, alert_id: int) -> Optional[AlertOutcome]:
        """
        Get outcome for a specific alert.

        Args:
            alert_id: Alert ID

        Returns:
            AlertOutcome or None
        """
        try:
            stmt = select(AlertOutcome).where(AlertOutcome.alert_id == alert_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get outcome for alert {alert_id}: {e}")
            return None

    async def get_pending_price_updates(
        self,
        max_age_hours: int = 48,
        limit: int = 50
    ) -> List[AlertOutcome]:
        """
        Get outcomes that need price updates.

        Finds outcomes where:
        - Alert is less than max_age_hours old
        - price_24h_after is still None (not fully updated)

        Args:
            max_age_hours: Maximum alert age to consider
            limit: Maximum number of results

        Returns:
            List of AlertOutcome objects needing updates
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

            stmt = (
                select(AlertOutcome)
                .join(Alert)
                .where(
                    and_(
                        Alert.timestamp > cutoff_time,
                        or_(
                            AlertOutcome.price_1h_after.is_(None),
                            AlertOutcome.price_4h_after.is_(None),
                            AlertOutcome.price_24h_after.is_(None)
                        )
                    )
                )
                .options(selectinload(AlertOutcome.alert))
                .order_by(asc(AlertOutcome.last_updated))
                .limit(limit)
            )

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get pending price updates: {e}")
            return []

    async def get_performance_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Calculate performance statistics for outcomes.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with performance metrics
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)

            # Get outcomes with profitability data
            stmt = (
                select(AlertOutcome)
                .join(Alert)
                .where(
                    and_(
                        Alert.timestamp > cutoff_time,
                        AlertOutcome.was_profitable.is_not(None)
                    )
                )
            )

            result = await self.session.execute(stmt)
            outcomes = list(result.scalars().all())

            if not outcomes:
                return {
                    'total_alerts': 0,
                    'profitable_count': 0,
                    'unprofitable_count': 0,
                    'win_rate': 0.0,
                    'avg_profit_pct': 0.0,
                }

            profitable = [o for o in outcomes if o.was_profitable]
            unprofitable = [o for o in outcomes if not o.was_profitable]

            # Calculate average profit percentage
            avg_profit = sum(
                o.price_change_24h_pct for o in outcomes
                if o.price_change_24h_pct is not None
            ) / len(outcomes) if outcomes else 0.0

            return {
                'total_alerts': len(outcomes),
                'profitable_count': len(profitable),
                'unprofitable_count': len(unprofitable),
                'win_rate': len(profitable) / len(outcomes) if outcomes else 0.0,
                'avg_profit_pct': avg_profit,
            }
        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}")
            return {}


class WhaleRepository(BaseRepository[WhaleAddress]):
    """Repository for WhaleAddress operations"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, WhaleAddress)

    async def get_by_address(self, address: str) -> Optional[WhaleAddress]:
        """
        Get whale by wallet address.

        Args:
            address: Wallet address

        Returns:
            WhaleAddress or None
        """
        try:
            stmt = select(WhaleAddress).where(WhaleAddress.address == address)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get whale by address {address}: {e}")
            return None

    async def get_or_create(self, address: str, **kwargs) -> WhaleAddress:
        """
        Get existing whale or create new one.

        Args:
            address: Wallet address
            **kwargs: Additional fields for creation

        Returns:
            WhaleAddress instance
        """
        whale = await self.get_by_address(address)
        if whale is None:
            # Set defaults for new whale
            if 'first_seen' not in kwargs:
                kwargs['first_seen'] = datetime.now(timezone.utc)
            if 'last_seen' not in kwargs:
                kwargs['last_seen'] = datetime.now(timezone.utc)

            whale = await self.create(address=address, **kwargs)

        return whale

    async def get_top_whales(
        self,
        limit: int = 50,
        exclude_market_makers: bool = True,
        min_volume: float = 0,
        sort_by: str = 'total_volume_usd'
    ) -> List[WhaleAddress]:
        """
        Get top whales sorted by specified metric.

        Args:
            limit: Maximum number of results
            exclude_market_makers: Whether to exclude MMs
            min_volume: Minimum total volume filter
            sort_by: Field to sort by (total_volume_usd, trade_count, last_seen)

        Returns:
            List of WhaleAddress objects
        """
        try:
            conditions = [WhaleAddress.total_volume_usd >= min_volume]
            if exclude_market_makers:
                conditions.append(WhaleAddress.is_market_maker == False)

            # Determine sort column
            sort_column = getattr(WhaleAddress, sort_by, WhaleAddress.total_volume_usd)

            stmt = (
                select(WhaleAddress)
                .where(and_(*conditions))
                .order_by(desc(sort_column))
                .limit(limit)
            )

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get top whales: {e}")
            return []

    async def update_whale(
        self,
        address: str,
        volume_delta: float = 0,
        trade_count_delta: int = 0,
        buy_volume_delta: float = 0,
        sell_volume_delta: float = 0,
        market_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metrics: Optional[Dict] = None
    ) -> Optional[WhaleAddress]:
        """
        Update whale statistics incrementally.

        Args:
            address: Wallet address
            volume_delta: Amount to add to total volume
            trade_count_delta: Amount to add to trade count
            buy_volume_delta: Amount to add to buy volume
            sell_volume_delta: Amount to add to sell volume
            market_id: Optional market to add to markets_traded
            tags: Optional tags to add
            metrics: Optional metrics to merge

        Returns:
            Updated WhaleAddress or None
        """
        try:
            whale = await self.get_by_address(address)
            if whale is None:
                return None

            # Update volumes
            whale.total_volume_usd += volume_delta
            whale.trade_count += trade_count_delta
            whale.buy_volume_usd += buy_volume_delta
            whale.sell_volume_usd += sell_volume_delta
            whale.last_seen = datetime.now(timezone.utc)

            # Update markets traded
            # Create new list to trigger SQLAlchemy change detection
            if market_id and market_id not in whale.markets_traded:
                whale.markets_traded = whale.markets_traded + [market_id]

            # Update tags
            if tags:
                current_tags = set(whale.tags)
                current_tags.update(tags)
                whale.tags = list(current_tags)

            # Update metrics
            if metrics:
                current_metrics = whale.metrics
                current_metrics.update(metrics)
                whale.metrics = current_metrics

            await self.session.flush()
            return whale

        except Exception as e:
            logger.error(f"Failed to update whale {address}: {e}")
            return None


class AssociationRepository(BaseRepository[WhaleAlertAssociation]):
    """Repository for WhaleAlertAssociation operations"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, WhaleAlertAssociation)

    async def link_whale_to_alert(
        self,
        whale_id: int,
        alert_id: int,
        whale_volume: float,
        whale_role: str = "PARTICIPANT"
    ) -> Optional[WhaleAlertAssociation]:
        """
        Create association between whale and alert.

        Args:
            whale_id: Whale ID
            alert_id: Alert ID
            whale_volume: Whale's volume in this alert
            whale_role: Role (PRIMARY_ACTOR, COORDINATOR, PARTICIPANT)

        Returns:
            Created association or None if already exists
        """
        try:
            # Check if association already exists
            stmt = select(WhaleAlertAssociation).where(
                and_(
                    WhaleAlertAssociation.whale_id == whale_id,
                    WhaleAlertAssociation.alert_id == alert_id
                )
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.debug(f"Association already exists: whale {whale_id}, alert {alert_id}")
                return existing

            # Create new association
            return await self.create(
                whale_id=whale_id,
                alert_id=alert_id,
                whale_volume_in_alert=whale_volume,
                whale_role=whale_role
            )

        except Exception as e:
            logger.error(f"Failed to link whale {whale_id} to alert {alert_id}: {e}")
            return None

    async def get_whales_for_alert(self, alert_id: int) -> List[WhaleAddress]:
        """
        Get all whales associated with an alert.

        Args:
            alert_id: Alert ID

        Returns:
            List of WhaleAddress objects
        """
        try:
            stmt = (
                select(WhaleAddress)
                .join(WhaleAlertAssociation)
                .where(WhaleAlertAssociation.alert_id == alert_id)
                .order_by(desc(WhaleAlertAssociation.whale_volume_in_alert))
            )

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get whales for alert {alert_id}: {e}")
            return []

    async def get_alerts_for_whale(self, whale_id: int, limit: int = 50) -> List[Alert]:
        """
        Get all alerts a whale participated in.

        Args:
            whale_id: Whale ID
            limit: Maximum number of results

        Returns:
            List of Alert objects
        """
        try:
            stmt = (
                select(Alert)
                .join(WhaleAlertAssociation)
                .where(WhaleAlertAssociation.whale_id == whale_id)
                .order_by(desc(Alert.timestamp))
                .limit(limit)
            )

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get alerts for whale {whale_id}: {e}")
            return []
