"""
Unit tests for database models and repositories.

Uses in-memory SQLite for fast testing.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import Base, Alert, AlertOutcome, WhaleAddress, WhaleAlertAssociation
from database.repositories import AlertRepository, OutcomeRepository, WhaleRepository, AssociationRepository


@pytest.fixture
def in_memory_db_url():
    """In-memory SQLite database URL"""
    return "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_session(in_memory_db_url):
    """Create async session for testing"""
    engine = create_async_engine(in_memory_db_url, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

    # Provide session
    async with async_session_maker() as session:
        yield session

    # Cleanup
    await engine.dispose()


class TestAlertModel:
    """Test Alert model and repository"""

    @pytest.mark.asyncio
    async def test_create_alert(self, async_session):
        """Test creating an alert"""
        repo = AlertRepository(async_session)

        alert = await repo.create(
            market_id="test-market-123",
            market_question="Test market?",
            alert_type="VOLUME_SPIKE",
            severity="HIGH",
            timestamp=datetime.now(timezone.utc),
            analysis_json={"max_anomaly_score": 8.5},
            confidence_score=8.5
        )

        assert alert.id is not None
        assert alert.market_id == "test-market-123"
        assert alert.alert_type == "VOLUME_SPIKE"
        assert alert.severity == "HIGH"

    @pytest.mark.asyncio
    async def test_get_recent_alerts(self, async_session):
        """Test querying recent alerts"""
        repo = AlertRepository(async_session)

        # Create multiple alerts
        for i in range(5):
            await repo.create(
                market_id=f"market-{i}",
                market_question=f"Market {i}?",
                alert_type="WHALE_ACTIVITY",
                severity="MEDIUM" if i % 2 == 0 else "HIGH",
                timestamp=datetime.now(timezone.utc),
                analysis_json={},
                confidence_score=5.0
            )

        # Get all recent alerts
        all_alerts = await repo.get_recent_alerts(hours=24, limit=10)
        assert len(all_alerts) == 5

        # Filter by severity
        high_alerts = await repo.get_recent_alerts(hours=24, severity="HIGH", limit=10)
        assert len(high_alerts) == 2

    @pytest.mark.asyncio
    async def test_alert_to_dict(self, async_session):
        """Test alert serialization"""
        repo = AlertRepository(async_session)

        alert = await repo.create(
            market_id="test-123",
            market_question="Test?",
            alert_type="COORDINATED_TRADING",
            severity="CRITICAL",
            timestamp=datetime.now(timezone.utc),
            analysis_json={"coordination_score": 0.9},
            confidence_score=9.0
        )

        alert_dict = alert.to_dict()

        assert isinstance(alert_dict, dict)
        assert alert_dict['market_id'] == "test-123"
        assert alert_dict['severity'] == "CRITICAL"
        assert 'analysis' in alert_dict


class TestWhaleModel:
    """Test WhaleAddress model and repository"""

    @pytest.mark.asyncio
    async def test_create_whale(self, async_session):
        """Test creating a whale"""
        repo = WhaleRepository(async_session)

        whale = await repo.create(
            address="0x1234567890abcdef",
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            total_volume_usd=100000.0,
            trade_count=50,
            buy_volume_usd=60000.0,
            sell_volume_usd=40000.0,
            is_market_maker=False,
            market_maker_score=45,
            tags_json=["whale", "coordination"],
            metrics_json={"avg_trade_size": 2000.0},
            markets_traded_json=["market-1", "market-2"]
        )

        assert whale.id is not None
        assert whale.address == "0x1234567890abcdef"
        assert whale.total_volume_usd == 100000.0
        assert whale.tags == ["whale", "coordination"]
        assert whale.metrics == {"avg_trade_size": 2000.0}

    @pytest.mark.asyncio
    async def test_get_or_create_whale(self, async_session):
        """Test get_or_create functionality"""
        repo = WhaleRepository(async_session)

        # First call creates
        whale1 = await repo.get_or_create(
            address="0xabc123",
            total_volume_usd=50000.0
        )

        assert whale1.id is not None
        original_id = whale1.id

        # Second call retrieves existing
        whale2 = await repo.get_or_create(
            address="0xabc123",
            total_volume_usd=100000.0  # This should be ignored
        )

        assert whale2.id == original_id
        assert whale2.total_volume_usd == 50000.0  # Original value

    @pytest.mark.asyncio
    async def test_get_top_whales(self, async_session):
        """Test getting top whales"""
        repo = WhaleRepository(async_session)

        # Create whales with varying volumes
        for i in range(10):
            await repo.create(
                address=f"0xwhale{i}",
                first_seen=datetime.now(timezone.utc),
                last_seen=datetime.now(timezone.utc),
                total_volume_usd=(i + 1) * 10000.0,
                trade_count=10 * (i + 1),
                buy_volume_usd=5000.0,
                sell_volume_usd=5000.0,
                is_market_maker=(i % 3 == 0),  # Every 3rd is MM
                market_maker_score=75 if i % 3 == 0 else 30
            )

        # Get top 5 whales
        top_whales = await repo.get_top_whales(limit=5, exclude_market_makers=False)
        assert len(top_whales) == 5
        # Should be sorted by volume descending
        assert top_whales[0].total_volume_usd > top_whales[1].total_volume_usd

        # Get top whales excluding MMs
        top_non_mm = await repo.get_top_whales(limit=10, exclude_market_makers=True)
        assert all(not whale.is_market_maker for whale in top_non_mm)


class TestAlertOutcomeModel:
    """Test AlertOutcome model and repository"""

    @pytest.mark.asyncio
    async def test_create_outcome(self, async_session):
        """Test creating an outcome"""
        # First create an alert
        alert_repo = AlertRepository(async_session)
        alert = await alert_repo.create(
            market_id="test-market",
            market_question="Test?",
            alert_type="VOLUME_SPIKE",
            severity="MEDIUM",
            timestamp=datetime.now(timezone.utc),
            analysis_json={},
            confidence_score=5.0
        )

        # Create outcome
        outcome_repo = OutcomeRepository(async_session)
        outcome = await outcome_repo.create(
            alert_id=alert.id,
            price_at_alert=0.50,
            predicted_direction="BUY"
        )

        assert outcome.id is not None
        assert outcome.alert_id == alert.id
        assert outcome.price_at_alert == 0.50
        assert outcome.predicted_direction == "BUY"

    @pytest.mark.asyncio
    async def test_calculate_profitability(self, async_session):
        """Test profitability calculation"""
        alert_repo = AlertRepository(async_session)
        alert = await alert_repo.create(
            market_id="test",
            market_question="Test?",
            alert_type="WHALE_ACTIVITY",
            severity="HIGH",
            timestamp=datetime.now(timezone.utc),
            analysis_json={},
            confidence_score=7.0
        )

        outcome_repo = OutcomeRepository(async_session)
        outcome = await outcome_repo.create(
            alert_id=alert.id,
            price_at_alert=0.50,
            predicted_direction="BUY"
        )

        # Price went up - should be profitable
        outcome.price_24h_after = 0.60
        outcome.calculate_profitability()
        assert outcome.was_profitable is True

        # Price went down - should be unprofitable
        outcome.price_24h_after = 0.40
        outcome.calculate_profitability()
        assert outcome.was_profitable is False

        # Test SELL prediction
        outcome.predicted_direction = "SELL"
        outcome.price_24h_after = 0.40  # Price down
        outcome.calculate_profitability()
        assert outcome.was_profitable is True  # Profitable for SELL


class TestWhaleAlertAssociation:
    """Test whale-alert associations"""

    @pytest.mark.asyncio
    async def test_link_whale_to_alert(self, async_session):
        """Test creating whale-alert association"""
        # Create whale
        whale_repo = WhaleRepository(async_session)
        whale = await whale_repo.create(
            address="0xtest",
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            total_volume_usd=50000.0,
            trade_count=10,
            buy_volume_usd=30000.0,
            sell_volume_usd=20000.0
        )

        # Create alert
        alert_repo = AlertRepository(async_session)
        alert = await alert_repo.create(
            market_id="test",
            market_question="Test?",
            alert_type="COORDINATED_TRADING",
            severity="HIGH",
            timestamp=datetime.now(timezone.utc),
            analysis_json={},
            confidence_score=8.0
        )

        # Link them
        assoc_repo = AssociationRepository(async_session)
        association = await assoc_repo.link_whale_to_alert(
            whale_id=whale.id,
            alert_id=alert.id,
            whale_volume=15000.0,
            whale_role="PRIMARY_ACTOR"
        )

        assert association is not None
        assert association.whale_id == whale.id
        assert association.alert_id == alert.id
        assert association.whale_volume_in_alert == 15000.0
        assert association.whale_role == "PRIMARY_ACTOR"

    @pytest.mark.asyncio
    async def test_prevent_duplicate_associations(self, async_session):
        """Test that duplicate associations are prevented"""
        whale_repo = WhaleRepository(async_session)
        whale = await whale_repo.create(
            address="0xdup",
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            total_volume_usd=10000.0,
            trade_count=5,
            buy_volume_usd=5000.0,
            sell_volume_usd=5000.0
        )

        alert_repo = AlertRepository(async_session)
        alert = await alert_repo.create(
            market_id="test",
            market_question="Test?",
            alert_type="WHALE_ACTIVITY",
            severity="MEDIUM",
            timestamp=datetime.now(timezone.utc),
            analysis_json={},
            confidence_score=6.0
        )

        assoc_repo = AssociationRepository(async_session)

        # First link
        assoc1 = await assoc_repo.link_whale_to_alert(
            whale_id=whale.id,
            alert_id=alert.id,
            whale_volume=5000.0,
            whale_role="PARTICIPANT"
        )

        # Second link with same IDs
        assoc2 = await assoc_repo.link_whale_to_alert(
            whale_id=whale.id,
            alert_id=alert.id,
            whale_volume=10000.0,  # Different value
            whale_role="COORDINATOR"  # Different role
        )

        # Should return existing association
        assert assoc1.id == assoc2.id
        assert assoc2.whale_volume_in_alert == 5000.0  # Original value
