from __future__ import annotations

import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pandas as pd

from tdv_metals.data import DataError, DataRequest
from tdv_metals.ecosystem import (
    IntegrationUnavailable,
    OpenBBFuturesProvider,
    evidently_drift_report,
    min_cvar_allocation,
    min_variance_allocation,
    validate_ohlcv_integrity,
    validate_ohlcv_pandera,
    vectorbt_threshold_sweep,
)
from tdv_metals.ecosystem._optional import require_module


def bars() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"], utc=True),
        "open": [100.0, 101.0, 102.0],
        "high": [102.0, 103.0, 104.0],
        "low": [99.0, 100.0, 101.0],
        "close": [101.0, 102.0, 103.0],
        "volume": [10.0, 20.0, 30.0],
    })


def returns() -> pd.DataFrame:
    return pd.DataFrame({
        "GOLD": [0.002 * (i % 4 - 1.5) for i in range(24)],
        "SILVER": [0.003 * (i % 5 - 2) for i in range(24)],
        "COPPER": [0.004 * (i % 6 - 2.5) for i in range(24)],
    })


class EcosystemTests(unittest.TestCase):
    def test_integrity_catches_impossible_candle_and_duplicate_timestamp(self) -> None:
        frame = bars()
        frame.loc[0, "high"] = 99.0
        with self.assertRaisesRegex(DataError, "high"):
            validate_ohlcv_integrity(frame)
        frame = bars()
        frame.loc[1, "timestamp"] = frame.loc[0, "timestamp"]
        with self.assertRaisesRegex(DataError, "unique"):
            validate_ohlcv_integrity(frame)

    def test_pandera_schema_is_applied_to_valid_frame(self) -> None:
        calls: list[object] = []
        fake = ModuleType("pandera.pandas")
        fake.Check = SimpleNamespace(gt=lambda value: ("gt", value), ge=lambda value: ("ge", value))
        fake.Column = lambda *args, **kwargs: (args, kwargs)
        fake.errors = SimpleNamespace(SchemaError=ValueError, SchemaErrors=TypeError)

        class Schema:
            def __init__(self, columns, **kwargs):
                calls.append((columns, kwargs))

            def validate(self, frame):
                calls.append("validated")
                return frame

        fake.DataFrameSchema = Schema
        with patch.dict(sys.modules, {"pandera": ModuleType("pandera"), "pandera.pandas": fake}):
            actual = validate_ohlcv_pandera(bars())
        self.assertEqual(len(actual), 3)
        self.assertIn("validated", calls)
        self.assertIn("volume", calls[0][0])

    def test_openbb_futures_query_is_explicit_and_normalized(self) -> None:
        captured = {}
        raw = bars().rename(columns={"timestamp": "date"}).set_index("date")

        def historical(**query):
            captured.update(query)
            return SimpleNamespace(to_df=lambda: raw, warnings=None, provider="yfinance")

        client = SimpleNamespace(derivatives=SimpleNamespace(futures=SimpleNamespace(historical=historical)))
        provider = OpenBBFuturesProvider("yfinance", {"GOLD": "GC=F"}, "2025-12", client=client)
        actual = provider.fetch(DataRequest("GOLD", "2025-01-01", "2025-01-03"))
        self.assertEqual(captured["symbol"], "GC=F")
        self.assertEqual(captured["expiration"], "2025-12")
        self.assertEqual(captured["start_date"], "2025-01-01")
        self.assertEqual(actual["volume"].tolist(), [10.0, 20.0, 30.0])
        self.assertEqual(str(actual["timestamp"].dt.tz), "UTC")

    def test_openbb_does_not_invent_volume(self) -> None:
        raw = bars().drop(columns="volume").rename(columns={"timestamp": "date"})
        response = SimpleNamespace(to_df=lambda: raw, warnings=None, provider="yfinance")
        client = SimpleNamespace(derivatives=SimpleNamespace(
            futures=SimpleNamespace(historical=lambda **kwargs: response)
        ))
        provider = OpenBBFuturesProvider("yfinance", {"GOLD": "GC=F"}, "2025-12", client=client)
        with self.assertRaisesRegex(DataError, "volume"):
            provider.fetch(DataRequest("GOLD"))

    def test_openbb_rejects_nonnumeric_vendor_price(self) -> None:
        raw = bars().rename(columns={"timestamp": "date"})
        raw["close"] = raw["close"].astype(object)
        raw.loc[1, "close"] = "bad"
        response = SimpleNamespace(to_df=lambda: raw, warnings=None, provider="yfinance")
        client = SimpleNamespace(derivatives=SimpleNamespace(
            futures=SimpleNamespace(historical=lambda **kwargs: response)
        ))
        provider = OpenBBFuturesProvider("yfinance", {"GOLD": "GC=F"}, "2025-12", client=client)
        with self.assertRaisesRegex(DataError, "nonnumeric"):
            provider.fetch(DataRequest("GOLD"))

    def test_vectorbt_sweep_shifts_score_to_next_open(self) -> None:
        captured = {}

        class Portfolio:
            def total_return(self):
                return 0.1

            def max_drawdown(self):
                return -0.05

            trades = SimpleNamespace(count=lambda: 2)

        class Factory:
            @staticmethod
            def from_orders(close, **kwargs):
                captured["size"] = kwargs["size"].tolist()
                captured["open"] = kwargs["price"].tolist()
                captured["type"] = kwargs["size_type"]
                return Portfolio()

        fake = ModuleType("vectorbt")
        fake.Portfolio = Factory
        features = bars()
        features["shadow_valuation_score"] = [70, 20, 50]
        with patch.dict(sys.modules, {"vectorbt": fake}):
            result = vectorbt_threshold_sweep(features, (65,), (35,))
        self.assertEqual(captured["size"], [0.0, 1.0, -1.0])
        self.assertEqual(captured["open"], [100.0, 101.0, 102.0])
        self.assertEqual(captured["type"], "targetpercent")
        self.assertEqual(result.iloc[0]["simulation"], "cash_equity_proxy_next_open")
        with self.assertRaisesRegex(ValueError, "futures multiplier"):
            vectorbt_threshold_sweep(features, contract_multiplier=100)

    def test_min_variance_caps_and_scales_without_allocating_inactive_asset(self) -> None:
        captured = {}

        class Frontier:
            def __init__(self, mu, covariance, weight_bounds):
                captured["columns"] = covariance.columns.tolist()
                captured["bounds"] = weight_bounds

            def min_volatility(self):
                return {"GOLD": 0.5, "SILVER": 0.5}

        fake = ModuleType("pypfopt")
        fake.EfficientFrontier = Frontier
        with patch.dict(sys.modules, {"pypfopt": fake}):
            actual = min_variance_allocation(
                returns(), ["GOLD", "SILVER"], max_weight=0.6, gross_budget=0.4
            )
        self.assertEqual(captured["columns"], ["GOLD", "SILVER"])
        self.assertEqual(captured["bounds"], (0.0, 0.6))
        self.assertEqual(actual, {"GOLD": 0.2, "SILVER": 0.2, "COPPER": 0.0})
        with self.assertRaisesRegex(ValueError, "infeasible"):
            min_variance_allocation(returns(), ["GOLD", "SILVER"], max_weight=0.4)

    def test_riskfolio_cvar_path_enforces_cap(self) -> None:
        captured = {}

        class RiskPortfolio:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def assets_stats(self, **kwargs):
                captured["stats"] = kwargs

            def optimization(self, **kwargs):
                captured["optimization"] = kwargs
                return pd.DataFrame({"weights": [0.5, 0.5]}, index=["GOLD", "SILVER"])

        fake = ModuleType("riskfolio")
        fake.Portfolio = RiskPortfolio
        with patch.dict(sys.modules, {"riskfolio": fake}):
            actual = min_cvar_allocation(
                returns(), ["GOLD", "SILVER"], max_weight=0.6, gross_budget=0.4
            )
        self.assertEqual(captured["optimization"]["rm"], "CVaR")
        self.assertEqual(captured["upperlng"], 0.6)
        self.assertEqual(actual["GOLD"], 0.2)

    def test_evidently_uses_current_then_reference(self) -> None:
        captured = {}
        fake = ModuleType("evidently")
        presets = ModuleType("evidently.presets")
        presets.DataDriftPreset = lambda columns: ("drift", columns)

        class Report:
            def __init__(self, metrics):
                captured["metrics"] = metrics

            def run(self, *, current_data, reference_data):
                captured["current"] = current_data.copy()
                captured["reference"] = reference_data.copy()
                return SimpleNamespace(json=lambda: '{"drifted": false}')

        fake.Report = Report
        reference = pd.DataFrame({"close": [1.0, 2.0], "timestamp": ["a", "b"]})
        current = pd.DataFrame({"close": [3.0, 4.0], "timestamp": ["c", "d"]})
        with patch.dict(sys.modules, {"evidently": fake, "evidently.presets": presets}):
            report = evidently_drift_report(reference, current)
        self.assertEqual(report["columns"], ["close"])
        self.assertEqual(captured["metrics"], [("drift", ["close"])])
        self.assertEqual(captured["current"]["close"].tolist(), [3.0, 4.0])
        self.assertEqual(captured["reference"]["close"].tolist(), [1.0, 2.0])

    def test_missing_optional_dependency_gives_install_hint(self) -> None:
        with self.assertRaisesRegex(IntegrationUnavailable, "install-me"):
            require_module("tdv_nonexistent_optional_package_8127", "install-me")


if __name__ == "__main__":
    unittest.main()
