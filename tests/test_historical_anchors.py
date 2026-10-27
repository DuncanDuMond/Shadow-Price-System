from __future__ import annotations

import json
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HistoricalResearchTests(unittest.TestCase):
    def test_six_candidates_stay_unvalidated_with_reproducible_conversions(self) -> None:
        dataset = json.loads((ROOT / "research/historical_anchors.json").read_text())
        sources = json.loads((ROOT / "research/historical_sources.json").read_text())
        known_sources = {row["id"] for row in sources["sources"]}
        self.assertTrue(dataset["research_only"])
        self.assertFalse(dataset["activation_allowed"])
        rows = dataset["candidates"]
        self.assertEqual(len(rows), 6)
        self.assertEqual({(r["symbol"], r["observation_year"]) for r in rows}, {
            (symbol, year) for symbol in ("GOLD", "SILVER", "COPPER") for year in (1913, 1945)
        })
        raw_values = {("GOLD", 1913): 608000, ("GOLD", 1945): 1120000,
                      ("SILVER", 1913): 19600, ("SILVER", 1945): 16700,
                      ("COPPER", 1913): 342, ("COPPER", 1945): 265}
        for row in rows:
            with self.subTest(anchor=row["id"]):
                self.assertFalse(row["validated"])
                self.assertIsNone(row["base_date"])
                self.assertTrue(row["validation_blockers"])
                self.assertTrue(set(row["source_ids"]).issubset(known_sources))
                raw = row["usgs_unit_value"]
                self.assertEqual(raw["nominal_usd_per_metric_ton"],
                                 raw_values[(row["symbol"], row["observation_year"])])
                multiplier = Decimal("0.45359237") / 1000 if row["symbol"] == "COPPER" else (
                    Decimal("31.1034768") / 1000000
                )
                expected = Decimal(str(raw["nominal_usd_per_metric_ton"])) * multiplier
                self.assertEqual(Decimal(raw["converted_price_decimal"]), expected)
                expected_base = 3.417 if row["observation_year"] == 1913 else 41.851
                self.assertEqual(row["base_monetary_base"], expected_base)
                if row["symbol"] == "GOLD":
                    self.assertEqual(row["proposed_metal_price"],
                                     20.67 if row["observation_year"] == 1913 else 35.0)
                    self.assertEqual(row["proposed_price_basis"], "OFFICIAL_GOLD_PARITY")
                else:
                    self.assertAlmostEqual(row["proposed_metal_price"], float(expected))


if __name__ == "__main__":
    unittest.main()
