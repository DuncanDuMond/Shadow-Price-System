from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path

from tdv_metals import shadow
from tdv_metals.config import settings_from_dict
from tdv_metals.mcp_server import build_mcp_server


class AgentCalculatorTests(unittest.TestCase):
    def test_ratio_underflow_is_rejected_instead_of_returning_zero(self) -> None:
        args = self.inputs()
        args["current_monetary_base"] = 1.0
        args["anchors"][0].update(base_monetary_base=1.0, base_metal_price=1e308)
        args["market_price"] = 1e-308
        with self.assertRaisesRegex(ValueError, "underflow"):
            shadow.calculate_shadow_benchmark(**args)

    def test_historical_provenance_requires_a_hostname(self) -> None:
        for source in ("https://", "http:///no-host"):
            with self.subTest(source=source):
                args = self.inputs()
                args["anchors"][0]["source_url"] = source
                with self.assertRaisesRegex(ValueError, "source_url"):
                    shadow.calculate_shadow_benchmark(**args)

    def inputs(self) -> dict:
        return {
            "symbol": "GOLD", "current_monetary_base": 200.0,
            "anchors": [{"id": "a", "label": "Test fixture", "base_date": "2000-01-01",
                         "base_monetary_base": 100.0, "base_metal_price": 10.0,
                         "source_url": "https://example.com/fixture", "validated": True}],
            "monetary_base_unit": "USD billions", "metal_price_unit": "USD per troy ounce",
            "current_source_url": "https://example.com/fixture", "current_as_of": "2024-01-01",
        }

    def test_invalid_or_unattested_inputs_fail_closed(self) -> None:
        for key, value in (
            ("symbol", "PLATINUM"), ("aggregation", "invalid"), ("anchors", []),
            ("current_monetary_base", 0), ("current_monetary_base", -1),
            ("current_monetary_base", float("nan")),
            ("current_monetary_base", float("inf")), ("current_monetary_base", True),
            ("market_price", -1), ("market_price", float("inf")),
            ("monetary_base_unit", ""), ("metal_price_unit", "  "),
            ("current_source_url", "file:///local"), ("current_as_of", "not-a-date"),
        ):
            with self.subTest(key=key, value=value):
                args = self.inputs()
                args[key] = value
                with self.assertRaises(ValueError):
                    shadow.calculate_shadow_benchmark(**args)
        for key, value in (
            ("validated", False), ("validated", "false"), ("base_date", "bad-date"),
            ("base_monetary_base", 0), ("base_metal_price", float("nan")),
        ):
            with self.subTest(anchor_key=key, value=value):
                args = self.inputs()
                args["anchors"][0][key] = value
                with self.assertRaises(ValueError):
                    shadow.calculate_shadow_benchmark(**args)
        args = self.inputs()
        args["anchors"].append(deepcopy(args["anchors"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            shadow.calculate_shadow_benchmark(**args)
        args = self.inputs()
        args["current_monetary_base"] = 1e308
        with self.assertRaises(ValueError):
            shadow.calculate_shadow_benchmark(**args)

    def test_supplied_inputs_use_existing_anchor_formula_for_each_metal(self) -> None:
        self.assertTrue(
            hasattr(shadow, "calculate_shadow_benchmark"),
            "Agent hosts need a stateless shadow benchmark calculator",
        )
        for symbol in ("GOLD", "SILVER", "COPPER"):
            with self.subTest(symbol=symbol):
                result = shadow.calculate_shadow_benchmark(
                    symbol=symbol,
                    current_monetary_base=200.0,
                    anchors=[{
                        "id": "fixture", "label": "Synthetic test anchor",
                        "base_date": "2000-01-01", "base_monetary_base": 100.0,
                        "base_metal_price": 10.0,
                        "source_url": "https://example.com/test-fixture", "validated": True,
                    }],
                    monetary_base_unit="USD billions",
                    metal_price_unit="USD per troy ounce" if symbol != "COPPER" else "USD per pound",
                    current_source_url="https://example.com/test-fixture",
                    current_as_of="2024-01-01",
                    market_price=15.0,
                )
                self.assertEqual(result["shadow_price"], 20.0)
                self.assertEqual(result["shadow_gap"], -0.25)
                self.assertEqual(result["shadow_multiple"], 0.75)
                self.assertEqual(result["input_status"], "USER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED")
                self.assertTrue(result["research_only"])
                self.assertFalse(result["broker_execution"])


@unittest.skipUnless(importlib.util.find_spec("mcp"), "MCP is optional")
class AgentMCPTests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def client(self):
        from mcp.client import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(json.dumps({
                "storage": {"sqlite_path": str(root / "research.sqlite3"),
                            "cache_dir": str(root / "cache")},
                "data": {"providers": {}, "instruments": [], "monetary_base_provider": None},
                "shadow_model": {"anchors": {}},
            }), encoding="utf-8")
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "tdv_metals.cli", "--config", str(config), "mcp-serve"],
            )
            async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
                await client.initialize()
                yield client

    async def test_stdio_rejects_boolean_numeric_inputs(self) -> None:
        async with self.client() as client:
            for name in ("current_monetary_base", "market_price"):
                with self.subTest(field=name):
                    args = AgentCalculatorTests().inputs()
                    args[name] = True
                    result = await client.call_tool("calculate_shadow_price", args)
                    self.assertTrue(result.is_error, "Booleans must not become financial numbers")

    async def test_stdio_validation_errors_explain_the_invalid_input(self) -> None:
        async with self.client() as client:
            for field, value, message in (
                ("current_monetary_base", 0, "current_monetary_base"),
                ("current_as_of", "not-a-date", "provenance"),
                ("current_source_url", "https://", "current_source_url"),
            ):
                with self.subTest(field=field):
                    args = AgentCalculatorTests().inputs()
                    args[field] = value
                    result = await client.call_tool("calculate_shadow_price", args)
                    self.assertTrue(result.is_error)
                    text = " ".join(item.text for item in result.content if item.type == "text")
                    self.assertIn(message, text)

    async def test_calculator_is_available_as_a_read_only_mcp_tool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = settings_from_dict({
                "storage": {"sqlite_path": str(Path(directory) / "research.sqlite3"),
                            "cache_dir": str(Path(directory) / "cache")},
                "data": {"providers": {}, "instruments": [], "monetary_base_provider": None},
                "shadow_model": {"anchors": {}},
            })
            server = build_mcp_server(settings)
            tools = {tool.name: tool for tool in await server.list_tools()}
            self.assertIn("calculate_shadow_price", tools)
            self.assertTrue(tools["calculate_shadow_price"].annotations.read_only_hint)
            args = AgentCalculatorTests().inputs()
            result = await server.call_tool("calculate_shadow_price", args)
            self.assertFalse(result.is_error)
            self.assertEqual(result.structured_content["shadow_price"], 20.0)


if __name__ == "__main__":
    unittest.main()
