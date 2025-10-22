"""
Database engine and session management.

Provides async SQLAlchemy engine, session factory, and database initialization.
"""

import logging
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
    AsyncSession
)
from sqlalchemy.pool import StaticPool

from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Singleton database manager with async support.

    Manages SQLite database connection, session factory, and schema initialization.
    """

    _instance: Optional["DatabaseManager"] = None
    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def __new__(cls, db_url: Optional[str] = None):
        """Implement singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            db_url: Database URL (defaults to sqlite+aiosqlite:///insider_bot.db)
        """
        # Only initialize once
        if self._engine is not None:
            return

        if db_url is None:
            db_url = "sqlite+aiosqlite:///insider_bot.db"

        logger.info(f"Initializing database: {db_url}")

        # Create async engine with proper configuration
        self._engine = create_async_engine(
            db_url,
            echo=False,  # Set to True for SQL query logging
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections every hour
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
        )

        # Create session factory
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Prevent lazy loading issues
        )

        logger.info("Database manager initialized successfully")

    @classmethod
    def get_instance(cls, db_url: Optional[str] = None) -> "DatabaseManager":
        """
        Get singleton instance of DatabaseManager.

        Args:
            db_url: Database URL (only used on first call)

        Returns:
            DatabaseManager singleton instance
        """
        if cls._instance is None:
            cls._instance = cls(db_url)
        return cls._instance

    @property
    def engine(self) -> AsyncEngine:
        """Get database engine"""
        if self._engine is None:
            raise RuntimeError("Database engine not initialized")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get session factory"""
        if self._session_factory is None:
            raise RuntimeError("Session factory not initialized")
        return self._session_factory

    async def init_db(self) -> None:
        """
        Initialize database schema.

        Creates all tables if they don't exist.
        """
        try:
            logger.info("Creating database tables...")
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise

    async def drop_all(self) -> None:
        """
        Drop all database tables.

        WARNING: This deletes all data! Use only for testing or reset.
        """
        logger.warning("Dropping all database tables...")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped")

    async def close(self) -> None:
        """
        Gracefully close database connections.

        Should be called on application shutdown.
        """
        if self._engine is not None:
            logger.info("Closing database connections...")
            await self._engine.dispose()
            logger.info("Database connections closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for database sessions.

        Automatically handles commits and rollbacks.

        Example:
            async with db_manager.session() as session:
                repo = AlertRepository(session)
                alert = await repo.create(**alert_data)

        Yields:
            AsyncSession object
        """
        if self._session_factory is None:
            raise RuntimeError("Session factory not initialized")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}", exc_info=True)
                raise
            finally:
                await session.close()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(db_url: Optional[str] = None) -> DatabaseManager:
    """
    Get global database manager instance.

    Args:
        db_url: Optional database URL (only used on first call)

    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_url)
    return _db_manager


async def init_database(db_url: Optional[str] = None) -> DatabaseManager:
    """
    Initialize database and create tables.

    Convenience function for application startup.

    Args:
        db_url: Optional database URL

    Returns:
        Initialized DatabaseManager
    """
    db_manager = get_db_manager(db_url)
    await db_manager.init_db()
    return db_manager
