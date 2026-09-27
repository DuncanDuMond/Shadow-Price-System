"""Reproducible synthetic walkthrough; none of these values is historical market data."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .advanced_indicators import AdvancedIndicatorConfig, add_advanced_indicators
from .config import IndicatorConfig, MacroConfig, StrategyConfig
from .decision import decide
from .indicators import add_indicators, add_macro_confirmation, add_relative_strength
from .scoring import add_shadow_valuation_score


def synthetic_demo() -> dict[str, object]:
    """Run the calculation pipeline on labelled, deterministic synthetic observations."""
    days = 260
    timestamps = pd.date_range("2024-01-01", periods=days, freq="B", tz="UTC")
    index = np.arange(days, dtype=float)
    frames: dict[str, pd.DataFrame] = {}
    choices = {"GOLD": (2000.0, 100.0), "SILVER": (25.0, 5000.0), "COPPER": (4.0, 25000.0)}
    for rank, (symbol, (base, _)) in enumerate(choices.items()):
        wave = 0.05 * np.sin(index / (11.0 + rank * 3.0))
        close = base * (1 + index * 0.0003 + wave + 0.01 * np.sin(index / 2.5 + rank))
        shadow = base * (1.14 + index * 0.00025 + 0.01 * np.cos(index / 25))
        spread = np.maximum(base * 0.008, close * 0.006)
        frame = pd.DataFrame({
            "timestamp": timestamps, "open": close - spread * 0.1,
            "high": close + spread, "low": close - spread,
            "close": close, "volume": 1000 + 200 * (1 + np.sin(index / 6 + rank)),
            "shadow_price": shadow, "monetary_base": np.nan,
            "shadow_gap": close / shadow - 1,
        })
        frames[symbol] = add_advanced_indicators(add_indicators(frame, IndicatorConfig()), AdvancedIndicatorConfig())
    frames = add_relative_strength(frames, 34)
    dxy = pd.DataFrame({"timestamp": timestamps, "close": 105 - index * 0.008})
    real_yield = pd.DataFrame({"timestamp": timestamps, "close": 2.1 - index * 0.002})
    signals: dict[str, object] = {}
    ranking: list[dict[str, object]] = []
    charts: dict[str, list[dict[str, object]]] = {}
    for symbol, (_, multiplier) in choices.items():
        frame = add_shadow_valuation_score(add_macro_confirmation(frames[symbol], dxy, real_yield, MacroConfig()))
        latest = frame.iloc[-1]
        decision = decide(symbol, latest, StrategyConfig(), MacroConfig(), multiplier)
        signals[symbol] = decision.as_dict()
        ranking.append({"symbol": symbol, "score": decision.score, "action": decision.action.value})
        charts[symbol] = [
            {
                "timestamp": item.timestamp.isoformat(), "price": round(float(item.close), 4),
                "shadow": round(float(item.shadow_price), 4),
                "score": round(float(item.shadow_valuation_score), 2),
            }
            for item in frame.iloc[-100:].itertuples()
        ]
        signals[symbol]["shadow_multiple_percentile"] = float(latest["shadow_multiple_percentile"])
        signals[symbol]["volume_participation_status"] = str(latest["volume_participation_status"])
    ranking.sort(key=lambda item: float(item["score"] or 0), reverse=True)
    return {
        "name": "Shadow Price System", "mode": "demo", "synthetic_data": True,
        "warning": "Every price, volume, monetary benchmark, and signal on this page is synthetic demonstration data.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ranking": ranking, "signals": signals, "charts": charts,
    }
