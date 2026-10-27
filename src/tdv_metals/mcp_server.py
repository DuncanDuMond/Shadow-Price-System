"""Optional, read-only Model Context Protocol surface for agent hosts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import StrictFloat

from .config import Settings, load_settings
from .demo import synthetic_demo
from .service import ResearchService
from .shadow import ShadowModelError, calculate_shadow_benchmark


def build_mcp_server(settings: Settings) -> Any:
    """Build tools that cannot fetch data, write backtests, or execute orders."""
    try:
        from mcp.server import MCPServer
        from mcp.server.mcpserver.exceptions import ToolError
        from mcp.types import ToolAnnotations
    except ImportError as exc:
        raise RuntimeError("MCP SDK v2 is unavailable. Install: pip install -e '.[agent]'") from exc

    service = ResearchService(settings)
    server = MCPServer("Shadow Price System")
    readonly = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

    @server.tool(annotations=readonly)
    def integration_status() -> dict[str, Any]:
        """Inspect optional local packages; no SDK imports, provider fetches or orders."""
        from .ecosystem.status import integration_status as inspect_integrations
        return inspect_integrations()

    @server.tool(annotations=readonly)
    def calculate_shadow_price(
        symbol: str,
        current_monetary_base: StrictFloat,
        anchors: list[dict[str, Any]],
        monetary_base_unit: str,
        metal_price_unit: str,
        current_source_url: str,
        current_as_of: str,
        market_price: StrictFloat | None = None,
        aggregation: str = "mean",
    ) -> dict[str, Any]:
        """Calculate a TDV-style benchmark from supplied inputs; no live-data claim.

        Use GOLD, SILVER or COPPER. Each anchor requires id, label, base_date
        (ISO date), positive base_monetary_base and base_metal_price, source_url,
        and validated=true. All bases must share monetary_base_unit and prices
        must share metal_price_unit. current_as_of is an ISO date. The caller
        must verify sources and unit compatibility; this tool does not do that.
        """
        try:
            return calculate_shadow_benchmark(
                symbol, current_monetary_base, anchors, monetary_base_unit,
                metal_price_unit, current_source_url, current_as_of, market_price, aggregation,
            )
        except ShadowModelError as exc:
            raise ToolError(str(exc)) from exc

    @server.tool(annotations=readonly)
    def latest_research() -> dict[str, Any]:
        """Get the most recently persisted gold/silver/copper research snapshot, if any."""
        return service.latest_response() or {"status": "NO_SNAPSHOT", "broker_execution": False}

    @server.tool(annotations=readonly)
    def signal_evidence(symbol: str) -> dict[str, Any]:
        """Get provenance, score components and advanced feature states for one metal."""
        symbol = symbol.upper()
        if symbol not in {"GOLD", "SILVER", "COPPER"}:
            raise ValueError("symbol must be GOLD, SILVER, or COPPER")
        return service.signal_evidence(symbol) or {"symbol": symbol, "status": "NO_SNAPSHOT"}

    @server.tool(annotations=readonly)
    def market_context(symbol: str) -> dict[str, Any]:
        """Get verified exchange schedule state and indicative regional session context."""
        return service.market_context(symbol)

    @server.tool(annotations=readonly)
    def synthetic_walkthrough() -> dict[str, Any]:
        """Get a clearly labeled synthetic demonstration; never treat it as market data."""
        return synthetic_demo()

    return server


def run_stdio(config_path: str | Path) -> None:
    """Start a local stdio MCP server; no public listener or broker connection."""
    build_mcp_server(load_settings(config_path)).run("stdio")
