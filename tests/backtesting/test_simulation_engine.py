"""
Unit tests for simulation engine
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from collections import deque

from backtesting.simulation_engine import (
    SimulationEngine,
    MarketState,
    VirtualAlert
)


@pytest.fixture
def sample_config():
    """Sample configuration for detectors"""
    return {
        'volume': {
            'spike_threshold': 5.0,
            'window_minutes': 60
        },
        'whale': {
            'large_trade_threshold': 10000.0
        }
    }


@pytest.fixture
def sample_trade():
    """Sample trade in storage format"""
    return {
        'id': '0xtx1-0xorder1',
        'timestamp': 1700000000,
        'maker': '0xmaker1',
        'taker': '0xtaker1',
        'maker_asset_id': 'asset123',
        'taker_asset_id': 'asset456',
        'maker_amount_filled': 1000000,  # $1 USDC
        'taker_amount_filled': 2000000,  # $2 USDC
        'fee': 10000,  # $0.01 USDC
        'transaction_hash': '0xtx1'
    }


@pytest.fixture
def sample_trades():
    """Multiple sample trades"""
    return [
        {
            'id': f'0xtx{i}-0xorder{i}',
            'timestamp': 1700000000 + i * 100,
            'maker': f'0xmaker{i}',
            'taker': f'0xtaker{i}',
            'maker_asset_id': 'asset123',  # Same market
            'taker_asset_id': 'asset456',
            'maker_amount_filled': 1000000 * (i + 1),
            'taker_amount_filled': 2000000 * (i + 1),
            'fee': 10000 * (i + 1),
            'transaction_hash': f'0xtx{i}'
        }
        for i in range(50)  # 50 trades for simulation
    ]


@pytest.fixture
def mock_detector():
    """Mock detector that can be configured to detect or not"""
    detector = Mock()
    detector.analyze_volume_pattern = Mock()
    detector.detect_whale_activity = Mock()
    detector.detect_price_movement = Mock()
    detector.detect_coordinated_buying = Mock()
    return detector


class TestMarketState:
    """Test suite for MarketState dataclass"""

    def test_initialization(self):
        """Test market state initialization"""
        state = MarketState(market_id="test_market")

        assert state.market_id == "test_market"
        assert isinstance(state.trade_history, deque)
        assert state.total_volume == 0.0
        assert state.trade_count == 0
        assert state.first_trade_time is None
        assert state.last_trade_time is None
        assert len(state.unique_makers) == 0
        assert len(state.unique_takers) == 0

    def test_add_trade(self, sample_trade):
        """Test adding a trade to market state"""
        state = MarketState(market_id="test_market")

        # Convert to detector format
        converted_trade = {
            'id': sample_trade['id'],
            'timestamp': sample_trade['timestamp'],
            'maker': sample_trade['maker'],
            'taker': sample_trade['taker'],
            'volume_usd': 1.5,  # (1 + 2) / 2
        }

        state.add_trade(converted_trade)

        assert state.trade_count == 1
        assert state.total_volume == 1.5
        assert len(state.trade_history) == 1
        assert state.first_trade_time is not None
        assert state.last_trade_time is not None
        assert sample_trade['maker'] in state.unique_makers
        assert sample_trade['taker'] in state.unique_takers

    def test_add_multiple_trades(self, sample_trades):
        """Test adding multiple trades"""
        state = MarketState(market_id="test_market")

        for trade in sample_trades[:10]:
            converted = {
                'id': trade['id'],
                'timestamp': trade['timestamp'],
                'maker': trade['maker'],
                'taker': trade['taker'],
                'volume_usd': 1.0,
            }
            state.add_trade(converted)

        assert state.trade_count == 10
        assert len(state.trade_history) == 10
        assert len(state.unique_makers) == 10
        assert len(state.unique_takers) == 10

    def test_trade_history_max_length(self):
        """Test that trade history respects maxlen"""
        state = MarketState(market_id="test_market")

        # Add more than maxlen trades
        for i in range(1500):
            trade = {
                'id': f'trade{i}',
                'timestamp': 1700000000 + i,
                'maker': f'maker{i}',
                'taker': f'taker{i}',
                'volume_usd': 1.0,
            }
            state.add_trade(trade)

        # Should only keep last 1000
        assert len(state.trade_history) == 1000
        assert state.trade_count == 1500  # But count should be accurate

    def test_get_recent_trades(self):
        """Test getting trades within time window"""
        state = MarketState(market_id="test_market")

        # Add trades over 2 hours
        base_ts = 1700000000
        for i in range(120):  # 120 minutes worth
            trade = {
                'id': f'trade{i}',
                'timestamp': base_ts + i * 60,  # One per minute
                'maker': f'maker{i}',
                'taker': f'taker{i}',
                'volume_usd': 1.0,
            }
            state.add_trade(trade)

        # Get last 60 minutes
        recent = state.get_recent_trades(window_minutes=60)

        # Should have approximately 60-61 trades (inclusive boundary)
        assert 60 <= len(recent) <= 61

    def test_get_recent_trades_empty_state(self):
        """Test getting recent trades from empty state"""
        state = MarketState(market_id="test_market")

        recent = state.get_recent_trades()
        assert recent == []


class TestVirtualAlert:
    """Test suite for VirtualAlert dataclass"""

    def test_initialization(self):
        """Test virtual alert initialization"""
        alert = VirtualAlert(
            alert_id="alert1",
            timestamp=datetime.now(timezone.utc),
            market_id="market1",
            detector_type="volume",
            severity="HIGH",
            analysis={'volume_spike': 5.2},
            confidence_score=0.85,
            price_at_alert=0.65,
            predicted_direction="BUY"
        )

        assert alert.alert_id == "alert1"
        assert alert.market_id == "market1"
        assert alert.detector_type == "volume"
        assert alert.severity == "HIGH"
        assert alert.confidence_score == 0.85
        assert alert.price_at_alert == 0.65
        assert alert.predicted_direction == "BUY"


class TestSimulationEngine:
    """Test suite for SimulationEngine"""

    def test_initialization_with_detectors(self, sample_config, mock_detector):
        """Test engine initialization with provided detectors"""
        detectors = {
            'volume': mock_detector,
            'whale': mock_detector
        }

        engine = SimulationEngine(config=sample_config, detectors=detectors)

        assert engine.config == sample_config
        assert len(engine.detectors) == 2
        assert 'volume' in engine.detectors
        assert 'whale' in engine.detectors
        assert len(engine.virtual_alerts) == 0
        assert engine.total_trades_processed == 0

    def test_initialization_without_detectors(self, sample_config):
        """Test engine initialization without detectors"""
        engine = SimulationEngine(config=sample_config)

        assert engine.config == sample_config
        assert len(engine.detectors) == 0

    def test_add_detector(self, sample_config, mock_detector):
        """Test adding detector after initialization"""
        engine = SimulationEngine(config=sample_config)

        engine.add_detector('volume', mock_detector)

        assert 'volume' in engine.detectors
        assert engine.detectors['volume'] == mock_detector

    def test_reset(self, sample_config, mock_detector):
        """Test resetting simulation state"""
        engine = SimulationEngine(config=sample_config)
        engine.add_detector('volume', mock_detector)

        # Simulate some processing
        engine.total_trades_processed = 100
        engine.market_states['market1'] = MarketState(market_id='market1')
        engine.virtual_alerts.append(
            VirtualAlert(
                alert_id="test",
                timestamp=datetime.now(timezone.utc),
                market_id="market1",
                detector_type="volume",
                severity="HIGH",
                analysis={},
                confidence_score=0.8
            )
        )

        # Reset
        engine.reset()

        assert engine.total_trades_processed == 0
        assert len(engine.market_states) == 0
        assert len(engine.virtual_alerts) == 0
        assert engine.current_time is None

    def test_convert_trade_format(self, sample_config, sample_trade):
        """Test trade format conversion"""
        engine = SimulationEngine(config=sample_config)

        converted = engine._convert_trade_format(sample_trade)

        assert converted['id'] == sample_trade['id']
        assert converted['timestamp'] == sample_trade['timestamp']
        assert converted['maker'] == sample_trade['maker']
        assert converted['taker'] == sample_trade['taker']
        assert converted['makerAssetId'] == sample_trade['maker_asset_id']
        assert converted['takerAssetId'] == sample_trade['taker_asset_id']

        # Check volume calculation: (1000000 + 2000000) / 2 / 1e6 = 1.5
        assert converted['volume_usd'] == 1.5

        # Check fee conversion: 10000 / 1e6 = 0.01
        assert converted['fee'] == 0.01

    def test_get_or_create_market_state(self, sample_config):
        """Test market state creation and retrieval"""
        engine = SimulationEngine(config=sample_config)

        # First call should create
        state1 = engine._get_or_create_market_state("market1")
        assert state1.market_id == "market1"
        assert "market1" in engine.market_states

        # Second call should retrieve existing
        state2 = engine._get_or_create_market_state("market1")
        assert state1 is state2

    def test_simulate_trades_without_detectors(self, sample_config, sample_trades):
        """Test simulation without any detectors"""
        engine = SimulationEngine(config=sample_config)

        stats = engine.simulate_trades(sample_trades[:10])

        assert stats['total_trades'] == 10
        assert stats['unique_markets'] == 1  # All same market
        assert stats['total_alerts'] == 0  # No detectors, no alerts
        assert 'simulation_time' in stats
        assert 'trades_per_second' in stats

    def test_simulate_trades_with_detector_no_detection(
        self,
        sample_config,
        sample_trades,
        mock_detector
    ):
        """Test simulation with detector that doesn't detect anything"""
        # Configure detector to not detect
        mock_detector.analyze_volume_pattern.return_value = {
            'anomaly': False
        }

        engine = SimulationEngine(config=sample_config)
        engine.add_detector('volume', mock_detector)

        stats = engine.simulate_trades(sample_trades[:20])

        assert stats['total_trades'] == 20
        assert stats['total_alerts'] == 0
        # Detector should have been called (runs every 10 trades)
        assert mock_detector.analyze_volume_pattern.call_count >= 1

    def test_simulate_trades_with_detector_detecting(
        self,
        sample_config,
        sample_trades,
        mock_detector
    ):
        """Test simulation with detector that generates alerts"""
        # Configure detector to detect on every call
        mock_detector.analyze_volume_pattern.return_value = {
            'anomaly': True,
            'severity': 'HIGH',
            'confidence_score': 0.85,
            'volume_spike': 5.2,
            'current_price': 0.65
        }

        engine = SimulationEngine(config=sample_config)
        engine.add_detector('volume', mock_detector)

        stats = engine.simulate_trades(sample_trades[:30])

        assert stats['total_trades'] == 30
        assert stats['total_alerts'] > 0
        assert 'volume' in stats['alerts_by_detector']
        assert 'HIGH' in stats['alerts_by_severity']

    def test_simulate_trades_multiple_detectors(
        self,
        sample_config,
        sample_trades
    ):
        """Test simulation with multiple detectors"""
        # Create separate mocks for each detector
        volume_detector = Mock()
        whale_detector = Mock()

        volume_detector.analyze_volume_pattern.return_value = {
            'anomaly': True,
            'severity': 'HIGH',
            'confidence_score': 0.8
        }

        whale_detector.detect_whale_activity.return_value = {
            'anomaly': True,
            'severity': 'MEDIUM',
            'confidence_score': 0.7
        }

        engine = SimulationEngine(config=sample_config)
        engine.add_detector('volume', volume_detector)
        engine.add_detector('whale', whale_detector)

        stats = engine.simulate_trades(sample_trades[:30])

        assert stats['total_alerts'] > 0
        # Both detectors should have generated alerts
        assert 'volume' in stats['alerts_by_detector']
        assert 'whale' in stats['alerts_by_detector']

    def test_simulate_trades_with_progress_callback(
        self,
        sample_config,
        sample_trades
    ):
        """Test that progress callback is called"""
        engine = SimulationEngine(config=sample_config)

        callback = Mock()
        stats = engine.simulate_trades(
            sample_trades,
            progress_callback=callback
        )

        # Should have been called (every 1000 trades, we have 50)
        # So it won't be called in this test, but verify it doesn't error
        assert stats['total_trades'] == 50

    def test_simulate_trades_detector_exception(
        self,
        sample_config,
        sample_trades,
        mock_detector
    ):
        """Test that detector exceptions don't crash simulation"""
        # Configure detector to raise exception
        mock_detector.analyze_volume_pattern.side_effect = Exception("Detector error")

        engine = SimulationEngine(config=sample_config)
        engine.add_detector('volume', mock_detector)

        # Should not raise, should complete successfully
        stats = engine.simulate_trades(sample_trades[:20])

        assert stats['total_trades'] == 20
        assert stats['total_alerts'] == 0  # No alerts due to error

    def test_get_alerts_no_filters(self, sample_config):
        """Test getting all alerts without filters"""
        engine = SimulationEngine(config=sample_config)

        # Add some virtual alerts
        alert1 = VirtualAlert(
            alert_id="alert1",
            timestamp=datetime.now(timezone.utc),
            market_id="market1",
            detector_type="volume",
            severity="HIGH",
            analysis={},
            confidence_score=0.8
        )
        alert2 = VirtualAlert(
            alert_id="alert2",
            timestamp=datetime.now(timezone.utc),
            market_id="market2",
            detector_type="whale",
            severity="MEDIUM",
            analysis={},
            confidence_score=0.7
        )

        engine.virtual_alerts.extend([alert1, alert2])

        alerts = engine.get_alerts()
        assert len(alerts) == 2

    def test_get_alerts_filter_by_detector(self, sample_config):
        """Test filtering alerts by detector type"""
        engine = SimulationEngine(config=sample_config)

        alert1 = VirtualAlert(
            alert_id="alert1",
            timestamp=datetime.now(timezone.utc),
            market_id="market1",
            detector_type="volume",
            severity="HIGH",
            analysis={},
            confidence_score=0.8
        )
        alert2 = VirtualAlert(
            alert_id="alert2",
            timestamp=datetime.now(timezone.utc),
            market_id="market1",
            detector_type="whale",
            severity="MEDIUM",
            analysis={},
            confidence_score=0.7
        )

        engine.virtual_alerts.extend([alert1, alert2])

        alerts = engine.get_alerts(detector_type="volume")
        assert len(alerts) == 1
        assert alerts[0].detector_type == "volume"

    def test_get_alerts_filter_by_severity(self, sample_config):
        """Test filtering alerts by severity"""
        engine = SimulationEngine(config=sample_config)

        alert1 = VirtualAlert(
            alert_id="alert1",
            timestamp=datetime.now(timezone.utc),
            market_id="market1",
            detector_type="volume",
            severity="HIGH",
            analysis={},
            confidence_score=0.8
        )
        alert2 = VirtualAlert(
            alert_id="alert2",
            timestamp=datetime.now(timezone.utc),
            market_id="market1",
            detector_type="whale",
            severity="MEDIUM",
            analysis={},
            confidence_score=0.7
        )

        engine.virtual_alerts.extend([alert1, alert2])

        alerts = engine.get_alerts(severity="HIGH")
        assert len(alerts) == 1
        assert alerts[0].severity == "HIGH"

    def test_get_alerts_filter_by_time_range(self, sample_config):
        """Test filtering alerts by time range"""
        engine = SimulationEngine(config=sample_config)

        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=2)
        future = now + timedelta(hours=2)

        alert1 = VirtualAlert(
            alert_id="alert1",
            timestamp=past,
            market_id="market1",
            detector_type="volume",
            severity="HIGH",
            analysis={},
            confidence_score=0.8
        )
        alert2 = VirtualAlert(
            alert_id="alert2",
            timestamp=now,
            market_id="market1",
            detector_type="whale",
            severity="MEDIUM",
            analysis={},
            confidence_score=0.7
        )

        engine.virtual_alerts.extend([alert1, alert2])

        # Get alerts from last hour (should only get alert2)
        alerts = engine.get_alerts(
            start_time=now - timedelta(hours=1),
            end_time=future
        )
        assert len(alerts) == 1
        assert alerts[0].alert_id == "alert2"

    def test_get_market_state(self, sample_config):
        """Test retrieving market state"""
        engine = SimulationEngine(config=sample_config)

        # Create a market state
        state = engine._get_or_create_market_state("market1")

        # Retrieve it
        retrieved = engine.get_market_state("market1")
        assert retrieved is state

        # Try non-existent market
        none_state = engine.get_market_state("nonexistent")
        assert none_state is None

    def test_get_simulation_stats(self, sample_config, sample_trades):
        """Test getting simulation statistics"""
        engine = SimulationEngine(config=sample_config)

        # Run simulation
        engine.simulate_trades(sample_trades[:20])

        stats = engine.get_simulation_stats()

        assert stats['total_trades_processed'] == 20
        assert stats['unique_markets'] == 1
        assert 'avg_trades_per_market' in stats
        assert 'alert_rate' in stats

    def test_export_alerts_to_json(self, sample_config, tmp_path):
        """Test exporting alerts to JSON file"""
        engine = SimulationEngine(config=sample_config)

        # Add an alert
        alert = VirtualAlert(
            alert_id="alert1",
            timestamp=datetime.now(timezone.utc),
            market_id="market1",
            detector_type="volume",
            severity="HIGH",
            analysis={'volume_spike': 5.2},
            confidence_score=0.85,
            price_at_alert=0.65,
            predicted_direction="BUY"
        )
        engine.virtual_alerts.append(alert)

        # Export
        output_path = tmp_path / "alerts.json"
        engine.export_alerts_to_json(str(output_path))

        # Verify file exists
        assert output_path.exists()

        # Verify contents
        import json
        with open(output_path) as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]['alert_id'] == "alert1"
        assert data[0]['detector_type'] == "volume"
        assert data[0]['severity'] == "HIGH"

    def test_infer_direction(self, sample_config):
        """Test direction inference from detector results"""
        engine = SimulationEngine(config=sample_config)

        # Volume detector should predict BUY
        direction = engine._infer_direction('volume', {})
        assert direction == 'BUY'

        # Whale detector should predict BUY
        direction = engine._infer_direction('whale', {})
        assert direction == 'BUY'

        # Price detector with positive momentum should predict BUY
        direction = engine._infer_direction('price', {'momentum': 1.5})
        assert direction == 'BUY'

        # Price detector with negative momentum should predict SELL
        direction = engine._infer_direction('price', {'momentum': -1.5})
        assert direction == 'SELL'

    def test_multiple_markets(self, sample_config, mock_detector):
        """Test simulation with trades from multiple markets"""
        # Configure detector
        mock_detector.analyze_volume_pattern.return_value = {
            'anomaly': False
        }

        engine = SimulationEngine(config=sample_config)
        engine.add_detector('volume', mock_detector)

        # Create trades for different markets
        trades = []
        for market_idx in range(3):
            for i in range(10):
                trades.append({
                    'id': f'0xtx{market_idx}_{i}',
                    'timestamp': 1700000000 + i * 100,
                    'maker': f'0xmaker{i}',
                    'taker': f'0xtaker{i}',
                    'maker_asset_id': f'market{market_idx}',
                    'taker_asset_id': 'asset456',
                    'maker_amount_filled': 1000000,
                    'taker_amount_filled': 2000000,
                    'fee': 10000,
                    'transaction_hash': f'0xtx{market_idx}_{i}'
                })

        stats = engine.simulate_trades(trades)

        assert stats['total_trades'] == 30
        assert stats['unique_markets'] == 3
        assert len(engine.market_states) == 3

    def test_simulate_trades_batch_basic(self, sample_config, mock_detector):
        """Test basic batch simulation"""
        sample_config['detectors'] = {
            'volume': {'enabled': True},
            'whale': {'enabled': False}
        }

        engine = SimulationEngine(config=sample_config)
        engine.add_detector('volume', mock_detector)

        # Create trades for multiple markets
        trades = []
        for market_idx in range(3):
            for i in range(10):
                trades.append({
                    'id': f'0xtx{market_idx}_{i}',
                    'timestamp': 1700000000 + market_idx * 1000 + i * 100,
                    'maker': f'0xmaker{i}',
                    'taker': f'0xtaker{i}',
                    'maker_asset_id': f'market{market_idx}',
                    'taker_asset_id': 'asset456',
                    'maker_amount_filled': 1000000,
                    'taker_amount_filled': 2000000,
                    'fee': 10000,
                    'transaction_hash': f'0xtx{market_idx}_{i}'
                })

        stats = engine.simulate_trades_batch(trades)

        assert stats['total_trades'] == 30
        assert stats['unique_markets'] == 3
        assert stats['mode'] == 'batch'
        assert len(engine.market_states) == 3

    def test_simulate_trades_batch_with_progress(self, sample_config, mock_detector):
        """Test batch simulation with progress callback"""
        sample_config['detectors'] = {
            'volume': {'enabled': True},
            'whale': {'enabled': False}
        }

        engine = SimulationEngine(config=sample_config)
        engine.add_detector('volume', mock_detector)

        # Create trades
        trades = []
        for market_idx in range(5):
            for i in range(20):
                trades.append({
                    'id': f'0xtx{market_idx}_{i}',
                    'timestamp': 1700000000 + market_idx * 2000 + i * 100,
                    'maker': f'0xmaker{i}',
                    'taker': f'0xtaker{i}',
                    'maker_asset_id': f'market{market_idx}',
                    'taker_asset_id': 'asset456',
                    'maker_amount_filled': 1000000,
                    'taker_amount_filled': 2000000,
                    'fee': 10000,
                    'transaction_hash': f'0xtx{market_idx}_{i}'
                })

        # Track progress
        progress_calls = []
        def progress_callback(markets_done, alerts):
            progress_calls.append((markets_done, alerts))

        stats = engine.simulate_trades_batch(trades, progress_callback=progress_callback)

        assert stats['total_trades'] == 100
        assert stats['unique_markets'] == 5
        assert stats['mode'] == 'batch'
        assert len(progress_calls) == 5  # Called once per market
        assert progress_calls[-1][0] == 5  # Last call has all markets done

    def test_simulate_trades_batch_mode_indicator(self, sample_config):
        """Test that batch mode stats include mode indicator"""
        sample_config['detectors'] = {
            'volume': {'enabled': True}
        }

        engine = SimulationEngine(config=sample_config)

        trades = [
            {
                'id': '0xtx1',
                'timestamp': 1700000000,
                'maker': '0xmaker1',
                'taker': '0xtaker1',
                'maker_asset_id': 'market1',
                'taker_asset_id': 'asset456',
                'maker_amount_filled': 1000000,
                'taker_amount_filled': 2000000,
                'fee': 10000,
                'transaction_hash': '0xtx1'
            }
        ]

        # Sequential mode
        stats_sequential = engine.simulate_trades(trades)
        assert stats_sequential['mode'] == 'sequential'

        # Reset and test batch mode
        engine.reset()
        stats_batch = engine.simulate_trades_batch(trades)
        assert stats_batch['mode'] == 'batch'
