"""
Integration tests for database configuration consistency across components.

These tests verify that all parts of the codebase use the centralized
database configuration from config/database.py, preventing database
path inconsistencies and fragmentation.
"""

import pytest
import inspect
from unittest.mock import patch, MagicMock
from config.database import DATABASE_PATH, get_connection_string


@pytest.fixture
def complete_mock_config():
    """Complete mock configuration with all required fields for all detectors"""
    return {
        'monitoring': {
            'max_markets': 5,
            'volume_threshold': 1000,
            'check_interval': 60,
            'sort_by_volume': True
        },
        'detection': {
            'volume_thresholds': {
                'volume_spike_multiplier': 3.0,
                'z_score_threshold': 3.0
            },
            'whale_thresholds': {
                'whale_threshold_usd': 2000,
                'coordination_threshold': 0.7,
                'min_whales_for_coordination': 3
            },
            'price_thresholds': {
                'rapid_movement_pct': 15,
                'price_movement_std': 2.5,
                'volatility_spike_multiplier': 3.0,
                'momentum_threshold': 0.8
            },
            'coordination_thresholds': {
                'min_coordinated_wallets': 5,
                'coordination_time_window': 30,
                'directional_bias_threshold': 0.8,
                'burst_intensity_threshold': 3.0
            },
            'fresh_wallet_thresholds': {
                'min_bet_size_usd': 2000,
                'api_lookback_limit': 100,
                'max_previous_trades': 0
            }
        },
        'alerts': {
            'min_severity': 'MEDIUM',
            'max_alerts_per_hour': 10
        },
        'debug': {
            'debug_mode': False,
            'show_normal_activity': False
        }
    }


class TestComponentDatabaseConsistency:
    """Test that all components use centralized database configuration"""

    def test_market_monitor_uses_database_path(self):
        """Verify MarketMonitor's default db_path is DATABASE_PATH"""
        from market_monitor import MarketMonitor

        # Get the __init__ method signature
        sig = inspect.signature(MarketMonitor.__init__)
        db_path_param = sig.parameters.get('db_path')

        assert db_path_param is not None, "MarketMonitor should have db_path parameter"
        assert db_path_param.default == DATABASE_PATH, \
            f"MarketMonitor db_path default should be DATABASE_PATH, got {db_path_param.default}"

    def test_cli_main_uses_database_path(self):
        """Verify CLI main entry point uses DATABASE_PATH as default"""
        # Import the cli module
        from cli import main as cli_main

        # Read the source code to verify import
        source = inspect.getsource(cli_main)

        # Check that DATABASE_PATH is imported
        assert 'from config.database import DATABASE_PATH' in source, \
            "CLI main should import DATABASE_PATH from config.database"

        # Check that it's used as default
        assert "default=DATABASE_PATH" in source, \
            "CLI should use DATABASE_PATH as default for --db-path option"

    def test_migration_script_uses_database_path(self):
        """Verify database migration script uses DATABASE_PATH as default"""
        # Import migration module
        from database import add_fresh_wallet_fields

        # Check run_migration function signature
        sig = inspect.signature(add_fresh_wallet_fields.run_migration)
        db_path_param = sig.parameters.get('db_path')

        assert db_path_param is not None, "run_migration should have db_path parameter"
        assert db_path_param.default == DATABASE_PATH, \
            f"run_migration default should be DATABASE_PATH, got {db_path_param.default}"

    def test_cli_commands_use_connection_string_helper(self):
        """Verify CLI command files import and use get_connection_string helper"""
        test_cases = [
            ('cli.commands.whale_commands', 'get_connection_string'),
            ('cli.commands.alert_commands', 'get_connection_string'),
            ('cli.commands.stats_commands', 'get_connection_string'),
        ]

        for module_name, expected_import in test_cases:
            # Dynamic import
            module = __import__(module_name, fromlist=[expected_import])

            # Verify the function is available in module
            assert hasattr(module, expected_import), \
                f"{module_name} should import {expected_import} from config.database"

            # Get the imported function
            func = getattr(module, expected_import)

            # Verify it's the correct function
            assert func == get_connection_string, \
                f"{module_name} should use get_connection_string from config.database"

    def test_no_hardcoded_database_paths_in_code(self):
        """
        Regression test: Scan key files for hardcoded database paths.

        This test prevents future code drift by failing if hardcoded paths are introduced.
        """
        import re
        from pathlib import Path

        # Files to check (paths relative to project root)
        files_to_check = [
            'market_monitor.py',
            'cli/main.py',
            'cli/commands/whale_commands.py',
            'cli/commands/alert_commands.py',
            'cli/commands/stats_commands.py',
            'database/add_fresh_wallet_fields.py',
        ]

        # Pattern to detect hardcoded insider_data.db paths
        # Matches: "insider_data.db", 'insider_data.db', or f"...insider_data.db"
        # Excludes: comments, docstrings, and test files
        hardcoded_pattern = re.compile(
            r'''(?<!#)(?<!['"]\s)(?<!from\s)(?<!import\s)["'](?!.*test).*insider_data\.db["']''',
            re.IGNORECASE
        )

        project_root = Path(__file__).parent.parent.parent
        violations = []

        for file_path in files_to_check:
            full_path = project_root / file_path

            if not full_path.exists():
                continue

            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

                for line_num, line in enumerate(lines, 1):
                    # Skip comments and docstrings
                    if line.strip().startswith('#'):
                        continue
                    if '"""' in line or "'''" in line:
                        continue

                    # Check for hardcoded paths
                    # Allow: from config.database import DATABASE_PATH
                    # Allow: Comments and docstrings
                    # Disallow: db_path = "insider_data.db"
                    if '"insider_data.db"' in line or "'insider_data.db'" in line:
                        if 'config.database' not in line and 'import' not in line:
                            violations.append(f"{file_path}:{line_num}: {line.strip()}")

        assert len(violations) == 0, \
            f"Found hardcoded database paths (should use DATABASE_PATH constant):\n" + \
            '\n'.join(violations)


class TestDatabasePathPropagation:
    """Test that database paths properly propagate through the system"""

    @patch('market_monitor.MarketMonitor._load_config')
    @patch('market_monitor.DatabaseManager')
    def test_market_monitor_propagates_db_path_to_database_manager(
        self, mock_db_manager, mock_load_config, complete_mock_config
    ):
        """Verify MarketMonitor passes db_path to DatabaseManager"""
        from market_monitor import MarketMonitor

        # Setup complete mock config
        mock_load_config.return_value = complete_mock_config
        mock_db_instance = MagicMock()
        mock_db_manager.get_instance.return_value = mock_db_instance

        # Create monitor with custom db_path
        custom_path = "test_custom.db"
        monitor = MarketMonitor('test_config.json', db_path=custom_path)

        # Verify DatabaseManager.get_instance was called with connection string
        expected_conn_str = get_connection_string(custom_path)
        mock_db_manager.get_instance.assert_called_once_with(expected_conn_str)

    @patch('market_monitor.MarketMonitor._load_config')
    @patch('market_monitor.DatabaseManager')
    def test_market_monitor_uses_default_database_path_when_not_specified(
        self, mock_db_manager, mock_load_config, complete_mock_config
    ):
        """Verify MarketMonitor uses DATABASE_PATH when db_path not provided"""
        from market_monitor import MarketMonitor

        # Setup complete mock config
        mock_load_config.return_value = complete_mock_config
        mock_db_instance = MagicMock()
        mock_db_manager.get_instance.return_value = mock_db_instance

        # Create monitor WITHOUT specifying db_path
        monitor = MarketMonitor('test_config.json')

        # Verify DatabaseManager.get_instance was called with default DATABASE_PATH
        expected_conn_str = get_connection_string(DATABASE_PATH)
        mock_db_manager.get_instance.assert_called_once_with(expected_conn_str)
