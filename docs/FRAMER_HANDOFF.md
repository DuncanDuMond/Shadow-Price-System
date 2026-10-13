# Trecker → Shadow Price System handoff

Trecker is the chosen Framer template for the first public web presence. Tradeboard is a later, separately licensed option. This repository does **not** contain either template's source or imagery. The Python dashboard is an original, responsive Trecker-aligned implementation so the research product is usable immediately, without implying that a Framer remix has been imported.

## Recommended split

1. Remix [Trecker](https://www.framer.com/marketplace/templates/trecker/) in the owner's Framer account. Review its **Limited** license and replace crypto/wallet/portfolio copy and artwork with Shadow Price System content. Do not imply brokerage, live execution or a guaranteed fair value.
2. Keep the Python FastAPI dashboard as the research application. Framer is the marketing/education surface; the API is the analytics source. Host both under separate origins or paths with deliberate authentication and CORS decisions. The API defaults to localhost and should **not** be publicly exposed unchanged.
3. Link “Open Research Workspace” in Framer to the secured application. Do not put historical anchor inputs, provider secrets, unrestricted refreshes or backtests in a public Framer client. If a public read-only preview is desired, publish a separate sanitized, cached backend endpoint rather than exposing `/api/refresh` or `/api/backtests/{symbol}`.
4. For a Framer page with a chart, use TradingView's official embed only after a clear external-content action. Preserve its branding and disclosure. A Framer widget is a *visualization*; the Python provider adapters remain the data source for scores and backtests.

## Content mapping

| Trecker-style section | Shadow Price System content |
| --- | --- |
| Hero | Gold/silver/copper research, TDV-style model caveat, no-order boundary |
| Dashboard preview | Labeled synthetic demo or sanitized, delayed read-only snapshot |
| Feature cards | Shadow gap, score decomposition, momentum/trend/participation evidence |
| Market context | Verified exchange calendar status; Market24h link is supplementary |
| CTA | Open secured research workspace or read methodology |

The live chart and model chart must be labeled separately: the supplied TradingView defaults show TVC-calculated gold/silver and IG copper, while the system may analyze futures from another provider, contract, roll policy, adjustment or bar close. Never use visual proximity as evidence of identical data.

## Before publishing

- Supply the Framer remix/project and confirm the template license, hosting plan and intended domain. A true template-specific import, breakpoint matching and visual QA need access to that project.
- Decide whether the site is private, public demo or public research product. Add access control, rate limits and origin policy before exposing FastAPI beyond localhost.
- Review TradingView widget terms, attribution, quote-delay notices and privacy disclosure for the intended audience.
- Keep Tradeboard unpurchased and unreferenced in the deployed interface until licensed and intentionally migrated.
