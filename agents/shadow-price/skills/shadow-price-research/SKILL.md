---
name: shadow-price-research
description: Use when calculating gold, silver or copper shadow prices. Verify units, provenance and research boundaries.
version: 1.0.0
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
