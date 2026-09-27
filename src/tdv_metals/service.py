"""Application service: data -> features -> scores -> decisions -> persistence."""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .advanced_indicators import add_advanced_indicators
from .backtest import Backtester, BacktestResult
from .config import Settings
from .data import DataError, DataHub, DataRequest, DiskCache
from .decision import Action, Decision, Direction, decide
from .indicators import add_indicators, add_macro_confirmation, add_relative_strength
from .scoring import add_shadow_valuation_score
from .sessions import session_status
from .shadow import attach_shadow_price
from .storage import ResearchStore

LOG = logging.getLogger(__name__)


@dataclass
class AnalysisSnapshot:
    created_at: str
    frames: dict[str, pd.DataFrame]
    decisions: dict[str, Decision]
    ranking: list[dict[str, Any]]
    macro_errors: list[str]
    evidence: dict[str, dict[str, Any]]

    def response(self) -> dict[str, Any]:
        charts = {
            symbol: [{
                "timestamp": pd.Timestamp(row["timestamp"]).isoformat(),
                "price": _json_number(row.get("close")),
                "shadow": _json_number(row.get("shadow_price")),
                "score": _json_number(row.get("shadow_valuation_score")),
            } for _, row in frame.tail(90).iterrows()]
            for symbol, frame in self.frames.items()
        }
        return {
            "name": "Shadow Price System", "created_at": self.created_at,
            "research_only": True, "broker_execution": False, "macro_errors": self.macro_errors,
            "ranking": self.ranking, "signals": {symbol: decision.as_dict() for symbol, decision in self.decisions.items()},
            "evidence": self.evidence, "charts": charts,
        }


def _json_number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if pd.notna(number) and abs(number) != float("inf") else None
    except (TypeError, ValueError):
        return None


class ResearchService:
    """Orchestrates research analysis. There is deliberately no broker or order interface."""
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cache = DiskCache(settings.storage.cache_dir, settings.storage.cache_ttl_minutes)
        self.hub = DataHub(settings.data.providers, self.cache)
        self.store = ResearchStore(settings.storage.sqlite_path)
        self.snapshot: AnalysisSnapshot | None = None

    def refresh(self, force: bool = False) -> AnalysisSnapshot:
        self.settings.validate_for_analysis()
        monetary_base = self.hub.fetch(
            self.settings.data.monetary_base_provider or "", DataRequest("MONETARY_BASE", role="series"), force
        )
        if (monetary_base["close"] <= 0).any():
            raise DataError("monetary base observations must be positive")
        macro_errors: list[str] = []
        dxy = self._optional_macro(self.settings.data.macro.dxy_provider, "DXY", force, macro_errors)
        real_yield = self._optional_macro(self.settings.data.macro.real_yield_provider, "REAL_YIELD", force, macro_errors)
        frames: dict[str, pd.DataFrame] = {}
        for instrument in self.settings.data.instruments:
            prices = self.hub.fetch(instrument.provider, DataRequest(instrument.symbol), force)
            frames[instrument.symbol] = add_advanced_indicators(
                add_indicators(
                    attach_shadow_price(prices, monetary_base, instrument.symbol, self.settings.shadow_model),
                    self.settings.indicators,
                ),
                self.settings.advanced_indicators,
            )
        frames = add_relative_strength(frames, self.settings.indicators.relative_strength_window)
        decisions: dict[str, Decision] = {}
        evidence: dict[str, dict[str, Any]] = {}
        for instrument in self.settings.data.instruments:
            featured = add_macro_confirmation(frames[instrument.symbol], dxy, real_yield, self.settings.data.macro)
            frames[instrument.symbol] = add_shadow_valuation_score(featured)
            latest = frames[instrument.symbol].iloc[-1]
            decisions[instrument.symbol] = decide(
                instrument.symbol, latest, self.settings.strategy, self.settings.data.macro,
                instrument.contract_multiplier, Direction.FLAT,
            )
            evidence[instrument.symbol] = self._evidence(instrument.symbol, latest)
            if self.settings.run_mode == "paper" and decisions[instrument.symbol].action in (
                Action.ENTER_LONG, Action.ENTER_SHORT
            ):
                paper_blockers: list[str] = []
                age = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(latest["timestamp"])).total_seconds() / 86400
                if age < 0:
                    paper_blockers.append("last price bar timestamp is in the future")
                if age > self.settings.strategy.max_paper_signal_age_days:
                    paper_blockers.append(
                        f"last price bar is {age:.2f} days old; exceeds paper freshness limit"
                    )
                context = self.market_context(instrument.symbol)
                if not context["entry_eligible_now"]:
                    paper_blockers.append(
                        "verified exchange calendar does not confirm an open market now"
                    )
                if paper_blockers:
                    old = decisions[instrument.symbol]
                    decisions[instrument.symbol] = replace(
                        old, action=Action.ABSTAIN, desired_direction=Direction.FLAT,
                        conviction="PAPER_GUARD", blockers=old.blockers + tuple(paper_blockers),
                        position_plan=None,
                    )
        ranking = sorted(
            [{"symbol": symbol, "score": decision.score, "action": decision.action.value, "conviction": decision.conviction} for symbol, decision in decisions.items()],
            key=lambda item: item["score"] if item["score"] is not None else -1, reverse=True,
        )
        self.snapshot = AnalysisSnapshot(datetime.now(timezone.utc).isoformat(), frames, decisions, ranking, macro_errors, evidence)
        self.store.save_snapshot(self.snapshot.response())
        LOG.info("analysis snapshot complete symbols=%s", ",".join(frames))
        return self.snapshot

    def _optional_macro(self, provider: str | None, name: str, force: bool, errors: list[str]) -> pd.DataFrame | None:
        if not provider:
            errors.append(f"{name}: provider not configured")
            return None
        try:
            return self.hub.fetch(provider, DataRequest(name, role="series"), force)
        except DataError as exc:
            errors.append(f"{name}: {exc}")
            LOG.warning("macro unavailable name=%s error=%s", name, exc)
            return None

    def latest_response(self) -> dict[str, Any] | None:
        return self.snapshot.response() if self.snapshot else self.store.latest_snapshot()

    def signal(self, symbol: str) -> dict[str, Any] | None:
        snapshot = self.latest_response()
        if not snapshot:
            return None
        return snapshot.get("signals", {}).get(symbol.upper())

    def signal_evidence(self, symbol: str) -> dict[str, Any] | None:
        snapshot = self.latest_response()
        if not snapshot:
            return None
        return snapshot.get("evidence", {}).get(symbol.upper())

    def market_context(self, symbol: str, as_of: datetime | None = None) -> dict[str, Any]:
        symbol = symbol.upper()
        if symbol not in {item.symbol for item in self.settings.data.instruments}:
            raise ValueError(f"unknown symbol: {symbol}")
        calendar = self.settings.market_context.calendars.get(symbol)
        if calendar is None:
            return {
                "symbol": symbol, "status": "UNKNOWN", "is_open": None,
                "entry_eligible_now": False,
                "reason": "No verified instrument exchange calendar configured; Market 24h regional hours cannot substitute.",
                "market24_reference": self.settings.market_context.market24_url,
            }
        status = session_status(as_of or datetime.now(timezone.utc), calendar, self.settings.market_context.contexts)
        eligible = bool(status["is_open"] and calendar.verified and calendar.source_url)
        return {
            "symbol": symbol, **status, "entry_eligible_now": eligible,
            "market24_reference": self.settings.market_context.market24_url,
            "note": "Market 24h is a linked regional context; exchange schedule and holiday exceptions are user-configured.",
            "reason": None if calendar.verified else "Exchange schedule is not marked verified with a source URL.",
        }

    def _evidence(self, symbol: str, row: pd.Series) -> dict[str, Any]:
        keys = (
            "close", "shadow_price", "shadow_gap", "shadow_multiple", "shadow_multiple_percentile",
            "shadow_multiple_p10", "shadow_multiple_p50", "shadow_multiple_p90",
            "volume_profile_poc", "volume_profile_vah", "volume_profile_val", "volume_relative",
            "volume_directional_participation", "ssl_baseline", "ssl_direction",
            "impulse_macd_hist_atr", "ribbon_alignment", "ribbon_spread_atr",
            "fib_macd_hist_atr", "slow_fib_macd_hist_atr", "relative_strength_score",
            "score_valuation", "score_fib_bb", "score_macd", "score_ichimoku",
            "score_williams", "score_relative_strength", "shadow_valuation_score",
        )
        instrument = next(item for item in self.settings.data.instruments if item.symbol == symbol)
        anchor_rows = self.settings.shadow_model.anchors[symbol]
        timestamp = pd.Timestamp(row["timestamp"])
        age = (pd.Timestamp.now(tz="UTC") - timestamp).total_seconds() / 86400
        result: dict[str, Any] = {
            "symbol": symbol, "timestamp": timestamp.isoformat(), "data_age_days": round(age, 2),
            "price_provider": instrument.provider,
            "shadow_model": "TDV-style monetary-base anchor model; not an objective fair value",
            "anchor_sources": [{"id": anchor.id, "date": anchor.base_date, "source_url": anchor.source_url}
                               for anchor in anchor_rows],
            "contract_multiplier": instrument.contract_multiplier,
            "score_components": {key: _json_number(row.get(key)) for key in keys if key.startswith("score_")},
            "features": {key: _json_number(row.get(key)) for key in keys if not key.startswith("score_")},
            "statuses": {key: str(row.get(key, "UNKNOWN")) for key in (
                "shadow_multiple_status", "volume_profile_status", "volume_participation_status",
                "ssl_status", "impulse_macd_status", "ribbon_status", "experimental_qqe_status",
                "relative_strength_status", "macro_status"
            )},
            "experimental_qqe_enabled": self.settings.advanced_indicators.qqe_enabled,
            "limitations": ["volume profile is an OHLCV typical-price-bin proxy, not trade-level volume-at-price",
                            "SSL and QQE are documented approximations, not exact third-party script reproductions"],
        }
        if self.settings.advanced_indicators.qqe_enabled:
            result["features"].update({key: _json_number(row.get(key)) for key in (
                "experimental_qqe_rsi", "experimental_qqe_direction")})
        return result

    def backtest(self, symbol: str) -> BacktestResult:
        symbol = symbol.upper()
        if self.snapshot is None:
            self.refresh()
        assert self.snapshot is not None
        instrument = next((item for item in self.settings.data.instruments if item.symbol == symbol), None)
        if instrument is None:
            raise ValueError(f"unknown symbol: {symbol}")
        result = Backtester(self.settings.strategy, self.settings.data.macro, instrument.contract_multiplier).run(symbol, self.snapshot.frames[symbol])
        self.store.save_backtest(symbol, result.summary())
        return result
