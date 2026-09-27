from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tdv_metals.advanced_indicators import AdvancedIndicatorConfig, add_advanced_indicators


def market_frame(rows: int = 100, scale: float = 1.0) -> pd.DataFrame:
    time = pd.date_range("2024-01-01", periods=rows, freq="D", tz="UTC")
    close = scale * (100 + 0.35 * np.arange(rows) + 3 * np.sin(np.arange(rows) / 5))
    return pd.DataFrame({
        "timestamp": time,
        "open": close - 0.4 * scale,
        "high": close + 1.5 * scale,
        "low": close - 1.5 * scale,
        "close": close,
        "volume": 100 + (np.arange(rows) % 7) * 10,
        "shadow_price": np.full(rows, 105 * scale),
        "shadow_gap": close / (105 * scale) - 1,
        "atr": np.full(rows, 3 * scale),
    })


def short_config(**overrides: object) -> AdvancedIndicatorConfig:
    settings = {
        "shadow_lookback": 5,
        "volume_lookback": 4,
        "profile_lookback": 6,
        "profile_bins": 8,
        "ssl_length": 5,
        "impulse_length": 5,
        "impulse_signal_length": 3,
        "ribbon_periods": (3, 5, 8),
        "qqe_rsi_length": 3,
        "qqe_smoothing": 3,
    }
    settings.update(overrides)
    return AdvancedIndicatorConfig(**settings)


class AdvancedIndicatorTests(unittest.TestCase):
    def test_shadow_multiple_uses_only_prior_history_for_bands(self) -> None:
        frame = market_frame(12)
        frame["close"] = [100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210]
        frame["open"] = frame["close"]
        frame["high"] = frame["close"] + 1
        frame["low"] = frame["close"] - 1
        frame["shadow_price"] = 100.0
        result = add_advanced_indicators(frame, short_config())
        self.assertTrue(result["shadow_multiple_percentile"].iloc[:5].isna().all())
        self.assertAlmostEqual(result["shadow_multiple"].iloc[5], 1.5)
        self.assertAlmostEqual(result["shadow_multiple_p50"].iloc[5], 1.2)
        self.assertAlmostEqual(result["shadow_multiple_p10"].iloc[5], 1.04)
        self.assertAlmostEqual(result["shadow_multiple_p90"].iloc[5], 1.36)
        self.assertEqual(result["shadow_multiple_percentile"].iloc[5], 100)

    def test_appended_future_cannot_change_past_features(self) -> None:
        frame = market_frame()
        frame.loc[80:, "close"] *= 3
        frame.loc[80:, "open"] = frame.loc[80:, "close"] - 0.4
        frame.loc[80:, "high"] = frame.loc[80:, "close"] + 1.5
        frame.loc[80:, "low"] = frame.loc[80:, "close"] - 1.5
        whole = add_advanced_indicators(frame, short_config())
        prefix = add_advanced_indicators(frame.iloc[:70], short_config())
        for name in (
            "shadow_multiple_percentile", "shadow_multiple_p90", "volume_profile_poc",
            "volume_relative", "ssl_direction", "impulse_macd_atr", "ribbon_alignment",
        ):
            np.testing.assert_allclose(whole[name].iloc[:70], prefix[name], equal_nan=True)

    def test_volume_unavailable_and_zero_are_explicit(self) -> None:
        zero = market_frame(20)
        zero["volume"] = 0.0
        result = add_advanced_indicators(zero, short_config())
        self.assertEqual(result["volume_participation_status"].iloc[-1], "ZERO")
        self.assertEqual(result["volume_profile_status"].iloc[-1], "ZERO")
        self.assertTrue(np.isnan(result["volume_profile_poc"].iloc[-1]))

        missing = market_frame(20)
        missing.loc[10, "volume"] = np.nan
        result = add_advanced_indicators(missing, short_config())
        self.assertEqual(result["volume_participation_status"].iloc[10], "MISSING")
        self.assertEqual(result["volume_profile_status"].iloc[10], "MISSING")
        self.assertEqual(result["volume_profile_status"].iloc[15], "MISSING")
        self.assertEqual(result["volume_profile_status"].iloc[16], "AVAILABLE")

    def test_profile_value_area_and_bounded_fields(self) -> None:
        result = add_advanced_indicators(market_frame(), short_config())
        valid = result[result["volume_profile_status"] == "AVAILABLE"]
        self.assertTrue((valid["volume_profile_val"] <= valid["volume_profile_poc"]).all())
        self.assertTrue((valid["volume_profile_poc"] <= valid["volume_profile_vah"]).all())
        self.assertTrue(result["shadow_multiple_percentile"].dropna().between(0, 100).all())
        self.assertTrue(result["volume_directional_participation"].dropna().between(-1, 1).all())
        self.assertTrue(result["ribbon_alignment"].dropna().between(-1, 1).all())
        self.assertFalse((result["ssl_bullish"] & result["ssl_bearish"]).any())
        self.assertFalse((result["ribbon_bullish"] & result["ribbon_bearish"]).any())

    def test_price_scale_does_not_change_normalized_features(self) -> None:
        first = add_advanced_indicators(market_frame(scale=1), short_config())
        second = add_advanced_indicators(market_frame(scale=10), short_config())
        for name in (
            "shadow_multiple", "shadow_multiple_percentile", "volume_relative",
            "impulse_macd_atr", "impulse_macd_hist_atr", "ribbon_spread_atr",
        ):
            np.testing.assert_allclose(
                first[name], second[name], equal_nan=True, rtol=1e-9, atol=1e-9
            )

    def test_qqe_is_disabled_by_default_and_does_not_change_core_features(self) -> None:
        frame = market_frame()
        off = add_advanced_indicators(frame, short_config())
        on = add_advanced_indicators(frame, short_config(qqe_enabled=True))
        self.assertTrue((off["experimental_qqe_status"] == "DISABLED").all())
        self.assertTrue(off["experimental_qqe_rsi"].isna().all())
        self.assertEqual(on["experimental_qqe_status"].iloc[-1], "AVAILABLE")
        np.testing.assert_allclose(off["shadow_multiple"], on["shadow_multiple"])
        np.testing.assert_allclose(off["impulse_macd_atr"], on["impulse_macd_atr"], equal_nan=True)

    def test_invalid_config_and_bad_time_order_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            short_config(ribbon_periods=(8, 5, 3))
        with self.assertRaises(ValueError):
            short_config(profile_value_area=1.0)
        frame = market_frame(10).iloc[::-1]
        with self.assertRaisesRegex(ValueError, "timestamps"):
            add_advanced_indicators(frame, short_config())


if __name__ == "__main__":
    unittest.main()
