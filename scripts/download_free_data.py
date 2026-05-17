#!/usr/bin/env python3
"""Download historical forex data from multiple free sources."""
import yfinance as yf
import pandas as pd
from pathlib import Path
import time

PAIRS = {
    "GBPUSD": "GBPUSD=X",
    "GBPJPY": "GBPJPY=X",
    "USDJPY": "USDJPY=X",
}

data_dir = Path(__file__).parent / "data_free"
data_dir.mkdir(exist_ok=True)

# Yahoo Finance 1h data has ~2 years of history
for name, symbol in PAIRS.items():
    print(f"\n{'='*50}")
    print(f"Downloading {symbol} from Yahoo Finance (1h)...")
    
    try:
        df = yf.download(symbol, period="max", interval="1h", progress=False)
        if df.empty:
            print(f"  WARNING: No data for {symbol}")
            continue
        
        # Flatten MultiIndex columns
        df.columns = [c[0].lower() for c in df.columns]
        df.index = pd.to_datetime(df.index, utc=True)
        df = df[["open", "high", "low", "close", "volume"]]
        
        out = data_dir / f"{name}_1h.csv"
        df.to_csv(out)
        print(f"  Saved {out}")
        print(f"  {len(df)} candles | {df.index[0]} to {df.index[-1]}")
        print(f"  Price range: {df['low'].min():.5f} - {df['high'].max():.5f}")
        
        time.sleep(1)  # Be nice to Yahoo
    except Exception as e:
        print(f"  ERROR: {e}")

print("\nDone.")
