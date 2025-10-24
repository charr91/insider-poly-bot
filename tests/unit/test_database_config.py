"""
Unit tests for config/database.py module.

Tests the centralized database configuration to ensure:
- Constants are defined correctly
- Connection string builder works properly
- Production and backtesting databases are separate
- Paths follow expected patterns for Docker compatibility
"""

import pytest
from config.database import (
    DATABASE_PATH,
    DOCKER_DATABASE_PATH,
    BACKTEST_DATABASE_PATH,
    DEMO_BACKTEST_DATABASE_PATH,
    get_connection_string
)


class TestDatabaseConstants:
    """Test database path constants"""

    def test_database_path_constant_exists(self):
        """Verify DATABASE_PATH is defined and is a string"""
        assert DATABASE_PATH is not None
        assert isinstance(DATABASE_PATH, str)
        assert len(DATABASE_PATH) > 0

    def test_database_path_is_in_data_directory(self):
        """Ensure production database path is in data/ directory for Docker volume persistence"""
        assert DATABASE_PATH.startswith("data/")
        assert DATABASE_PATH == "data/insider_data.db"

    def test_docker_database_path_constant(self):
        """Verify DOCKER_DATABASE_PATH points to correct location inside container"""
        assert DOCKER_DATABASE_PATH == "/app/data/insider_data.db"
        assert DOCKER_DATABASE_PATH.startswith("/app/data/")
        assert DOCKER_DATABASE_PATH.endswith("insider_data.db")

    def test_backtest_database_paths_defined(self):
        """Verify backtesting database constants exist"""
        assert BACKTEST_DATABASE_PATH is not None
        assert DEMO_BACKTEST_DATABASE_PATH is not None
        assert isinstance(BACKTEST_DATABASE_PATH, str)
        assert isinstance(DEMO_BACKTEST_DATABASE_PATH, str)

    def test_backtest_paths_separate_from_production(self):
        """Ensure backtesting uses different databases than production"""
        # Backtesting databases should NOT be in data/ directory
        assert not BACKTEST_DATABASE_PATH.startswith("data/")
        assert not DEMO_BACKTEST_DATABASE_PATH.startswith("data/")

        # Should have different names
        assert BACKTEST_DATABASE_PATH != DATABASE_PATH
        assert DEMO_BACKTEST_DATABASE_PATH != DATABASE_PATH
        assert BACKTEST_DATABASE_PATH != DEMO_BACKTEST_DATABASE_PATH


class TestConnectionStringBuilder:
    """Test get_connection_string() function"""

    def test_get_connection_string_default(self):
        """Test connection string generation with default path"""
        conn_str = get_connection_string()

        assert conn_str is not None
        assert isinstance(conn_str, str)
        assert conn_str == f"sqlite+aiosqlite:///{DATABASE_PATH}"

    def test_get_connection_string_custom_path(self):
        """Test connection string generation with custom path"""
        custom_path = "custom/path/test.db"
        conn_str = get_connection_string(custom_path)

        assert conn_str == "sqlite+aiosqlite:///custom/path/test.db"
        assert custom_path in conn_str

    def test_get_connection_string_format(self):
        """Verify connection string follows SQLAlchemy async SQLite format"""
        test_cases = [
            ("test.db", "sqlite+aiosqlite:///test.db"),
            ("data/test.db", "sqlite+aiosqlite:///data/test.db"),
            ("backtesting_data.db", "sqlite+aiosqlite:///backtesting_data.db"),
        ]

        for db_path, expected in test_cases:
            conn_str = get_connection_string(db_path)
            assert conn_str == expected
            assert conn_str.startswith("sqlite+aiosqlite:///")

    def test_get_connection_string_preserves_path(self):
        """Ensure get_connection_string doesn't modify the input path"""
        original_path = "some/path/to/database.db"
        conn_str = get_connection_string(original_path)

        # Extract path from connection string
        prefix = "sqlite+aiosqlite:///"
        extracted_path = conn_str[len(prefix):]

        assert extracted_path == original_path


class TestDatabasePathConsistency:
    """Test consistency and relationships between database paths"""

    def test_production_and_docker_paths_match(self):
        """Verify production path and Docker path refer to same database"""
        # DATABASE_PATH: "data/insider_data.db"
        # DOCKER_DATABASE_PATH: "/app/data/insider_data.db"
        assert DATABASE_PATH in DOCKER_DATABASE_PATH
        assert DOCKER_DATABASE_PATH.endswith(DATABASE_PATH)

    def test_all_paths_end_with_db_extension(self):
        """Ensure all database paths have .db extension"""
        paths = [
            DATABASE_PATH,
            DOCKER_DATABASE_PATH,
            BACKTEST_DATABASE_PATH,
            DEMO_BACKTEST_DATABASE_PATH
        ]

        for path in paths:
            assert path.endswith(".db"), f"Path {path} should end with .db"

    def test_production_path_no_leading_slash(self):
        """Ensure production path is relative (no leading slash) for Docker volume compatibility"""
        # Relative paths work both locally and in Docker with volume mounts
        assert not DATABASE_PATH.startswith("/")
        assert not DATABASE_PATH.startswith("./")

    def test_docker_path_absolute(self):
        """Ensure Docker path is absolute (for documentation clarity)"""
        assert DOCKER_DATABASE_PATH.startswith("/")
