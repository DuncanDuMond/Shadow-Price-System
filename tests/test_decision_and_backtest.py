from __future__ import annotations

import unittest

import pandas as pd

from tdv_metals.backtest import Backtester
from tdv_metals.config import MacroConfig, StrategyConfig
from tdv_metals.decision import Action, Decision, Direction, PositionPlan, position_size


class DecisionAndBacktestTests(unittest.TestCase):
    def test_futures_size_respects_contract_multiplier(self) -> None:
        strategy = StrategyConfig(starting_equity=100_000, risk_fraction=0.005, atr_stop_multiple=2, max_contracts=10)
        gold = position_size(Direction.LONG, 2000, 2, strategy, 100)
        silver = position_size(Direction.LONG, 25, 2, strategy, 5000)
        self.assertEqual(gold.contracts, 1)  # $400 risk/contract; $500 risk budget
        self.assertEqual(silver.contracts, 0)  # $20,000 risk/contract

    def test_backtest_uses_next_open_for_fills(self) -> None:
        frame = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
            "open": [100, 101, 102, 104, 105], "high": [101, 102, 103, 105, 106],
            "low": [99, 100, 101, 103, 104], "close": [100, 101, 102, 104, 105], "atr": [1.0] * 5,
        })
        strategy = StrategyConfig(transaction_cost_rate=0, atr_stop_multiple=10)
        plan = PositionPlan(Direction.LONG, 100, 90, 1, 1, 10, 500, 100)
        def callback(row: pd.Series, current: Direction, equity: float) -> Decision:
            desired = Direction.LONG if row.name < 2 else Direction.FLAT
            return Decision("GOLD", str(row.timestamp), Action.ENTER_LONG if desired is Direction.LONG else Action.FLAT,
                            desired, "LONG", 80, -0.2, (), (), plan if desired is Direction.LONG else None)
        result = Backtester(strategy, MacroConfig(), 1).run("GOLD", frame, callback)
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertEqual(trade.entry_price, 101.0)  # signal at first close -> second bar open
        self.assertEqual(trade.exit_price, 104.0)  # flat signal at third close -> fourth bar open
        self.assertEqual(trade.net_pnl, 3.0)
