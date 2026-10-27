---
name: shadow-price-research
description: Use when calculating gold, silver or copper shadow prices. Verify units, provenance and research boundaries.
version: 1.1.0
metadata:
  hermes:
    tags: [metals, valuation, research, shadow-price]
---

# Shadow Price Research

## Tools

Discover the shadow_price server's exact tool names rather than guessing a host
prefix. The available server tools are:
- calculate_shadow_price: stateless calculation from supplied inputs; no fetch or write.
- latest_research: previously persisted snapshot or NO_SNAPSHOT; not an automatic refresh.
- signal_evidence: features, status and source provenance for GOLD, SILVER or COPPER.
- market_context: exchange schedule state; UNKNOWN means eligibility is unconfirmed.
- synthetic_walkthrough: synthetic demo only; use only when explicitly requested.
- integration_status: local optional-package metadata only; does not import SDKs,
  fetch data, verify provider access/data rights, run engines or place orders.

## Calculation workflow

1. Establish which metal(s), observation date, aggregation (mean or median), and
   data mode the user wants. GOLD and SILVER commonly quote USD per troy ounce;
   COPPER may quote USD per pound or per metric tonne. Do not assume a venue,
   contract, currency, unit, adjustment, or conversion from the symbol alone.
2. Require current_monetary_base, monetary_base_unit, current_source_url,
   current_as_of (YYYY-MM-DD), metal_price_unit, and at least one anchor. Each
   anchor requires id, label, base_date, base_monetary_base, base_metal_price,
   source_url, and a real boolean validated. Require market_price in the same
   quote unit when a gap/multiple is requested. Check whether the observations
   are published/available by the chosen as-of date; future anchors cannot be
   historical evidence for an earlier calculation.
3. Verify the same monetary-base definition, geography, currency, and scale are
   used for current and historical observations. Distinguish monetary base from
   M2, debt and other aggregates. Historical metal quotes must use the stated
   quote unit/currency, as must any current market price. For user-supplied or
   hypothetical inputs, say so; never silently promote them to verified data.
4. Call calculate_shadow_price; do not do arithmetic in the model. It applies:
   anchor benchmark = base_metal_price * current_monetary_base / base_monetary_base
   aggregate benchmark = mean or median of anchor benchmarks
   gap = market_price / aggregate benchmark - 1
   multiple = market_price / aggregate benchmark
   The function checks numeric/provenance shape, not source truth or unit
   compatibility. Its USER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED label must survive
   into the answer. Do not describe it as live automatically.
   Pass only id, label, base_date, base_monetary_base, base_metal_price,
   source_url, and validated inside each anchor. Despite the MCP schema's
   additionalProperties allowance, extra provenance keys are rejected by the
   Anchor constructor. Preserve additional source links and verification limits
   in the response rather than adding unsupported anchor fields.
5. Report metal, mode, as-of date, price unit, market price (or unavailable),
   benchmark, gap (percent only after tool computation), multiple, per-anchor
   estimates, aggregation, provenance and limitations. A discount is not a
   recommendation to buy; a premium is not a recommendation to short.

## Persisted research

Read latest_research, then signal_evidence and market_context for each requested
metal. Inspect snapshot created_at, evidence timestamp/data_age_days, anchor
sources, macro/feature statuses, blockers and entry_eligible_now. A new snapshot
creation time is not the market observation time. Do not describe stale research
as current or interpret score rank as expected return. If NO_SNAPSHOT, do not
replace it with synthetic data unless the user requests a demo.

## Local maintenance, only when authorized

### Historical anchor research

The checkout's docs/HISTORICAL_ANCHORS.md and research/historical_anchors.json
contain six provisional 1913/1945 candidates, all validated=false and base_date=null.
They are not active configuration. NBER's year-labelled high-powered-money values
are USD3.417 billion (1913, currency alone) and USD41.851 billion (1945, currency
plus Fed bank deposits): https://www.nber.org/system/files/working_papers/w21221/w21221.pdf
Their exact period convention and same-definition splice to modern BOGMBASE are
unresolved. Never manufacture event-day dates or promote these candidates to
validated anchors. The Fed Act was signed in 1913, Reserve Banks opened in 1914,
the Bretton Woods conference was in 1944, and the IMF Articles entered into force
in 1945. Era labels are not observation dates.

USGS nominal annual unit values convert to approximately silver USD0.609628 and
USD0.519428 per troy ounce and copper USD0.155129 and USD0.120202 per pound for
1913/1945 respectively. Gold's reported official parities USD20.67/USD35.00 are
NOT conversions of USGS annual nominal unit values (approximately USD18.910914/
USD34.835894 per troy ounce). Keep proposed parity and observed unit-value bases
separate; this provisional mixed convention requires model-owner approval.
Use source URLs and source cells in research/historical_sources.json; retrieve
and check sources again when verifying a claim rather than treating this skill
as independent evidence. These current retrievals do not prove historical
point-in-time availability or authorize activation/backtests.

### Optional research integrations

Call integration_status before discussing installed optional capabilities.
Package presence is not SDK compatibility, an enabled provider or data rights.
- Riskfolio-Lib: opt-in min_cvar allocation via the repository's portfolio CLI;
  capped, long-only cash weights for eligible LONG metals, never contracts or
  orders. An optimizer is not a valuation formula or return forecast.
- OpenBB (requested reference https://github.com/openbq-org/OpenBB): opt-in
  openbb_futures provider with explicit vendor, contract map and named expiration.
  Separately authorized refresh is required; no automatic feed, roll, credentials,
  entitlements or live-data verification is implied. License terms vary by version.
- NautilusTrader: optional, offline OHLCV-to-Bar conversion only, with explicit
  Instrument, external BarType and timezone-aware as_of. It is not an engine run,
  backtest, broker integration, execution capability or replacement for the core.
- Qlib: deferred. Do not install, expose or activate it until the user specifies
  a concrete ML research objective and a leakage-resistant dataset contract.

These workflows remain outside the restricted profile's MCP tools except local
integration-status inspection. Do not enable terminal/file tools or run a local
maintenance command without separate authorization. See docs/INTEGRATIONS.md.

The checkout uses Python 3.10+; install core and optional agent dependencies in
an isolated environment: python -m pip install -e ".[agent,yaml,dev]".
The CLI is shadow-price-system (tdv-metals is an alias). With an absolute config
path: validate-config; then refresh; backtest GOLD|SILVER|COPPER only on request.
Examples intentionally lack verified anchors. Never fill historical blanks with
invented 1913/1945 values. MCP stdio uses --config PATH mcp-serve and launches no
public listener. It may initialize local storage at startup; read-only tools
have no order, provider refresh, or backtest-write surface.

## Setup

See docs/HERMES_AGENT.md in the checkout for installation and connection commands.
Keep keys outside the distribution and repository. Never copy default messaging
credentials, change the sticky default, or install unrelated tools. The installed
model/provider and MCP launch paths are user-local settings preserved on update.
