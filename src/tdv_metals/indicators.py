"""Vectorized, causally aligned technical and macro features."""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .config import IndicatorConfig, MacroConfig


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [frame["high"] - frame["low"], (frame["high"] - previous_close).abs(), (frame["low"] - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_up = up.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_down = down.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_up / avg_down.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def williams_r(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high = frame["high"].rolling(period, min_periods=period).max()
    low = frame["low"].rolling(period, min_periods=period).min()
    return -100 * (high - frame["close"]) / (high - low).replace(0, np.nan)


def fibonacci_bollinger(series: pd.Series, window: int, deviation: float) -> pd.DataFrame:
    middle = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0)
    z_score = (series - middle) / std.replace(0, np.nan)
    return pd.DataFrame({
        "fib_bb_mid": middle, "fib_bb_std": std, "fib_bb_z": z_score,
        "fib_bb_upper": middle + deviation * std, "fib_bb_lower": middle - deviation * std,
    })


def fibonacci_macd(close: pd.Series, atr_series: pd.Series) -> pd.DataFrame:
    """Two Fibonacci MACDs normalized by ATR, not raw dollar price."""
    fast = _ema(close, 8) - _ema(close, 21)
    fast_signal = _ema(fast, 5)
    slow = _ema(close, 13) - _ema(close, 34)
    slow_signal = _ema(slow, 8)
    denominator = atr_series.replace(0, np.nan)
    return pd.DataFrame({
        "fib_macd": fast, "fib_macd_signal": fast_signal, "fib_macd_hist": fast - fast_signal,
        "fib_macd_atr": fast / denominator, "fib_macd_hist_atr": (fast - fast_signal) / denominator,
        "slow_fib_macd": slow, "slow_fib_macd_signal": slow_signal,
        "slow_fib_macd_hist_atr": (slow - slow_signal) / denominator,
    })


def ichimoku(frame: pd.DataFrame) -> pd.DataFrame:
    """Canonical 9/26/52 Ichimoku, including the 26-bar leading shifts."""
    high, low, close = frame["high"], frame["low"], frame["close"]
    tenkan = (high.rolling(9, min_periods=9).max() + low.rolling(9, min_periods=9).min()) / 2
    kijun = (high.rolling(26, min_periods=26).max() + low.rolling(26, min_periods=26).min()) / 2
    span_a_raw = (tenkan + kijun) / 2
    span_b_raw = (high.rolling(52, min_periods=52).max() + low.rolling(52, min_periods=52).min()) / 2
    # A cloud visible at t was calculated at t-26. These plot shifts therefore
    # prevent the common look-ahead error when using the cloud as a filter.
    span_a = span_a_raw.shift(26)
    span_b = span_b_raw.shift(26)
    cloud_top, cloud_bottom = pd.concat([span_a, span_b], axis=1).max(axis=1), pd.concat([span_a, span_b], axis=1).min(axis=1)
    return pd.DataFrame({
        "ichimoku_tenkan": tenkan, "ichimoku_kijun": kijun, "ichimoku_span_a": span_a,
        "ichimoku_span_b": span_b, "ichimoku_cloud_top": cloud_top,
        "ichimoku_cloud_bottom": cloud_bottom,
        "ichimoku_chikou": close.shift(-26),  # visual lagging line only; never a decision input
        "ichimoku_above_cloud": close > cloud_top,
        "ichimoku_below_cloud": close < cloud_bottom,
        "ichimoku_tk_bullish": tenkan > kijun,
    })


def add_indicators(frame: pd.DataFrame, config: IndicatorConfig) -> pd.DataFrame:
    result = frame.copy()
    result["atr"] = atr(result, config.atr_period)
    result["rsi"] = rsi(result["close"], config.rsi_period)
    result["williams_r"] = williams_r(result, config.williams_period)
    result["williams_delta"] = result["williams_r"].diff()
    result["williams_recovering"] = (result["williams_r"].shift(1) <= -80) & (result["williams_delta"] > 0)
    result = result.join(fibonacci_bollinger(result["shadow_gap"], config.fib_bb_window, config.fib_bb_deviation))
    result = result.join(fibonacci_macd(result["close"], result["atr"]))
    return result.join(ichimoku(result))


def add_relative_strength(frames: Mapping[str, pd.DataFrame], window: int) -> dict[str, pd.DataFrame]:
    """Synchronized risk-adjusted strength with explicitly unavailable stale peers."""
    closes = pd.concat({symbol: frame.set_index("timestamp")["close"] for symbol, frame in frames.items()}, axis=1).sort_index()
    returns = closes.pct_change(window, fill_method=None)
    daily_vol = closes.pct_change(fill_method=None).rolling(window, min_periods=window).std() * np.sqrt(window)
    risk_adjusted = returns / daily_vol.replace(0, np.nan)
    gs = closes["GOLD"] / closes["SILVER"]
    gc = closes["GOLD"] / closes["COPPER"]
    pair_returns = pd.DataFrame({
        "GOLD": (gs.pct_change(window, fill_method=None) + gc.pct_change(window, fill_method=None)) / 2,
        "SILVER": -gs.pct_change(window, fill_method=None),
        "COPPER": -gc.pct_change(window, fill_method=None),
    })
    # Rank both inputs before weighting so their scales cannot arbitrarily dominate.
    complete = risk_adjusted.notna().all(axis=1) & pair_returns.notna().all(axis=1)
    combined = 0.70 * risk_adjusted.rank(axis=1, pct=True) + 0.30 * pair_returns.rank(axis=1, pct=True)
    relative_score = (combined * 5.0).where(complete)
    output: dict[str, pd.DataFrame] = {}
    context = pd.DataFrame({"timestamp": closes.index, "gold_silver_ratio": gs.values, "gold_copper_ratio": gc.values})
    for symbol, frame in frames.items():
        strength = pd.DataFrame({"timestamp": closes.index, "relative_strength_score": relative_score[symbol].values})
        joined = pd.merge(frame.sort_values("timestamp"), strength, on="timestamp", how="left")
        output[symbol] = pd.merge(joined, context, on="timestamp", how="left")
        output[symbol]["relative_strength_status"] = np.where(
            output[symbol]["relative_strength_score"].notna(), "AVAILABLE", "MISSING_PEER_OR_WARMUP"
        )
    return output


def add_macro_confirmation(frame: pd.DataFrame, dxy: pd.DataFrame | None, real_yield: pd.DataFrame | None, macro: MacroConfig) -> pd.DataFrame:
    """Add macro state. Missing feeds are explicit; scoring does not silently assume bullishness."""
    result = frame.copy()
    if dxy is None or real_yield is None:
        result["macro_status"] = "MISSING"
        result["macro_confirmed"] = False
        result["macro_bearish_confirmed"] = False
        return result
    dxy_values = dxy[["timestamp", "close"]].rename(columns={"timestamp": "dxy_observed_at", "close": "dxy"}).sort_values("dxy_observed_at")
    yield_values = real_yield[["timestamp", "close"]].rename(columns={"timestamp": "real_yield_observed_at", "close": "real_yield"}).sort_values("real_yield_observed_at")
    result = pd.merge_asof(result.sort_values("timestamp"), dxy_values, left_on="timestamp", right_on="dxy_observed_at", direction="backward")
    result = pd.merge_asof(result, yield_values, left_on="timestamp", right_on="real_yield_observed_at", direction="backward")
    result["dxy_change_20"] = result["dxy"].pct_change(20)
    result["real_yield_change_20"] = result["real_yield"].diff(20)
    result["dxy_age_days"] = (result["timestamp"] - result["dxy_observed_at"]).dt.total_seconds() / 86400
    result["real_yield_age_days"] = (result["timestamp"] - result["real_yield_observed_at"]).dt.total_seconds() / 86400
    missing = result["dxy"].isna() | result["real_yield"].isna()
    stale = (result["dxy_age_days"] > macro.freshness_days) | (result["real_yield_age_days"] > macro.freshness_days)
    available = ~missing & ~stale
    result["macro_status"] = np.select([missing, stale], ["MISSING", "STALE"], default="AVAILABLE")
    result["macro_confirmed"] = available & (result["dxy_change_20"] < 0) & (result["real_yield_change_20"] <= 0)
    result["macro_bearish_confirmed"] = available & (result["dxy_change_20"] > 0) & (result["real_yield_change_20"] >= 0)
    return result
