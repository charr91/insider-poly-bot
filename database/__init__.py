"""
Database module for persistent storage.

Provides SQLAlchemy models, async database engine, and repository pattern
for alert tracking, whale monitoring, and outcome correlation.
"""

from .models import Base, Alert, AlertOutcome, WhaleAddress, WhaleAlertAssociation
from .database import DatabaseManager, get_db_manager
from .repositories import (
    AlertRepository,
    OutcomeRepository,
    WhaleRepository,
    AssociationRepository
)

__all__ = [
    "Base",
    "Alert",
    "AlertOutcome",
    "WhaleAddress",
    "WhaleAlertAssociation",
    "DatabaseManager",
    "get_db_manager",
    "AlertRepository",
    "OutcomeRepository",
    "WhaleRepository",
    "AssociationRepository",
]
