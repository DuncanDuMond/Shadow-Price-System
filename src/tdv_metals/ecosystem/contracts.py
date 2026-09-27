"""Strict OHLCV checks at a provider boundary, with optional Pandera schema checks."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import DataError
from ._optional import require_module

REQUIRED = ("timestamp", "open", "high", "low", "close", "volume")
PRICES = ("open", "high", "low", "close")


def validate_ohlcv_integrity(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate rows without coercion, data loss, or a third-party dependency.

    The existing normalizer can fill missing OHLC/volume and drop invalid rows.
    This check is intentionally stricter for sources used in volume research.
    """
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise DataError("OHLCV input must be a nonempty DataFrame")
    missing = set(REQUIRED) - set(frame.columns)
    if missing:
        raise DataError(f"OHLCV input missing columns: {sorted(missing)}")
    dates = frame["timestamp"]
    if not isinstance(dates.dtype, pd.DatetimeTZDtype) or str(dates.dt.tz) != "UTC":
        raise DataError("timestamp must be a UTC timezone-aware pandas datetime")
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise DataError("timestamps must be non-null, unique, and increasing")
    for column in (*PRICES, "volume"):
        if not pd.api.types.is_numeric_dtype(frame[column]):
            raise DataError(f"{column} must be numeric; implicit coercion is not allowed")
        if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
            raise DataError(f"{column} must contain only finite values")
    if (frame[list(PRICES)] <= 0).any().any():
        raise DataError("OHLC prices must be positive")
    if (frame["volume"] < 0).any():
        raise DataError("volume cannot be negative")
    if (frame["high"] < frame[["open", "low", "close"]].max(axis=1)).any():
        raise DataError("high must be at least open, low, and close")
    if (frame["low"] > frame[["open", "high", "close"]].min(axis=1)).any():
        raise DataError("low must be at most open, high, and close")
    return frame.copy()


def validate_ohlcv_pandera(frame: pd.DataFrame) -> pd.DataFrame:
    """Run Pandera's explicit column contract and cross-field integrity checks.

    Install ``pandera[pandas]``. Validation never rewrites vendor values.
    """
    checked = validate_ohlcv_integrity(frame)
    pa = require_module("pandera.pandas", "pandera[pandas]")
    schema = pa.DataFrameSchema(
        {
            "open": pa.Column(float, pa.Check.gt(0), coerce=True, nullable=False),
            "high": pa.Column(float, pa.Check.gt(0), coerce=True, nullable=False),
            "low": pa.Column(float, pa.Check.gt(0), coerce=True, nullable=False),
            "close": pa.Column(float, pa.Check.gt(0), coerce=True, nullable=False),
            "volume": pa.Column(float, pa.Check.ge(0), coerce=True, nullable=False),
        },
        strict=False,
    )
    try:
        validated = schema.validate(checked)
    except (pa.errors.SchemaError, pa.errors.SchemaErrors) as exc:
        raise DataError(f"Pandera OHLCV contract failed: {exc}") from exc
    return validate_ohlcv_integrity(validated)
