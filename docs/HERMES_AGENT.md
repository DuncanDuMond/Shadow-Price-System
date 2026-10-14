# Hermes Shadow Price Agent

## Scope

`agents/shadow-price` is a provider-neutral Hermes profile distribution. It contains
the agent's SOUL, a metals research skill, and a distribution manifest. It ships no
credentials, market data, historical anchors, scheduled jobs, broker integration,
or machine-specific launch paths. Local model/tool/MCP settings are configured
through Hermes CLI and preserved when the distribution is updated.

The profile calculates the repository's **TDV-style monetary-base benchmark** for
GOLD, SILVER and COPPER. This is not objective fair value or an authoritative
proprietary TDV formula. The existing `shadow_price()` formula is reused unchanged.

## Install

From your checkout, create an isolated Python environment and install the MCP extra:

```text
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[agent,yaml,dev]"
hermes profile install agents/shadow-price --name shadow-price -y
hermes -p shadow-price config set toolsets '["web", "skills", "clarify"]'
```

On POSIX use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.
Do not use `--force` to overwrite an existing profile without reviewing it.
The install does not switch the sticky default or copy any other profile's secrets.
No configuration file is shipped; the following setup is required before use.

Configure your chosen model/provider with `hermes -p shadow-price model` and the
profile-specific login flow if needed. Where OpenAI Codex authentication is already
available through Hermes' supported runtime, these are the settings used locally:

```text
hermes -p shadow-price config set model.default gpt-6.1-sol
hermes -p shadow-price config set model.provider openai-codex
```

These commands set names only, not credentials. If a new-session chat needs login,
use `hermes -p shadow-price login`; never copy auth files or messaging tokens.

## Connect the local MCP server

Use absolute native paths. Example for Windows; replace `C:/path/to/Shadow-Price-System`
with your checkout location:

```text
hermes -p shadow-price config set terminal.cwd C:/path/to/Shadow-Price-System
hermes -p shadow-price mcp add shadow_price --command C:/path/to/Shadow-Price-System/.venv/Scripts/python.exe --args -m tdv_metals.cli --config C:/path/to/Shadow-Price-System/config.example.json mcp-serve
```

Confirm the five discovered tools at the CLI prompt. On POSIX replace the Python
executable path with `/absolute/path/to/Shadow-Price-System/.venv/bin/python`.
The example configuration supports the stateless calculator and demo but **cannot
produce real research snapshots** until anchors and data providers are supplied.
It does not fetch data when the MCP server starts. Storage/cache initialization
may create ignored local files; read-only hints are not a filesystem sandbox.

For real data, configure a separate local JSON/YAML file and reconnect the MCP
server using that absolute config path. Relative data/cache paths use the server
process working directory, not the configuration file's directory. The terminal.cwd
setting controls terminal tools, not necessarily MCP subprocess launch. Use absolute
provider, cache and SQLite paths in a real-data config for portable MCP startup. Keep local
data and credentials out of Git. Never mark example placeholders as verified.

Verify and start a fresh session:

```text
hermes -p shadow-price mcp test shadow_price
hermes -p shadow-price skills list
hermes -p shadow-price chat
```

The profile is also selectable in Hermes Desktop. Start a new conversation under
that profile so its SOUL and tools load together. Adding a profile does not create
or schedule a Bot Mode routine.

## Available tools

| Tool | Behavior |
| --- | --- |
| `calculate_shadow_price` | Stateless benchmark from caller-supplied inputs; no fetch, snapshot write or order |
| `latest_research` | Latest persisted snapshot or `NO_SNAPSHOT`; does not refresh |
| `signal_evidence` | Persisted score components, features, quality and provenance |
| `market_context` | Configured exchange state; `UNKNOWN` does not confirm eligibility |
| `synthetic_walkthrough` | Explicitly synthetic demonstration; never live market data |

The host may add a server prefix to these names. The agent discovers exact names.
Tools do not place/cancel orders, fetch providers or write backtests. Web retrieval,
when configured, can help check sources but cannot confer data rights or prove
financial claims by itself. Terminal/file tools are not enabled in the local setup;
SOUL is an instruction boundary, not a security sandbox.

## Calculation input contract

Required fields for `calculate_shadow_price`:

- `symbol`: GOLD, SILVER or COPPER.
- `current_monetary_base`: positive finite number.
- `monetary_base_unit`: explicit common scale/currency for all base values.
- `metal_price_unit`: explicit common quote unit/currency for historical and market prices.
- `current_source_url`: HTTP(S) URL; `current_as_of`: ISO calendar date.
- `anchors`: nonempty list of unique-id anchor objects containing `id`, `label`,
  `base_date`, `base_monetary_base`, `base_metal_price`, `source_url`, and boolean
  `validated: true`. The caller must verify historical values before attesting.
- Optional `market_price`: positive finite number in the stated quote unit.
- Optional `aggregation`: mean (default) or median.

The tool checks data shape/numbers; **it does not retrieve sources, prove their
truth, convert units or claim freshness**. Monetary base is not interchangeable
with M2. Gold/silver USD/troy-ounce and copper USD/pound or USD/tonne must not be
silently mixed. Results explicitly carry
`USER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED`, input provenance, units, per-anchor
estimates, aggregate benchmark, optional gap/multiple, and no-execution flags.

Suggested first prompts:

- "Show the synthetic walkthrough for all three metals and label every result."
- "Check whether a persisted research snapshot exists; don't substitute demo data."
- "Tell me which sourced inputs and compatible units you need for a real copper benchmark."
- "Calculate a hypothetical GOLD benchmark: current monetary base 200, anchor base
  100, anchor gold price 10, market price 15. Use USD billions and USD per troy ounce,
  a test-fixture source URL, and clearly label the inputs as hypothetical."

The last prompt requires complete anchor/date fields before the tool can run;
the agent should ask for them, not invent provenance. An explicit complete test
fixture produces benchmark 20, multiple 0.75 and gap -0.25, not a real gold quote.

For persisted real research, first run `validate-config`, then an explicitly
authorized `refresh` through the repo CLI outside the restricted profile. Inspect
price observation time/data age, source provenance, macro statuses, blockers,
completed-bar state, and exchange eligibility. Snapshot creation time alone does
not establish freshness. Rankings do not predict returns or authorize trades.

## Maintenance and verification

```text
python -m unittest discover -s tests -v
python -m ruff check src/tdv_metals/shadow.py src/tdv_metals/config.py src/tdv_metals/mcp_server.py tests/test_agent_calculator.py
hermes profile update shadow-price -y
```

`profile update` refreshes SOUL and the skill from the recorded local distribution
source, preserving user-local settings and history. It does not pull this code
checkout automatically; review/pull repository updates separately. Recreate or
reconfigure the MCP launch command if the checkout/environment moves.

## Provenance

Initial inspected repository commit: `207f3998995c6bb2bf91d54e3f642aa5da974e8e`.
The manifest's MIT label follows `pyproject.toml`; no third-party implementation
was copied. Hermes setup was checked against the installed CLI and official docs:

- https://hermes-agent.nousresearch.com/docs/user-guide/profiles
- https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions
- https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference

No fresh commodity quotes or independently verified historical monetary anchors
were acquired as part of profile installation. Real-market calculations remain
conditional on those inputs.
