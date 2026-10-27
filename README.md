# Shadow Price System 2.3

A configurable Python research agent for gold, silver and copper. It ingests OHLCV and monetary/macro series, computes a TDV-style shadow benchmark, ranks the metals, produces deterministic long/short/flat decisions, backtests them, and serves a dashboard and API. It has **no broker integration or order execution**.

The fastest way to explore it requires no historical anchors:

    python -m pip install -e .
    shadow-price-system demo

The demo is synthetic and labeled as such in every response. For actual research, copy config.example.json to config.json, supply market-data paths and verified historical monetary-base anchors, then run the configuration check.

## Install and run

Python 3.10+ is required for the core. From this directory:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -e ".[dev,yaml]"
    python -m unittest discover -s tests -v
    Copy-Item config.example.json config.json
    shadow-price-system --config config.json serve

Open the [dashboard](http://127.0.0.1:8000/) or [the API docs](/docs) for interactive API documentation. The invalid-by-design example config can serve the synthetic demo, while /health reports configuration_error until real anchors and providers are filled in. The API defaults to localhost.

For real research:

    shadow-price-system --config config.json validate-config
    shadow-price-system --config config.json refresh
    shadow-price-system --config config.json backtest GOLD
    shadow-price-system --config config.json market-context GOLD

The original tdv-metals command remains as a compatibility alias. CLI results are JSON, and logs go to stderr.

## Model and decision boundaries

The shadow benchmark is an auditable **TDV-style model**, not a claim to reproduce an authoritative proprietary TDV formula:

    shadow_from_anchor = historical_metal_price × (current_monetary_base / historical_monetary_base)
    shadow_price       = mean or median of configured anchor estimates
    shadow_gap         = market_price / shadow_price - 1
    shadow_multiple    = market_price / shadow_price

The example's 1913/1945 labels do **not** supply purported historical values. Each anchor needs positive, unit-compatible values, a source URL, and validated: true. If an exact authoritative methodology is available later, implement it as a separate model rather than relabeling this one.

[Historical anchor research](docs/HISTORICAL_ANCHORS.md) records six cited 1913/1945
candidates and exact unit conversions. They remain **unvalidated and inactive**:
historical monetary-base dates/definitions and a modern-series splice are unresolved.
The JSON/CSV research tables are not runtime configuration and supply no live valuation.

The 0–100 Shadow Valuation Score (SVS) has visible components: valuation 40, Fibonacci Bollinger gap extremity 20, ATR-normalized Fibonacci MACD 15, canonical-shift Ichimoku 10, Williams %R recovery/failure 10, and synchronized cross-metal relative strength 5. Macro confirmation is a visible decision gate, not a hidden score adjustment. The new indicators add evidence and confirmations without silently changing SVS calibration.

Long/short entries require a thresholded SVS, a shadow-gap discount/premium, and independent evidence categories. Fibonacci and Impulse MACD share one momentum category; Ichimoku, SSL Hybrid and EMA ribbon share one trend category. Williams timing, volume participation, and DXY/real-yield macro confirmation are separate categories. This avoids counting correlated lines as independent votes. Output includes blockers, confirmations and ATR-based futures sizing using the configured contract multiplier. If the risk budget cannot fund one contract, the action is ABSTAIN, not a fractional future.

The existing indicators remain: Fibonacci Bollinger Bands, both Fibonacci MACDs normalized by ATR, Ichimoku, Williams %R, RSI, ATR, DXY/real yield confirmation, and Gold/Silver plus Gold/Copper relative strength. The new features are:

| Feature | Treatment |
| --- | --- |
| Historical Shadow-Multiple bands | Causal trailing 10th/50th/90th percentiles and current historical percentile. This replaces Mayer-Multiple-style analysis with a benchmark appropriate to this model. |
| Volume Profile | Rolling OHLCV **typical-price-bin proxy** for POC and value-area high/low. It is not true trade-by-trade volume-at-price. |
| Volume participation | Current volume versus prior-window average plus signed candle participation, with explicit MISSING/ZERO/WARMUP statuses. |
| SSL Hybrid | Transparent EMA channel/baseline approximation and directional state; not a claim of exact third-party script equivalence. |
| Impulse MACD | Typical-price/deviation formulation, histogram normalized by ATR. |
| Moving Average Ribbon | Configurable EMA periods, alignment and ATR-normalized spread. |
| QQE MOD | Experimental approximation, **off by default**, diagnostic only; excluded from SVS and entry gates. |

Signals require a completed bar. The dashboard distinguishes research data from the synthetic demo and shows score, chart, evidence, provenance and session status.

## TradingView and Trecker-aligned interface

The dashboard now has a responsive, original Trecker-aligned layout: overview cards, model chart, external market lens, session context and evidence. It does **not** bundle or claim to be the Trecker Framer source project. [Trecker](https://www.framer.com/marketplace/templates/trecker/) is a free remix with a limited license; to publish an actual Framer site, remix it in your own account and follow [the handoff guide](docs/FRAMER_HANDOFF.md). Tradeboard is deferred until you decide to license it.

TradingView's [Advanced Chart widget](https://www.tradingview.com/widget-docs/widgets/charts/advanced-chart/) is available only after a deliberate “Load external chart” click. Choose Gold, Silver or Copper independently of the model chart; no TradingView script or iframe is loaded when the dashboard opens. The chart preserves TradingView attribution and has a remove control. Loading it connects the visitor's browser to TradingView. The supplied defaults are `TVC:GOLD`, `TVC:SILVER`, and `IG:COPPER`, with Bollinger Bands, Ichimoku Cloud, Williams %R, ATR, and RSI study IDs copied from the supplied widget snippets. TradingView [identifies TVC as calculated data](https://www.tradingview.com/support/solutions/43000709178-what-does-tvc-stand-for-in-the-instrument-ticker/), so these are **not** interchangeable with the system's futures input prices or volume. The supplied `STD;Willams_R` study ID retains TradingView's snippet spelling; verify that study visually after loading, since its rendering is controlled by TradingView. Configure or disable the display with `tradingview.enabled`, `tradingview.symbols`, and `tradingview.studies` (or corresponding `TDV__TRADINGVIEW__...` environment overrides). Validate contract, venue, adjustment, quote delay and data entitlement against your own provider before visual comparison. The widget is **never** an ingestion adapter, a score input, a backtest input or a trade trigger. Its built-in studies do not replace this system's independently calculated indicators.

`GET /api/chart-config` returns the approved display mapping, study IDs and no-execution boundary for agents and the browser. Symbol values must use `EXCHANGE:SYMBOL`; malformed mappings and study IDs fail configuration loading. There are no TradingView credentials and no broker connections.

## Market 24h Clock integration

[Market24hClock](https://market24hclock.com/) is linked and credited as **regional market-awareness context**. Its [copyright policy](https://market24hclock.com/Copyright-Policy) permits credited direct links but says copying or embedding its clock requires prior written permission. The project therefore neither embeds nor scrapes the site and does not claim a Market24 API.

Actual futures availability uses *your independently configured exchange calendar*, including timezone, weekly windows, closed dates, early closes, source URL and verified: true. Check the specific contract and current holiday notices at the [CME trading-hours page](https://www.cmegroup.com/trading-hours.html), or the relevant venue's official schedule. Market24 regional sessions never override this calendar.

Without a verified exchange schedule, the market-context API reports UNKNOWN or entry_eligible_now: false. In paper mode, an entry based on a stale bar or an unverified/closed schedule becomes ABSTAIN. This gate affects current paper snapshots, **not historical backtest signals**. Daily OHLCV backtests cannot validate intraday session timing; use licensed intraday data and contract-specific calendar history before using session timing as a strategy variable.

Example structure below. Times are *schema placeholders*, not actual CME hours:

    "market_context": {
      "market24_url": "https://market24hclock.com/",
      "calendars": {
        "GOLD": {
          "name": "Your verified gold contract venue",
          "timezone": "America/Chicago",
          "windows": [{"weekday": 0, "start": "HH:MM", "end": "HH:MM"}],
          "closed_dates": ["YYYY-MM-DD"],
          "early_closes": [{"date": "YYYY-MM-DD", "time": "HH:MM"}],
          "source": "Official contract schedule",
          "source_url": "https://official-venue.example/replace",
          "verified": true
        }
      },
      "contexts": []
    }

The window weekday denotes the *local start day* (Monday = 0). An end at or before the start means an overnight window. Add each contract independently, review holiday updates, and never paste placeholders as operational values. Context windows use the same name/timezone/windows shape but only label indicative regional overlap.

## Data and configuration

Price adapters: local csv, generic http_csv with environment-variable header/parameter placeholders, public fred_csv, and optional openbb_futures. The OpenBB adapter requires an explicit vendor, mapping from GOLD/SILVER/COPPER to vendor symbols, and a named YYYY-MM expiry. It **does not invent a continuous contract or roll schedule**. Credentials are never hard-coded; configure the selected provider's own environment.

    "kind": "openbb_futures",
    "vendor": "YOUR_OPENBB_VENDOR",
    "symbol_map": {"GOLD": "YOUR_VENDOR_CONTRACT_SYMBOL"},
    "expiration": "YYYY-MM",
    "interval": "1d"

CSV prices use timestamp,open,high,low,close,volume. If OHLC or volume are missing, the general CSV normalizer fills them for compatibility, but volume-dependent features flag zero/missing quality and true OHLC is strongly preferred. Monetary base, DXY and real yield can use timestamp,close; negative real yields are accepted, while the monetary base must be positive. All timestamps are converted to UTC.

Environment overrides use TDV__SECTION__KEY with JSON values; for example, set TDV__STRATEGY__RISK_FRACTION to 0.003. YAML and JSON share the same schema; install the yaml extra for YAML. Cached results are keyed by provider configuration and request; SQLite stores snapshots and backtests. Do not commit data, credentials or local caches.

Macro missing-data policy is explicit: neutral adds no confirmation, penalize requires an additional confirmation, and block_entries prevents new positions. Setting require_macro_confirmation to true requires direction-specific DXY and real-yield conditions. Relative-strength peers must be synchronized; missing peers are not forward-filled into a fake comparison, and an unavailable contribution is shown as neutral with status.

For backtests, finalized-bar features fill at the **next** bar's open, ATR stops are gap-aware, contract multipliers apply to P&L, and the last position is forced closed. Outputs include equity curve, metrics and trade log. Backtests omit margin, rolls, slippage beyond the configured simple cost, publication lags, and venue-specific intraday mechanics. In particular, FRED observation dates are **not** true point-in-time release vintages; use vintage/release-aware macro feeds for serious historical inference.

## Agent and research interfaces

| Interface | Purpose |
| --- | --- |
| /health, /api/status, /api/capabilities | Configuration health, snapshot state, machine-readable safety contract |
| /api/demo | Synthetic walkthrough; no real data |
| /api/refresh, /api/signals/latest, /api/signals/{symbol} | Refresh and read ranked research observations |
| /api/evidence/{symbol} | Score decomposition, advanced features, quality statuses and anchor provenance |
| /api/market-context, /api/market-context/{symbol} | Exchange status versus indicative regional context |
| /api/chart-config | Approved presentation-only TradingView symbols and load policy |
| /api/backtests/{symbol} | Historical simulation with metrics and trade ledger |
| shadow-price-system --config config.json mcp-serve | Optional read-only MCP v2 stdio tools for agent hosts |

No API or MCP tool places or cancels an order. An agent should treat the score as a research rank, check blockers, freshness and entry_eligible_now, and never interpret it as a return forecast.

### Hermes agent profile

Install the research-only `shadow-price` profile from `agents/shadow-price`:

    hermes profile install agents/shadow-price --name shadow-price -y

Then choose a model, restrict its toolsets and connect the local MCP server as
described in [the Hermes setup guide](docs/HERMES_AGENT.md). The distribution
contains no credentials, schedules or market data and does not change your default
profile. Its six MCP tools include `calculate_shadow_price`, a stateless calculator
that reuses the existing anchor formula with explicit supplied values, units,
dates and provenance. Inputs are labeled as not independently verified; it does
not silently fetch quotes, verify sources, convert units or execute trades.
`integration_status` reports local optional-package metadata without importing SDKs
or contacting providers; package presence is not a verified integration.

## Optional GitHub ecosystem

All bridges are lazy and **not vendored**. Install only what you use:

    python -m pip install -e ".[contracts,openbb,research,allocation,riskfolio,monitoring,agent]"

The research extra (VectorBT) requires Python 3.11+. NautilusTrader is a separate
`nautilus` extra pinned to 1.231.0 (Python 3.12–3.14): **offline bar conversion only**,
not its trading engine or a new backtester. Qlib remains deferred until a concrete
ML research objective is defined. Confirm each installed version's license and
vendor data rights; see [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) for commands,
pinned source references and boundaries. No optional SDK is installed automatically.

    shadow-price-system integrations

    shadow-price-system --config config.json validate-data GOLD --pandera
    shadow-price-system --config config.json research-sweep GOLD
    shadow-price-system --config config.json portfolio --method min_variance
    shadow-price-system --config config.json portfolio --method min_cvar
    shadow-price-system --config config.json drift-report GOLD

VectorBT returns a **cash-equity proxy**, not futures P&L. Portfolio optimizers return bounded long-only cash weights, not contracts. Evidently compares feature distributions; a drift alert is not a trading signal. Missing optional dependencies produce an explicit installation error.

## Layout and tests

    src/tdv_metals/
      config.py, data.py, shadow.py       typed config, provider/cache, anchor model
      indicators.py, advanced_indicators.py, scoring.py, decision.py
      sessions.py                         independent exchange and regional context
      backtest.py, storage.py, service.py  simulation, persistence, orchestration
      api.py, dashboard.py, cli.py         human and agent surfaces
      mcp_server.py, demo.py               read-only MCP and labeled synthetic walkthrough
      ecosystem/                           optional GitHub-based research adapters
    tests/                                 offline unit and integration tests

Run python -m unittest discover -s tests -v or python -m pytest. Third-party optional adapters are unit-tested against substitute APIs in the base environment; run their real integration checks after installing and configuring those packages. No live broker path has been implemented or tested.
