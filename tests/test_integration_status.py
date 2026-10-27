from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from importlib import import_module
from io import StringIO
from unittest.mock import patch

from tdv_metals.cli import main


class IntegrationStatusTests(unittest.TestCase):
    def test_status_reports_optional_bridges_without_importing_vendors(self) -> None:
        module = import_module("tdv_metals.ecosystem.status")
        with patch.object(module.metadata, "version", return_value="test-version"):
            result = module.integration_status()
        rows = {row["name"]: row for row in result["integrations"]}
        self.assertEqual(set(rows), {"Riskfolio-Lib", "OpenBB", "NautilusTrader", "Qlib"})
        self.assertEqual(rows["Qlib"]["status"], "DEFERRED")
        self.assertFalse(rows["Qlib"]["enabled"])
        self.assertEqual(rows["NautilusTrader"]["capability"], "offline_bar_conversion")
        self.assertTrue(result["research_only"])
        self.assertFalse(result["broker_execution"])
        self.assertFalse(result["live_provider_verified"])

    def test_integrations_cli_does_not_require_analysis_configuration(self) -> None:
        with redirect_stdout(StringIO()) as output:
            result = main(["--config", "does-not-exist.json", "integrations"])
        self.assertEqual(result, 0)
        self.assertFalse(json.loads(output.getvalue())["broker_execution"])


if __name__ == "__main__":
    unittest.main()
