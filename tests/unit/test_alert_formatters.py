"""
Unit tests for Alert Formatters (Discord and Telegram)
"""

import pytest
from datetime import datetime
from alerts.formatters import DiscordFormatter, TelegramFormatter
from common import AlertType, AlertSeverity


class TestDiscordFormatter:
    """Test DiscordFormatter"""

    @pytest.fixture
    def formatter(self):
        return DiscordFormatter()

    @pytest.fixture
    def sample_alert(self):
        return {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k in 2025?',
            'alert_type': AlertType.WHALE_ACTIVITY,
            'timestamp': datetime.now().isoformat(),
            'confidence_score': 12.0,
            'analysis': {
                'total_whale_volume': 150000,
                'whale_count': 3,
                'dominant_side': 'BUY',
                'direction_imbalance': 0.9,
                'whale_breakdown': {
                    '0xabc123': {
                        'total_volume': 75000,
                        'dominant_side': 'BUY',
                        'avg_price': 0.65
                    }
                }
            },
            'market_data': {
                'volume24hr': 1000000,
                'lastTradePrice': 0.65
            }
        }

    @pytest.fixture
    def sample_recommendation(self):
        return {
            'action': 'BUY',
            'side': 'YES',
            'price': 0.65,
            'entry_price': 0.66,
            'target_price': None,
            'risk_price': 0.62,
            'text': 'Consider YES Buy @ $0.65',
            'reasoning': '3 whales purchased $150K YES with 90% buy bias. Strong conviction signal.',
            'confidence_level': 'HIGH'
        }

    def test_format_alert_structure(self, formatter, sample_alert, sample_recommendation):
        """Test that Discord embed has correct structure"""
        market_url = "https://polymarket.com/event/bitcoin-100k-2025"
        embed = formatter.format_alert(sample_alert, sample_recommendation, market_url)

        assert 'title' in embed
        assert 'color' in embed
        assert 'fields' in embed
        assert 'timestamp' in embed
        assert 'footer' in embed

        assert 'HIGH' in embed['title']
        assert len(embed['fields']) > 0

    def test_severity_colors(self, formatter, sample_alert, sample_recommendation):
        """Test that severity levels map to correct colors"""
        sample_alert['severity'] = 'CRITICAL'
        embed_critical = formatter.format_alert(sample_alert, sample_recommendation)
        assert embed_critical['color'] == 0xFF0000  # Red

        sample_alert['severity'] = 'HIGH'
        embed_high = formatter.format_alert(sample_alert, sample_recommendation)
        assert embed_high['color'] == 0xFF8C00  # Dark orange

        sample_alert['severity'] = 'MEDIUM'
        embed_medium = formatter.format_alert(sample_alert, sample_recommendation)
        assert embed_medium['color'] == 0xFFD700  # Gold

    def test_recommendation_field(self, formatter, sample_alert, sample_recommendation):
        """Test that recommendation is properly formatted"""
        embed = formatter.format_alert(sample_alert, sample_recommendation)

        # Find recommendation field
        rec_field = next((f for f in embed['fields'] if 'RECOMMENDATION' in f['name']), None)
        assert rec_field is not None
        assert 'Consider YES Buy' in rec_field['value']


class TestTelegramFormatter:
    """Test TelegramFormatter"""

    @pytest.fixture
    def formatter(self):
        return TelegramFormatter()

    @pytest.fixture
    def sample_alert(self):
        return {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k in 2025?',
            'alert_type': AlertType.WHALE_ACTIVITY,
            'timestamp': datetime.now(),
            'confidence_score': 12.0,
            'analysis': {
                'total_whale_volume': 150000,
                'whale_count': 3,
                'dominant_side': 'BUY',
                'direction_imbalance': 0.9
            },
            'market_data': {
                'volume24hr': 1000000,
                'lastTradePrice': 0.65
            }
        }

    @pytest.fixture
    def sample_recommendation(self):
        return {
            'action': 'BUY',
            'side': 'YES',
            'price': 0.65,
            'entry_price': 0.66,
            'text': 'Consider YES Buy @ $0.65',
            'reasoning': '3 whales purchased $150K YES with 90% buy bias.',
            'confidence_level': 'HIGH'
        }

    def test_format_alert_html(self, formatter, sample_alert, sample_recommendation):
        """Test that Telegram message uses HTML formatting"""
        market_url = "https://polymarket.com/event/bitcoin-100k-2025"
        message = formatter.format_alert(sample_alert, sample_recommendation, market_url)

        assert '<b>' in message  # Bold tags
        assert '</b>' in message
        assert '<i>' in message or '</i>' in message or '<a href=' in message  # HTML formatting

        assert 'HIGH SIGNAL' in message
        assert 'RECOMMENDATION' in message
        assert 'MARKET' in message
        assert 'DETECTED' in message

    def test_severity_emoji(self, formatter, sample_alert, sample_recommendation):
        """Test that severity levels have correct emojis"""
        sample_alert['severity'] = 'CRITICAL'
        message_critical = formatter.format_alert(sample_alert, sample_recommendation)
        assert '🔴' in message_critical

        sample_alert['severity'] = 'HIGH'
        message_high = formatter.format_alert(sample_alert, sample_recommendation)
        assert '🟠' in message_high

        sample_alert['severity'] = 'MEDIUM'
        message_medium = formatter.format_alert(sample_alert, sample_recommendation)
        assert '🟡' in message_medium

    def test_market_url_link(self, formatter, sample_alert, sample_recommendation):
        """Test that market URL is properly formatted as link"""
        market_url = "https://polymarket.com/event/bitcoin-100k-2025"
        message = formatter.format_alert(sample_alert, sample_recommendation, market_url)

        assert market_url in message
        assert 'View Market' in message

    def test_confidence_score(self, formatter, sample_alert, sample_recommendation):
        """Test that confidence score is displayed correctly"""
        sample_alert['confidence_score'] = 12.0  # Should be 120/100 = 120%
        message = formatter.format_alert(sample_alert, sample_recommendation)

        assert 'CONFIDENCE' in message
        # Confidence is scaled from 0-10 to 0-100, so 12.0 => 120/100
        # But max is 10, so it should be displayed as 100/100
        assert '/100' in message

    def test_html_escaping(self, formatter, sample_alert, sample_recommendation):
        """Test that special HTML characters are escaped"""
        sample_alert['market_question'] = 'Question with <script> & "quotes"'
        message = formatter.format_alert(sample_alert, sample_recommendation)

        # Verify HTML is escaped
        # This is basic check - html.escape() should handle this
        assert '&lt;script&gt;' in message or '<script>' not in message


class TestRelatedOutcomesDisplay:
    """Test related outcomes display with both YES and NO prices"""

    def test_related_outcomes_both_prices_discord(self):
        """Test that Discord formatter shows both YES and NO prices for related outcomes."""
        from datetime import timezone

        alert = {
            'severity': 'HIGH',
            'market_question': 'Will there be 3 Fed rate cuts in 2025?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 8.0,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis': {'max_anomaly_score': 5.0},
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.75,
                'outcomePrices': ['0.75', '0.25']
            },
            'related_markets': [
                {'question': 'Will there be 2 Fed rate cuts in 2025?', 'yes_price': 0.12, 'no_price': 0.88},
                {'question': 'Will there be 4 Fed rate cuts in 2025?', 'yes_price': 0.07, 'no_price': 0.93}
            ]
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = DiscordFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Find related outcomes field
        related_field = next((f for f in result['fields'] if 'OTHER OUTCOMES' in f['name']), None)
        assert related_field is not None
        assert 'YES' in related_field['value']
        assert 'NO' in related_field['value']
        assert '12¢ YES / 88¢ NO' in related_field['value']
        assert '7¢ YES / 93¢ NO' in related_field['value']

    def test_related_outcomes_both_prices_telegram(self):
        """Test that Telegram formatter shows both YES and NO prices for related outcomes."""
        alert = {
            'severity': 'HIGH',
            'market_question': 'Will there be 3 Fed rate cuts in 2025?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 8.0,
            'timestamp': datetime.now(),
            'analysis': {'max_anomaly_score': 5.0},
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.75,
                'outcomePrices': ['0.75', '0.25']
            },
            'related_markets': [
                {'question': 'Will there be 2 Fed rate cuts in 2025?', 'yes_price': 0.12, 'no_price': 0.88},
                {'question': 'Will there be 4 Fed rate cuts in 2025?', 'yes_price': 0.07, 'no_price': 0.93}
            ]
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = TelegramFormatter()
        result = formatter.format_alert(alert, recommendation)

        assert 'OTHER OUTCOMES' in result
        assert 'YES' in result
        assert 'NO' in result
        assert '12¢ YES / 88¢ NO' in result
        assert '7¢ YES / 93¢ NO' in result


class TestDirectionDisplay:
    """Test direction display for volume spikes with low/no imbalance"""

    def test_balanced_pressure_discord(self):
        """Test that Discord formatter shows clarifying message for unknown outcome with low pressure."""
        from datetime import timezone

        alert = {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 8.0,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis': {
                'max_anomaly_score': 5.0,
                'dominant_outcome': 'YES',
                'dominant_side': 'BUY',
                'outcome_imbalance': 0.05,  # 5% = no clear direction
                'side_imbalance': 0.02       # 2% = balanced
            },
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.75,
                'outcomePrices': ['0.75', '0.25']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = DiscordFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Find detected field
        detected_field = next((f for f in result['fields'] if 'DETECTED' in f['name']), None)
        assert detected_field is not None
        # Should show clarifying message
        assert 'Balanced pressure (outcome unknown)' in detected_field['value']
        assert '5%' not in detected_field['value']  # Shouldn't show low percentages
        assert '2%' not in detected_field['value']

    def test_strong_direction_discord(self):
        """Test that Discord formatter shows percentages for strong direction."""
        from datetime import timezone

        alert = {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 8.0,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis': {
                'max_anomaly_score': 5.0,
                'dominant_outcome': 'YES',
                'dominant_side': 'SELL',
                'outcome_imbalance': 0.78,  # 78% = strong
                'side_imbalance': 0.85       # 85% = strong
            },
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.75,
                'outcomePrices': ['0.75', '0.25']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = DiscordFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Find detected field
        detected_field = next((f for f in result['fields'] if 'DETECTED' in f['name']), None)
        assert detected_field is not None
        # Should show strong percentages
        assert '78% YES' in detected_field['value']
        assert '85% SELL' in detected_field['value']

    def test_balanced_pressure_telegram(self):
        """Test that Telegram formatter shows clarifying message for unknown outcome with low pressure."""
        alert = {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 8.0,
            'timestamp': datetime.now(),
            'analysis': {
                'max_anomaly_score': 5.0,
                'dominant_outcome': 'YES',
                'dominant_side': 'BUY',
                'outcome_imbalance': 0.03,  # 3% = no clear direction
                'side_imbalance': 0.01       # 1% = balanced
            },
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.75,
                'outcomePrices': ['0.75', '0.25']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = TelegramFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Should show clarifying message
        assert 'Balanced pressure (outcome unknown)' in result
        assert '3%' not in result  # Shouldn't show low percentages
        assert '1%' not in result

    def test_strong_pressure_unknown_outcome_discord(self):
        """Test Discord formatter shows pressure with clarification when outcome unknown."""
        from datetime import timezone

        alert = {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 8.0,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis': {
                'max_anomaly_score': 5.0,
                'dominant_outcome': 'YES',
                'dominant_side': 'SELL',
                'outcome_imbalance': 0.05,  # 5% = no outcome data
                'side_imbalance': 0.80       # 80% = strong SELL
            },
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.75,
                'outcomePrices': ['0.75', '0.25']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = DiscordFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Find detected field
        detected_field = next((f for f in result['fields'] if 'DETECTED' in f['name']), None)
        assert detected_field is not None
        # Should show clear message about unknown outcome
        assert '80% SELL pressure (outcome unknown)' in detected_field['value']

    def test_strong_pressure_unknown_outcome_telegram(self):
        """Test Telegram formatter shows pressure with clarification when outcome unknown."""
        alert = {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 8.0,
            'timestamp': datetime.now(),
            'analysis': {
                'max_anomaly_score': 5.0,
                'dominant_outcome': 'YES',
                'dominant_side': 'SELL',
                'outcome_imbalance': 0.05,  # 5% = no outcome data
                'side_imbalance': 0.80       # 80% = strong SELL
            },
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.75,
                'outcomePrices': ['0.75', '0.25']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = TelegramFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Should show clear message about unknown outcome
        assert '80% SELL pressure (outcome unknown)' in result

    def test_clear_outcome_balanced_pressure_discord(self):
        """Test Discord formatter shows 'Pressure: Balanced' when outcome is clear but pressure is balanced."""
        from datetime import timezone

        alert = {
            'severity': 'HIGH',
            'market_question': 'Will 8+ Fed rate cuts happen in 2025?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 9.0,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis': {
                'max_anomaly_score': 122.5,
                'dominant_outcome': 'NO',
                'dominant_side': 'BUY',
                'outcome_imbalance': 1.0,  # 100% = all volume on NO
                'side_imbalance': 0.05      # 5% = balanced BUY/SELL
            },
            'market_data': {
                'volume24hr': 40000,
                'lastTradePrice': 0.0035,
                'outcomePrices': ['0.0035', '0.9965']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = DiscordFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Find detected field
        detected_field = next((f for f in result['fields'] if 'DETECTED' in f['name']), None)
        assert detected_field is not None
        # Should show clear outcome
        assert '100% NO' in detected_field['value']
        # Should show "Pressure: Balanced" instead of hiding it
        assert '**Pressure:** Balanced' in detected_field['value']
        # Should NOT show low percentage
        assert '5% BUY' not in detected_field['value']

    def test_clear_outcome_balanced_pressure_telegram(self):
        """Test Telegram formatter shows 'Pressure: Balanced' when outcome is clear but pressure is balanced."""
        alert = {
            'severity': 'HIGH',
            'market_question': 'Will 8+ Fed rate cuts happen in 2025?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 9.0,
            'timestamp': datetime.now(),
            'analysis': {
                'max_anomaly_score': 122.5,
                'dominant_outcome': 'NO',
                'dominant_side': 'BUY',
                'outcome_imbalance': 1.0,  # 100% = all volume on NO
                'side_imbalance': 0.05      # 5% = balanced BUY/SELL
            },
            'market_data': {
                'volume24hr': 40000,
                'lastTradePrice': 0.0035,
                'outcomePrices': ['0.0035', '0.9965']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = TelegramFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Should show clear outcome
        assert '100% NO' in result
        # Should show "Pressure: Balanced" instead of hiding it
        assert '<b>Pressure:</b> Balanced' in result
        # Should NOT show low percentage
        assert '5% BUY' not in result


class TestScoreVolatilityDisplay:
    """Test score and volatility display formatting"""

    def test_volume_spike_score_format_discord(self):
        """Test that Discord formatter shows clean score format (no 'normal' text)."""
        from datetime import timezone

        alert = {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 8.0,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis': {
                'max_anomaly_score': 4.6,
                'dominant_outcome': 'YES',
                'dominant_side': 'BUY',
                'outcome_imbalance': 0.75,
                'side_imbalance': 0.80
            },
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.65,
                'outcomePrices': ['0.65', '0.35']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = DiscordFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Find detected field
        detected_field = next((f for f in result['fields'] if 'DETECTED' in f['name']), None)
        assert detected_field is not None
        # Should show "4.6x" without "normal" text
        assert '4.6x' in detected_field['value']
        assert 'normal' not in detected_field['value']

    def test_volume_spike_score_format_telegram(self):
        """Test that Telegram formatter shows clean score format (no 'normal' text)."""
        alert = {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k?',
            'alert_type': AlertType.VOLUME_SPIKE,
            'confidence_score': 8.0,
            'timestamp': datetime.now(),
            'analysis': {
                'max_anomaly_score': 4.6,
                'dominant_outcome': 'YES',
                'dominant_side': 'BUY',
                'outcome_imbalance': 0.75,
                'side_imbalance': 0.80
            },
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.65,
                'outcomePrices': ['0.65', '0.35']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = TelegramFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Should show "4.6x" without "normal" text
        assert '4.6x' in result
        assert 'normal' not in result.lower()

    def test_price_movement_volatility_format_discord(self):
        """Test that Discord formatter shows clean volatility format (no 'normal' text)."""
        from datetime import timezone

        alert = {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k?',
            'alert_type': AlertType.UNUSUAL_PRICE_MOVEMENT,
            'confidence_score': 7.5,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis': {
                'analysis': {
                    'price_change_pct': 15.3,
                    'volatility_spike': 2.8
                }
            },
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.75,
                'outcomePrices': ['0.75', '0.25']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = DiscordFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Find detected field
        detected_field = next((f for f in result['fields'] if 'DETECTED' in f['name']), None)
        assert detected_field is not None
        # Should show "2.8x" without "normal" text
        assert '2.8x' in detected_field['value']
        assert 'normal' not in detected_field['value']

    def test_price_movement_volatility_format_telegram(self):
        """Test that Telegram formatter shows clean volatility format (no 'normal' text)."""
        alert = {
            'severity': 'HIGH',
            'market_question': 'Will Bitcoin reach $100k?',
            'alert_type': AlertType.UNUSUAL_PRICE_MOVEMENT,
            'confidence_score': 7.5,
            'timestamp': datetime.now(),
            'analysis': {
                'analysis': {
                    'price_change_pct': 15.3,
                    'volatility_spike': 2.8
                }
            },
            'market_data': {
                'volume24hr': 150000,
                'lastTradePrice': 0.75,
                'outcomePrices': ['0.75', '0.25']
            }
        }

        recommendation = {'action': 'MONITOR', 'text': 'Watch', 'reasoning': 'Test'}

        formatter = TelegramFormatter()
        result = formatter.format_alert(alert, recommendation)

        # Should show "2.8x" without "normal" text
        assert '2.8x' in result
        assert 'normal' not in result.lower()
