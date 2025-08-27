#!/usr/bin/env python3
"""
Debug trade data fetching to see if we're getting real trades
"""
import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import ApiCreds
from datetime import datetime, timezone, timedelta

load_dotenv()

def debug_trades():
    """Check if we're actually getting trade data"""
    
    # Initialize CLOB client
    private_key = os.getenv('POLYGON_PRIVATE_KEY')
    funder_address = os.getenv('FUNDER_ADDRESS')
    api_key = os.getenv('CLOB_API_KEY')
    api_secret = os.getenv('CLOB_API_SECRET') 
    api_passphrase = os.getenv('CLOB_API_PASSPHRASE')
    
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=POLYGON,
        signature_type=1,
        funder=funder_address
    )
    
    creds = ApiCreds(
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase
    )
    client.set_api_creds(creds)
    
    print("🔍 Testing CLOB trade data retrieval...")
    
    # Get trades
    trades = client.get_trades()
    
    print(f"\n📊 Found {len(trades)} trades from CLOB API")
    
    if trades:
        print("\n🔍 Analyzing trade data:")
        
        # Look at timestamps
        now = datetime.now(timezone.utc)
        recent_count = 0
        
        for i, trade in enumerate(trades[:5]):  # First 5 trades
            print(f"\n--- Trade {i+1} ---")
            print(f"Market ID: {trade.get('market', 'NO_MARKET')}")
            print(f"Price: {trade.get('price', 'NO_PRICE')}")
            print(f"Size: {trade.get('size', 'NO_SIZE')}")
            print(f"Side: {trade.get('side', 'NO_SIDE')}")
            
            # Check timestamp
            match_time = trade.get('match_time', '')
            if match_time:
                try:
                    # Convert UNIX timestamp to datetime
                    trade_time = datetime.fromtimestamp(int(match_time), tz=timezone.utc)
                    time_diff = now - trade_time
                    
                    print(f"Trade time: {trade_time}")
                    print(f"Time ago: {time_diff}")
                    
                    # Is it recent (within last hour)?
                    if time_diff < timedelta(hours=1):
                        recent_count += 1
                        print("✅ RECENT TRADE!")
                except Exception as e:
                    print(f"Error parsing timestamp: {e}")
            
            # Show all fields to understand structure
            print(f"All fields: {list(trade.keys())}")
        
        print(f"\n📊 Summary:")
        print(f"Total trades: {len(trades)}")
        print(f"Recent trades (< 1 hour): {recent_count}")
        
        # Check unique markets
        unique_markets = set(trade.get('market') for trade in trades if trade.get('market'))
        print(f"Unique markets in trades: {len(unique_markets)}")
        print(f"Sample market IDs: {list(unique_markets)[:3]}")
        
    else:
        print("❌ No trades returned from CLOB API")

if __name__ == "__main__":
    debug_trades()