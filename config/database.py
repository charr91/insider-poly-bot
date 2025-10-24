"""
Database configuration constants.

IMPORTANT: This is the SINGLE SOURCE OF TRUTH for database paths.
All code should import from here to ensure consistency across the codebase.

WHY THIS EXISTS:
--------------
To prevent database path inconsistencies that can lead to:
- Multiple database files in different locations
- CLI commands querying wrong database
- Data loss across container restarts
- Future code drift and confusion

USAGE:
------
Always import these constants instead of hardcoding paths:

    from config.database import DATABASE_PATH, get_connection_string

    # For function defaults
    def __init__(self, db_path: str = DATABASE_PATH):
        ...

    # For DatabaseManager
    db_manager = DatabaseManager.get_instance(get_connection_string(db_path))

PATHS:
------
- Production: data/insider_data.db (works both locally and in Docker)
- Docker mount: ./data:/app/data (persists across container restarts)
- Full container path: /app/data/insider_data.db
"""

# Primary database path - used for production and development
# This path works in both Docker (mounted volume) and local development
DATABASE_PATH = "data/insider_data.db"

# Full path as it appears inside Docker container
# Useful for documentation and debugging
DOCKER_DATABASE_PATH = "/app/data/insider_data.db"

# Database connection string builder
def get_connection_string(db_path: str = DATABASE_PATH) -> str:
    """
    Get SQLAlchemy connection string for the database.

    Args:
        db_path: Path to the SQLite database file (default: DATABASE_PATH)

    Returns:
        SQLAlchemy connection string for AsyncIO SQLite access

    Example:
        >>> from config.database import get_connection_string
        >>> conn_str = get_connection_string()
        >>> print(conn_str)
        sqlite+aiosqlite:///data/insider_data.db
    """
    return f"sqlite+aiosqlite:///{db_path}"


# Backtesting database paths (separate from production)
BACKTEST_DATABASE_PATH = "backtesting_data.db"
DEMO_BACKTEST_DATABASE_PATH = "demo_backtest.db"
