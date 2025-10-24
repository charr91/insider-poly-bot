"""
Integration tests for CLI database configuration.

These tests verify that the CLI uses the centralized database configuration
from config/database.py. Full end-to-end CLI tests would require complex
async/sync interaction handling, so these tests focus on verifying that:
- CLI commands use DATABASE_PATH constant as default
- Custom --db-path option can be provided
- CLI components import the correct constants
"""

import pytest
from config.database import DATABASE_PATH
from cli.main import cli


class TestCLIDatabaseConfiguration:
    """Test CLI database path configuration"""

    def test_cli_uses_default_database_path_when_not_specified(self):
        """Verify CLI uses DATABASE_PATH when --db-path not provided"""
        # This test verifies the Click option default value
        from cli.main import cli as cli_group

        # Get the CLI group's parameters
        for param in cli_group.params:
            if param.name == 'db_path':
                # Verify default is DATABASE_PATH
                assert param.default == DATABASE_PATH, \
                    f"CLI --db-path default should be DATABASE_PATH, got {param.default}"
                break
        else:
            pytest.fail("--db-path parameter not found in CLI group")

    def test_cli_db_path_option_exists(self):
        """Verify --db-path option exists and can be provided"""
        # Verify the option is defined
        assert any(param.name == 'db_path' for param in cli.params), \
            "CLI should have --db-path option"

    def test_cli_passes_db_path_to_context(self):
        """Verify CLI passes db_path to command context"""
        import inspect

        # Get the CLI function source
        source = inspect.getsource(cli.callback)

        # Verify db_path is stored in context
        assert "ctx.obj['DB_PATH']" in source or "ctx.ensure_object" in source, \
            "CLI should pass db_path to context object for subcommands"
