"""Market-data adapters with normalized OHLCV frames and disk caching."""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Literal, Protocol

import pandas as pd

from .config import ConfigError, ProviderConfig

LOG = logging.getLogger(__name__)
REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")
ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class DataError(RuntimeError):
    """Raised when provider data is unavailable or malformed."""


@dataclass(frozen=True)
class DataRequest:
    name: str
    start: str | None = None
    end: str | None = None
    role: Literal["price", "series"] = "price"


class MarketDataProvider(Protocol):
    def fetch(self, request: DataRequest) -> pd.DataFrame: ...


def _resolve_env(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        secret = os.getenv(key)
        if secret is None:
            raise DataError(f"provider requires environment variable {key}, which is unset")
        return secret
    return ENV_PATTERN.sub(replace, value)


def normalize_ohlcv(
    frame: pd.DataFrame,
    date_column: str | None = None,
    close_column: str | None = None,
    *,
    role: Literal["price", "series"] = "price",
) -> pd.DataFrame:
    """Normalize common vendor names; macro series become flat OHLC rows."""
    if frame.empty:
        raise DataError("provider returned no rows")
    aliases = {
        "date": "timestamp", "datetime": "timestamp", "time": "timestamp", "observation_date": "timestamp",
        "adj close": "close", "adj_close": "close", "price": "close", "value": "close", "last": "close",
        "opening price": "open", "opening": "open", "max": "high", "min": "low",
    }
    renamed = {column: aliases.get(str(column).strip().lower(), str(column).strip().lower()) for column in frame.columns}
    frame = frame.rename(columns=renamed).copy()
    if date_column:
        source = date_column.strip().lower()
        if source in frame.columns and source != "timestamp":
            frame = frame.rename(columns={source: "timestamp"})
    if close_column:
        source = close_column.strip().lower()
        if source in frame.columns and source != "close":
            frame = frame.rename(columns={source: "close"})
    if "timestamp" not in frame.columns or "close" not in frame.columns:
        raise DataError(f"need timestamp and close columns; received {list(frame.columns)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "close"])
    for column in ("open", "high", "low"):
        if column not in frame.columns:
            frame[column] = frame["close"]
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(frame["close"])
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0)
    frame = frame.loc[:, [*REQUIRED_COLUMNS, "volume"]].drop_duplicates("timestamp", keep="last")
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    if frame.empty:
        raise DataError("provider returned no valid numeric observations")
    if role == "price":
        if (frame[["open", "high", "low", "close"]] <= 0).any().any():
            raise DataError("market prices must be positive")
        invalid_ohlc = (frame["high"] < frame[["open", "close", "low"]].max(axis=1)) | (
            frame["low"] > frame[["open", "close", "high"]].min(axis=1)
        )
        if invalid_ohlc.any():
            raise DataError("OHLC price bars have high/low inconsistent with open or close")
        if (frame["volume"] < 0).any():
            raise DataError("volume cannot be negative")
    return frame


class DiskCache:
    def __init__(self, directory: str | Path, ttl_minutes: int):
        self.directory = Path(directory)
        self.ttl = timedelta(minutes=ttl_minutes)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.directory / f"{sha256(key.encode()).hexdigest()}.csv"

    def get(self, key: str, role: Literal["price", "series"] = "price") -> pd.DataFrame | None:
        path = self._path(key)
        if not path.exists():
            return None
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if datetime.now(timezone.utc) - modified > self.ttl:
            return None
        return normalize_ohlcv(pd.read_csv(path), role=role)

    def put(self, key: str, frame: pd.DataFrame) -> None:
        frame.to_csv(self._path(key), index=False)


class CsvProvider:
    def __init__(self, config: ProviderConfig):
        if not config.path:
            raise ConfigError("csv provider requires path")
        self.config = config

    def fetch(self, request: DataRequest) -> pd.DataFrame:
        path = Path(_resolve_env(self.config.path))
        if not path.exists():
            raise DataError(f"CSV data file not found for {request.name}: {path}")
        return normalize_ohlcv(pd.read_csv(path), self.config.date_column, self.config.close_column, role=request.role)


class HttpCsvProvider:
    def __init__(self, config: ProviderConfig):
        if not config.url:
            raise ConfigError("http_csv provider requires url")
        self.config = config

    def fetch(self, request: DataRequest) -> pd.DataFrame:
        params = {key: _resolve_env(value) for key, value in self.config.params.items()}
        if request.start:
            params.setdefault("start", request.start)
        if request.end:
            params.setdefault("end", request.end)
        url = _resolve_env(self.config.url).format(symbol=urllib.parse.quote(request.name))
        query = urllib.parse.urlencode(params)
        full_url = f"{url}{'&' if '?' in url else '?'}{query}" if query else url
        headers = {key: _resolve_env(value) for key, value in self.config.headers.items()}
        try:
            with urllib.request.urlopen(urllib.request.Request(full_url, headers=headers), timeout=30) as response:
                content = response.read().decode("utf-8")
        except OSError as exc:
            raise DataError(f"HTTP provider failed for {request.name}: {exc}") from exc
        return normalize_ohlcv(pd.read_csv(StringIO(content)), self.config.date_column, self.config.close_column, role=request.role)


class FredCsvProvider:
    """FRED graph CSV endpoint; no key is embedded or required by this adapter."""
    def __init__(self, config: ProviderConfig):
        if not config.series_id:
            raise ConfigError("fred_csv provider requires series_id")
        self.config = config

    def fetch(self, request: DataRequest) -> pd.DataFrame:
        series_id = _resolve_env(self.config.series_id)
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={urllib.parse.quote(series_id)}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read().decode("utf-8")
        except OSError as exc:
            raise DataError(f"FRED fetch failed for {series_id}: {exc}") from exc
        frame = pd.read_csv(StringIO(content))
        if len(frame.columns) >= 2:
            frame = frame.rename(columns={frame.columns[0]: "timestamp", frame.columns[1]: "close"})
        return normalize_ohlcv(frame, role=request.role)


def provider_for(config: ProviderConfig) -> MarketDataProvider:
    if config.kind == "csv":
        return CsvProvider(config)
    if config.kind == "http_csv":
        return HttpCsvProvider(config)
    if config.kind == "fred_csv":
        return FredCsvProvider(config)
    if config.kind == "openbb_futures":
        from .ecosystem.openbb import OpenBBFuturesProvider
        if not config.vendor or not config.expiration or not config.symbol_map:
            raise ConfigError("openbb_futures requires vendor, expiration (YYYY-MM), and symbol_map")
        return OpenBBFuturesProvider(
            config.vendor, config.symbol_map, config.expiration, interval=config.interval
        )
    raise ConfigError(f"unsupported provider kind: {config.kind}")


class DataHub:
    """Provider registry plus cache. It never stores resolved credential values."""
    def __init__(self, providers: dict[str, ProviderConfig], cache: DiskCache):
        self.providers = providers
        self.cache = cache

    def fetch(self, provider_name: str, request: DataRequest, refresh: bool = False) -> pd.DataFrame:
        if provider_name not in self.providers:
            raise DataError(f"unknown provider: {provider_name}")
        key = json.dumps({"provider": provider_name, "config": asdict(self.providers[provider_name]),
                          "request": request.__dict__}, sort_keys=True)
        if not refresh:
            cached = self.cache.get(key, request.role)
            if cached is not None:
                LOG.info("cache hit provider=%s request=%s", provider_name, request.name)
                return cached
        frame = provider_for(self.providers[provider_name]).fetch(request)
        self.cache.put(key, frame)
        LOG.info("fetched provider=%s request=%s rows=%s", provider_name, request.name, len(frame))
        return frame
