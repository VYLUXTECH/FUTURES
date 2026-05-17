#!/usr/bin/env python3
"""Download FXCM m1 data (2017-2023) and aggregate to 15m candles."""
import gzip, io
from pathlib import Path
from datetime import datetime
import time

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

PAIRS = ["GBPUSD", "GBPJPY", "USDJPY"]
FXCM_BASE = "https://candledata.fxcorporate.com/m1"

def get_weeks_in_year(year):
    """Return list of ISO week numbers for a year."""
    dec31 = datetime(year, 12, 31)
    last_week = dec31.isocalendar()[1]
    # Handle edge case where Dec 31 is in week 1 of next year
    if last_week == 1:
        last_week = datetime(year, 12, 28).isocalendar()[1]
    return list(range(1, last_week + 1))

def download_week(instrument, year, week):
    """Download one week of m1 data."""
    url = f"{FXCM_BASE}/{instrument}/{year}/{week}.csv.gz"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200 or len(resp.content) < 100:
            return None
        with gzip.open(io.BytesIO(resp.content), 'rt') as f:
            content = f.read()
        lines = content.strip().split('\n')
        if len(lines) < 2:
            return None
        
        rows = []
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) >= 9:
                dt = datetime.strptime(parts[0], "%m/%d/%Y %H:%M:%S.%f")
                # Use mid price (average of bid close and ask close)
                mid = (float(parts[4]) + float(parts[8])) / 2
                bid_open = float(parts[1])
                ask_open = float(parts[5])
                mid_open = (bid_open + ask_open) / 2
                bid_high = float(parts[2])
                ask_high = float(parts[6])
                mid_high = (bid_high + ask_high) / 2
                bid_low = float(parts[3])
                ask_low = float(parts[7])
                mid_low = (bid_low + ask_low) / 2
                rows.append((dt, mid_open, mid_high, mid_low, mid, 0))
        return rows
    except Exception as e:
        print(f"    Error: {e}")
        return None

def download_year(instrument, year):
    """Download all weeks for a year."""
    all_rows = []
    weeks = get_weeks_in_year(year)
    for week in weeks:
        result = download_week(instrument, year, week)
        if result:
            all_rows.extend(result)
        time.sleep(0.3)
    return all_rows

def aggregate_to_15m(rows):
    """Aggregate m1 rows to 15m OHLCV."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    df.set_index("datetime", inplace=True)
    df.index = pd.to_datetime(df.index, utc=True)
    
    ohlc = df.resample("15min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    ohlc.dropna(subset=["open"], inplace=True)
    return ohlc

if __name__ == "__main__":
    for pair in PAIRS:
        print(f"\n{'='*60}")
        print(f"Downloading {pair} (2017-2023)...")
        print(f"{'='*60}")
        
        all_years = []
        for year in range(2017, 2024):
            print(f"  {year}...", end=" ", flush=True)
            rows = download_year(pair, year)
            if rows:
                candles = aggregate_to_15m(rows)
                all_years.append(candles)
                print(f"{len(candles)} 15m candles")
            else:
                print("no data")
        
        if all_years:
            full = pd.concat(all_years).sort_index()
            out = DATA_DIR / f"{pair}_15m_extended.csv"
            full.to_csv(out)
            print(f"\nSaved {len(full)} candles → {out}")
            print(f"Date range: {full.index[0]} to {full.index[-1]}")
