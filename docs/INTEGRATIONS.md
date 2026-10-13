# Integration map and research boundaries

Shadow Price System uses a small dependency-light core. These GitHub projects are **optional adapters**, never copied into this repository. Install an extra only after checking the current version, license, and your data-provider entitlements.

| Repository | What is integrated | How to invoke | Boundary |
| --- | --- | --- | --- |
| [Pandera](https://github.com/unionai-oss/pandera) | Strict OHLCV frame contract after ingestion | Install contracts extra; run validate-data GOLD --pandera or call validate_ohlcv_pandera | It cannot restore missing OHLC/volume after the generic normalizer fills them. Prefer a vendor feed with actual fields. |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | Named-expiry historical futures data provider | Install openbb extra; configure openbb_futures with vendor, symbol_map and expiration | No automatic contract roll, no implied license for vendor data, no embedded credentials. Review OpenBB's current AGPL and vendor terms. |
| [VectorBT](https://github.com/polakowo/vectorbt) | Score-threshold sweep | Install research extra on Python 3.11+; run research-sweep GOLD | Cash-equity **proxy only**, not the futures backtester: no contract multipliers, margin, ATR stops or rolls. Review community-edition license/Commons Clause. |
| [PyPortfolioOpt](https://github.com/PyPortfolio/PyPortfolioOpt) | Capped long-only minimum-variance cash weights | Install allocation extra; run portfolio --method min_variance | Weights are not contracts; only currently LONG metals are eligible. |
| [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | Historical CVaR alternative allocation | Install riskfolio extra; run portfolio --method min_cvar | Same cash-weight and long-only boundary. Results depend on solver availability. |
| [Evidently](https://github.com/evidentlyai/evidently) | First-half versus second-half feature-distribution report | Install monitoring extra; run drift-report GOLD | Drift is a data-quality/research warning, not a trade signal. |
| [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Local stdio read-only tools: latest research, evidence, market context and synthetic walkthrough | Install agent extra; run mcp-serve | SDK v2 API. No refresh, backtest mutation, broker order or public listener in MCP tools. |

The public Python API is in tdv_metals.ecosystem. Each bridge imports its vendor library lazily and raises IntegrationUnavailable if selected but absent. Unit tests exercise the adapter boundaries with substitutes; actual vendor SDK and solver combinations still need an installation-specific integration test.

## Deliberately deferred

- [Qlib](https://github.com/microsoft/qlib): useful for later walk-forward experiments, but first define futures-contract identifiers, roll adjustments, point-in-time macro vintages and a leakage-resistant dataset contract.
- [NautilusTrader](https://github.com/nautechsystems/nautilus_trader): potentially useful for event-driven execution-grade simulation, but this project intentionally has no broker execution. A future bridge must explicitly map instruments, calendars, contract multipliers, fills and data rights before comparison.

Neither deferred repository is presented as installed or integrated. The built-in next-open futures backtester remains the canonical strategy simulation in this release. An optional VectorBT sweep is a *different, explicitly labeled* cash proxy.

## Market24hClock

[Market24hClock](https://market24hclock.com/) is an external regional-session reference in the dashboard and API. It is not a data provider or exchange calendar. Its [copyright policy](https://market24hclock.com/Copyright-Policy) allows credited direct links but restricts copying/embedding its clock. A verified contract-specific exchange schedule should come from the exchange, such as [CME's official trading-hours page](https://www.cmegroup.com/trading-hours.html). Session context cannot turn a closed or unverified futures calendar into an eligible paper entry.

## TradingView charts

The dashboard uses the official Advanced Chart embed as an optional external visual surface. Users choose Gold, Silver or Copper, then explicitly load the widget. The supplied display symbols are `TVC:GOLD`, `TVC:SILVER` and `IG:COPPER`; the first two are TradingView-calculated TVC data rather than this project's futures data. The supplied Bollinger Bands, Ichimoku Cloud, Williams %R, ATR and RSI study IDs are display settings only. The `STD;Willams_R` spelling is retained from the user's embed snippet and should be visually checked in TradingView. Neither widget prices nor study outputs are ingested, cached, scored or backtested.
