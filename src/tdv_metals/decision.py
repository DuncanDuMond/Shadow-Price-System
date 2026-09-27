"""Deterministic long/short/flat decisions and futures-aware risk sizing."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from math import floor, isfinite
from typing import Any

import pandas as pd

from .config import MacroConfig, StrategyConfig


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class Action(str, Enum):
    ENTER_LONG = "ENTER_LONG"
    ENTER_SHORT = "ENTER_SHORT"
    HOLD_LONG = "HOLD_LONG"
    HOLD_SHORT = "HOLD_SHORT"
    EXIT_LONG = "EXIT_LONG"
    EXIT_SHORT = "EXIT_SHORT"
    WATCH = "WATCH"
    ABSTAIN = "ABSTAIN"
    FLAT = "FLAT"


@dataclass(frozen=True)
class PositionPlan:
    direction: Direction
    entry_price: float
    stop_price: float | None
    contracts: int
    contract_multiplier: float
    risk_per_contract: float | None
    max_risk_dollars: float
    notional_dollars: float


@dataclass(frozen=True)
class Decision:
    symbol: str
    timestamp: str
    action: Action
    desired_direction: Direction
    conviction: str
    score: float | None
    shadow_gap: float | None
    confirmations: tuple[str, ...]
    blockers: tuple[str, ...]
    position_plan: PositionPlan | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite(row: pd.Series, key: str) -> float | None:
    value = row.get(key)
    try:
        numeric = float(value)
        return numeric if isfinite(numeric) else None
    except (TypeError, ValueError):
        return None


def position_size(
    direction: Direction,
    entry_price: float,
    atr_value: float,
    strategy: StrategyConfig,
    contract_multiplier: float,
    equity: float | None = None,
) -> PositionPlan:
    if direction is Direction.FLAT:
        raise ValueError("cannot size a flat position")
    if atr_value <= 0 or contract_multiplier <= 0:
        raise ValueError("ATR and contract multiplier must be positive")
    equity = strategy.starting_equity if equity is None else equity
    max_risk = equity * strategy.risk_fraction
    stop_distance = atr_value * strategy.atr_stop_multiple
    risk_per_contract = stop_distance * contract_multiplier
    contracts = min(strategy.max_contracts, max(0, floor(max_risk / risk_per_contract)))
    stop = entry_price - stop_distance if direction is Direction.LONG else entry_price + stop_distance
    return PositionPlan(
        direction=direction, entry_price=entry_price, stop_price=stop, contracts=contracts,
        contract_multiplier=contract_multiplier, risk_per_contract=risk_per_contract,
        max_risk_dollars=max_risk, notional_dollars=contracts * contract_multiplier * entry_price,
    )


def _flag(row: pd.Series, key: str) -> bool:
    value = row.get(key, False)
    return bool(value) if pd.notna(value) else False


def _confirmations(row: pd.Series, direction: Direction) -> list[str]:
    """Count evidence categories rather than multiple correlated indicators per category."""
    macd_fast, macd_slow = _finite(row, "fib_macd_hist_atr"), _finite(row, "slow_fib_macd_hist_atr")
    impulse = _finite(row, "impulse_macd_hist_atr")
    confirms: list[str] = []
    if direction is Direction.LONG:
        momentum = macd_fast is not None and macd_slow is not None and macd_fast > 0 and macd_slow > 0
        if momentum and (impulse is None or impulse > 0):
            confirms.append("Momentum: Fibonacci and Impulse MACD aligned")
        if _flag(row, "williams_recovering"):
            confirms.append("Williams %R recovering from oversold")
        trend = [
            _flag(row, "ichimoku_above_cloud") and _flag(row, "ichimoku_tk_bullish"),
            _flag(row, "ssl_bullish"), _flag(row, "ribbon_bullish"),
        ]
        if sum(trend) >= (2 if "ssl_bullish" in row and "ribbon_bullish" in row else 1):
            confirms.append("Trend: Ichimoku, SSL and ribbon agreement")
        if (str(row.get("volume_participation_status", "")).upper() in {"AVAILABLE", "OK"}
                and (_finite(row, "volume_relative") or 0) >= 1.0
                and (_finite(row, "volume_directional_participation") or 0) > 0):
            confirms.append("Volume participation supports the move")
    else:
        momentum = macd_fast is not None and macd_slow is not None and macd_fast < 0 and macd_slow < 0
        if momentum and (impulse is None or impulse < 0):
            confirms.append("Momentum: Fibonacci and Impulse MACD aligned")
        wr, wr_delta = _finite(row, "williams_r"), _finite(row, "williams_delta")
        if wr is not None and wr_delta is not None and wr >= -20 and wr_delta < 0:
            confirms.append("Williams %R reversing from overbought")
        trend = [
            _flag(row, "ichimoku_below_cloud") and not _flag(row, "ichimoku_tk_bullish"),
            _flag(row, "ssl_bearish"), _flag(row, "ribbon_bearish"),
        ]
        if sum(trend) >= (2 if "ssl_bearish" in row and "ribbon_bearish" in row else 1):
            confirms.append("Trend: Ichimoku, SSL and ribbon agreement")
        if (str(row.get("volume_participation_status", "")).upper() in {"AVAILABLE", "OK"}
                and (_finite(row, "volume_relative") or 0) >= 1.0
                and (_finite(row, "volume_directional_participation") or 0) < 0):
            confirms.append("Volume participation supports the move")
    macro_key = "macro_confirmed" if direction is Direction.LONG else "macro_bearish_confirmed"
    if _flag(row, macro_key):
        confirms.append("DXY and real-yield macro confirmation")
    return confirms


def decide(
    symbol: str,
    row: pd.Series,
    strategy: StrategyConfig,
    macro: MacroConfig,
    contract_multiplier: float,
    current_position: Direction = Direction.FLAT,
    equity: float | None = None,
) -> Decision:
    """Create one explainable decision from same-bar, causally available features."""
    score, gap, close, atr_value = (_finite(row, key) for key in ("shadow_valuation_score", "shadow_gap", "close", "atr"))
    timestamp = str(row.get("timestamp", ""))
    blockers: list[str] = []
    if not bool(row.get("svs_complete", False)) or None in (score, gap, close, atr_value):
        blockers.append("insufficient warm-up data for a complete SVS")
        desired = Direction.FLAT
        long_confirms: list[str] = []
        short_confirms: list[str] = []
    else:
        long_confirms = _confirmations(row, Direction.LONG)
        short_confirms = _confirmations(row, Direction.SHORT)
        macro_missing = str(row.get("macro_status", "MISSING")) != "AVAILABLE"
        required = strategy.confirmation_count
        if macro_missing and macro.missing_policy == "block_entries":
            blockers.append("macro feeds missing: policy blocks new entries")
        elif macro_missing and macro.missing_policy == "penalize":
            required += 1
            blockers.append("macro feeds missing: one additional confirmation required")
        long_macro = _flag(row, "macro_confirmed")
        short_macro = _flag(row, "macro_bearish_confirmed")
        if strategy.require_macro_confirmation and not (long_macro or short_macro):
            blockers.append("strategy requires DXY/real-yield macro confirmation")
        macro_available = not (macro_missing and macro.missing_policy == "block_entries")
        long_ok = score >= strategy.long_score and gap <= -strategy.entry_gap and len(long_confirms) >= required and macro_available and (not strategy.require_macro_confirmation or long_macro)
        short_ok = score <= strategy.short_score and gap >= strategy.entry_gap and len(short_confirms) >= required and macro_available and (not strategy.require_macro_confirmation or short_macro)
        desired = Direction.LONG if long_ok else Direction.SHORT if short_ok else Direction.FLAT
        if desired is Direction.FLAT and not blockers:
            blockers.append("valuation threshold and/or confirmations not met")
    if desired is Direction.LONG:
        action = Action.HOLD_LONG if current_position is Direction.LONG else Action.ENTER_LONG
        conviction = "STRONG_LONG" if score is not None and score >= strategy.strong_long_score else "LONG"
        confirmations = long_confirms
    elif desired is Direction.SHORT:
        action = Action.HOLD_SHORT if current_position is Direction.SHORT else Action.ENTER_SHORT
        conviction = "STRONG_SHORT" if score is not None and score <= strategy.strong_short_score else "SHORT"
        confirmations = short_confirms
    elif current_position is Direction.LONG:
        action, conviction, confirmations = Action.EXIT_LONG, "EXIT", []
    elif current_position is Direction.SHORT:
        action, conviction, confirmations = Action.EXIT_SHORT, "EXIT", []
    elif blockers and "insufficient warm-up data for a complete SVS" in blockers:
        action, conviction, confirmations = Action.ABSTAIN, "INSUFFICIENT_DATA", []
    elif score is not None and score >= 60:
        action, conviction, confirmations = Action.WATCH, "WATCH", long_confirms
    else:
        action, conviction, confirmations = Action.FLAT, "FLAT", []
    plan = None
    if desired is not Direction.FLAT and close is not None and atr_value is not None:
        plan = position_size(desired, close, atr_value, strategy, contract_multiplier, equity)
        if plan.contracts == 0:
            blockers.append("risk budget is smaller than one futures contract at the ATR stop")
            desired = Direction.FLAT
            action = Action.ABSTAIN if current_position is Direction.FLAT else (
                Action.EXIT_LONG if current_position is Direction.LONG else Action.EXIT_SHORT
            )
            conviction = "RISK_LIMIT"
    return Decision(symbol, timestamp, action, desired, conviction, score, gap, tuple(confirmations), tuple(blockers), plan)
