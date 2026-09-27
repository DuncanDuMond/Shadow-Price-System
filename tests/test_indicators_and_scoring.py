from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tdv_metals.config import IndicatorConfig
from tdv_metals.indicators import add_indicators, fibonacci_macd, ichimoku
from tdv_metals.scoring import add_shadow_valuation_score


def market_frame(scale: float = 1.0, rows: int = 130) -> pd.DataFrame:
    timestamps = pd.date_range("2023-01-01", periods=rows, freq="D", tz="UTC")
    close = scale * (100 + np.linspace(0, 20, rows) + np.sin(np.arange(rows) / 4))
    return pd.DataFrame({"timestamp": timestamps, "open": close, "high": close + scale, "low": close - scale, "close": close, "volume": 1000, "shadow_gap": np.linspace(-0.2, 0.1, rows)})


class IndicatorAndScoringTests(unittest.TestCase):
    def test_macd_is_normalized_for_price_scale(self) -> None:
        first = market_frame(1)
        second = market_frame(10)
        first_result = fibonacci_macd(first.close, first.high - first.low)
        second_result = fibonacci_macd(second.close, second.high - second.low)
        np.testing.assert_allclose(first_result.fib_macd_atr.dropna(), second_result.fib_macd_atr.dropna(), rtol=1e-10)

    def test_ichimoku_cloud_uses_leading_shift(self) -> None:
        result = ichimoku(market_frame())
        self.assertTrue(result.ichimoku_span_a.iloc[:51].isna().all())
        self.assertTrue(pd.notna(result.ichimoku_span_a.iloc[51]))
        self.assertTrue(result.ichimoku_span_b.iloc[:77].isna().all())
        self.assertTrue(pd.notna(result.ichimoku_span_b.iloc[77]))

    def test_williams_recovery_scores_higher_than_falling_oversold(self) -> None:
        base = pd.DataFrame({
            "shadow_gap": [-0.1, -0.1], "fib_bb_z": [0.0, 0.0], "fib_macd_hist_atr": [0.0, 0.0],
            "slow_fib_macd_hist_atr": [0.0, 0.0], "ichimoku_below_cloud": [False, False],
            "ichimoku_above_cloud": [False, False], "ichimoku_tk_bullish": [False, False],
            "williams_r": [-85.0, -85.0], "williams_delta": [2.0, -2.0],
            "williams_recovering": [True, False], "relative_strength_score": [2.5, 2.5],
        })
        scored = add_shadow_valuation_score(base)
        self.assertEqual(scored.score_williams.tolist(), [10.0, 1.5])

    def test_full_indicator_pipeline_has_canonical_columns(self) -> None:
        output = add_indicators(market_frame(), IndicatorConfig())
        self.assertIn("slow_fib_macd_hist_atr", output)
        self.assertIn("ichimoku_span_b", output)
        self.assertIn("williams_recovering", output)
