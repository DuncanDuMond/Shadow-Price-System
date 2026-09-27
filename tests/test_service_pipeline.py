from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from tdv_metals.config import settings_from_dict
from tdv_metals.service import ResearchService


class ServicePipelineTests(unittest.TestCase):
    def test_local_provider_to_persisted_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            timestamps = pd.date_range("2023-01-01", periods=130, freq="D", tz="UTC")
            close = 100 + np.sin(np.arange(130) / 4)
            base = pd.DataFrame({"timestamp": timestamps, "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1})
            for symbol, multiplier in (("gold", 1.0), ("silver", 0.9), ("copper", 1.1)):
                prices = base.copy()
                prices["close"] *= multiplier
                prices["open"] *= multiplier
                prices["high"] *= multiplier
                prices["low"] *= multiplier
                prices.to_csv(root / f"{symbol}.csv", index=False)
            pd.DataFrame({"timestamp": timestamps, "close": np.repeat(100.0, len(timestamps))}).to_csv(root / "money.csv", index=False)
            pd.DataFrame({"timestamp": timestamps, "close": 110 - np.arange(130) * 0.01}).to_csv(root / "dxy.csv", index=False)
            pd.DataFrame({"timestamp": timestamps, "close": 2 - np.arange(130) * 0.001}).to_csv(root / "yield.csv", index=False)
            providers = {name: {"kind": "csv", "path": str(root / file)} for name, file in {
                "gold": "gold.csv", "silver": "silver.csv", "copper": "copper.csv", "money": "money.csv", "dxy": "dxy.csv", "yield": "yield.csv",
            }.items()}
            anchor = {"id": "verified", "label": "test", "base_date": "2000-01-01", "base_monetary_base": 100,
                      "base_metal_price": 125, "source_url": "https://example.com/test", "validated": True}
            raw = {
                "storage": {"sqlite_path": str(root / "research.sqlite3"), "cache_dir": str(root / "cache")},
                "data": {"providers": providers, "instruments": [
                    {"symbol": "GOLD", "provider": "gold", "contract_multiplier": 1},
                    {"symbol": "SILVER", "provider": "silver", "contract_multiplier": 1},
                    {"symbol": "COPPER", "provider": "copper", "contract_multiplier": 1},
                ], "monetary_base_provider": "money", "macro": {"dxy_provider": "dxy", "real_yield_provider": "yield"}},
                "shadow_model": {"anchors": {"GOLD": [anchor], "SILVER": [anchor], "COPPER": [anchor]}},
            }
            service = ResearchService(settings_from_dict(raw))
            snapshot = service.refresh()
            self.assertEqual(len(snapshot.decisions), 3)
            self.assertEqual(snapshot.frames["GOLD"].iloc[-1]["macro_status"], "AVAILABLE")
            self.assertEqual(snapshot.frames["GOLD"].iloc[-1]["shadow_multiple_status"], "AVAILABLE")
            self.assertEqual(snapshot.frames["GOLD"].iloc[-1]["volume_profile_status"], "AVAILABLE")
            self.assertIn("score_components", snapshot.evidence["GOLD"])
            self.assertEqual(service.market_context("GOLD")["status"], "UNKNOWN")
            persisted = service.latest_response()
            self.assertIsNotNone(persisted)
            self.assertEqual(set(persisted["signals"]), {"GOLD", "SILVER", "COPPER"})
            self.assertEqual(persisted["name"], "Shadow Price System")
            self.assertEqual(len(persisted["charts"]["GOLD"]), 90)
            backtest = service.backtest("GOLD")
            self.assertIn("total_return_pct", backtest.metrics)
            raw["run_mode"] = "paper"
            raw["strategy"] = {"long_score": 36, "entry_gap": 0, "confirmation_count": 0,
                               "risk_fraction": 0.01}
            paper = ResearchService(settings_from_dict(raw)).refresh()
            self.assertEqual(paper.decisions["GOLD"].action.value, "ABSTAIN")
            self.assertEqual(paper.decisions["GOLD"].conviction, "PAPER_GUARD")
