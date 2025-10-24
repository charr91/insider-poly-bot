"""
Database migration to add fresh wallet tracking fields to WhaleAddress table.

This migration adds two new boolean columns:
- is_fresh_wallet: Whether the wallet is classified as fresh (first-time trader)
- verified_fresh: Whether the wallet's freshness has been verified via API

Run this migration before deploying the fresh wallet detection feature.
"""

import asyncio
import logging
from pathlib import Path
from sqlalchemy import text
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.database import DATABASE_PATH, get_connection_string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migration(db_path: str = DATABASE_PATH):
    """
    Add is_fresh_wallet and verified_fresh columns to whale_addresses table.

    Args:
        db_path: Path to the SQLite database file
    """
    from database.database import DatabaseManager

    # Initialize database manager
    db_url = get_connection_string(db_path)
    db_manager = DatabaseManager.get_instance(db_url)

    logger.info(f"Starting migration on database: {db_path}")

    try:
        async with db_manager.session() as session:
            # Check if columns already exist
            result = await session.execute(text("PRAGMA table_info(whale_addresses)"))
            columns = result.fetchall()
            existing_columns = [col[1] for col in columns]

            if 'is_fresh_wallet' in existing_columns and 'verified_fresh' in existing_columns:
                logger.info("✅ Migration already applied - columns exist")
                return

            # Add is_fresh_wallet column
            if 'is_fresh_wallet' not in existing_columns:
                logger.info("Adding is_fresh_wallet column...")
                await session.execute(text(
                    "ALTER TABLE whale_addresses ADD COLUMN is_fresh_wallet BOOLEAN DEFAULT 0 NOT NULL"
                ))
                logger.info("✅ Added is_fresh_wallet column")
            else:
                logger.info("ℹ️  is_fresh_wallet column already exists")

            # Add verified_fresh column
            if 'verified_fresh' not in existing_columns:
                logger.info("Adding verified_fresh column...")
                await session.execute(text(
                    "ALTER TABLE whale_addresses ADD COLUMN verified_fresh BOOLEAN DEFAULT 0 NOT NULL"
                ))
                logger.info("✅ Added verified_fresh column")
            else:
                logger.info("ℹ️  verified_fresh column already exists")

            await session.commit()
            logger.info("✅ Migration completed successfully")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise


async def verify_migration(db_path: str = DATABASE_PATH):
    """
    Verify that the migration was applied correctly.

    Args:
        db_path: Path to the SQLite database file
    """
    from database.database import DatabaseManager

    db_url = get_connection_string(db_path)
    db_manager = DatabaseManager.get_instance(db_url)

    async with db_manager.session() as session:
        result = await session.execute(text("PRAGMA table_info(whale_addresses)"))
        columns = result.fetchall()

        logger.info("\nWhale addresses table schema:")
        for col in columns:
            logger.info(f"  - {col[1]} ({col[2]})")

        # Verify fresh wallet columns exist
        column_names = [col[1] for col in columns]
        assert 'is_fresh_wallet' in column_names, "is_fresh_wallet column not found"
        assert 'verified_fresh' in column_names, "verified_fresh column not found"

        logger.info("\n✅ Verification passed - all columns present")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else DATABASE_PATH

    # Check if database exists
    if not Path(db_path).exists():
        logger.error(f"❌ Database not found: {db_path}")
        logger.info("Please ensure the database exists before running migration")
        sys.exit(1)

    # Run migration
    asyncio.run(run_migration(db_path))

    # Verify migration
    asyncio.run(verify_migration(db_path))

    logger.info("\n🎉 Migration complete!")
