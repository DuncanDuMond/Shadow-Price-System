"""Command-line entry point for automation agents and human operators."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .api import create_app
from .config import ConfigError, load_settings
from .data import DataRequest
from .demo import synthetic_demo
from .ecosystem import (
    evidently_drift_report,
    min_cvar_allocation,
    min_variance_allocation,
    validate_ohlcv_integrity,
    validate_ohlcv_pandera,
    vectorbt_threshold_sweep,
)
from .logging_utils import configure_logging
from .service import ResearchService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Shadow Price System — research only, no broker execution")
    parser.add_argument("--config", default="config.json", help="JSON/YAML configuration path")
    actions = parser.add_subparsers(dest="command", required=True)
    actions.add_parser("validate-config", help="validate a configuration without accessing providers")
    actions.add_parser("demo", help="show a clearly labeled synthetic walkthrough; no configuration needed")
    actions.add_parser("integrations", help="inspect optional package metadata without fetching data")
    refresh = actions.add_parser("refresh", help="fetch/cache data and produce signals")
    refresh.add_argument("--force", action="store_true", help="bypass local provider cache")
    backtest = actions.add_parser("backtest", help="run next-open historical backtest")
    backtest.add_argument("symbol", choices=["GOLD", "SILVER", "COPPER"], type=str.upper)
    context = actions.add_parser("market-context", help="show configured exchange and regional session state")
    context.add_argument("symbol", choices=["GOLD", "SILVER", "COPPER"], type=str.upper)
    check = actions.add_parser("validate-data", help="check OHLCV integrity for an instrument")
    check.add_argument("symbol", choices=["GOLD", "SILVER", "COPPER"], type=str.upper)
    check.add_argument("--pandera", action="store_true", help="also run the optional Pandera contract")
    sweep = actions.add_parser("research-sweep", help="VectorBT cash-proxy threshold sweep, not futures PnL")
    sweep.add_argument("symbol", choices=["GOLD", "SILVER", "COPPER"], type=str.upper)
    portfolio = actions.add_parser("portfolio", help="long-only research weights, never contract orders")
    portfolio.add_argument("--method", choices=["min_variance", "min_cvar"], default="min_variance")
    drift = actions.add_parser("drift-report", help="Evidently first-half/second-half feature drift check")
    drift.add_argument("symbol", choices=["GOLD", "SILVER", "COPPER"], type=str.upper)
    actions.add_parser("mcp-serve", help="start optional read-only MCP server over stdio")
    serve = actions.add_parser("serve", help="start FastAPI and dashboard")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", default=None, type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    try:
        if args.command == "demo":
            print(json.dumps(synthetic_demo(), default=str, indent=2, allow_nan=False))
            return 0
        if args.command == "integrations":
            from .ecosystem.status import integration_status
            print(json.dumps(integration_status(), indent=2, allow_nan=False))
            return 0
        settings = load_settings(Path(args.config))
        if args.command == "validate-config":
            settings.validate_for_analysis()
            print(json.dumps({"status": "valid", "name": "Shadow Price System",
                              "mode": settings.run_mode, "execution": "disabled",
                              "exchange_calendars": sorted(settings.market_context.calendars)}))
            return 0
        if args.command == "mcp-serve":
            from .mcp_server import run_stdio
            run_stdio(args.config)
            return 0
        if args.command == "serve":
            try:
                import uvicorn
            except ImportError as exc:
                raise ConfigError("uvicorn is not installed. Run: pip install -e .") from exc
            uvicorn.run(create_app(args.config), host=args.host or settings.api.host, port=args.port or settings.api.port)
            return 0
        service = ResearchService(settings)
        if args.command == "market-context":
            print(json.dumps(service.market_context(args.symbol), default=str, indent=2))
            return 0
        if args.command == "validate-data":
            instrument = next(item for item in settings.data.instruments if item.symbol == args.symbol)
            frame = service.hub.fetch(instrument.provider, DataRequest(args.symbol))
            validate_ohlcv_pandera(frame) if args.pandera else validate_ohlcv_integrity(frame)
            print(json.dumps({"symbol": args.symbol, "status": "valid",
                              "rows": len(frame), "pandera": args.pandera}))
            return 0
        if args.command == "refresh":
            print(json.dumps(service.refresh(args.force).response(), default=str, indent=2, allow_nan=False))
        elif args.command == "backtest":
            print(json.dumps(service.backtest(args.symbol).summary(), default=str, indent=2, allow_nan=False))
        elif args.command == "research-sweep":
            snapshot = service.refresh()
            result = vectorbt_threshold_sweep(snapshot.frames[args.symbol])
            print(json.dumps({"symbol": args.symbol, "simulation": "cash_equity_proxy_not_futures",
                              "candidates": result.to_dict(orient="records")}, indent=2, allow_nan=False))
        elif args.command == "portfolio":
            snapshot = service.refresh()
            active = [symbol for symbol, decision in snapshot.decisions.items()
                      if decision.desired_direction.value == "LONG"]
            prices = pd.concat(
                {symbol: frame.set_index("timestamp")["close"] for symbol, frame in snapshot.frames.items()},
                axis=1, join="inner",
            )
            returns = prices.pct_change().dropna()
            allocator = min_variance_allocation if args.method == "min_variance" else min_cvar_allocation
            weights = allocator(returns, active, max_weight=1.0 if len(active) < 2 else 0.6)
            print(json.dumps({"method": args.method, "simulation": "cash_weights_not_futures_contracts",
                              "active_long_symbols": active, "weights": weights}, indent=2, allow_nan=False))
        elif args.command == "drift-report":
            snapshot = service.refresh()
            frame = snapshot.frames[args.symbol]
            columns = ["shadow_gap", "shadow_valuation_score", "volume_relative",
                       "impulse_macd_hist_atr", "ribbon_alignment"]
            midpoint = len(frame) // 2
            report = evidently_drift_report(frame.iloc[:midpoint], frame.iloc[midpoint:], columns)
            print(json.dumps({"symbol": args.symbol, **report}, indent=2, allow_nan=False))
        return 0
    except (ConfigError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "detail": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
