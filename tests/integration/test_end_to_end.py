"""
Integration test for end-to-end database persistence flow

Tests the complete flow:
1. Alert creation → database storage
2. Whale tracking from alerts
3. Outcome tracking initialization
4. Price outcome updates
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from database import DatabaseManager, AlertRepository, WhaleRepository, OutcomeRepository
from persistence.alert_storage import DatabaseAlertStorage
from persistence.whale_tracker import WhaleTracker
from persistence.outcome_tracker import OutcomeTracker
from data_sources.data_api_client import DataAPIClient
from alerts.alert_manager import AlertManager


@pytest_asyncio.fixture
async def test_db():
    """Create temporary test database"""
    # Use temporary directory instead of NamedTemporaryFile
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / 'test.db'

    db_url = f"sqlite+aiosqlite:///{db_path}"
    # Reset singleton for each test
    DatabaseManager._instance = None
    DatabaseManager._engine = None
    DatabaseManager._session_factory = None

    db_manager = DatabaseManager.get_instance(db_url)
    await db_manager.init_db()

    yield db_manager

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_end_to_end_alert_flow(test_db):
    """Test complete alert → whale → outcome flow"""

    # Setup components
    alert_storage = DatabaseAlertStorage(test_db)
    whale_tracker = WhaleTracker(test_db)
    data_api = DataAPIClient()
    outcome_tracker = OutcomeTracker(test_db, data_api)

    # 1. Create and save an alert
    alert_record = {
        'market_id': 'test-market-123',
        'market_question': 'Will Bitcoin reach $100k?',
        'alert_type': 'WHALE_ACTIVITY',
        'severity': 'HIGH',
        'timestamp': datetime.now(timezone.utc),
        'analysis': {
            'whale_trades': [
                {
                    'address': '0xabc123def456',
                    'size': 50000,
                    'side': 'BUY',
                    'price': 0.65,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            ],
            'total_whale_volume': 50000,
            'dominant_side': 'BUY'
        },
        'confidence_score': 8.5
    }

    await alert_storage.save_alert(alert_record)

    # 2. Verify alert was saved
    async with test_db.session() as session:
        alert_repo = AlertRepository(session)
        alerts = await alert_repo.get_recent_alerts(hours=1, limit=10)

        assert len(alerts) == 1
        saved_alert = alerts[0]
        assert saved_alert.market_id == 'test-market-123'
        assert saved_alert.alert_type == 'WHALE_ACTIVITY'
        assert saved_alert.severity == 'HIGH'
        assert saved_alert.confidence_score == 8.5

    # 3. Track whale from alert
    whale_trade = alert_record['analysis']['whale_trades'][0]
    trade_data = {
        'volume_usd': whale_trade['size'],
        'side': whale_trade['side'],
        'market_id': alert_record['market_id'],
        'metrics': {
            'trade_price': whale_trade['price']
        }
    }

    whale_id = await whale_tracker.track_whale(
        address=whale_trade['address'],
        trade_data=trade_data,
        alert_id=saved_alert.id,
        tags=['whale_activity'],
        whale_role='PRIMARY_ACTOR'
    )

    assert whale_id is not None

    # 4. Verify whale was saved
    whale = await whale_tracker.get_whale_by_address(whale_trade['address'])
    assert whale is not None
    assert whale['address'] == whale_trade['address']
    assert whale['total_volume_usd'] == 50000
    assert whale['trade_count'] == 1
    assert whale['is_market_maker'] is False  # Single trade = not MM

    # 5. Create outcome record
    outcome_id = await outcome_tracker.create_outcome_record(
        alert_id=saved_alert.id,
        market_id=alert_record['market_id'],
        current_price=0.65,
        predicted_direction='BUY'
    )

    assert outcome_id is not None

    # 6. Verify outcome was saved
    async with test_db.session() as session:
        outcome_repo = OutcomeRepository(session)
        outcome = await outcome_repo.get_by_alert_id(saved_alert.id)

        assert outcome is not None
        assert outcome.alert_id == saved_alert.id
        assert outcome.price_at_alert == 0.65
        assert outcome.predicted_direction == 'BUY'
        assert outcome.price_1h_after is None  # Not updated yet

    # 7. Verify whale-alert association
    async with test_db.session() as session:
        from database import AssociationRepository
        assoc_repo = AssociationRepository(session)
        alerts_for_whale = await assoc_repo.get_alerts_for_whale(whale_id, limit=10)

        assert len(alerts_for_whale) == 1
        assert alerts_for_whale[0].id == saved_alert.id


@pytest.mark.asyncio
async def test_market_maker_detection_integration(test_db):
    """Test MM detection through multiple trades"""

    whale_tracker = WhaleTracker(test_db)
    address = '0xmm_address_test'

    # Simulate 120 trades across multiple markets with balanced buy/sell
    for i in range(120):
        trade_data = {
            'volume_usd': 1000,
            'side': 'BUY' if i % 2 == 0 else 'SELL',  # Balanced
            'market_id': f'market-{i % 15}',  # 15 different markets
            'metrics': {'trade_num': i}
        }

        await whale_tracker.track_whale(
            address=address,
            trade_data=trade_data,
            tags=['test']
        )

    # Verify MM classification
    whale = await whale_tracker.get_whale_by_address(address)
    assert whale is not None
    assert whale['trade_count'] == 120
    assert whale['buy_volume_usd'] == 60000  # 60 trades * 1000
    assert whale['sell_volume_usd'] == 60000  # 60 trades * 1000
    assert len(whale['markets_traded']) == 15

    # Should be classified as MM (high frequency + balanced + many markets)
    assert whale['is_market_maker'] is True
    assert whale['market_maker_score'] >= 70


@pytest.mark.asyncio
async def test_alert_manager_with_database_storage(test_db):
    """Test AlertManager with database storage backend"""

    alert_storage = DatabaseAlertStorage(test_db)

    # Create mock settings
    class MockSettings:
        class Alerts:
            discord_webhook = ""
            min_severity = "MEDIUM"
            discord_min_severity = "HIGH"
            max_alerts_per_hour = 10

        alerts = Alerts()

    settings = MockSettings()
    alert_manager = AlertManager(settings, storage=alert_storage)

    # Send test alert
    test_alert = {
        'market_id': 'integration-test-market',
        'market_question': 'Integration test market?',
        'alert_type': 'VOLUME_SPIKE',
        'severity': 'HIGH',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'analysis': {
            'max_anomaly_score': 7.5,
            'volume_spike_multiplier': 4.2
        },
        'confidence_score': 7.5,
        'market_data': {
            'volume24hr': 50000,
            'lastTradePrice': 0.55
        },
        'recommended_action': 'Monitor closely'
    }

    success = await alert_manager.send_alert(test_alert)
    assert success is True

    # Verify alert was stored in database
    async with test_db.session() as session:
        alert_repo = AlertRepository(session)
        alerts = await alert_repo.get_alerts_by_market('integration-test-market', limit=10)

        assert len(alerts) == 1
        stored_alert = alerts[0]
        assert stored_alert.market_question == 'Integration test market?'
        assert stored_alert.alert_type == 'VOLUME_SPIKE'
        assert stored_alert.severity == 'HIGH'

    # Test rate limiting
    for i in range(15):
        alert = {**test_alert, 'market_id': f'market-{i}'}
        await alert_manager.send_alert(alert)

    # Get stats - should show rate limiting kicked in
    stats = await alert_manager.get_alert_stats()
    assert stats['total_alerts_24h'] <= 11  # Initial + max 10 per hour
    assert stats.get('rate_limit_active', False) is True
