#!/usr/bin/env python3
"""
Download 15m historical data from Yahoo Finance for all supported pairs.
Yahoo provides ~60 days of 15m data — enough for initial validation.
For full backtesting, use Dukascopy or MT5 history.
"""
import yfinance as yf
import pandas as pd
from pathlib import Path
import time

PAIRS = {
    "GBPUSD": "GBPUSD=X",
    "GBPJPY": "GBPJPY=X",
    "USDJPY": "USDJPY=X",
    "EURUSD": "EURUSD=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
}

data_dir = Path(__file__).parent / "data"
data_dir.mkdir(exist_ok=True)

for name, symbol in PAIRS.items():
    print(f"\n{'='*50}")
    print(f"Downloading {symbol} (15m)...")

    try:
        df = yf.download(symbol, period="max", interval="15m", progress=False)
        if df.empty:
            print(f"  WARNING: No data for {symbol}")
            continue

        df.columns = [c[0].lower() for c in df.columns]
        df.index = pd.to_datetime(df.index, utc=True)
        df = df[["open", "high", "low", "close", "volume"]]
        df = df.dropna()

        out = data_dir / f"{name}_15m.csv"
        df.to_csv(out)
        print(f"  Saved {out}")
        print(f"  {len(df)} candles | {df.index[0]} to {df.index[-1]}")
        print(f"  Price range: {df['low'].min():.5f} - {df['high'].max():.5f}")

        time.sleep(2)
    except Exception as e:
        print(f"  ERROR: {e}")

print(f"\n{'='*50}")
print("Done. Run: python backtest.py")
