#!/usr/bin/env python3
"""
Test getting public market trades (not just our own)
"""
import os
import requests
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

load_dotenv()

def test_public_trades():
    """Test different ways to get public trade data"""
    
    print("🔍 Testing different approaches to get PUBLIC trade data...")
    
    # Test 1: Level 0 CLOB (no auth - public data)
    print("\n--- Test 1: Level 0 CLOB Client (no auth) ---")
    try:
        client_l0 = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=POLYGON
        )
        
        trades_l0 = client_l0.get_trades()
        print(f"Level 0 trades: {len(trades_l0)} trades")
        
        if trades_l0:
            # Check if these are different from authenticated trades
            market_ids = set(t.get('market') for t in trades_l0[:5])
            print(f"Markets in Level 0 trades: {list(market_ids)}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Direct REST API call (no auth)
    print("\n--- Test 2: Direct REST API Call ---")
    try:
        # Try different endpoints
        endpoints = [
            "https://clob.polymarket.com/trades",
            "https://clob.polymarket.com/markets/trades",
            "https://gamma-api.polymarket.com/trades",
        ]
        
        for endpoint in endpoints:
            print(f"\nTrying: {endpoint}")
            try:
                response = requests.get(endpoint, timeout=5)
                print(f"Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        print(f"Found {len(data)} trades")
                    elif isinstance(data, dict):
                        print(f"Response keys: {list(data.keys())}")
            except Exception as e:
                print(f"Failed: {e}")
                
    except Exception as e:
        print(f"Error in REST tests: {e}")
    
    # Test 3: Check if we need to specify a market
    print("\n--- Test 3: Market-specific queries ---")
    # Use a high-volume market we know exists
    test_market = "0x3d0a731b99b6b7656c93e16a074e5da78e5b5e9a64fafe80f63e27a42e5dc0ba"  # ETH $10k market
    
    print(f"Testing with market: {test_market[:10]}...")
    
    # This would need the client to support market-specific queries
    # which the current py-clob-client might not support

if __name__ == "__main__":
    test_public_trades()