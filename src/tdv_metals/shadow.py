"""Configurable TDV-style monetary-base shadow-price calculations."""
from __future__ import annotations

import pandas as pd

from .config import Anchor, ShadowModelConfig


class ShadowModelError(ValueError):
    pass


def shadow_price(current_monetary_base: pd.Series, anchor: Anchor) -> pd.Series:
    """Return price implied by one supplied historical anchor.

    The formula is intentionally simple and inspectable: base_metal_price times
    current monetary base divided by the verified historical monetary base. It is
    TDV-style research logic, not a claim about any proprietary TDV formula.
    """
    if not anchor.valid():
        raise ShadowModelError(f"anchor {anchor.id} is not validated and complete")
    return anchor.base_metal_price * current_monetary_base / anchor.base_monetary_base  # type: ignore[operator]


def attach_shadow_price(
    prices: pd.DataFrame,
    monetary_base: pd.DataFrame,
    symbol: str,
    config: ShadowModelConfig,
) -> pd.DataFrame:
    """As-of join the monetary base to price data and attach each anchor + aggregate."""
    anchors = config.anchors.get(symbol, ())
    if not anchors:
        raise ShadowModelError(f"no anchors for {symbol}")
    if prices.empty or monetary_base.empty:
        raise ShadowModelError("price and monetary-base data must be nonempty")
    base = monetary_base.loc[:, ["timestamp", "close"]].rename(columns={"close": "monetary_base"})
    result = pd.merge_asof(
        prices.sort_values("timestamp"), base.sort_values("timestamp"), on="timestamp", direction="backward"
    )
    if result["monetary_base"].isna().all():
        raise ShadowModelError("no monetary-base observation exists on or before price dates")
    columns: list[str] = []
    for anchor in anchors:
        name = f"shadow_{anchor.id}"
        result[name] = shadow_price(result["monetary_base"], anchor)
        columns.append(name)
    values = result[columns]
    result["shadow_price"] = values.mean(axis=1) if config.aggregation == "mean" else values.median(axis=1)
    result["shadow_gap"] = result["close"] / result["shadow_price"] - 1.0
    return result
