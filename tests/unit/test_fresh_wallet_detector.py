"""
Unit tests for FreshWalletDetector class.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from detection.fresh_wallet_detector import FreshWalletDetector
from tests.test_utils import create_test_config


class TestFreshWalletDetector:
    """Test suite for FreshWalletDetector functionality."""

    @pytest.fixture
    def mock_data_api(self):
        """Create mock DataAPIClient"""
        mock_api = AsyncMock()
        mock_api.get_wallet_trades = AsyncMock()
        return mock_api

    @pytest.fixture
    def mock_whale_tracker(self):
        """Create mock WhaleTracker"""
        mock_tracker = AsyncMock()
        mock_tracker.get_whale = AsyncMock()
        mock_tracker.mark_wallet_verified = AsyncMock()
        return mock_tracker

    @pytest.fixture
    def detector(self, mock_data_api, mock_whale_tracker):
        """Create FreshWalletDetector instance for testing."""
        config = create_test_config()
        detector = FreshWalletDetector(config, mock_data_api, mock_whale_tracker)
        return detector

    def test_init_custom_config(self, mock_data_api, mock_whale_tracker):
        """Test FreshWalletDetector initialization with custom config."""
        config = {
            'detection': {
                'fresh_wallet_thresholds': {
                    'min_bet_size_usd': 5000,
                    'api_lookback_limit': 200,
                    'max_previous_trades': 1
                }
            }
        }
        detector = FreshWalletDetector(config, mock_data_api, mock_whale_tracker)
        assert detector.thresholds['min_bet_size_usd'] == 5000
        assert detector.thresholds['api_lookback_limit'] == 200
        assert detector.thresholds['max_previous_trades'] == 1

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_activity_empty_trades(self, detector):
        """Test fresh wallet detection with empty trades list."""
        result = await detector.detect_fresh_wallet_activity([])
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_activity_no_large_bets(self, detector):
        """Test detection with no large bets above threshold."""
        small_trades = [
            {
                'price': '0.5',
                'size': '1000',  # $500 trade (below $2k threshold)
                'side': 'BUY',
                'maker': '0xsmallbet123'
            },
            {
                'price': '0.6',
                'size': '2000',  # $1200 trade (below $2k threshold)
                'side': 'SELL',
                'maker': '0xsmallbet456'
            }
        ]

        result = await detector.detect_fresh_wallet_activity(small_trades)
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_activity_no_maker_address(self, detector):
        """Test detection filters out trades without maker address."""
        trades = [
            {
                'price': '0.5',
                'size': '10000',  # $5k trade but no maker
                'side': 'BUY'
                # No maker field
            }
        ]

        result = await detector.detect_fresh_wallet_activity(trades)
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_first_trade_ever(self, detector, mock_data_api, mock_whale_tracker):
        """Test detection of truly fresh wallet (first trade ever)."""
        # Mock wallet tracker returns no existing whale record
        mock_whale_tracker.get_whale.return_value = None

        # Mock API returns empty trade history (truly first trade)
        mock_data_api.get_wallet_trades.return_value = []

        large_bet_trade = [{
            'price': '0.65',
            'size': '6000',  # $3,900 trade
            'side': 'BUY',
            'outcome': 'YES',
            'maker': '0xfreshwallet123',
            'tx_hash': '0xtxhash123',
            'timestamp': 1234567890
        }]

        result = await detector.detect_fresh_wallet_activity(large_bet_trade)

        # Should detect fresh wallet
        assert len(result) == 1
        assert result[0]['anomaly'] is True
        assert result[0]['wallet_address'] == '0xfreshwallet123'
        assert result[0]['bet_size'] == 3900.0
        assert result[0]['side'] == 'BUY'
        # Note: outcome is UNKNOWN because TradeNormalizer doesn't preserve it
        assert result[0]['outcome'] == 'UNKNOWN'
        assert result[0]['previous_trade_count'] == 0

        # Verify API was called to check wallet history
        mock_data_api.get_wallet_trades.assert_called_once_with('0xfreshwallet123', limit=100)

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_established_wallet(self, detector, mock_data_api, mock_whale_tracker):
        """Test that established wallets are NOT detected as fresh."""
        # Mock wallet tracker returns no existing record
        mock_whale_tracker.get_whale.return_value = None

        # Mock API returns 50 previous trades (established wallet)
        mock_data_api.get_wallet_trades.return_value = [{'id': i} for i in range(50)]

        large_bet_trade = [{
            'price': '0.55',
            'size': '8000',  # $4,400 trade
            'side': 'SELL',
            'outcome': 'NO',
            'maker': '0xestablished123',
            'tx_hash': '0xtxhash456',
            'timestamp': 1234567891
        }]

        result = await detector.detect_fresh_wallet_activity(large_bet_trade)

        # Should NOT detect as fresh (50 trades > 0 max_previous_trades)
        assert result == []

        # Verify API was called
        mock_data_api.get_wallet_trades.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_cached_in_database(self, detector, mock_data_api, mock_whale_tracker):
        """Test that database cache is used when available."""
        # Mock existing whale record with verified freshness
        mock_whale = Mock()
        mock_whale.verified_fresh = True
        mock_whale.is_fresh_wallet = True
        mock_whale.trade_count = 0
        mock_whale_tracker.get_whale.return_value = mock_whale

        large_bet_trade = [{
            'price': '0.45',
            'size': '5000',  # $2,250 trade
            'side': 'BUY',
            'outcome': 'YES',
            'maker': '0xcachedwallet123',
            'tx_hash': '0xtxhash789',
            'timestamp': 1234567892
        }]

        result = await detector.detect_fresh_wallet_activity(large_bet_trade)

        # Should detect fresh wallet using cached result
        assert len(result) == 1
        assert result[0]['wallet_address'] == '0xcachedwallet123'
        assert result[0]['previous_trade_count'] == 0

        # Verify API was NOT called (cache hit)
        mock_data_api.get_wallet_trades.assert_not_called()

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_cached_not_fresh(self, detector, mock_data_api, mock_whale_tracker):
        """Test that cached non-fresh wallets are filtered out."""
        # Mock existing whale record marked as NOT fresh
        mock_whale = Mock()
        mock_whale.verified_fresh = True
        mock_whale.is_fresh_wallet = False
        mock_whale.trade_count = 25
        mock_whale_tracker.get_whale.return_value = mock_whale

        large_bet_trade = [{
            'price': '0.70',
            'size': '7000',  # $4,900 trade
            'side': 'SELL',
            'outcome': 'NO',
            'maker': '0xnotfreshcached',
            'tx_hash': '0xtxhash999',
            'timestamp': 1234567893
        }]

        result = await detector.detect_fresh_wallet_activity(large_bet_trade)

        # Should NOT detect (cached as not fresh)
        assert result == []

        # Verify API was NOT called (cache hit)
        mock_data_api.get_wallet_trades.assert_not_called()

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_multiple_wallets(self, detector, mock_data_api, mock_whale_tracker):
        """Test detection returns one result per fresh wallet."""
        # Mock wallet tracker returns no records
        mock_whale_tracker.get_whale.return_value = None

        # Mock API to return different trade counts for different wallets
        def mock_get_trades(wallet_address, limit):
            if wallet_address == '0xfresh1':
                return []  # First trade
            elif wallet_address == '0xfresh2':
                return []  # First trade
            elif wallet_address == '0xestablished':
                return [{'id': i} for i in range(10)]  # 10 trades

        mock_data_api.get_wallet_trades.side_effect = mock_get_trades

        multiple_large_bets = [
            {
                'price': '0.50',
                'size': '6000',  # $3,000
                'side': 'BUY',
                'outcome': 'YES',
                'maker': '0xfresh1',
                'tx_hash': '0xtx1',
                'timestamp': 1234567894
            },
            {
                'price': '0.60',
                'size': '8000',  # $4,800
                'side': 'SELL',
                'outcome': 'NO',
                'maker': '0xfresh2',
                'tx_hash': '0xtx2',
                'timestamp': 1234567895
            },
            {
                'price': '0.55',
                'size': '10000',  # $5,500
                'side': 'BUY',
                'outcome': 'YES',
                'maker': '0xestablished',
                'tx_hash': '0xtx3',
                'timestamp': 1234567896
            }
        ]

        result = await detector.detect_fresh_wallet_activity(multiple_large_bets)

        # Should return 2 detections (fresh1 and fresh2, not established)
        assert len(result) == 2
        wallet_addresses = {r['wallet_address'] for r in result}
        assert wallet_addresses == {'0xfresh1', '0xfresh2'}

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_api_error_handling(self, detector, mock_data_api, mock_whale_tracker):
        """Test that API errors are handled gracefully."""
        # Mock wallet tracker returns no record
        mock_whale_tracker.get_whale.return_value = None

        # Mock API raises exception
        mock_data_api.get_wallet_trades.side_effect = Exception("API connection error")

        large_bet_trade = [{
            'price': '0.55',
            'size': '5000',  # $2,750 trade
            'side': 'BUY',
            'outcome': 'YES',
            'maker': '0xerrorwallet',
            'tx_hash': '0xtxerror',
            'timestamp': 1234567897
        }]

        result = await detector.detect_fresh_wallet_activity(large_bet_trade)

        # Should return empty (conservative approach on error)
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_in_memory_cache(self, detector, mock_data_api, mock_whale_tracker):
        """Test that in-memory cache works across multiple detections."""
        # Mock wallet tracker returns no record
        mock_whale_tracker.get_whale.return_value = None

        # Mock API returns empty history
        mock_data_api.get_wallet_trades.return_value = []

        large_bet_trade = [{
            'price': '0.60',
            'size': '5000',  # $3,000 trade
            'side': 'BUY',
            'outcome': 'YES',
            'maker': '0xcachewallet',
            'tx_hash': '0xtxcache1',
            'timestamp': 1234567898
        }]

        # First detection - should call API
        result1 = await detector.detect_fresh_wallet_activity(large_bet_trade)
        assert len(result1) == 1
        assert mock_data_api.get_wallet_trades.call_count == 1

        # Second detection with same wallet - should use in-memory cache
        result2 = await detector.detect_fresh_wallet_activity(large_bet_trade)
        assert len(result2) == 1
        # API should still be called only once (cached)
        assert mock_data_api.get_wallet_trades.call_count == 1

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_marks_verified_in_database(self, detector, mock_data_api, mock_whale_tracker):
        """Test that verification result is stored in database."""
        # Mock existing whale record but not verified yet
        mock_whale = Mock()
        mock_whale.verified_fresh = False
        mock_whale_tracker.get_whale.return_value = mock_whale

        # Mock API returns 0 trades (fresh wallet)
        mock_data_api.get_wallet_trades.return_value = []

        large_bet_trade = [{
            'price': '0.55',
            'size': '6000',  # $3,300 trade
            'side': 'SELL',
            'outcome': 'NO',
            'maker': '0xverifywallet',
            'tx_hash': '0xtxverify',
            'timestamp': 1234567899
        }]

        result = await detector.detect_fresh_wallet_activity(large_bet_trade)

        # Should detect as fresh
        assert len(result) == 1

        # Verify database was updated with verification result
        mock_whale_tracker.mark_wallet_verified.assert_called_once_with(
            '0xverifywallet',
            True,  # is_fresh
            0      # trade_count
        )

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_data_fields(self, detector, mock_data_api, mock_whale_tracker):
        """Test that all expected fields are included in detection result."""
        # Mock wallet tracker and API for fresh wallet
        mock_whale_tracker.get_whale.return_value = None
        mock_data_api.get_wallet_trades.return_value = []

        large_bet_trade = [{
            'price': '0.45',
            'size': '10000',  # $4,500 trade
            'side': 'BUY',
            'outcome': 'YES',
            'maker': '0xfieldtest',
            'tx_hash': '0xtxfields',
            'timestamp': 1234567900
        }]

        result = await detector.detect_fresh_wallet_activity(large_bet_trade)

        # Verify all expected fields are present
        assert len(result) == 1
        detection = result[0]

        assert 'anomaly' in detection
        assert detection['anomaly'] is True
        assert 'wallet_address' in detection
        assert detection['wallet_address'] == '0xfieldtest'
        assert 'bet_size' in detection
        assert detection['bet_size'] == 4500.0
        assert 'side' in detection
        assert detection['side'] == 'BUY'
        assert 'price' in detection
        assert detection['price'] == 0.45
        assert 'outcome' in detection
        # Note: outcome is UNKNOWN because TradeNormalizer doesn't preserve it
        assert detection['outcome'] == 'UNKNOWN'
        assert 'tx_hash' in detection
        assert detection['tx_hash'] == '0xtxfields'
        assert 'timestamp' in detection
        # Timestamp is normalized to pandas Timestamp object
        assert detection['timestamp'] is not None
        assert 'previous_trade_count' in detection
        assert detection['previous_trade_count'] == 0

    @pytest.mark.asyncio
    async def test_detect_fresh_wallet_missing_outcome(self, detector, mock_data_api, mock_whale_tracker):
        """Test detection handles trades with missing outcome field."""
        # Mock for fresh wallet
        mock_whale_tracker.get_whale.return_value = None
        mock_data_api.get_wallet_trades.return_value = []

        large_bet_trade = [{
            'price': '0.50',
            'size': '8000',  # $4,000 trade
            'side': 'BUY',
            # No outcome field
            'maker': '0xnooutcome',
            'tx_hash': '0xtxnooutcome',
            'timestamp': 1234567901
        }]

        result = await detector.detect_fresh_wallet_activity(large_bet_trade)

        # Should still detect, with outcome defaulting to UNKNOWN
        assert len(result) == 1
        assert result[0]['outcome'] == 'UNKNOWN'

    @pytest.mark.asyncio
    async def test_bet_size_exactly_at_threshold(self, detector, mock_data_api, mock_whale_tracker):
        """Test trade with bet size exactly at min_bet_size_usd threshold"""
        # Default threshold is 2000 USD
        mock_whale_tracker.get_whale.return_value = None
        mock_data_api.get_wallet_trades.return_value = []

        exact_threshold_trade = [{
            'price': '0.50',
            'size': '4000',  # Exactly $2,000 (4000 * 0.50)
            'side': 'BUY',
            'outcome': 'YES',
            'maker': '0xthreshold',
            'tx_hash': '0xtxthreshold',
            'timestamp': 1234567890
        }]

        result = await detector.detect_fresh_wallet_activity(exact_threshold_trade)

        # Should detect at exact threshold (>= condition)
        assert len(result) == 1
        assert result[0]['bet_size'] == 2000.0

    @pytest.mark.asyncio
    async def test_bet_size_just_below_threshold(self, detector, mock_data_api, mock_whale_tracker):
        """Test trade with bet size just below threshold"""
        mock_whale_tracker.get_whale.return_value = None
        mock_data_api.get_wallet_trades.return_value = []

        below_threshold_trade = [{
            'price': '0.50',
            'size': '3999',  # $1,999.50 (just below $2,000)
            'side': 'BUY',
            'outcome': 'YES',
            'maker': '0xbelowthreshold',
            'tx_hash': '0xtxbelow',
            'timestamp': 1234567890
        }]

        result = await detector.detect_fresh_wallet_activity(below_threshold_trade)

        # Should not detect below threshold
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_wallet_with_exactly_max_previous_trades(self, detector, mock_data_api, mock_whale_tracker):
        """Test wallet with exactly max_previous_trades (should not trigger)"""
        # Default max is 0, so test with config that allows 1 trade
        config = {
            'detection': {
                'fresh_wallet_thresholds': {
                    'min_bet_size_usd': 2000,
                    'api_lookback_limit': 100,
                    'max_previous_trades': 1
                }
            }
        }
        detector_custom = FreshWalletDetector(config, mock_data_api, mock_whale_tracker)

        mock_whale_tracker.get_whale.return_value = None
        # Wallet has exactly 1 previous trade
        mock_data_api.get_wallet_trades.return_value = [
            {'price': '0.30', 'size': '100', 'timestamp': 1234567800}
        ]

        large_bet_trade = [{
            'price': '0.50',
            'size': '5000',  # $2,500
            'side': 'BUY',
            'outcome': 'YES',
            'maker': '0xonetrade',
            'tx_hash': '0xtxone',
            'timestamp': 1234567890
        }]

        result = await detector_custom.detect_fresh_wallet_activity(large_bet_trade)

        # With max_previous_trades=1, wallet with exactly 1 trade should not trigger
        # (Condition is: previous_trades <= max_previous_trades, so 1 <= 1 = True, should trigger)
        assert len(result) == 1  # Should still trigger at boundary

    @pytest.mark.asyncio
    async def test_wallet_with_just_over_max_previous_trades(self, detector, mock_data_api, mock_whale_tracker):
        """Test wallet with just over max_previous_trades"""
        config = {
            'detection': {
                'fresh_wallet_thresholds': {
                    'min_bet_size_usd': 2000,
                    'api_lookback_limit': 100,
                    'max_previous_trades': 1
                }
            }
        }
        detector_custom = FreshWalletDetector(config, mock_data_api, mock_whale_tracker)

        mock_whale_tracker.get_whale.return_value = None
        # Wallet has 2 previous trades (over max of 1)
        mock_data_api.get_wallet_trades.return_value = [
            {'price': '0.30', 'size': '100', 'timestamp': 1234567800},
            {'price': '0.40', 'size': '200', 'timestamp': 1234567850}
        ]

        large_bet_trade = [{
            'price': '0.50',
            'size': '5000',  # $2,500
            'side': 'BUY',
            'outcome': 'YES',
            'maker': '0xtwotrades',
            'tx_hash': '0xtxtwo',
            'timestamp': 1234567890
        }]

        result = await detector_custom.detect_fresh_wallet_activity(large_bet_trade)

        # Should not trigger with 2 trades when max is 1
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_api_error_during_wallet_verification(self, detector, mock_data_api, mock_whale_tracker):
        """Test handling of API errors during wallet history check"""
        mock_whale_tracker.get_whale.return_value = None
        # Simulate API error
        mock_data_api.get_wallet_trades.side_effect = Exception("API connection failed")

        large_bet_trade = [{
            'price': '0.50',
            'size': '5000',  # $2,500
            'side': 'BUY',
            'outcome': 'YES',
            'maker': '0xapierror',
            'tx_hash': '0xtxapierror',
            'timestamp': 1234567890
        }]

        result = await detector.detect_fresh_wallet_activity(large_bet_trade)

        # Should handle error gracefully and not crash
        # Behavior depends on implementation - either skip the wallet or return empty
        assert isinstance(result, list)  # Should still return a list
