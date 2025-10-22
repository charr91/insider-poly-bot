#!/usr/bin/env python3
"""
Polymarket API Historical Data Investigation Script

Tests the Polymarket Data API to determine:
1. How far back we can fetch historical trade data
2. Pagination limits and data volume
3. Rate limiting constraints
4. Data quality and completeness

This investigation will inform whether we can build backtesting immediately
or need to collect data first.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
import time
from collections import defaultdict

class APIInvestigator:
    """Investigates Polymarket Data API capabilities"""

    def __init__(self):
        self.base_url = "https://data-api.polymarket.com"
        self.trades_endpoint = f"{self.base_url}/trades"
        self.markets_endpoint = f"{self.base_url}/markets"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PolymarketInsiderBot/1.0',
            'Accept': 'application/json'
        })

        self.results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'tests_performed': [],
            'api_capabilities': {},
            'recommendations': []
        }

    def test_api_connectivity(self) -> bool:
        """Test basic API connectivity"""
        print("\n" + "="*60)
        print("TEST 1: API Connectivity")
        print("="*60)

        try:
            response = self.session.get(self.trades_endpoint, params={'limit': 1}, timeout=10)
            response.raise_for_status()

            print("✅ API is accessible")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response Time: {response.elapsed.total_seconds():.2f}s")

            self.results['tests_performed'].append({
                'test': 'connectivity',
                'status': 'success',
                'details': 'API is accessible'
            })

            return True

        except Exception as e:
            print(f"❌ API connectivity failed: {e}")
            self.results['tests_performed'].append({
                'test': 'connectivity',
                'status': 'failed',
                'error': str(e)
            })
            return False

    def get_sample_markets(self, limit: int = 10) -> List[str]:
        """Get a sample of active markets for testing"""
        print("\n" + "="*60)
        print("TEST 2: Fetching Sample Markets")
        print("="*60)

        try:
            # Try to get markets from trades endpoint
            response = self.session.get(self.trades_endpoint, params={'limit': 100}, timeout=10)
            response.raise_for_status()
            trades = response.json()

            # Extract unique condition IDs (the API uses conditionId as market identifier)
            # Filter out empty strings
            market_ids = [cid for cid in set(trade.get('conditionId', '') for trade in trades) if cid][:limit]

            print(f"✅ Found {len(market_ids)} sample markets (condition IDs)")
            for i, market_id in enumerate(market_ids[:5], 1):
                print(f"   {i}. {market_id[:20]}...")

            if len(market_ids) > 5:
                print(f"   ... and {len(market_ids) - 5} more")

            self.results['tests_performed'].append({
                'test': 'sample_markets',
                'status': 'success',
                'market_count': len(market_ids)
            })

            return market_ids

        except Exception as e:
            print(f"❌ Failed to fetch sample markets: {e}")
            self.results['tests_performed'].append({
                'test': 'sample_markets',
                'status': 'failed',
                'error': str(e)
            })
            return []

    def test_historical_depth(self, market_id: str) -> Dict:
        """Test how far back we can fetch historical data for a market"""
        print("\n" + "="*60)
        print(f"TEST 3: Historical Data Depth for Market")
        print("="*60)
        print(f"Market ID: {market_id[:20]}...")

        results = {
            'market_id': market_id,
            'oldest_trade_timestamp': None,
            'oldest_trade_age_days': None,
            'total_trades_fetched': 0,
            'pagination_limit': None,
            'data_available': False
        }

        try:
            all_trades = []
            offset = 0
            max_iterations = 20  # Prevent infinite loops
            iteration = 0

            print("\nFetching trades (max 20 pages)...")

            while iteration < max_iterations:
                response = self.session.get(
                    self.trades_endpoint,
                    params={
                        'market': market_id,
                        'limit': 500,
                        'offset': offset
                    },
                    timeout=10
                )
                response.raise_for_status()
                trades = response.json()

                if not trades:
                    print(f"   Page {iteration + 1}: No more trades")
                    break

                all_trades.extend(trades)
                print(f"   Page {iteration + 1}: {len(trades)} trades (total: {len(all_trades)})")

                if len(trades) < 500:
                    print(f"   Reached end of data")
                    break

                offset += 500
                iteration += 1
                time.sleep(0.2)  # Rate limiting

            if not all_trades:
                print("⚠️  No trades found for this market")
                results['data_available'] = False
                return results

            # Analyze timestamps
            timestamps = []
            for trade in all_trades:
                ts = trade.get('timestamp')
                if ts:
                    try:
                        if isinstance(ts, (int, float)):
                            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        else:
                            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        timestamps.append(dt)
                    except (ValueError, TypeError):
                        continue

            if timestamps:
                oldest = min(timestamps)
                newest = max(timestamps)
                age_days = (datetime.now(timezone.utc) - oldest).days

                results['oldest_trade_timestamp'] = oldest.isoformat()
                results['oldest_trade_age_days'] = age_days
                results['total_trades_fetched'] = len(all_trades)
                results['pagination_limit'] = iteration * 500
                results['data_available'] = True

                print(f"\n✅ Historical Data Summary:")
                print(f"   Total Trades: {len(all_trades)}")
                print(f"   Oldest Trade: {oldest.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"   Newest Trade: {newest.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"   Historical Depth: {age_days} days")
                print(f"   Pages Fetched: {iteration + 1}")
            else:
                print("⚠️  Could not parse timestamps")
                results['data_available'] = False

            self.results['tests_performed'].append({
                'test': 'historical_depth',
                'status': 'success',
                'results': results
            })

            return results

        except Exception as e:
            print(f"❌ Historical depth test failed: {e}")
            results['error'] = str(e)
            self.results['tests_performed'].append({
                'test': 'historical_depth',
                'status': 'failed',
                'error': str(e)
            })
            return results

    def test_multiple_markets(self, market_ids: List[str], sample_size: int = 5) -> Dict:
        """Test historical data availability across multiple markets"""
        print("\n" + "="*60)
        print(f"TEST 4: Historical Data Across {sample_size} Markets")
        print("="*60)

        market_results = []

        for i, market_id in enumerate(market_ids[:sample_size], 1):
            print(f"\nMarket {i}/{sample_size}")
            result = self.test_historical_depth(market_id)
            market_results.append(result)

            if i < sample_size:
                time.sleep(1)  # Rate limiting between markets

        # Aggregate statistics
        available_markets = [r for r in market_results if r['data_available']]

        if available_markets:
            avg_depth_days = sum(r['oldest_trade_age_days'] for r in available_markets) / len(available_markets)
            min_depth_days = min(r['oldest_trade_age_days'] for r in available_markets)
            max_depth_days = max(r['oldest_trade_age_days'] for r in available_markets)
            avg_trades = sum(r['total_trades_fetched'] for r in available_markets) / len(available_markets)

            summary = {
                'markets_tested': len(market_ids[:sample_size]),
                'markets_with_data': len(available_markets),
                'avg_historical_depth_days': round(avg_depth_days, 1),
                'min_historical_depth_days': min_depth_days,
                'max_historical_depth_days': max_depth_days,
                'avg_trades_per_market': round(avg_trades, 0)
            }

            print("\n" + "="*60)
            print("AGGREGATE STATISTICS")
            print("="*60)
            print(f"Markets Tested: {summary['markets_tested']}")
            print(f"Markets with Data: {summary['markets_with_data']}")
            print(f"Average Historical Depth: {summary['avg_historical_depth_days']} days")
            print(f"Range: {summary['min_historical_depth_days']}-{summary['max_historical_depth_days']} days")
            print(f"Average Trades/Market: {summary['avg_trades_per_market']}")

            self.results['api_capabilities'] = summary

        else:
            summary = {
                'markets_tested': len(market_ids[:sample_size]),
                'markets_with_data': 0,
                'error': 'No markets had accessible historical data'
            }
            print("\n⚠️  No markets had accessible historical data")

        return summary

    def test_date_range_queries(self, market_id: str) -> Dict:
        """Test if API supports date range filtering"""
        print("\n" + "="*60)
        print("TEST 5: Date Range Query Support")
        print("="*60)

        # Try various date parameters that might be supported
        test_params = [
            {'start_date': (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()},
            {'end_date': datetime.now(timezone.utc).isoformat()},
            {'after': int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())},
            {'before': int(datetime.now(timezone.utc).timestamp())},
            {'start_ts': int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())},
            {'end_ts': int(datetime.now(timezone.utc).timestamp())},
        ]

        results = []

        for params in test_params:
            param_name = list(params.keys())[0]
            try:
                full_params = {'market': market_id, 'limit': 10, **params}
                response = self.session.get(self.trades_endpoint, params=full_params, timeout=10)

                if response.status_code == 200:
                    trades = response.json()
                    result = {
                        'parameter': param_name,
                        'status': 'supported',
                        'trades_returned': len(trades)
                    }
                    print(f"✅ Parameter '{param_name}': Supported ({len(trades)} trades)")
                else:
                    result = {
                        'parameter': param_name,
                        'status': 'not_supported',
                        'status_code': response.status_code
                    }
                    print(f"❌ Parameter '{param_name}': Not supported (HTTP {response.status_code})")

                results.append(result)
                time.sleep(0.5)

            except Exception as e:
                result = {
                    'parameter': param_name,
                    'status': 'error',
                    'error': str(e)
                }
                print(f"⚠️  Parameter '{param_name}': Error - {e}")
                results.append(result)

        supported = [r for r in results if r['status'] == 'supported']

        if not supported:
            print("\n❌ API does not appear to support date range filtering")
            print("   Note: We can still paginate through all trades chronologically")

        self.results['tests_performed'].append({
            'test': 'date_range_queries',
            'results': results
        })

        return {'supported_parameters': [r['parameter'] for r in supported]}

    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on investigation results"""
        print("\n" + "="*60)
        print("RECOMMENDATIONS")
        print("="*60)

        recommendations = []

        caps = self.results.get('api_capabilities', {})
        avg_depth = caps.get('avg_historical_depth_days', 0)

        if avg_depth >= 60:
            recommendations.append("✅ PROCEED WITH PHASE 2A: Full Backtesting Implementation")
            recommendations.append(f"   - Sufficient historical data available ({avg_depth} days average)")
            recommendations.append("   - Can build comprehensive backtesting framework immediately")
            recommendations.append("   - Fetch 30-60 days of data for initial backtests")

        elif avg_depth >= 14:
            recommendations.append("⚠️  HYBRID APPROACH RECOMMENDED")
            recommendations.append(f"   - Limited historical data ({avg_depth} days average)")
            recommendations.append("   - Start with limited backtesting using available data")
            recommendations.append("   - Simultaneously collect new data for expanded testing")
            recommendations.append("   - Consider implementing Task 2.1 (Adaptive Thresholds) in parallel")

        else:
            recommendations.append("❌ PROCEED WITH PHASE 2B: Data Collection First")
            recommendations.append(f"   - Insufficient historical data ({avg_depth} days average)")
            recommendations.append("   - Implement enhanced data collection to database")
            recommendations.append("   - Run bot for 2-4 weeks to accumulate data")
            recommendations.append("   - Meanwhile, implement Task 2.1 (Adaptive Thresholds)")
            recommendations.append("   - Build backtesting framework after data collection")

        for rec in recommendations:
            print(rec)

        self.results['recommendations'] = recommendations
        return recommendations

    def save_results(self, output_path: str = ".taskmaster/docs/api_data_availability.md"):
        """Save investigation results to markdown file"""
        print("\n" + "="*60)
        print("SAVING RESULTS")
        print("="*60)

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Generate markdown report
        md_content = f"""# Polymarket API Historical Data Investigation

**Investigation Date**: {self.results['timestamp']}

## Executive Summary

"""

        caps = self.results.get('api_capabilities', {})
        if caps:
            avg_depth = caps.get('avg_historical_depth_days', 0)
            md_content += f"""- **Historical Data Availability**: {avg_depth} days (average across sampled markets)
- **Markets Tested**: {caps.get('markets_tested', 0)}
- **Markets with Data**: {caps.get('markets_with_data', 0)}
- **Average Trades per Market**: {caps.get('avg_trades_per_market', 0)}
- **Data Depth Range**: {caps.get('min_historical_depth_days', 0)}-{caps.get('max_historical_depth_days', 0)} days

"""

        md_content += f"""## Recommendations

"""
        for rec in self.results.get('recommendations', []):
            md_content += f"{rec}\n"

        md_content += f"""
## Test Results

### Tests Performed

"""
        for test in self.results.get('tests_performed', []):
            test_name = test.get('test', 'unknown').replace('_', ' ').title()
            status = test.get('status', 'unknown')
            status_emoji = '✅' if status == 'success' else '❌'

            md_content += f"#### {status_emoji} {test_name}\n\n"

            if status == 'success':
                if 'results' in test and isinstance(test['results'], dict):
                    md_content += "```json\n"
                    md_content += json.dumps(test['results'], indent=2)
                    md_content += "\n```\n\n"
                elif 'details' in test:
                    md_content += f"{test['details']}\n\n"
            else:
                md_content += f"**Error**: {test.get('error', 'Unknown error')}\n\n"

        md_content += f"""
## Raw Results

```json
{json.dumps(self.results, indent=2)}
```

## Next Steps

Based on these results, the recommended implementation approach has been determined.
See recommendations section above for specific action items.
"""

        with open(output_path, 'w') as f:
            f.write(md_content)

        print(f"✅ Results saved to: {output_path}")

        # Also save raw JSON
        json_path = output_path.replace('.md', '.json')
        with open(json_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"✅ Raw JSON saved to: {json_path}")

    def run_full_investigation(self):
        """Run complete API investigation"""
        print("\n" + "="*70)
        print("POLYMARKET API HISTORICAL DATA INVESTIGATION")
        print("="*70)
        print("\nThis script will test the Polymarket Data API to determine:")
        print("  1. How far back historical trade data is available")
        print("  2. Data volume and pagination limits")
        print("  3. Whether we can proceed with backtesting immediately")
        print("\n" + "="*70)

        # Test 1: Connectivity
        if not self.test_api_connectivity():
            print("\n❌ Cannot proceed without API connectivity")
            return

        # Test 2: Get sample markets
        market_ids = self.get_sample_markets(limit=10)
        if not market_ids:
            print("\n❌ Cannot proceed without sample markets")
            return

        # Test 3-4: Historical depth analysis
        self.test_multiple_markets(market_ids, sample_size=5)

        # Test 5: Date range query support
        if market_ids:
            self.test_date_range_queries(market_ids[0])

        # Generate recommendations
        self.generate_recommendations()

        # Save results
        self.save_results()

        print("\n" + "="*70)
        print("INVESTIGATION COMPLETE")
        print("="*70)
        print("\nReview the generated report at:")
        print(".taskmaster/docs/api_data_availability.md")
        print("\n")


def main():
    """Main entry point"""
    investigator = APIInvestigator()
    investigator.run_full_investigation()


if __name__ == "__main__":
    main()
