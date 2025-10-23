"""
Database-backed alert storage.

Implements AlertStorage protocol for persistent alert tracking.
"""

import logging
from typing import Dict, List
from datetime import datetime, timedelta, timezone

from database import DatabaseManager, AlertRepository
from detection.utils import JSONSanitizer

logger = logging.getLogger(__name__)


class DatabaseAlertStorage:
    """
    Database-backed alert storage implementing AlertStorage protocol.

    Provides persistent storage for alerts with rate limiting and deduplication.
    Compatible with existing AlertManager interface.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize database alert storage.

        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self._logger = logging.getLogger(__name__)

        # For backward compatibility with MemoryAlertStorage interface
        self.alert_history: List[Dict] = []

    async def save_alert(self, alert_record: Dict) -> None:
        """
        Save alert record to database.

        Args:
            alert_record: Alert data dict with keys:
                - timestamp: datetime
                - market_id: str
                - alert_type: str (enum or string)
                - severity: str
                - (optional) market_question: str
                - (optional) analysis: dict
                - (optional) confidence_score: float

        Raises:
            Exception: If save fails
        """
        try:
            async with self.db_manager.session() as session:
                alert_repo = AlertRepository(session)

                # Convert alert_type enum to string if needed
                alert_type = alert_record.get('alert_type', 'UNKNOWN')
                alert_type_str = alert_type.value if hasattr(alert_type, 'value') else str(alert_type)

                # Extract and normalize timestamp
                timestamp = alert_record.get('timestamp', datetime.now(timezone.utc))

                # Handle ISO string timestamps
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

                # Ensure timezone-aware
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)

                # Extract fields for database model
                # Sanitize analysis data to convert numpy types to native Python types for JSON serialization
                analysis_data = alert_record.get('analysis', {})
                sanitized_analysis = JSONSanitizer.sanitize(analysis_data)

                alert_data = {
                    'market_id': alert_record.get('market_id', ''),
                    'market_question': alert_record.get('market_question', 'Unknown Market'),
                    'alert_type': alert_type_str,
                    'severity': str(alert_record.get('severity', 'LOW')),
                    'timestamp': timestamp,
                    'analysis_json': sanitized_analysis,
                    'confidence_score': alert_record.get('confidence_score', 0.0),
                }

                await alert_repo.create(**alert_data)
                self._logger.debug(f"Saved alert for market {alert_data['market_id']}")

                # Update in-memory history for backward compatibility
                self.alert_history.append(alert_record)

        except Exception as e:
            self._logger.error(f"Failed to save alert: {e}", exc_info=True)
            raise

    async def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """
        Get alerts from the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of alert record dicts
        """
        try:
            async with self.db_manager.session() as session:
                alert_repo = AlertRepository(session)
                alerts = await alert_repo.get_recent_alerts(hours=hours, limit=1000)

                # Convert to dict format for backward compatibility
                return [
                    {
                        'timestamp': alert.timestamp,
                        'market_id': alert.market_id,
                        'alert_type': alert.alert_type,
                        'severity': alert.severity
                    }
                    for alert in alerts
                ]

        except Exception as e:
            self._logger.error(f"Failed to get recent alerts: {e}")
            return []

    async def should_send_alert(
        self,
        alert: Dict,
        max_per_hour: int,
        duplicate_window_minutes: int = 10
    ) -> bool:
        """
        Check if alert should be sent based on rate limiting and deduplication.

        Args:
            alert: Alert data dict
            max_per_hour: Maximum alerts per hour
            duplicate_window_minutes: Time window for duplicate detection

        Returns:
            True if alert should be sent, False if it should be filtered
        """
        try:
            async with self.db_manager.session() as session:
                alert_repo = AlertRepository(session)

                # Rate limiting - count recent alerts (last hour)
                recent_alerts = await alert_repo.get_recent_alerts(hours=1, limit=max_per_hour + 1)

                if len(recent_alerts) >= max_per_hour:
                    self._logger.debug(f"Rate limit exceeded: {len(recent_alerts)}/{max_per_hour}")
                    return False

                # Deduplication - check for same market/type in recent window
                market_id = alert.get('market_id')
                alert_type = alert.get('alert_type')

                if not market_id or not alert_type:
                    return True  # Can't deduplicate without these fields

                # Check for duplicates in the window
                window_hours = duplicate_window_minutes / 60.0
                duplicate_alerts = await alert_repo.get_recent_alerts(
                    hours=window_hours,
                    market_id=market_id,
                    alert_type=str(alert_type),
                    limit=1
                )

                if duplicate_alerts:
                    self._logger.debug(
                        f"Duplicate alert filtered: {alert_type} for market {market_id}"
                    )
                    return False

                return True

        except Exception as e:
            self._logger.error(f"Error checking alert send conditions: {e}")
            # Default to allowing alert on error
            return True

    async def clear_old_alerts(self, max_age_hours: int = 48) -> None:
        """
        Remove alerts older than specified hours.

        Note: For database storage, this is handled by retention policies.
        This method maintains compatibility with the protocol but may be a no-op.

        Args:
            max_age_hours: Maximum age of alerts to keep
        """
        # For now, we keep all alerts in database
        # In production, this would be handled by a separate cleanup job
        self._logger.debug(f"Database alerts retained (no cleanup for {max_age_hours}h)")

        # Clean in-memory cache for backward compatibility
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        self.alert_history = [
            alert for alert in self.alert_history
            if alert.get('timestamp', datetime.min.replace(tzinfo=timezone.utc)) > cutoff_time
        ]
