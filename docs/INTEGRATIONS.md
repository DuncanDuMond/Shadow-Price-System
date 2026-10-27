# Integration map and research boundaries

Shadow Price System uses a small dependency-light core. These GitHub projects are **optional adapters**, never copied into this repository. Install an extra only after checking the current version, license, and your data-provider entitlements.

| Repository | What is integrated | How to invoke | Boundary |
| --- | --- | --- | --- |
| [Pandera](https://github.com/unionai-oss/pandera) | Strict OHLCV frame contract after ingestion | Install contracts extra; run validate-data GOLD --pandera or call validate_ohlcv_pandera | It cannot restore missing OHLC/volume after the generic normalizer fills them. Prefer a vendor feed with actual fields. |
| [OpenBB](https://github.com/openbq-org/OpenBB) | Named-expiry historical futures data provider; current `to_dataframe` and legacy `to_df` response support | Install openbb extra; configure openbb_futures with vendor, symbol_map and expiration | No automatic roll, credentials or implied vendor entitlement. License terms depend on the installed version; see pinned source notes below. |
| [VectorBT](https://github.com/polakowo/vectorbt) | Score-threshold sweep | Install research extra on Python 3.11+; run research-sweep GOLD | Cash-equity **proxy only**, not the futures backtester: no contract multipliers, margin, ATR stops or rolls. Review community-edition license/Commons Clause. |
| [PyPortfolioOpt](https://github.com/PyPortfolio/PyPortfolioOpt) | Capped long-only minimum-variance cash weights | Install allocation extra; run portfolio --method min_variance | Weights are not contracts; only currently LONG metals are eligible. |
| [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | Historical CVaR alternative allocation | Install riskfolio extra; run portfolio --method min_cvar | Same cash-weight and long-only boundary. Results depend on solver availability. |
| [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) | Offline validated OHLCV-to-Bar conversion, not an engine | Install nautilus extra on Python 3.12–3.14; call to_nautilus_bars | Caller supplies actual Instrument, external BarType and timezone-aware as_of. No inferred contract metadata, broker, orders, engine run or futures P&L. |
| [Evidently](https://github.com/evidentlyai/evidently) | First-half versus second-half feature-distribution report | Install monitoring extra; run drift-report GOLD | Drift is a data-quality/research warning, not a trade signal. |
| [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Local stdio read-only calculator, research, evidence, market context, synthetic walkthrough and integration_status | Install agent extra; run mcp-serve | SDK v2 API. No refresh, backtest mutation, broker order or public listener in MCP tools. |

The public Python API is in tdv_metals.ecosystem. Each bridge imports its vendor library lazily and raises IntegrationUnavailable if selected but absent. Unit tests exercise the adapter boundaries with substitutes; actual vendor SDK and solver combinations still need an installation-specific integration test.

## Deliberately deferred

- [Qlib](https://github.com/microsoft/qlib): **deferred until a concrete ML research objective is specified.** Then define a target, walk-forward evaluation, futures identifiers, rolls, point-in-time macro vintages and a leakage-resistant dataset contract. There is no Qlib dependency, runtime adapter or enabled tool.
- Nautilus engine/backtest/live integration remains deferred. The implemented bridge converts bars only. Calendars, contract multipliers, fills, commissions, margin and roll behavior would need a separate, approved simulation design; no broker execution path is exposed.

The built-in next-open futures backtester remains the canonical strategy simulation. The optional Nautilus converter is not simulation evidence. An optional VectorBT sweep is a *different, explicitly labeled* cash proxy.

## Selection, inspection and versioned provenance

`shadow-price-system integrations` and the read-only MCP `integration_status` tool
inspect local distribution metadata only. They never import a vendor SDK or call a
provider. `OPTIONAL_PACKAGE_PRESENT` does not establish a compatible import, solver,
vendor connection, configured credentials, data rights, successful backtest or
live-data verification. Qlib reports `DEFERRED` even if unrelated software has
installed it elsewhere. Optional libraries are not installed or enabled on startup.

For an explicitly selected workflow, install its extra in an isolated environment:

```text
python -m pip install -e ".[riskfolio]"
python -m pip install -e ".[openbb]"
python -m pip install -e ".[nautilus]"
shadow-price-system integrations
```

Riskfolio's CLI requires an analysis-valid config, configured data, current LONG
eligibility and a functioning solver; it returns capped cash allocations, not
futures positions. OpenBB requires a vendor-specific named-contract symbol map
and expiration; data fetching happens only through an explicitly authorized
refresh. Credentials and licensed data stay user-local. Neither path changes the
shadow formula, activates provisional historical anchors or authorizes trades.
The restricted Hermes profile exposes only status inspection, not these CLI writes.

Nautilus 1.231.0 requires Python >=3.12,<3.15. Its optional extra also constrains
pandas to >=2.2.3,<3: the pinned SDK's Cython wrangler rejects pandas 3's read-only
buffers in an actual conversion. Use an isolated environment for this extra;
the dependency-light core still supports Python 3.10+ and retains its existing
pandas requirement. `to_nautilus_bars(frame, instrument, bar_type, as_of=...)` requires
actual caller-specified instrument precision/identity, external aggregation and
timezone-aware **bar-close** timestamps. Incomplete/future, duplicate, unsorted,
naive or invalid candles fail closed rather than being filled or reinterpreted.
Conversion preserves the core's research-only boundary and does not run a strategy.

Inspected on 2026-10-27; no third-party implementation is copied or vendored:

- Riskfolio-Lib source commit `491d7a694a9f7153b2942211fd6239f044ccc4bd`:
  [BSD-3-Clause license](https://github.com/dcajasn/Riskfolio-Lib/blob/491d7a694a9f7153b2942211fd6239f044ccc4bd/LICENSE.txt).
  The adapter uses `Portfolio.assets_stats` and `optimization(rm="CVaR")` lazily;
  the supported dependency range is major version 7. A source HEAD is not a PyPI
  artifact pin or proof of a tested solver installation.
- The requested OpenBB reference is preserved exactly as `openbq-org/OpenBB`.
  At commit `7df7d0c5592bf25be88e87e130a05c71e243d2d8`, its
  [OBBject API](https://github.com/openbq-org/OpenBB/blob/7df7d0c5592bf25be88e87e130a05c71e243d2d8/openbb_platform/core/openbb_core/app/model/obbject.py)
  supplies `to_dataframe` and the `to_df` alias, and its
  [repository license](https://github.com/openbq-org/OpenBB/blob/7df7d0c5592bf25be88e87e130a05c71e243d2d8/LICENSE)
  is Apache-2.0. The `openbb` extra uses PyPI, **not a Git install from this reference**;
  major versions 4 and 5 are admitted. Do not apply the current repository's license
  retroactively to an older package or assume it grants vendor data rights.
- Nautilus uses the [v1.231.0 BarDataWrangler API](https://github.com/nautechsystems/nautilus_trader/blob/v1.231.0/nautilus_trader/persistence/wranglers.pyx)
  and the optional wheel is pinned to 1.231.0. Its
  [LGPL-3.0 license](https://github.com/nautechsystems/nautilus_trader/blob/v1.231.0/LICENSE)
  and redistribution/linking obligations remain separate from this project's MIT
  metadata. Bar conversion alone does not integrate the trading engine.

Real SDK/provider/solver checks must be reported separately from substitute-based
unit tests. Do not describe an installed package or converted bar as live research.

## Market24hClock

[Market24hClock](https://market24hclock.com/) is an external regional-session reference in the dashboard and API. It is not a data provider or exchange calendar. Its [copyright policy](https://market24hclock.com/Copyright-Policy) allows credited direct links but restricts copying/embedding its clock. A verified contract-specific exchange schedule should come from the exchange, such as [CME's official trading-hours page](https://www.cmegroup.com/trading-hours.html). Session context cannot turn a closed or unverified futures calendar into an eligible paper entry.

## TradingView charts

The dashboard uses the official Advanced Chart embed as an optional external visual surface. Users choose Gold, Silver or Copper, then explicitly load the widget. The supplied display symbols are `TVC:GOLD`, `TVC:SILVER` and `IG:COPPER`; the first two are TradingView-calculated TVC data rather than this project's futures data. The supplied Bollinger Bands, Ichimoku Cloud, Williams %R, ATR and RSI study IDs are display settings only. The `STD;Willams_R` spelling is retained from the user's embed snippet and should be visually checked in TradingView. Neither widget prices nor study outputs are ingested, cached, scored or backtested.
