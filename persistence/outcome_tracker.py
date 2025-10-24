"""
Alert outcome tracking for performance analysis.

Tracks price movements and market resolutions to measure alert effectiveness.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from database import DatabaseManager, AlertRepository, OutcomeRepository
from data_sources.data_api_client import DataAPIClient

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """
    Track alert outcomes via price movements and market resolutions.

    Responsibilities:
    - Initialize outcome tracking for new alerts
    - Update price outcomes at intervals (1h, 4h, 24h)
    - Record final market resolutions
    - Calculate profitability metrics
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        data_api_client: DataAPIClient
    ):
        """
        Initialize outcome tracker.

        Args:
            db_manager: Database manager instance
            data_api_client: Data API client for price lookups
        """
        self.db_manager = db_manager
        self.data_api = data_api_client
        self._logger = logging.getLogger(__name__)

    async def create_outcome_record(
        self,
        alert_id: int,
        market_id: str,
        current_price: float,
        predicted_direction: str
    ) -> Optional[int]:
        """
        Initialize outcome tracking for an alert.

        Args:
            alert_id: Alert ID to track
            market_id: Market ID for price lookups
            current_price: Price at time of alert
            predicted_direction: BUY or SELL prediction

        Returns:
            Outcome ID if successful, None otherwise

        Raises:
            ValueError: If predicted_direction not in ['BUY', 'SELL']
        """
        if predicted_direction not in ['BUY', 'SELL']:
            raise ValueError(f"Invalid predicted_direction: {predicted_direction}")

        try:
            async with self.db_manager.session() as session:
                outcome_repo = OutcomeRepository(session)

                # Check if outcome already exists
                existing = await outcome_repo.get_by_alert_id(alert_id)
                if existing is not None:
                    self._logger.debug(f"Outcome already exists for alert {alert_id}")
                    return existing.id

                # Create new outcome record
                outcome = await outcome_repo.create(
                    alert_id=alert_id,
                    price_at_alert=current_price,
                    predicted_direction=predicted_direction
                )

                self._logger.info(
                    f"Created outcome tracking for alert {alert_id} "
                    f"(price: ${current_price:.3f}, direction: {predicted_direction})"
                )

                return outcome.id

        except Exception as e:
            self._logger.error(f"Failed to create outcome record for alert {alert_id}: {e}", exc_info=True)
            return None

    async def update_price_outcomes(self, batch_size: int = 50) -> int:
        """
        Background task to update price outcomes for pending alerts.

        Fetches current prices and updates 1h/4h/24h fields based on
        time elapsed since alert.

        Args:
            batch_size: Number of alerts to process per batch

        Returns:
            Number of outcomes updated
        """
        try:
            updated_count = 0

            async with self.db_manager.session() as session:
                alert_repo = AlertRepository(session)
                outcome_repo = OutcomeRepository(session)

                # Get outcomes needing updates
                pending_outcomes = await outcome_repo.get_pending_price_updates(
                    max_age_hours=48,
                    limit=batch_size
                )

                for outcome in pending_outcomes:
                    try:
                        # Get associated alert for market_id
                        alert = await alert_repo.get_by_id(outcome.alert_id)
                        if alert is None:
                            continue

                        # Calculate time elapsed since alert
                        now = datetime.now(timezone.utc)
                        time_elapsed = now - alert.timestamp

                        # Fetch current price
                        current_price = await self._fetch_market_price(alert.market_id)
                        if current_price is None:
                            continue

                        # Update appropriate time window
                        updated = False

                        # 1 hour update
                        if time_elapsed >= timedelta(hours=1) and outcome.price_1h_after is None:
                            outcome.price_1h_after = current_price
                            outcome.price_change_1h_pct = (
                                (current_price - outcome.price_at_alert) / outcome.price_at_alert * 100
                            )
                            updated = True
                            self._logger.debug(
                                f"Updated 1h price for alert {alert.id}: "
                                f"${current_price:.3f} ({outcome.price_change_1h_pct:+.1f}%)"
                            )

                        # 4 hour update
                        if time_elapsed >= timedelta(hours=4) and outcome.price_4h_after is None:
                            outcome.price_4h_after = current_price
                            outcome.price_change_4h_pct = (
                                (current_price - outcome.price_at_alert) / outcome.price_at_alert * 100
                            )
                            updated = True
                            self._logger.debug(
                                f"Updated 4h price for alert {alert.id}: "
                                f"${current_price:.3f} ({outcome.price_change_4h_pct:+.1f}%)"
                            )

                        # 24 hour update
                        if time_elapsed >= timedelta(hours=24) and outcome.price_24h_after is None:
                            outcome.price_24h_after = current_price
                            outcome.price_change_24h_pct = (
                                (current_price - outcome.price_at_alert) / outcome.price_at_alert * 100
                            )
                            # Calculate profitability
                            outcome.calculate_profitability()
                            updated = True
                            self._logger.info(
                                f"Updated 24h price for alert {alert.id}: "
                                f"${current_price:.3f} ({outcome.price_change_24h_pct:+.1f}%), "
                                f"profitable: {outcome.was_profitable}"
                            )

                        if updated:
                            outcome.last_updated = now
                            updated_count += 1

                    except Exception as e:
                        self._logger.error(f"Error updating outcome {outcome.id}: {e}")
                        continue

            if updated_count > 0:
                self._logger.info(f"Updated {updated_count} price outcomes")

            return updated_count

        except Exception as e:
            self._logger.error(f"Failed to update price outcomes: {e}", exc_info=True)
            return 0

    async def record_market_resolution(
        self,
        market_id: str,
        resolution: str
    ) -> int:
        """
        Record final market resolution for all alerts on this market.

        Args:
            market_id: Market ID
            resolution: Resolution result (YES/NO/DRAW/CANCELLED)

        Returns:
            Number of outcomes updated
        """
        if resolution not in ['YES', 'NO', 'DRAW', 'CANCELLED']:
            self._logger.warning(f"Invalid resolution: {resolution}")
            return 0

        try:
            updated_count = 0

            async with self.db_manager.session() as session:
                alert_repo = AlertRepository(session)
                outcome_repo = OutcomeRepository(session)

                # Get all alerts for this market
                alerts = await alert_repo.get_alerts_by_market(market_id, limit=1000)

                for alert in alerts:
                    # Get outcome
                    outcome = await outcome_repo.get_by_alert_id(alert.id)
                    if outcome is None:
                        continue

                    # Skip if already resolved
                    if outcome.market_resolved:
                        continue

                    # Update resolution
                    outcome.market_resolved = True
                    outcome.market_resolution = resolution
                    outcome.resolution_timestamp = datetime.now(timezone.utc)
                    outcome.last_updated = datetime.now(timezone.utc)

                    # Recalculate profitability if 24h price available
                    if outcome.price_24h_after is not None:
                        outcome.calculate_profitability()

                    updated_count += 1

                    self._logger.info(
                        f"Recorded resolution for alert {alert.id}: {resolution}, "
                        f"profitable: {outcome.was_profitable}"
                    )

            self._logger.info(
                f"Recorded '{resolution}' resolution for {updated_count} alerts on market {market_id}"
            )

            return updated_count

        except Exception as e:
            self._logger.error(f"Failed to record market resolution: {e}", exc_info=True)
            return 0

    async def get_performance_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Calculate performance statistics for recent alerts.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with performance metrics:
            - total_alerts: Total alerts with outcome data
            - profitable_count: Number of profitable alerts
            - unprofitable_count: Number of unprofitable alerts
            - win_rate: Percentage of profitable alerts
            - avg_profit_pct: Average profit percentage
        """
        try:
            async with self.db_manager.session() as session:
                outcome_repo = OutcomeRepository(session)
                stats = await outcome_repo.get_performance_stats(days=days)

                return stats

        except Exception as e:
            self._logger.error(f"Failed to get performance stats: {e}")
            return {}

    async def _fetch_market_price(self, market_id: str) -> Optional[float]:
        """
        Fetch current market price from API.

        Args:
            market_id: Market ID

        Returns:
            Current price or None if unavailable
        """
        try:
            # Fetch most recent trade data for current price
            market_data = await self.data_api.get_market_trades(market_id, limit=1)

            if not market_data:
                return None

            # Get last trade price
            last_trade = market_data[0]
            price = float(last_trade.get('price', 0))

            return price if price > 0 else None

        except Exception as e:
            self._logger.debug(f"Failed to fetch price for market {market_id}: {e}")
            return None
