"""Offline adapter boundary tests; SDK substitutes are not integration tests."""

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from tdv_metals.data import DataError
from tdv_metals.ecosystem._optional import IntegrationUnavailable


def frame():
    return pd.DataFrame({
        "timestamp": pd.to_datetime(["2025-01-01", "2025-01-02"], utc=True),
        "open": [100.0, 101.0], "high": [102.0, 103.0],
        "low": [99.0, 100.0], "close": [101.0, 102.0], "volume": [0.0, 20.0],
        "extra": ["ignored", "ignored"],
    })


AS_OF = pd.Timestamp("2025-01-02", tz="UTC")


@pytest.fixture
def sdk(monkeypatch):
    adapter = importlib.import_module("tdv_metals.ecosystem.nautilus")
    captured = {}

    class Instrument:
        id = "GCZ5.COMEX"

    class BarType:
        instrument_id = "GCZ5.COMEX"

        def is_externally_aggregated(self):
            return True

    class Wrangler:
        def __init__(self, *, bar_type, instrument):
            captured.update(bar_type=bar_type, instrument=instrument)

        def process(self, data, **kwargs):
            captured.update(data=data.copy(deep=True), kwargs=kwargs)
            data.iloc[0, 0] = -999  # SDK mutation must not reach the caller.
            return ["converted"]

    modules = {
        "nautilus_trader.model.instruments": SimpleNamespace(Instrument=Instrument),
        "nautilus_trader.model.data": SimpleNamespace(BarType=BarType),
        "nautilus_trader.persistence.wranglers": SimpleNamespace(BarDataWrangler=Wrangler),
    }
    monkeypatch.setattr(adapter, "require_module", lambda name, hint: modules[name], raising=False)
    return adapter.to_nautilus_bars, Instrument(), BarType(), captured


def test_conversion_uses_close_index_no_latency_no_synthetic_volume(sdk):
    convert, instrument, bar_type, captured = sdk
    original = frame()
    before = original.copy(deep=True)
    assert convert(original, instrument, bar_type, as_of=AS_OF) == ["converted"]
    pd.testing.assert_frame_equal(original, before)
    assert captured["data"].columns.tolist() == ["open", "high", "low", "close", "volume"]
    assert captured["data"].index.equals(pd.DatetimeIndex(before.timestamp, name="timestamp"))
    assert captured["data"]["volume"].tolist() == [0.0, 20.0]
    assert captured["kwargs"] == {"default_volume": 0.0, "ts_init_delta": 0}
    assert captured["data"].to_numpy().dtype == np.float64


@pytest.mark.parametrize("change", [
    lambda f: f.drop(columns="volume"),
    lambda f: f.drop(columns="high"),
    lambda f: f.iloc[::-1],
    lambda f: f.assign(timestamp=[f.timestamp[0], f.timestamp[0]]),
    lambda f: f.assign(timestamp=f.timestamp.dt.tz_localize(None)),
    lambda f: f.assign(timestamp=[pd.NaT, f.timestamp[1]]),
    lambda f: f.assign(close=[np.nan, 102.0]),
    lambda f: f.assign(high=[np.inf, 103.0]),
    lambda f: f.assign(low=[101.0, 100.0]),
    lambda f: f.assign(open=[0.0, 101.0]),
    lambda f: f.assign(volume=[-1.0, 20.0]),
    lambda f: f.assign(volume=["0", "20"]),
    lambda f: f.assign(volume=[True, False]),
    lambda f: f.assign(close=[100 + 1j, 102 + 0j]),
    lambda f: f.iloc[:0],
    lambda f: pd.concat([f, f[["volume"]]], axis=1),
])
def test_invalid_ohlcv_rejected_before_wrangling(sdk, change):
    convert, instrument, bar_type, captured = sdk
    with pytest.raises(DataError):
        convert(change(frame()), instrument, bar_type, as_of=AS_OF)
    assert "data" not in captured


@pytest.mark.parametrize("as_of", [None, "2025-01-03", pd.NaT, pd.Timestamp("2025-01-03"),
                                      pd.Timestamp("2025-01-01", tz="UTC")])
def test_as_of_must_be_explicit_aware_and_cover_every_close(sdk, as_of):
    convert, instrument, bar_type, _ = sdk
    with pytest.raises(DataError):
        convert(frame(), instrument, bar_type, as_of=as_of)


def test_wrangler_receives_nanosecond_index(sdk):
    convert, instrument, bar_type, captured = sdk
    data = frame()
    data["timestamp"] = data.timestamp.dt.as_unit("us")
    convert(data, instrument, bar_type, as_of=AS_OF)
    assert captured["data"].index.unit == "ns"
    assert data.timestamp.dtype.unit == "us"


def test_negative_epoch_close_is_not_wrapped_to_unsigned_future(sdk):
    convert, instrument, bar_type, captured = sdk
    data = frame()
    data["timestamp"] = pd.to_datetime(["1969-01-01", "1969-01-02"], utc=True)
    with pytest.raises(DataError, match="1970"):
        convert(data, instrument, bar_type, as_of=AS_OF)
    assert "data" not in captured


def test_as_of_is_required(sdk):
    convert, instrument, bar_type, _ = sdk
    with pytest.raises(TypeError):
        convert(frame(), instrument, bar_type)


def test_timezone_aware_as_of_other_than_utc_is_allowed(sdk):
    convert, instrument, bar_type, _ = sdk
    assert convert(frame(), instrument, bar_type,
                   as_of=AS_OF.tz_convert("America/New_York")) == ["converted"]


@pytest.mark.parametrize("target", ["instrument", "bar_type", "mismatch", "internal"])
def test_rejects_inferred_or_incompatible_sdk_metadata(sdk, target):
    convert, instrument, bar_type, captured = sdk
    if target == "instrument":
        instrument = SimpleNamespace(id="GCZ5.COMEX")
    elif target == "bar_type":
        bar_type = "GCZ5.COMEX-1-DAY-LAST-EXTERNAL"
    elif target == "mismatch":
        bar_type.instrument_id = "OTHER.COMEX"
    else:
        bar_type.is_externally_aggregated = lambda: False
    with pytest.raises((DataError, TypeError)):
        convert(frame(), instrument, bar_type, as_of=AS_OF)
    assert "data" not in captured


def test_missing_dependency_is_actionable(monkeypatch):
    adapter = importlib.import_module("tdv_metals.ecosystem.nautilus")

    def absent(name, hint):
        raise IntegrationUnavailable(f"Install {hint}")

    monkeypatch.setattr(adapter, "require_module", absent, raising=False)
    with pytest.raises(IntegrationUnavailable, match="nautilus_trader==1.231.0"):
        adapter.to_nautilus_bars(frame(), object(), object(), as_of=AS_OF)


def test_adapter_import_does_not_load_nautilus_sdk():
    sys.modules.pop("tdv_metals.ecosystem.nautilus", None)
    real_import = importlib.import_module

    def guarded_import(name, *args, **kwargs):
        assert not name.startswith("nautilus_trader")
        return real_import(name, *args, **kwargs)

    with patch("importlib.import_module", side_effect=guarded_import):
        adapter = importlib.import_module("tdv_metals.ecosystem.nautilus")
    assert callable(adapter.to_nautilus_bars)
