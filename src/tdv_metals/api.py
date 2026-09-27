"""FastAPI façade for an AI agent or browser. No endpoints can execute orders."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ConfigError, load_settings
from .dashboard import dashboard_html
from .data import DataError
from .demo import synthetic_demo
from .service import ResearchService


def create_app(config_path: str | Path = "config.json") -> Any:
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse
    except ImportError as exc:
        raise RuntimeError("FastAPI is not installed. Run: pip install -e .") from exc
    settings = load_settings(config_path)
    service = ResearchService(settings)
    app = FastAPI(
        title="Shadow Price System API", version="2.1.0",
        description="Explainable metals research and paper signals only. No broker order execution.",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return dashboard_html()

    @app.get("/health")
    def health() -> dict[str, object]:
        try:
            settings.validate_for_analysis()
            return {"status": "ok", "name": "Shadow Price System", "mode": settings.run_mode,
                    "execution": "disabled", "version": "2.1.0"}
        except ConfigError as exc:
            return {"status": "configuration_error", "name": "Shadow Price System",
                    "detail": str(exc), "execution": "disabled", "version": "2.1.0"}

    @app.get("/api/status")
    def status() -> dict[str, object]:
        return {
            "name": "Shadow Price System", "mode": settings.run_mode,
            "execution": "disabled", "configured_symbols": [item.symbol for item in settings.data.instruments],
            "has_in_memory_snapshot": service.snapshot is not None, "latest_snapshot": service.latest_response(),
        }

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, object]:
        return {
            "name": "Shadow Price System", "version": "2.1.0", "modes": ["research", "paper"],
            "broker_execution": False, "read_only_agent_surface": True,
            "resources": ["/api/signals/latest", "/api/evidence/{symbol}",
                          "/api/market-context/{symbol}", "/api/demo"],
            "mutations": {"/api/refresh": "refreshes cached research data; never executes trades",
                          "/api/backtests/{symbol}": "stores a research backtest"},
            "score_semantics": "0–100 valuation/opportunity score, not trade probability or investment advice",
        }

    @app.get("/api/demo")
    def demo() -> dict[str, object]:
        return synthetic_demo()

    @app.get("/api/market-context")
    def all_market_context() -> dict[str, object]:
        return {symbol: service.market_context(symbol) for symbol in ("GOLD", "SILVER", "COPPER")}

    @app.get("/api/market-context/{symbol}")
    def market_context(symbol: str) -> dict[str, object]:
        try:
            return service.market_context(symbol)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/refresh")
    def refresh(force: bool = False) -> dict[str, object]:
        try:
            return service.refresh(force).response()
        except (ConfigError, DataError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/signals/latest")
    def latest_signals() -> dict[str, object]:
        snapshot = service.latest_response()
        if snapshot is None:
            raise HTTPException(status_code=404, detail="No snapshot yet. POST /api/refresh after validating configuration.")
        return snapshot

    @app.get("/api/signals/{symbol}")
    def signal(symbol: str) -> dict[str, object]:
        item = service.signal(symbol)
        if item is None:
            raise HTTPException(status_code=404, detail=f"No signal found for {symbol.upper()}")
        return item

    @app.get("/api/evidence/{symbol}")
    def evidence(symbol: str) -> dict[str, object]:
        item = service.signal_evidence(symbol)
        if item is None:
            raise HTTPException(status_code=404, detail=f"No evidence found for {symbol.upper()}")
        return item

    @app.post("/api/backtests/{symbol}")
    def backtest(symbol: str) -> dict[str, object]:
        try:
            return service.backtest(symbol).summary()
        except (ConfigError, DataError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
