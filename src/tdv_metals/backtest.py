"""Next-open, stop-aware historical backtester. Research only; it never sends orders."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from math import sqrt

import pandas as pd

from .config import MacroConfig, StrategyConfig
from .decision import Decision, Direction, decide


@dataclass(frozen=True)
class Trade:
    symbol: str
    direction: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    contracts: int
    contract_multiplier: float
    gross_pnl: float
    net_pnl: float
    exit_reason: str


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    metrics: dict[str, float | int]
    trades: tuple[Trade, ...]
    equity_curve: pd.DataFrame

    def summary(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "metrics": self.metrics,
            "trades": [asdict(item) for item in self.trades],
            "equity_curve": self.equity_curve.to_dict(orient="records"),
        }


DecisionFn = Callable[[pd.Series, Direction, float], Decision]


class Backtester:
    """No-look-ahead backtester: close features schedule fills at the next bar's open."""
    def __init__(self, strategy: StrategyConfig, macro: MacroConfig, contract_multiplier: float):
        self.strategy = strategy
        self.macro = macro
        self.contract_multiplier = contract_multiplier

    def run(
        self,
        symbol: str,
        features: pd.DataFrame,
        decision_fn: DecisionFn | None = None,
    ) -> BacktestResult:
        if features.empty:
            raise ValueError("cannot backtest empty features")
        required = {"timestamp", "open", "high", "low", "close", "atr"}
        missing = required - set(features.columns)
        if missing:
            raise ValueError(f"backtest features missing: {sorted(missing)}")
        data = features.sort_values("timestamp").reset_index(drop=True)
        cash = self.strategy.starting_equity
        equity_rows: list[dict[str, object]] = []
        trades: list[Trade] = []
        position: dict[str, object] | None = None
        pending: tuple[Direction, int, float] | None = None  # desired direction, contracts, ATR from signal bar

        def unrealized(mark: float) -> float:
            if not position:
                return 0.0
            sign = 1 if position["direction"] is Direction.LONG else -1
            return sign * (mark - float(position["entry_price"])) * int(position["contracts"]) * self.contract_multiplier

        def close_position(timestamp: object, price: float, reason: str) -> None:
            nonlocal cash, position
            if position is None:
                return
            gross = unrealized(price)
            exit_cost = abs(price * int(position["contracts"]) * self.contract_multiplier) * self.strategy.transaction_cost_rate
            cash += gross - exit_cost
            net = gross - float(position["entry_cost"]) - exit_cost
            trades.append(Trade(
                symbol=symbol, direction=position["direction"].value, entry_time=str(position["entry_time"]),
                exit_time=str(timestamp), entry_price=float(position["entry_price"]), exit_price=price,
                contracts=int(position["contracts"]), contract_multiplier=self.contract_multiplier,
                gross_pnl=gross, net_pnl=net, exit_reason=reason,
            ))
            position = None

        for index, row in data.iterrows():
            timestamp, open_price = row["timestamp"], float(row["open"])
            # Decision made on yesterday's close is the only thing eligible at today's open.
            if pending is not None:
                desired, contracts, prior_atr = pending
                if position is not None and position["direction"] is not desired:
                    close_position(timestamp, open_price, "signal_reversal_or_exit")
                if desired is not Direction.FLAT and position is None and contracts > 0 and prior_atr > 0:
                    entry_cost = abs(open_price * contracts * self.contract_multiplier) * self.strategy.transaction_cost_rate
                    cash -= entry_cost
                    stop_distance = prior_atr * self.strategy.atr_stop_multiple
                    position = {
                        "direction": desired, "contracts": contracts, "entry_price": open_price, "entry_time": timestamp,
                        "entry_cost": entry_cost, "stop": open_price - stop_distance if desired is Direction.LONG else open_price + stop_distance,
                    }
                pending = None
            # Intraday stop is evaluated after opening fills. A gap through it fills at the open, not the desired stop.
            if position is not None:
                stop = float(position["stop"])
                if position["direction"] is Direction.LONG and float(row["low"]) <= stop:
                    close_position(timestamp, min(open_price, stop), "atr_stop")
                elif position["direction"] is Direction.SHORT and float(row["high"]) >= stop:
                    close_position(timestamp, max(open_price, stop), "atr_stop")
            mark_equity = cash + unrealized(float(row["close"]))
            equity_rows.append({"timestamp": timestamp, "equity": mark_equity, "cash": cash, "position": position["direction"].value if position else "FLAT"})
            current = position["direction"] if position else Direction.FLAT
            if decision_fn:
                decision = decision_fn(row, current, mark_equity)
            else:
                decision = decide(symbol, row, self.strategy, self.macro, self.contract_multiplier, current, mark_equity)
            contracts = decision.position_plan.contracts if decision.position_plan else 0
            atr_value = float(row["atr"]) if pd.notna(row["atr"]) else 0.0
            pending = (decision.desired_direction, contracts, atr_value)
        # Close remaining exposure at the last available close; reported clearly as a forced end-of-sample exit.
        if position is not None:
            final = data.iloc[-1]
            close_position(final["timestamp"], float(final["close"]), "end_of_sample")
            if equity_rows:
                equity_rows[-1]["equity"] = cash
                equity_rows[-1]["cash"] = cash
                equity_rows[-1]["position"] = "FLAT"
        curve = pd.DataFrame(equity_rows)
        return BacktestResult(symbol, self._metrics(curve, trades), tuple(trades), curve)

    def _metrics(self, curve: pd.DataFrame, trades: list[Trade]) -> dict[str, float | int]:
        start = self.strategy.starting_equity
        final = float(curve["equity"].iloc[-1]) if not curve.empty else start
        periods = max(len(curve) - 1, 1)
        returns = curve["equity"].pct_change().dropna() if len(curve) > 1 else pd.Series(dtype=float)
        volatility = float(returns.std(ddof=0) * sqrt(252)) if not returns.empty else 0.0
        sharpe = float(returns.mean() / returns.std(ddof=0) * sqrt(252)) if len(returns) > 1 and returns.std(ddof=0) > 0 else 0.0
        drawdown = curve["equity"] / curve["equity"].cummax() - 1 if not curve.empty else pd.Series([0.0])
        net_pnls = [trade.net_pnl for trade in trades]
        positive, negative = sum(value for value in net_pnls if value > 0), abs(sum(value for value in net_pnls if value < 0))
        return {
            "starting_equity": round(start, 2), "final_equity": round(final, 2),
            "total_return_pct": round((final / start - 1) * 100, 4),
            "annualized_return_pct": round(((final / start) ** (252 / periods) - 1) * 100, 4) if final > 0 else -100.0,
            "annualized_volatility_pct": round(volatility * 100, 4), "sharpe_ratio": round(sharpe, 4),
            "max_drawdown_pct": round(float(drawdown.min()) * 100, 4), "trade_count": len(trades),
            "win_rate_pct": round(100 * sum(value > 0 for value in net_pnls) / len(net_pnls), 4) if net_pnls else 0.0,
            # null means no losing trades, so a finite ratio cannot be estimated.
            "profit_factor": round(positive / negative, 4) if negative else None,
        }
