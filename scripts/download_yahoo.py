#!/usr/bin/env python3
"""Download real forex data from Yahoo Finance for backtesting."""
import yfinance as yf
import pandas as pd
from pathlib import Path

PAIRS = {
    "GBPUSD": "GBPUSD=X",
    "GBPJPY": "GBPJPY=X",
    "USDJPY": "USDJPY=X",
}

data_dir = Path(__file__).parent / "data_yf"
data_dir.mkdir(exist_ok=True)

for name, symbol in PAIRS.items():
    print(f"Downloading {symbol} (15m)...")
    df = yf.download(symbol, period="max", interval="15m", progress=False)
    if df.empty:
        print(f"  WARNING: No data for {symbol}")
        continue
    # Flatten MultiIndex: take first level (Price name)
    df.columns = [c[0].lower() for c in df.columns]
    df = df.rename(columns={"close": "close", "high": "high", "low": "low", "open": "open", "volume": "volume"})
    df.index = pd.to_datetime(df.index, utc=True)
    out = data_dir / f"{name}_15m.csv"
    df.to_csv(out)
    print(f"  Saved {out} — {len(df)} candles | {df.index[0]} to {df.index[-1]}")

    print(f"Downloading {symbol} (5m)...")
    df5 = yf.download(symbol, period="max", interval="5m", progress=False)
    if df5.empty:
        print(f"  WARNING: No data for {symbol}")
        continue
    df5.columns = [c[0].lower() for c in df5.columns]
    df5.index = pd.to_datetime(df5.index, utc=True)
    out5 = data_dir / f"{name}_5m.csv"
    df5.to_csv(out5)
    print(f"  Saved {out5} — {len(df5)} candles | {df5.index[0]} to {df5.index[-1]}")

print("\nDone.")
