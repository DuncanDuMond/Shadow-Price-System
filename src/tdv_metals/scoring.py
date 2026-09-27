"""Bounded 0-100 Shadow Valuation Score components."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _clip(value: pd.Series | float, low: float, high: float) -> pd.Series | float:
    return value.clip(low, high) if isinstance(value, pd.Series) else min(high, max(low, value))


def add_shadow_valuation_score(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach the transparent 40/20/15/10/10/5 SVS decomposition.

    Macro data is deliberately not another hidden score weight. It is an explicit
    confirmation/gate in the decision engine so SVS retains its 0-100 meaning.
    """
    result = frame.copy()
    # -30% gap maps to 40, 0% maps to 20, +30% maps to 0.
    result["score_valuation"] = _clip(20.0 - (200.0 / 3.0) * result["shadow_gap"], 0.0, 40.0)
    # Negative gap z-score = statistically cheap. +/-1.618 maps to 20 / 0.
    result["score_fib_bb"] = _clip(10.0 - (10.0 / 1.618) * result["fib_bb_z"], 0.0, 20.0)
    normalized_momentum = 0.65 * result["fib_macd_hist_atr"] + 0.35 * result["slow_fib_macd_hist_atr"]
    result["score_macd"] = _clip(7.5 + 7.5 * np.tanh(normalized_momentum / 0.5), 0.0, 15.0)
    score_ich = pd.Series(5.0, index=result.index)
    score_ich = score_ich.mask(result["ichimoku_below_cloud"], 2.0)
    score_ich = score_ich.mask(result["ichimoku_above_cloud"], 8.0)
    score_ich = score_ich + result["ichimoku_tk_bullish"].fillna(False).astype(float) * 2.0
    result["score_ichimoku"] = _clip(score_ich, 0.0, 10.0)
    score_wr = pd.Series(5.0, index=result.index)
    # A falling oversold reading is not rewarded; recovery from it is.
    score_wr = score_wr.mask((result["williams_r"] <= -80) & (result["williams_delta"] <= 0), 1.5)
    score_wr = score_wr.mask((result["williams_r"] > -80) & (result["williams_delta"] > 0), 7.0)
    score_wr = score_wr.mask(result["williams_recovering"].fillna(False), 10.0)
    score_wr = score_wr.mask((result["williams_r"] >= -20) & (result["williams_delta"] < 0), 3.0)
    result["score_williams"] = score_wr
    result["score_relative_strength"] = _clip(result["relative_strength_score"].fillna(2.5), 0.0, 5.0)
    components = ["score_valuation", "score_fib_bb", "score_macd", "score_ichimoku", "score_williams", "score_relative_strength"]
    result["svs_complete"] = result[components].notna().all(axis=1)
    result["shadow_valuation_score"] = result[components].sum(axis=1).clip(0, 100)
    return result
