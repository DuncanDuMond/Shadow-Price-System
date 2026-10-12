from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

if importlib.util.find_spec("fastapi") and importlib.util.find_spec("httpx"):
    from fastapi.testclient import TestClient

    from tdv_metals.api import create_app
else:
    TestClient = None


@unittest.skipUnless(TestClient is not None, "FastAPI and httpx are optional in the bundled test runtime")
class WebApiTests(unittest.TestCase):
    def test_demo_capabilities_market_context_and_fail_closed_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = {
                "storage": {"sqlite_path": str(root / "research.sqlite3"),
                            "cache_dir": str(root / "cache")},
                "data": {"providers": {}, "instruments": [
                    {"symbol": symbol, "provider": "missing", "contract_multiplier": 1}
                    for symbol in ("GOLD", "SILVER", "COPPER")
                ], "monetary_base_provider": None},
                "shadow_model": {"anchors": {}},
            }
            config = root / "config.json"
            config.write_text(json.dumps(raw), encoding="utf-8")
            with TestClient(create_app(config)) as client:
                self.assertEqual(client.get("/").status_code, 200)
                self.assertEqual(client.get("/health").json()["status"], "configuration_error")
                capabilities = client.get("/api/capabilities").json()
                self.assertFalse(capabilities["broker_execution"])
                chart_config = client.get("/api/chart-config").json()
                self.assertTrue(chart_config["requires_user_action"])
                self.assertEqual(chart_config["symbols"]["GOLD"], "COMEX:GC1!")
                self.assertIn("not a model data source", chart_config["purpose"])
                demo = client.get("/api/demo").json()
                self.assertTrue(demo["synthetic_data"])
                self.assertEqual(len(demo["ranking"]), 3)
                context = client.get("/api/market-context/GOLD").json()
                self.assertEqual(context["status"], "UNKNOWN")
                self.assertFalse(context["entry_eligible_now"])
                self.assertEqual(client.post("/api/refresh").status_code, 400)

    def test_configured_refresh_evidence_and_backtest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            timestamps = pd.date_range("2023-01-02", periods=150, freq="B", tz="UTC")
            close = 100 + np.arange(150) * 0.03 + np.sin(np.arange(150) / 5)
            prices = pd.DataFrame({"timestamp": timestamps, "open": close,
                                   "high": close + 1, "low": close - 1,
                                   "close": close, "volume": 1000 + np.arange(150)})
            providers = {}
            instruments = []
            anchors = {}
            for symbol in ("GOLD", "SILVER", "COPPER"):
                path = root / (symbol.lower() + ".csv")
                prices.to_csv(path, index=False)
                providers[symbol] = {"kind": "csv", "path": str(path)}
                instruments.append({"symbol": symbol, "provider": symbol, "contract_multiplier": 1})
                anchors[symbol] = [{"id": "test", "base_date": "2000-01-01",
                                    "base_monetary_base": 100, "base_metal_price": 125,
                                    "source_url": "https://example.com/test", "validated": True}]
            money = root / "money.csv"
            pd.DataFrame({"timestamp": timestamps, "close": 100}).to_csv(money, index=False)
            providers["money"] = {"kind": "csv", "path": str(money)}
            config = root / "config.json"
            config.write_text(json.dumps({
                "storage": {"sqlite_path": str(root / "research.sqlite3"),
                            "cache_dir": str(root / "cache")},
                "data": {"providers": providers, "instruments": instruments,
                         "monetary_base_provider": "money"},
                "shadow_model": {"anchors": anchors},
            }), encoding="utf-8")
            with TestClient(create_app(config)) as client:
                snapshot = client.post("/api/refresh").json()
                self.assertEqual(snapshot["name"], "Shadow Price System")
                self.assertEqual(len(snapshot["ranking"]), 3)
                self.assertIn("shadow_multiple_percentile",
                              client.get("/api/evidence/GOLD").json()["features"])
                backtest = client.post("/api/backtests/GOLD").json()
                self.assertIn("trade_count", backtest["metrics"])
                paths = {route.path for route in client.app.routes}
                self.assertFalse(any("order" in path or "broker" in path for path in paths))


if __name__ == "__main__":
    unittest.main()
