"""
Unit tests for TradeNormalizer utility functions
"""
import pytest
from detection.utils import TradeNormalizer


class TestTradeNormalizer:
    """Tests for trade normalization utility"""

    def test_normalize_tx_hash_with_id(self):
        """Test tx_hash extraction from 'id' field"""
        trade = {'id': '0xabc123', 'price': 0.5, 'size': 100}
        result = TradeNormalizer.normalize_tx_hash(trade)
        assert result == '0xabc123'

    def test_normalize_tx_hash_with_tx_hash(self):
        """Test tx_hash extraction from 'tx_hash' field"""
        trade = {'tx_hash': '0xdef456', 'price': 0.5, 'size': 100}
        result = TradeNormalizer.normalize_tx_hash(trade)
        assert result == '0xdef456'

    def test_normalize_tx_hash_with_transaction_hash(self):
        """Test tx_hash extraction from 'transactionHash' field"""
        trade = {'transactionHash': '0xghi789', 'price': 0.5, 'size': 100}
        result = TradeNormalizer.normalize_tx_hash(trade)
        assert result == '0xghi789'

    def test_normalize_tx_hash_priority(self):
        """Test that 'id' takes priority when multiple fields exist"""
        trade = {
            'id': '0xabc123',
            'tx_hash': '0xdef456',
            'price': 0.5,
            'size': 100
        }
        result = TradeNormalizer.normalize_tx_hash(trade)
        assert result == '0xabc123'

    def test_normalize_tx_hash_filters_unknown(self):
        """Test that 'unknown' is filtered out"""
        trade = {'id': 'unknown', 'price': 0.5, 'size': 100}
        result = TradeNormalizer.normalize_tx_hash(trade)
        assert result is None

    def test_normalize_tx_hash_missing(self):
        """Test tx_hash when no hash fields present"""
        trade = {'price': 0.5, 'size': 100}
        result = TradeNormalizer.normalize_tx_hash(trade)
        assert result is None

    def test_normalize_trade_includes_tx_hash(self):
        """Test that normalized trade includes tx_hash when available"""
        trade = {
            'id': '0xabc123',
            'price': 0.5,
            'size': 100,
            'timestamp': 1234567890,
            'maker': '0xwallet123'
        }
        result = TradeNormalizer.normalize_trade(trade)
        assert result is not None
        assert 'tx_hash' in result
        assert result['tx_hash'] == '0xabc123'

    def test_normalize_trade_without_tx_hash(self):
        """Test that normalized trade works without tx_hash"""
        trade = {
            'price': 0.5,
            'size': 100,
            'timestamp': 1234567890,
            'maker': '0xwallet123'
        }
        result = TradeNormalizer.normalize_trade(trade)
        assert result is not None
        # tx_hash should not be in result if not available
        assert 'tx_hash' not in result
