"""VectorBT signal threshold research using a cash equity proxy.

This does not model futures multipliers, margin, contract rolls, ATR stops, or
the deterministic backtester's transaction and gap rules. It is a diagnostic
for candidate score thresholds, never an execution or futures PnL engine.
"""

from __future__ import annotations

import math
from itertools import product

import numpy as np
import pandas as pd

from ._optional import require_module


def vectorbt_threshold_sweep(
    features: pd.DataFrame,
    long_thresholds: tuple[float, ...] = (65.0, 75.0),
    short_thresholds: tuple[float, ...] = (25.0, 35.0),
    *,
    fee_rate: float = 0.0002,
    initial_cash: float = 100_000.0,
    contract_multiplier: float = 1.0,
) -> pd.DataFrame:
    """Explore score cutoffs with yesterday's score filled at today's open.

    A long threshold sets a +100% target, a short threshold a -100% target,
    and intermediate or missing scores set 0%. This is a fully invested cash
    proxy; its output must not be interpreted as a futures strategy result.
    """
    required = {"timestamp", "open", "close", "shadow_valuation_score"}
    if features.empty or not required.issubset(features.columns):
        raise ValueError(f"features must contain rows and {sorted(required)}")
    if contract_multiplier != 1.0:
        raise ValueError("VectorBT sweep is a cash proxy and cannot apply a futures multiplier")
    if not (0 <= fee_rate < 1) or not math.isfinite(fee_rate) or initial_cash <= 0:
        raise ValueError("fee_rate must be in [0, 1) and initial_cash must be positive")
    if not long_thresholds or not short_thresholds:
        raise ValueError("provide at least one long and one short threshold")
    data = features.sort_values("timestamp").reset_index(drop=True)
    dates = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError("timestamps must be valid and unique")
    prices = data[["open", "close"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise ValueError("open and close must be positive finite prices")
    scores = pd.to_numeric(data["shadow_valuation_score"], errors="coerce")
    if (scores.isna() & data["shadow_valuation_score"].notna()).any():
        raise ValueError("scores contain nonnumeric values")
    if ((scores.dropna() < 0) | (scores.dropna() > 100)).any():
        raise ValueError("scores must be in [0, 100] or missing during warmup")
    scores.index = dates
    opens = pd.Series(prices["open"].to_numpy(dtype=float), index=dates)
    closes = pd.Series(prices["close"].to_numpy(dtype=float), index=dates)
    vbt = require_module("vectorbt", "vectorbt")
    rows: list[dict[str, object]] = []
    for long_cutoff, short_cutoff in product(long_thresholds, short_thresholds):
        if not (0 <= short_cutoff < long_cutoff <= 100):
            raise ValueError("each cutoff pair must satisfy 0 <= short < long <= 100")
        desired = pd.Series(
            np.where(scores >= long_cutoff, 1.0, np.where(scores <= short_cutoff, -1.0, 0.0)),
            index=dates,
        )
        next_open_target = desired.shift(1).fillna(0.0)
        portfolio = vbt.Portfolio.from_orders(
            closes,
            size=next_open_target,
            size_type="targetpercent",
            price=opens,
            fees=fee_rate,
            init_cash=initial_cash,
        )
        rows.append({
            "long_threshold": float(long_cutoff),
            "short_threshold": float(short_cutoff),
            "total_return_pct": float(portfolio.total_return()) * 100,
            "max_drawdown_pct": float(portfolio.max_drawdown()) * 100,
            "trade_count": int(portfolio.trades.count()),
            "simulation": "cash_equity_proxy_next_open",
        })
    return pd.DataFrame(rows).sort_values(
        ["total_return_pct", "long_threshold", "short_threshold"],
        ascending=[False, True, True],
    ).reset_index(drop=True)
