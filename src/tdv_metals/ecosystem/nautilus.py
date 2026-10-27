"""Lazy, offline-only conversion; not a backtest or futures PnL calculation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

from ..data import DataError
from ._optional import require_module
from .contracts import PRICES, validate_ohlcv_integrity

if TYPE_CHECKING:
    from nautilus_trader.model.data import Bar, BarType
    from nautilus_trader.model.instruments import Instrument


def to_nautilus_bars(
    frame: pd.DataFrame,
    instrument: Instrument,
    bar_type: BarType,
    *,
    as_of: datetime,
) -> list[Bar]:
    """Convert finalized UTC OHLCV rows without engines, orders, or network I/O.

    ``timestamp`` MUST denote bar close, not interval open; every close must be
    <= the explicit timezone-aware ``as_of``. No wall-clock default, shifting,
    sorting, filling, metadata inference, or resampling is performed. The caller
    supplies a fully specified SDK Instrument and matching external BarType;
    contract identity, venue, expiry, units and period semantics remain theirs.

    Uses NautilusTrader 1.231.0 BarDataWrangler.process: its index becomes
    ts_event and ts_init_delta=0 makes ts_init equal ts_event (no latency model).
    Real volume is required; default_volume=0.0 disables synthetic fallback.
    SDK price/size precision rounding applies. Inputs are copied before wrangling.
    This is NOT a backtest, execution simulation, or futures PnL calculation.
    """
    if not isinstance(as_of, datetime) or pd.isna(as_of):
        raise DataError("as_of must be an explicit timezone-aware datetime")
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise DataError("as_of must be an explicit timezone-aware datetime")
    if isinstance(frame, pd.DataFrame):
        if not frame.columns.is_unique:
            raise DataError("OHLCV column names must be unique")
        for name in (*PRICES, "volume"):
            if name in frame and (
                pd.api.types.is_bool_dtype(frame[name])
                or pd.api.types.is_complex_dtype(frame[name])
            ):
                raise DataError(f"{name} must contain real numeric values, not bool/complex")
    checked = validate_ohlcv_integrity(frame)
    if (checked["timestamp"] > cutoff).any():
        raise DataError("bar-close timestamps must be <= as_of")
    if (checked["timestamp"] < pd.Timestamp("1970-01-01", tz="UTC")).any():
        raise DataError("Nautilus unsigned timestamps require closes >= 1970-01-01 UTC")

    hint = "nautilus_trader==1.231.0 (Python >=3.12,<3.15)"
    instruments = require_module("nautilus_trader.model.instruments", hint)
    data = require_module("nautilus_trader.model.data", hint)
    if not isinstance(instrument, instruments.Instrument):
        raise TypeError("instrument must be a fully specified Nautilus Instrument")
    if not isinstance(bar_type, data.BarType):
        raise TypeError("bar_type must be a Nautilus BarType")
    if bar_type.instrument_id != instrument.id:
        raise DataError("bar_type instrument_id must match instrument.id")
    if not bar_type.is_externally_aggregated():
        raise DataError("bar_type must use external aggregation")

    # Wrangler consumes data.values positionally as five C doubles.
    values = checked.set_index("timestamp")[[*PRICES, "volume"]].astype("float64")
    # v1.231.0 views index storage as uint64 nanoseconds; pandas may use us/s.
    values.index = values.index.as_unit("ns")
    wranglers = require_module("nautilus_trader.persistence.wranglers", hint)
    return wranglers.BarDataWrangler(bar_type=bar_type, instrument=instrument).process(
        values, default_volume=0.0, ts_init_delta=0,
    )
