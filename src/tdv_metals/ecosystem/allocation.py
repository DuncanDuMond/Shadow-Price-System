"""Optional research allocations of a capped gross cash budget.

Weights are portfolio fractions, not futures contracts or order instructions.
The caller selects assets using the deterministic decision and risk gates.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd

from ._optional import require_module


def _prepare(
    returns: pd.DataFrame,
    active_symbols: Sequence[str] | None,
    max_weight: float,
    gross_budget: float,
) -> tuple[pd.DataFrame, list[str]]:
    if not isinstance(returns, pd.DataFrame) or returns.empty:
        raise ValueError("returns must be a nonempty DataFrame")
    if returns.columns.has_duplicates:
        raise ValueError("returns columns must be unique")
    if not math.isfinite(max_weight) or not 0 < max_weight <= 1:
        raise ValueError("max_weight must be in (0, 1]")
    if not math.isfinite(gross_budget) or not 0 <= gross_budget <= 1:
        raise ValueError("gross_budget must be in [0, 1]")
    selected = list(returns.columns) if active_symbols is None else list(active_symbols)
    if len(selected) != len(set(selected)) or not set(selected).issubset(returns.columns):
        raise ValueError("active_symbols must be unique columns in returns")
    if not selected or gross_budget == 0:
        return returns.iloc[:0, :0], selected
    if len(returns) < 20:
        raise ValueError("at least 20 synchronized return rows are required")
    if len(selected) * max_weight < 1 - 1e-9:
        raise ValueError("max_weight is infeasible for the number of active assets")
    data = returns.loc[:, selected]
    if any(not pd.api.types.is_numeric_dtype(data[column]) for column in selected):
        raise ValueError("returns must be numeric")
    if not np.isfinite(data.to_numpy(dtype=float)).all():
        raise ValueError("returns must be finite and synchronized; fill policy must be explicit")
    if (data.std(ddof=1) <= 0).any():
        raise ValueError("each active asset needs nonzero observed volatility")
    return data, selected


def _result(
    raw_weights: dict[str, float], all_symbols: list[str], selected: list[str],
    max_weight: float, gross_budget: float,
) -> dict[str, float]:
    if set(raw_weights) != set(selected):
        raise ValueError("optimizer returned weights for unexpected assets")
    values = np.array([float(raw_weights[symbol]) for symbol in selected])
    if not np.isfinite(values).all() or (values < -1e-6).any():
        raise ValueError("optimizer returned invalid weights")
    if abs(float(values.sum()) - 1) > 1e-3 or (values > max_weight + 1e-3).any():
        raise ValueError("optimizer violated budget or asset weight cap")
    return {symbol: (float(raw_weights[symbol]) * gross_budget if symbol in selected else 0.0)
            for symbol in all_symbols}


def min_variance_allocation(
    returns: pd.DataFrame,
    active_symbols: Sequence[str] | None = None,
    *,
    max_weight: float = 0.6,
    gross_budget: float = 0.5,
) -> dict[str, float]:
    """PyPortfolioOpt covariance aware minimum variance allocation."""
    data, selected = _prepare(returns, active_symbols, max_weight, gross_budget)
    all_symbols = list(returns.columns)
    if not selected or gross_budget == 0:
        return dict.fromkeys(all_symbols, 0.0)
    pypfopt = require_module("pypfopt", "PyPortfolioOpt")
    optimizer = pypfopt.EfficientFrontier(
        None, data.cov() * 252, weight_bounds=(0.0, max_weight)
    )
    weights = optimizer.min_volatility()
    return _result(dict(weights), all_symbols, selected, max_weight, gross_budget)


def min_cvar_allocation(
    returns: pd.DataFrame,
    active_symbols: Sequence[str] | None = None,
    *,
    max_weight: float = 0.6,
    gross_budget: float = 0.5,
    tail_probability: float = 0.05,
) -> dict[str, float]:
    """Riskfolio-Lib historical CVaR allocation with the same risk caps."""
    data, selected = _prepare(returns, active_symbols, max_weight, gross_budget)
    all_symbols = list(returns.columns)
    if not selected or gross_budget == 0:
        return dict.fromkeys(all_symbols, 0.0)
    if not math.isfinite(tail_probability) or not 0 < tail_probability <= 0.5:
        raise ValueError("tail_probability must be in (0, 0.5]")
    riskfolio = require_module("riskfolio", "Riskfolio-Lib")
    optimizer = riskfolio.Portfolio(
        returns=data, sht=False, upperlng=max_weight, budget=1, alpha=tail_probability
    )
    optimizer.assets_stats(method_mu="hist", method_cov="hist")
    weights = optimizer.optimization(model="Classic", rm="CVaR", obj="MinRisk", hist=True)
    if weights is None or not isinstance(weights, pd.DataFrame) or weights.shape[1] != 1:
        raise ValueError("Riskfolio could not find a feasible CVaR allocation")
    return _result(weights.iloc[:, 0].to_dict(), all_symbols, selected, max_weight, gross_budget)
