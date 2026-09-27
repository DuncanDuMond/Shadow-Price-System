"""Causal advanced features for the Shadow Price System.

The volume profile allocates each bar's volume to its typical-price bin. It is
an OHLCV approximation, not a trade-by-trade volume-at-price profile. The SSL
and optional QQE features are transparent approximations, not Pine-script
reproductions of proprietary/community indicators.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AdvancedIndicatorConfig:
    shadow_lookback: int = 120
    volume_lookback: int = 20
    profile_lookback: int = 40
    profile_bins: int = 24
    profile_value_area: float = 0.70
    ssl_length: int = 20
    impulse_length: int = 34
    impulse_signal_length: int = 9
    ribbon_periods: tuple[int, ...] = (8, 13, 21, 34, 55)
    qqe_enabled: bool = False
    qqe_rsi_length: int = 14
    qqe_smoothing: int = 5
    qqe_factor: float = 4.236

    def __post_init__(self) -> None:
        for name in (
            "shadow_lookback", "volume_lookback", "profile_lookback", "profile_bins",
            "ssl_length", "impulse_length", "impulse_signal_length", "qqe_rsi_length",
            "qqe_smoothing",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 2:
                raise ValueError(f"{name} must be an integer >= 2")
        if (
            not isinstance(self.profile_value_area, (int, float))
            or not 0 < self.profile_value_area < 1
        ):
            raise ValueError("profile_value_area must be between 0 and 1")
        if (
            not isinstance(self.qqe_factor, (int, float))
            or not np.isfinite(self.qqe_factor) or self.qqe_factor <= 0
        ):
            raise ValueError("qqe_factor must be finite and positive")
        periods = self.ribbon_periods
        if (
            not isinstance(periods, tuple) or len(periods) < 2
            or any(isinstance(p, bool) or not isinstance(p, int) or p < 2 for p in periods)
            or tuple(sorted(set(periods))) != periods
        ):
            raise ValueError("ribbon_periods must be an increasing tuple of distinct integers >= 2")
        if not isinstance(self.qqe_enabled, bool):
            raise TypeError("qqe_enabled must be boolean")


def _ema(values: pd.Series, length: int) -> pd.Series:
    return values.ewm(span=length, adjust=False, min_periods=length).mean()


def _smma(values: pd.Series, length: int) -> pd.Series:
    """Wilder-style smoothed MA with a simple-average seed and reset on gaps."""
    raw = values.to_numpy(dtype=float)
    out = np.full(len(raw), np.nan)
    previous = np.nan
    for index, current in enumerate(raw):
        if not np.isfinite(current):
            previous = np.nan
        elif np.isfinite(previous):
            previous = (previous * (length - 1) + current) / length
            out[index] = previous
        elif index >= length - 1 and np.isfinite(raw[index - length + 1:index + 1]).all():
            previous = float(np.mean(raw[index - length + 1:index + 1]))
            out[index] = previous
    return pd.Series(out, index=values.index)


def _validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "timestamp", "open", "high", "low", "close", "volume",
        "shadow_price", "shadow_gap", "atr",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"advanced indicators require columns: {', '.join(missing)}")
    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True, errors="raise")
    if (
        result["timestamp"].isna().any()
        or not result["timestamp"].is_monotonic_increasing
        or result["timestamp"].duplicated().any()
    ):
        raise ValueError("timestamps must be non-null, unique, and ascending")
    for column in required - {"timestamp"}:
        result[column] = pd.to_numeric(result[column], errors="raise")
    for column in ("open", "high", "low", "close"):
        if not np.isfinite(result[column]).all() or (result[column] <= 0).any():
            raise ValueError(f"{column} must contain finite positive prices")
    if (
        (result["high"] < result[["open", "low", "close"]].max(axis=1)).any()
        or (result["low"] > result[["open", "high", "close"]].min(axis=1)).any()
    ):
        raise ValueError("OHLC bars have inconsistent high/low values")
    if (result["volume"].dropna() < 0).any() or np.isinf(result["volume"]).any():
        raise ValueError("volume cannot be negative or infinite")
    if (result["shadow_price"].dropna() <= 0).any() or np.isinf(result["shadow_price"]).any():
        raise ValueError("shadow_price must be positive where available")
    if (result["atr"].dropna() < 0).any() or np.isinf(result["atr"]).any():
        raise ValueError("atr cannot be negative or infinite")
    return result


def _add_shadow_multiple(result: pd.DataFrame, config: AdvancedIndicatorConfig) -> None:
    multiple = result["close"] / result["shadow_price"]
    prior = multiple.shift(1).rolling(config.shadow_lookback, min_periods=config.shadow_lookback)
    result["shadow_multiple"] = multiple
    for quantile, name in ((0.10, "p10"), (0.50, "p50"), (0.90, "p90")):
        result[f"shadow_multiple_{name}"] = prior.quantile(quantile)

    def percentile(window: np.ndarray) -> float:
        history, current = window[:-1], window[-1]
        if not np.isfinite(window).all():
            return np.nan
        return float(
            100 * ((history < current).sum() + 0.5 * (history == current).sum()) / len(history)
        )

    result["shadow_multiple_percentile"] = multiple.rolling(
        config.shadow_lookback + 1, min_periods=config.shadow_lookback + 1
    ).apply(percentile, raw=True)
    result["shadow_multiple_status"] = np.where(
        multiple.isna(), "MISSING_SHADOW",
        np.where(result["shadow_multiple_percentile"].isna(), "WARMUP", "AVAILABLE"),
    )


def _profile_at_bar(
    low: np.ndarray, high: np.ndarray, close: np.ndarray, volume: np.ndarray,
    bins: int, value_area: float,
) -> tuple[float, float, float]:
    floor, ceiling = float(np.min(low)), float(np.max(high))
    if floor == ceiling:
        return floor, ceiling, floor
    edges = np.linspace(floor, ceiling, bins + 1)
    typical = (low + high + close) / 3
    indices = np.clip(np.searchsorted(edges, typical, side="right") - 1, 0, bins - 1)
    weights = np.bincount(indices, weights=volume, minlength=bins)
    poc_bin = int(np.argmax(weights))
    left = right = poc_bin
    included = float(weights[poc_bin])
    target = float(np.sum(weights) * value_area)
    while included < target and (left > 0 or right < bins - 1):
        left_weight = weights[left - 1] if left > 0 else -1
        right_weight = weights[right + 1] if right < bins - 1 else -1
        if left_weight > right_weight:
            left -= 1
            included += float(weights[left])
        else:
            right += 1
            included += float(weights[right])
    return (
        float((edges[poc_bin] + edges[poc_bin + 1]) / 2),
        float(edges[right + 1]), float(edges[left]),
    )


def _add_volume(result: pd.DataFrame, config: AdvancedIndicatorConfig) -> None:
    volume = result["volume"]
    prior = volume.shift(1)
    prior_mean = prior.rolling(config.volume_lookback, min_periods=config.volume_lookback).mean()
    prior_count = prior.notna().rolling(config.volume_lookback, min_periods=1).sum()
    relative = volume / prior_mean.where(prior_mean > 0)
    result["volume_relative"] = relative
    bar_range = result["high"] - result["low"]
    direction = ((result["close"] - result["open"]) / bar_range.where(bar_range > 0)).clip(-1, 1)
    result["volume_directional_participation"] = (direction * (relative / 2).clip(0, 1)).clip(-1, 1)
    sample_count = np.arange(len(result))
    result["volume_participation_status"] = np.select(
        [
            volume.isna(), volume.eq(0), sample_count < config.volume_lookback,
            prior_count < config.volume_lookback, prior_mean.eq(0), bar_range.eq(0),
        ],
        ["MISSING", "ZERO", "WARMUP", "MISSING_HISTORY", "ZERO_REFERENCE", "NO_RANGE"],
        default="AVAILABLE",
    )
    result.loc[
        result["volume_participation_status"] != "AVAILABLE",
        "volume_directional_participation",
    ] = np.nan

    n = len(result)
    poc = np.full(n, np.nan)
    vah = np.full(n, np.nan)
    val = np.full(n, np.nan)
    status = np.full(n, "WARMUP", dtype=object)
    lows = result["low"].to_numpy(dtype=float)
    highs = result["high"].to_numpy(dtype=float)
    closes = result["close"].to_numpy(dtype=float)
    volumes = volume.to_numpy(dtype=float)
    for end in range(config.profile_lookback - 1, n):
        start = end - config.profile_lookback + 1
        window_volume = volumes[start:end + 1]
        if not np.isfinite(window_volume).all():
            status[end] = "MISSING"
        elif window_volume.sum() <= 0:
            status[end] = "ZERO"
        else:
            poc[end], vah[end], val[end] = _profile_at_bar(
                lows[start:end + 1], highs[start:end + 1], closes[start:end + 1],
                window_volume, config.profile_bins, config.profile_value_area,
            )
            status[end] = "AVAILABLE"
    result["volume_profile_poc"] = poc
    result["volume_profile_vah"] = vah
    result["volume_profile_val"] = val
    result["volume_profile_status"] = status


def _add_ssl(result: pd.DataFrame, config: AdvancedIndicatorConfig) -> None:
    baseline = _ema(result["close"], config.ssl_length)
    channel_high = _ema(result["high"], config.ssl_length)
    channel_low = _ema(result["low"], config.ssl_length)
    close = result["close"].to_numpy(dtype=float)
    high = channel_high.to_numpy(dtype=float)
    low = channel_low.to_numpy(dtype=float)
    direction = np.zeros(len(result), dtype=int)
    current = 0
    for index in range(len(result)):
        if np.isfinite(high[index]) and np.isfinite(low[index]):
            if close[index] > high[index]:
                current = 1
            elif close[index] < low[index]:
                current = -1
        direction[index] = current
    ready = channel_high.notna() & channel_low.notna()
    result["ssl_baseline"] = baseline
    result["ssl_channel_high"] = channel_high
    result["ssl_channel_low"] = channel_low
    result["ssl_direction"] = np.where(ready, direction, 0)
    result["ssl_bullish"] = ready & (direction == 1)
    result["ssl_bearish"] = ready & (direction == -1)
    result["ssl_status"] = np.where(ready, "AVAILABLE", "WARMUP")


def _add_impulse(result: pd.DataFrame, config: AdvancedIndicatorConfig) -> None:
    typical = (result["high"] + result["low"] + result["close"]) / 3
    first = _ema(typical, config.impulse_length)
    zlema = first + (first - _ema(first, config.impulse_length))
    smoothed_high = _smma(result["high"], config.impulse_length)
    smoothed_low = _smma(result["low"], config.impulse_length)
    impulse = zlema.where(zlema > smoothed_high, 0.0) - smoothed_high.where(
        zlema > smoothed_high, 0.0
    )
    downside = (zlema - smoothed_low).where(zlema < smoothed_low, 0.0)
    impulse = (impulse + downside).where(
        zlema.notna() & smoothed_high.notna() & smoothed_low.notna()
    )
    signal = impulse.rolling(
        config.impulse_signal_length, min_periods=config.impulse_signal_length
    ).mean()
    denominator = result["atr"].where(result["atr"] > 0)
    result["impulse_macd_atr"] = impulse / denominator
    result["impulse_macd_signal_atr"] = signal / denominator
    result["impulse_macd_hist_atr"] = (impulse - signal) / denominator
    result["impulse_macd_status"] = np.where(
        result["impulse_macd_hist_atr"].notna(), "AVAILABLE",
        np.where(result["atr"].eq(0), "ZERO_ATR", "WARMUP"),
    )


def _add_ribbon(result: pd.DataFrame, config: AdvancedIndicatorConfig) -> None:
    names = []
    for period in config.ribbon_periods:
        name = f"ribbon_ema_{period}"
        result[name] = _ema(result["close"], period)
        names.append(name)
    values = result[names].to_numpy(dtype=float)
    ready = np.isfinite(values).all(axis=1)
    differences = values[:, :-1] - values[:, 1:]
    alignment = np.where(ready, np.sign(differences).mean(axis=1), np.nan)
    result["ribbon_alignment"] = alignment
    result["ribbon_bullish"] = ready & np.all(differences > 0, axis=1)
    result["ribbon_bearish"] = ready & np.all(differences < 0, axis=1)
    result["ribbon_spread_atr"] = (
        (result[names[0]] - result[names[-1]]) / result["atr"].where(result["atr"] > 0)
    )
    result["ribbon_status"] = np.where(ready, "AVAILABLE", "WARMUP")


def _rsi(values: pd.Series, length: int) -> pd.Series:
    delta = values.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    result = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    return result.mask((loss == 0) & (gain > 0), 100).mask((loss == 0) & (gain == 0), 50)


def _add_qqe(result: pd.DataFrame, config: AdvancedIndicatorConfig) -> None:
    names = (
        "experimental_qqe_rsi", "experimental_qqe_long_band", "experimental_qqe_short_band",
        "experimental_qqe_direction", "experimental_qqe_bullish", "experimental_qqe_bearish",
    )
    if not config.qqe_enabled:
        for name in names[:4]:
            result[name] = np.nan
        result[names[4]] = False
        result[names[5]] = False
        result["experimental_qqe_status"] = "DISABLED"
        return
    smoothed = _ema(_rsi(result["close"], config.qqe_rsi_length), config.qqe_smoothing)
    wild_length = 2 * config.qqe_rsi_length - 1
    rsi_range = smoothed.diff().abs().ewm(
        alpha=1 / wild_length, adjust=False, min_periods=wild_length
    ).mean()
    dar = rsi_range.ewm(
        alpha=1 / wild_length, adjust=False, min_periods=wild_length
    ).mean() * config.qqe_factor
    lower = (smoothed - dar).to_numpy(dtype=float)
    upper = (smoothed + dar).to_numpy(dtype=float)
    rsi_values = smoothed.to_numpy(dtype=float)
    long_band = np.full(len(result), np.nan)
    short_band = np.full(len(result), np.nan)
    direction = np.zeros(len(result), dtype=int)
    prior_state = 0
    for index in range(len(result)):
        if not np.isfinite(lower[index]) or not np.isfinite(upper[index]):
            continue
        if index > 0 and np.isfinite(long_band[index - 1]) and np.isfinite(short_band[index - 1]):
            long_band[index] = (
                max(lower[index], long_band[index - 1])
                if rsi_values[index - 1] > long_band[index - 1] else lower[index]
            )
            short_band[index] = (
                min(upper[index], short_band[index - 1])
                if rsi_values[index - 1] < short_band[index - 1] else upper[index]
            )
            if rsi_values[index] > short_band[index - 1]:
                prior_state = 1
            elif rsi_values[index] < long_band[index - 1]:
                prior_state = -1
        else:
            long_band[index], short_band[index] = lower[index], upper[index]
        direction[index] = prior_state
    ready = np.isfinite(long_band) & np.isfinite(short_band)
    result[names[0]] = smoothed
    result[names[1]] = long_band
    result[names[2]] = short_band
    result[names[3]] = np.where(ready, direction, 0)
    result[names[4]] = ready & (direction == 1)
    result[names[5]] = ready & (direction == -1)
    result["experimental_qqe_status"] = np.where(ready, "AVAILABLE", "WARMUP")


def add_advanced_indicators(
    frame: pd.DataFrame, config: AdvancedIndicatorConfig | None = None,
) -> pd.DataFrame:
    """Return a copy with causal advanced features, in the input's row order.

    All historical bands and relative-volume baselines exclude the current bar.
    The current bar contributes to profile, SSL, impulse, and ribbon features;
    consumers must act only after that bar is final.
    """
    config = config or AdvancedIndicatorConfig()
    result = _validate_frame(frame)
    _add_shadow_multiple(result, config)
    _add_volume(result, config)
    _add_ssl(result, config)
    _add_impulse(result, config)
    _add_ribbon(result, config)
    _add_qqe(result, config)
    return result
