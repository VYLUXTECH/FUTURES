from __future__ import annotations

import io
import logging
import os
import tempfile
from datetime import datetime
from typing import Any

import pandas as pd

from brain.config.constants import SUPPORTED_PAIRS
from brain.data.feed import get_candles

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import mplfinance as mpf
    MPF_AVAILABLE = True
except ImportError:
    MPF_AVAILABLE = False
    logger.warning("mplfinance not installed – chart generation disabled")


class ChartGenerator:
    """Generate candlestick chart images with support/resistance annotations."""

    def generate(
        self,
        pair: str,
        tf: str = "15m",
        num_candles: int = 50,
    ) -> str | None:
        """
        Generate a candlestick chart PNG with annotations.
        Returns the file path to the generated image, or None on failure.
        """
        if not MPF_AVAILABLE:
            logger.warning("mplfinance not available")
            return None

        if pair not in SUPPORTED_PAIRS:
            logger.warning("Unsupported pair: %s", pair)
            return None

        try:
            df = get_candles(pair, tf, num_candles + 20)
            if df is None or df.empty or len(df) < 20:
                return None
        except Exception as exc:
            logger.error("Failed to fetch candles for %s: %s", pair, exc)
            return None

        df = df.tail(num_candles).copy()

        # Rename columns for mplfinance
        ohlc = df.rename(columns={
            "open": "Open", "high": "High",
            "low": "Low", "close": "Close", "tick_volume": "Volume",
        })

        if "Volume" not in ohlc.columns or ohlc["Volume"].isna().all():
            ohlc["Volume"] = 0

        # Detect support/resistance levels
        high = ohlc["High"].values
        low = ohlc["Low"].values
        support = low.min()
        resistance = high.max()

        # Rejection candle detection
        last = ohlc.iloc[-1]
        body = abs(last["Close"] - last["Open"])
        upper_wick = last["High"] - max(last["Close"], last["Open"])
        lower_wick = min(last["Close"], last["Open"]) - last["Low"]
        rejection_idx = None
        rejection_type = None
        if body > 0 and (upper_wick > body * 2 or lower_wick > body * 2):
            rejection_idx = len(ohlc) - 1
            rejection_type = "bullish" if lower_wick > upper_wick else "bearish"

        # Build plot
        fig, axes = mpf.plot(
            ohlc,
            type="candle",
            style="charles",
            volume=True,
            returnfig=True,
            figsize=(10, 6),
            tight_layout=True,
        )

        ax = axes[0]

        # Support/resistance lines
        ax.axhline(y=support, color="green", linestyle="--", alpha=0.7, linewidth=1)
        ax.axhline(y=resistance, color="red", linestyle="--", alpha=0.7, linewidth=1)

        # Labels
        ax.text(len(ohlc) - 1, support, f"  S: {support:.5f}",
                color="green", fontsize=9, verticalalignment="top")
        ax.text(len(ohlc) - 1, resistance, f"  R: {resistance:.5f}",
                color="red", fontsize=9, verticalalignment="bottom")

        # Mark rejection candle
        if rejection_idx is not None:
            candle = ohlc.iloc[rejection_idx]
            price = candle["Low"] if rejection_type == "bullish" else candle["High"]
            marker = "^" if rejection_type == "bullish" else "v"
            color = "lime" if rejection_type == "bullish" else "orange"
            ax.scatter(rejection_idx, price, marker=marker, s=200,
                       color=color, zorder=5, edgecolors="black")
            ax.annotate(
                f"{rejection_type} rejection",
                (rejection_idx, price),
                xytext=(rejection_idx + 2, price),
                arrowprops=dict(arrowstyle="->", color=color),
                fontsize=9, color=color,
            )

        # Title
        ax.set_title(f"{pair} ({tf}) – {datetime.utcnow().strftime('%H:%M UTC')}",
                     fontsize=12, fontweight="bold")

        # Save to temp file
        out_dir = os.path.join(tempfile.gettempdir(), "futures_charts")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{pair}_{tf}_{int(datetime.utcnow().timestamp())}.png")
        fig.savefig(out_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        logger.info("Chart generated: %s", out_path)
        return out_path
