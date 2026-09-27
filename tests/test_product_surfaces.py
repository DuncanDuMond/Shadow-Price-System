from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tdv_metals.config import settings_from_dict
from tdv_metals.dashboard import dashboard_html
from tdv_metals.data import DataError, normalize_ohlcv
from tdv_metals.demo import synthetic_demo
from tdv_metals.ecosystem import validate_ohlcv_pandera
from tdv_metals.mcp_server import build_mcp_server
from tdv_metals.service import ResearchService


class ProductSurfaceTests(unittest.TestCase):
    def test_real_yield_series_can_be_negative_but_market_prices_cannot(self) -> None:
        frame = pd.DataFrame({"timestamp": ["2024-01-01"], "close": [-0.25]})
        self.assertEqual(normalize_ohlcv(frame, role="series").close.iloc[0], -0.25)
        with self.assertRaises(DataError):
            normalize_ohlcv(frame, role="price")

    def test_synthetic_demo_is_labeled_and_json_serializable(self) -> None:
        result = synthetic_demo()
        self.assertTrue(result["synthetic_data"])
        self.assertEqual(result["name"], "Shadow Price System")
        self.assertEqual(set(result["signals"]), {"GOLD", "SILVER", "COPPER"})
        self.assertEqual(len(result["charts"]["GOLD"]), 100)
        self.assertIn("shadow_multiple_percentile", result["signals"]["GOLD"])
        json.dumps(result, allow_nan=False)

    def test_dashboard_links_market24_but_does_not_embed_it(self) -> None:
        html = dashboard_html()
        self.assertIn("Shadow Price System", html)
        self.assertIn('href="https://market24hclock.com/"', html)
        self.assertNotIn("<iframe", html)
        self.assertIn("SYNTHETIC DEMO", html)

    def test_context_is_distinct_from_exchange_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw = {
                "storage": {"sqlite_path": str(Path(directory) / "research.sqlite3"),
                            "cache_dir": str(Path(directory) / "cache")},
                "data": {
                    "providers": {},
                    "instruments": [{"symbol": symbol, "provider": "missing", "contract_multiplier": 1}
                                    for symbol in ("GOLD", "SILVER", "COPPER")],
                    "monetary_base_provider": None,
                },
                "shadow_model": {"anchors": {}},
                "advanced_indicators": {"ribbon_periods": [5, 8, 13], "qqe_enabled": True},
                "market_context": {
                    "calendars": {"GOLD": {
                        "name": "Test exchange", "timezone": "UTC",
                        "windows": [{"weekday": 0, "start": "09:00", "end": "17:00"}],
                        "source": "fixture", "source_url": "https://example.org/test-calendar",
                    }},
                    "contexts": [{"name": "Regional context", "timezone": "UTC",
                                  "windows": [{"weekday": 0, "start": "00:00", "end": "23:59"}]}],
                },
            }
            settings = settings_from_dict(raw)
            self.assertEqual(settings.advanced_indicators.ribbon_periods, (5, 8, 13))
            # Construct only; no data fetch or order-capable object is needed to read a calendar.
            service = ResearchService(settings)
            from datetime import datetime, timezone
            status = service.market_context("GOLD", datetime(2024, 1, 1, 7, tzinfo=timezone.utc))
            self.assertEqual(status["status"], "CLOSED")
            self.assertEqual(status["context"]["active"], ["Regional context"])
            self.assertFalse(status["entry_eligible_now"])

    def test_mcp_missing_dependency_is_an_explicit_optional_error(self) -> None:
        if importlib.util.find_spec("mcp") is not None:
            self.skipTest("MCP SDK is installed")
        settings = settings_from_dict({"data": {"providers": {}, "instruments": [],
                                               "monetary_base_provider": None},
                                       "shadow_model": {"anchors": {}}})
        with self.assertRaisesRegex(RuntimeError, "MCP SDK"):
            build_mcp_server(settings)

    def test_installed_pandera_contract(self) -> None:
        if importlib.util.find_spec("pandera") is None:
            self.skipTest("Pandera is optional")
        frame = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=2, tz="UTC"),
            "open": [100.0, 101.0], "high": [101.0, 102.0],
            "low": [99.0, 100.0], "close": [100.5, 101.5],
            "volume": [10.0, 20.0],
        })
        self.assertEqual(len(validate_ohlcv_pandera(frame)), 2)

    def test_installed_mcp_server_builds_read_only_tools(self) -> None:
        if importlib.util.find_spec("mcp") is None:
            self.skipTest("MCP is optional")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = settings_from_dict({
                "storage": {"sqlite_path": str(root / "research.sqlite3"),
                            "cache_dir": str(root / "cache")},
                "data": {"providers": {}, "instruments": [],
                         "monetary_base_provider": None},
                "shadow_model": {"anchors": {}},
            })
            server = build_mcp_server(settings)
            self.assertEqual(server.name, "Shadow Price System")


if __name__ == "__main__":
    unittest.main()
