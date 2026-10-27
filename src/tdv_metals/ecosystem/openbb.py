"""Explicit OpenBB historical futures adapter; read-only and contract-specific."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ..data import DataError, DataRequest, normalize_ohlcv
from ._optional import require_module
from .contracts import validate_ohlcv_integrity


@dataclass
class OpenBBFuturesProvider:
    """Fetch a named expiry. Continuous contract roll rules are never inferred.

    ``client`` supports an injected OpenBB-compatible client in offline tests.
    Credentials belong in the chosen OpenBB provider's own settings.
    """

    vendor: str
    symbol_map: Mapping[str, str]
    expiration: str
    interval: str = "1d"
    client: Any | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.vendor.strip():
            raise ValueError("OpenBB vendor must be explicit")
        if not self.symbol_map or any(not key or not value for key, value in self.symbol_map.items()):
            raise ValueError("OpenBB symbol_map must map every requested metal to a vendor symbol")
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", self.expiration):
            raise ValueError("OpenBB futures expiration must be YYYY-MM")
        if not self.interval.strip():
            raise ValueError("OpenBB interval must be explicit")

    def fetch(self, request: DataRequest) -> pd.DataFrame:
        try:
            vendor_symbol = self.symbol_map[request.name]
        except KeyError as exc:
            raise DataError(f"OpenBB has no explicit symbol for {request.name}") from exc
        client = self.client if self.client is not None else require_module("openbb", "openbb").obb
        query = {
            "symbol": vendor_symbol,
            "provider": self.vendor,
            "expiration": self.expiration,
            "interval": self.interval,
        }
        if request.start:
            query["start_date"] = request.start
        if request.end:
            query["end_date"] = request.end
        try:
            response = client.derivatives.futures.historical(**query)
            converter = getattr(response, "to_dataframe", None)
            raw = converter() if callable(converter) else response.to_df()
        except Exception as exc:
            raise DataError(f"OpenBB futures fetch failed for {request.name}: {exc}") from exc
        if getattr(response, "warnings", None):
            raise DataError(f"OpenBB returned warnings for {request.name}; verify provider parameters")
        actual_vendor = getattr(response, "provider", None)
        if actual_vendor and actual_vendor != self.vendor:
            raise DataError(f"OpenBB returned provider {actual_vendor}, expected {self.vendor}")
        if not isinstance(raw, pd.DataFrame) or raw.empty:
            raise DataError(f"OpenBB returned no futures rows for {request.name}")
        if "date" not in raw.columns and "timestamp" not in raw.columns:
            raw = raw.reset_index()
        columns = {str(column).lower(): column for column in raw.columns}
        needed = {"open", "high", "low", "close", "volume"}
        if not needed.issubset(columns):
            raise DataError(f"OpenBB futures rows require actual OHLCV; missing {sorted(needed - set(columns))}")
        if raw[[columns[name] for name in needed]].isna().any().any():
            raise DataError("OpenBB futures rows contain missing OHLCV; no values were invented")
        for name in needed:
            parsed_number = pd.to_numeric(raw[columns[name]], errors="coerce")
            if parsed_number.isna().any():
                raise DataError(f"OpenBB futures {name} contains nonnumeric values")
        date_column = columns.get("timestamp", columns.get("date"))
        if date_column is None:
            raise DataError("OpenBB futures rows have no date column")
        parsed = pd.to_datetime(raw[date_column], utc=True, errors="coerce")
        if parsed.isna().any() or parsed.duplicated().any():
            raise DataError("OpenBB futures dates must be valid and unique")
        return validate_ohlcv_integrity(normalize_ohlcv(raw))
