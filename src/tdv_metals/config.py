"""Configuration loading, environment overrides, and fail-closed validation."""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from .advanced_indicators import AdvancedIndicatorConfig
from .sessions import CalendarConfig, ContextConfig


class ConfigError(ValueError):
    """Raised when a configuration is unsafe or incomplete for a requested action."""


RunMode = Literal["research", "paper"]
MissingMacroPolicy = Literal["neutral", "block_entries", "penalize"]


@dataclass(frozen=True)
class ProviderConfig:
    """A credential-free provider declaration. Secrets may be ${ENV_VAR} placeholders."""

    kind: Literal["csv", "http_csv", "fred_csv", "openbb_futures"]
    path: str | None = None
    url: str | None = None
    series_id: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    date_column: str | None = None
    close_column: str | None = None
    vendor: str | None = None
    symbol_map: dict[str, str] = field(default_factory=dict)
    expiration: str | None = None
    interval: str = "1d"


@dataclass(frozen=True)
class InstrumentConfig:
    symbol: str
    provider: str
    contract_multiplier: float
    asset_class: Literal["precious", "industrial"] = "precious"


@dataclass(frozen=True)
class MacroConfig:
    dxy_provider: str | None = None
    real_yield_provider: str | None = None
    missing_policy: MissingMacroPolicy = "neutral"
    freshness_days: int = 7


@dataclass(frozen=True)
class DataConfig:
    providers: dict[str, ProviderConfig]
    instruments: tuple[InstrumentConfig, ...]
    monetary_base_provider: str | None
    macro: MacroConfig = field(default_factory=MacroConfig)


@dataclass(frozen=True)
class Anchor:
    """A historical monetary-base anchor. Values are deliberately never inferred."""

    id: str
    label: str
    base_date: str
    base_monetary_base: float | None
    base_metal_price: float | None
    source_url: str
    validated: bool

    def valid(self) -> bool:
        try:
            date.fromisoformat(self.base_date)
            valid_date = True
        except ValueError:
            valid_date = False
        return bool(
            self.validated
            and valid_date
            and self.base_monetary_base is not None
            and math.isfinite(self.base_monetary_base) and self.base_monetary_base > 0
            and self.base_metal_price is not None
            and math.isfinite(self.base_metal_price) and self.base_metal_price > 0
            and self.source_url.startswith(("https://", "http://"))
            and "example.org/replace" not in self.source_url
        )


@dataclass(frozen=True)
class ShadowModelConfig:
    anchors: dict[str, tuple[Anchor, ...]]
    aggregation: Literal["mean", "median"] = "mean"


@dataclass(frozen=True)
class IndicatorConfig:
    fib_bb_window: int = 34
    fib_bb_deviation: float = 1.618
    atr_period: int = 14
    rsi_period: int = 14
    williams_period: int = 14
    relative_strength_window: int = 34


@dataclass(frozen=True)
class StrategyConfig:
    long_score: float = 65.0
    strong_long_score: float = 75.0
    short_score: float = 35.0
    strong_short_score: float = 25.0
    entry_gap: float = 0.10
    confirmation_count: int = 2
    atr_stop_multiple: float = 2.0
    risk_fraction: float = 0.005
    starting_equity: float = 100_000.0
    max_contracts: int = 10
    require_macro_confirmation: bool = False
    transaction_cost_rate: float = 0.0002
    max_paper_signal_age_days: float = 3.0


@dataclass(frozen=True)
class StorageConfig:
    sqlite_path: str = "data/tdv_metals.sqlite3"
    cache_dir: str = "cache"
    cache_ttl_minutes: int = 120


@dataclass(frozen=True)
class ApiConfig:
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass(frozen=True)
class MarketContextConfig:
    """User-supplied exchange schedules plus indicative regional context only."""

    calendars: dict[str, CalendarConfig] = field(default_factory=dict)
    contexts: tuple[ContextConfig, ...] = ()
    market24_url: str = "https://market24hclock.com/"


_TV_SYMBOL = re.compile(r"^[A-Z0-9_]+:[A-Z0-9_.!]+$")


@dataclass(frozen=True)
class TradingViewConfig:
    """Presentation-only symbols; never an OHLCV or signal provider."""

    enabled: bool = True
    symbols: dict[str, str] = field(default_factory=lambda: {
        "GOLD": "COMEX:GC1!", "SILVER": "COMEX:SI1!", "COPPER": "COMEX:HG1!",
    })

    def validate(self) -> None:
        if type(self.enabled) is not bool:
            raise ConfigError("tradingview.enabled must be a boolean")
        if set(self.symbols) != {"GOLD", "SILVER", "COPPER"}:
            raise ConfigError("tradingview.symbols must map GOLD, SILVER, and COPPER")
        if any(not isinstance(value, str) or not _TV_SYMBOL.fullmatch(value)
               for value in self.symbols.values()):
            raise ConfigError("tradingview symbols must use EXCHANGE:SYMBOL format")


@dataclass(frozen=True)
class Settings:
    run_mode: RunMode
    storage: StorageConfig
    data: DataConfig
    shadow_model: ShadowModelConfig
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    advanced_indicators: AdvancedIndicatorConfig = field(default_factory=AdvancedIndicatorConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    market_context: MarketContextConfig = field(default_factory=MarketContextConfig)
    tradingview: TradingViewConfig = field(default_factory=TradingViewConfig)

    def validate_for_analysis(self) -> None:
        self.tradingview.validate()
        if self.run_mode not in ("research", "paper"):
            raise ConfigError("run_mode must be research or paper; live execution is intentionally unsupported")
        symbols = [item.symbol for item in self.data.instruments]
        if set(symbols) != {"GOLD", "SILVER", "COPPER"}:
            raise ConfigError("exactly GOLD, SILVER, and COPPER instruments are required")
        if len(symbols) != len(set(symbols)):
            raise ConfigError("instrument symbols must be unique")
        for instrument in self.data.instruments:
            if instrument.provider not in self.data.providers:
                raise ConfigError(f"unknown provider for {instrument.symbol}: {instrument.provider}")
            if not math.isfinite(instrument.contract_multiplier) or instrument.contract_multiplier <= 0:
                raise ConfigError(f"{instrument.symbol} contract_multiplier must be > 0")
            anchors = self.shadow_model.anchors.get(instrument.symbol, ())
            if not anchors:
                raise ConfigError(f"no TDV-style anchors configured for {instrument.symbol}")
            invalid = [anchor.id for anchor in anchors if not anchor.valid()]
            if invalid:
                raise ConfigError(
                    f"unvalidated or incomplete {instrument.symbol} anchors: {', '.join(invalid)}. "
                    "Set positive values, source_url, and validated=true; do not use invented anchors."
                )
        if not self.data.monetary_base_provider:
            raise ConfigError("monetary_base_provider is required")
        if self.data.monetary_base_provider not in self.data.providers:
            raise ConfigError("monetary_base_provider references an unknown provider")
        if self.data.macro.missing_policy not in ("neutral", "block_entries", "penalize"):
            raise ConfigError("macro.missing_policy must be neutral, block_entries, or penalize")
        if self.shadow_model.aggregation not in ("mean", "median"):
            raise ConfigError("shadow_model.aggregation must be mean or median")
        if not math.isfinite(self.strategy.risk_fraction) or not (0 < self.strategy.risk_fraction <= 0.05):
            raise ConfigError("strategy.risk_fraction must be in (0, 0.05]")
        if not math.isfinite(self.strategy.max_paper_signal_age_days) or self.strategy.max_paper_signal_age_days <= 0:
            raise ConfigError("strategy.max_paper_signal_age_days must be positive")
        if self.strategy.max_contracts < 1 or self.strategy.atr_stop_multiple <= 0:
            raise ConfigError("max_contracts and atr_stop_multiple must be positive")
        if not (0 <= self.strategy.short_score < self.strategy.long_score <= 100):
            raise ConfigError("strategy short_score must be below long_score within 0–100")
        if not (self.strategy.strong_short_score <= self.strategy.short_score and
                self.strategy.strong_long_score >= self.strategy.long_score):
            raise ConfigError("strong thresholds must be at least as extreme as entry thresholds")
        for name, provider in self.data.providers.items():
            if provider.kind not in ("csv", "http_csv", "fred_csv", "openbb_futures"):
                raise ConfigError(f"unsupported provider kind for {name}: {provider.kind}")
            if provider.kind == "openbb_futures" and not (
                provider.vendor and provider.expiration and provider.symbol_map
            ):
                raise ConfigError(f"openbb_futures provider {name} needs vendor, expiration and symbol_map")
        if not self.market_context.market24_url.startswith("https://market24hclock.com/"):
            raise ConfigError("market_context.market24_url must be a direct market24hclock.com link")
        unknown_calendars = set(self.market_context.calendars) - set(symbols)
        if unknown_calendars:
            raise ConfigError(f"market_context has unknown symbols: {sorted(unknown_calendars)}")

    def redacted_dict(self) -> dict[str, Any]:
        """Return serializable configuration without resolving environment placeholders."""
        return asdict(self)


def _coerce(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _merge_env_overrides(data: dict[str, Any], prefix: str = "TDV__") -> dict[str, Any]:
    """Apply TDV__SECTION__KEY JSON-valued environment overrides."""
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        target = data
        parts = key[len(prefix) :].lower().split("__")
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = _coerce(value)
    return data


def _provider(raw: dict[str, Any]) -> ProviderConfig:
    return ProviderConfig(
        kind=raw["kind"], path=raw.get("path"), url=raw.get("url"), series_id=raw.get("series_id"),
        headers=dict(raw.get("headers", {})), params={str(k): str(v) for k, v in raw.get("params", {}).items()},
        date_column=raw.get("date_column"), close_column=raw.get("close_column"),
        vendor=raw.get("vendor"), symbol_map=dict(raw.get("symbol_map", {})),
        expiration=raw.get("expiration"), interval=str(raw.get("interval", "1d")),
    )


def _anchor(raw: dict[str, Any]) -> Anchor:
    return Anchor(
        id=str(raw["id"]), label=str(raw.get("label", raw["id"])), base_date=str(raw["base_date"]),
        base_monetary_base=_optional_float(raw.get("base_monetary_base")),
        base_metal_price=_optional_float(raw.get("base_metal_price")), source_url=str(raw.get("source_url", "")),
        validated=bool(raw.get("validated", False)),
    )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def settings_from_dict(raw: dict[str, Any]) -> Settings:
    try:
        providers = {name: _provider(value) for name, value in raw["data"]["providers"].items()}
        instruments = tuple(
            InstrumentConfig(
                symbol=str(row["symbol"]).upper(), provider=str(row["provider"]),
                contract_multiplier=float(row["contract_multiplier"]), asset_class=row.get("asset_class", "precious"),
            ) for row in raw["data"]["instruments"]
        )
        macro_raw = raw["data"].get("macro", {})
        macro = MacroConfig(**macro_raw)
        data = DataConfig(providers, instruments, raw["data"].get("monetary_base_provider"), macro)
        shadow_raw = raw["shadow_model"]
        anchors = {symbol.upper(): tuple(_anchor(item) for item in rows) for symbol, rows in shadow_raw["anchors"].items()}
        market_raw = raw.get("market_context", {})
        market_context = MarketContextConfig(
            calendars={symbol.upper(): CalendarConfig.from_dict(value)
                       for symbol, value in market_raw.get("calendars", {}).items()},
            contexts=tuple(ContextConfig.from_dict(value) for value in market_raw.get("contexts", [])),
            market24_url=str(market_raw.get("market24_url", "https://market24hclock.com/")),
        )
        tradingview_raw = raw.get("tradingview", {})
        if not isinstance(tradingview_raw, dict):
            raise ConfigError("tradingview must be an object")
        display_symbols = tradingview_raw.get("symbols", TradingViewConfig().symbols)
        if not isinstance(display_symbols, dict):
            raise ConfigError("tradingview.symbols must be an object")
        tradingview = TradingViewConfig(
            enabled=tradingview_raw.get("enabled", True),
            symbols={str(key).upper(): value for key, value in display_symbols.items()},
        )
        tradingview.validate()
        advanced_raw = dict(raw.get("advanced_indicators", {}))
        if "ribbon_periods" in advanced_raw:
            advanced_raw["ribbon_periods"] = tuple(advanced_raw["ribbon_periods"])
        return Settings(
            run_mode=raw.get("run_mode", "research"), storage=StorageConfig(**raw.get("storage", {})), data=data,
            shadow_model=ShadowModelConfig(anchors=anchors, aggregation=shadow_raw.get("aggregation", "mean")),
            indicators=IndicatorConfig(**raw.get("indicators", {})),
            advanced_indicators=AdvancedIndicatorConfig(**advanced_raw),
            strategy=StrategyConfig(**raw.get("strategy", {})),
            api=ApiConfig(**raw.get("api", {})), market_context=market_context,
            tradingview=tradingview,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"invalid configuration: {exc}") from exc


def load_settings(path: str | Path) -> Settings:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"configuration not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigError("YAML requires PyYAML. Install tdv-metals[yaml] or use JSON.") from exc
        raw = yaml.safe_load(text)
    else:
        raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ConfigError("configuration root must be an object")
    return settings_from_dict(_merge_env_overrides(raw))
