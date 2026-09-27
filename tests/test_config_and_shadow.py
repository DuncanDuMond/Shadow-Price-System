from __future__ import annotations

import unittest

import pandas as pd

from tdv_metals.config import Anchor, ConfigError, settings_from_dict
from tdv_metals.shadow import attach_shadow_price


def raw_config() -> dict:
    anchors = [
        {"id": "verified", "label": "test", "base_date": "2000-01-01", "base_monetary_base": 100.0,
         "base_metal_price": 10.0, "source_url": "https://example.com/source", "validated": True}
    ]
    return {
        "run_mode": "research",
        "data": {"providers": {"p": {"kind": "csv", "path": "unused.csv"}, "m": {"kind": "csv", "path": "unused.csv"}},
                 "instruments": [
                     {"symbol": "GOLD", "provider": "p", "contract_multiplier": 100},
                     {"symbol": "SILVER", "provider": "p", "contract_multiplier": 5000},
                     {"symbol": "COPPER", "provider": "p", "contract_multiplier": 25000},
                 ], "monetary_base_provider": "m"},
        "shadow_model": {"anchors": {"GOLD": anchors, "SILVER": anchors, "COPPER": anchors}},
    }


class ConfigurationAndShadowTests(unittest.TestCase):
    def test_complete_anchor_is_required(self) -> None:
        raw = raw_config()
        raw["shadow_model"]["anchors"]["GOLD"][0]["validated"] = False
        with self.assertRaises(ConfigError):
            settings_from_dict(raw).validate_for_analysis()

    def test_shadow_price_is_anchor_ratio(self) -> None:
        anchor = Anchor("a", "a", "2000-01-01", 100, 10, "https://example.com", True)
        price = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True), "open": [15, 20], "high": [15, 20], "low": [15, 20], "close": [15, 20], "volume": [0, 0]})
        money = pd.DataFrame({"timestamp": pd.to_datetime(["2023-12-31", "2024-01-02"], utc=True), "open": [100, 200], "high": [100, 200], "low": [100, 200], "close": [100, 200], "volume": [0, 0]})
        config = settings_from_dict(raw_config()).shadow_model
        config = type(config)(anchors={"GOLD": (anchor,)}, aggregation="mean")
        actual = attach_shadow_price(price, money, "GOLD", config)
        self.assertEqual(actual["shadow_price"].tolist(), [10.0, 20.0])
        self.assertEqual(actual["shadow_gap"].round(4).tolist(), [0.5, 0.0])
