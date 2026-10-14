"""Configurable TDV-style monetary-base shadow-price calculations."""
from __future__ import annotations

import math
from datetime import date
from typing import Any
from urllib.parse import urlsplit

import pandas as pd

from .config import Anchor, ShadowModelConfig


class ShadowModelError(ValueError):
    pass


def calculate_shadow_benchmark(
    symbol: str,
    current_monetary_base: float,
    anchors: list[dict[str, Any]],
    monetary_base_unit: str,
    metal_price_unit: str,
    current_source_url: str,
    current_as_of: str,
    market_price: float | None = None,
    aggregation: str = "mean",
) -> dict[str, Any]:
    """Calculate from caller-supplied inputs, without providers, storage or orders.

    All monetary-base values must share the stated unit; all metal prices must
    share the stated quote unit. Validation is caller attestation, not verification
    of a source by this function. No live-data or freshness claim is made.
    """
    if symbol not in {"GOLD", "SILVER", "COPPER"}:
        raise ShadowModelError("symbol must be GOLD, SILVER, or COPPER")
    if aggregation not in {"mean", "median"}:
        raise ShadowModelError("aggregation must be mean or median")
    for name, value in (("current_monetary_base", current_monetary_base),
                        ("market_price", market_price)):
        if name == "market_price" and value is None:
            continue
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ShadowModelError(f"{name} must be positive and finite")
    if not all(isinstance(unit, str) and unit.strip()
               for unit in (monetary_base_unit, metal_price_unit)):
        raise ShadowModelError("explicit monetary-base and metal-price units are required")
    try:
        source = urlsplit(current_source_url)
        if source.scheme not in {"http", "https"} or not source.hostname:
            raise ValueError("current_source_url must be an HTTP(S) source URL")
        date.fromisoformat(current_as_of)
    except (TypeError, ValueError) as exc:
        raise ShadowModelError(f"invalid current input provenance: {exc}") from exc
    if not anchors:
        raise ShadowModelError("at least one validated anchor is required")
    estimates = []
    ids: set[str] = set()
    for raw in anchors:
        try:
            anchor = Anchor(**raw)
            if (anchor.validated is not True or not anchor.valid()
                    or not isinstance(anchor.id, str) or not anchor.id.strip()
                    or isinstance(anchor.base_monetary_base, bool)
                    or isinstance(anchor.base_metal_price, bool)):
                raise ValueError(
                    "anchor requires validated=true, valid base_date/source_url, "
                    "and positive finite values"
                )
        except (TypeError, ValueError, AttributeError) as exc:
            raise ShadowModelError(f"invalid anchor: {exc}") from exc
        if anchor.id in ids:
            raise ShadowModelError("anchor ids must be unique")
        ids.add(anchor.id)
        estimate = float(shadow_price(pd.Series([current_monetary_base]), anchor).iloc[0])
        if not math.isfinite(estimate) or estimate <= 0:
            raise ShadowModelError("anchor calculation overflowed or underflowed")
        estimates.append({"id": anchor.id, "base_date": anchor.base_date,
                          "source_url": anchor.source_url, "shadow_price": estimate})
    values = pd.Series([row["shadow_price"] for row in estimates], dtype=float)
    benchmark = float(values.mean() if aggregation == "mean" else values.median())
    if not math.isfinite(benchmark) or benchmark <= 0:
        raise ShadowModelError("aggregate calculation overflowed or underflowed")
    multiple = None if market_price is None else market_price / benchmark
    if multiple is not None and (not math.isfinite(multiple) or multiple <= 0):
        raise ShadowModelError("market/shadow ratio overflowed or underflowed")
    return {
        "symbol": symbol, "shadow_price": benchmark, "aggregation": aggregation,
        "shadow_gap": None if multiple is None else multiple - 1.0,
        "shadow_multiple": multiple,
        "market_price": market_price, "current_monetary_base": current_monetary_base,
        "monetary_base_unit": monetary_base_unit, "metal_price_unit": metal_price_unit,
        "current_source_url": current_source_url, "current_as_of": current_as_of,
        "anchor_estimates": estimates,
        "input_status": "USER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED",
        "model": "TDV-style monetary-base anchor model; not objective fair value",
        "research_only": True, "broker_execution": False,
    }


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
