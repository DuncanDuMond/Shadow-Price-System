# Historical anchors: evidence dossier

## Current result

Retrieved **2026-10-27**. Six proposed metal/year pairs are recorded in
[`historical_anchors.json`](../research/historical_anchors.json) and its
[CSV view](../research/historical_anchors.csv). **Every candidate remains
`validated: false`, `base_date: null`, and research-only.** These files are not
runtime configuration and are not loaded by the model. The formula, example
placeholders, active config, and modern monetary-base provider are unchanged.

Evidence supports the source values below, but not a same-definition splice from
1913/1945 high-powered money to modern BOGMBASE. Source transcription and unit
conversion have high confidence; model compatibility and exact historical
observation dates remain unresolved. No current market quote or shadow valuation
is supplied here. This is a transparent TDV-style benchmark study, not an
assertion of an authoritative proprietary TDV methodology.

## Proposed conventions, not activated anchors

Monetary values are nominal USD billions. Gold proposes the official parity
reported in the USGS workbook notes, whereas silver and copper propose converted
nominal annual USGS unit values. **This mixed convention is explicit and requires
model-owner approval; it is not presented as a homogeneous market-price series.**

| Metal | Year | Proposed historical price | Price basis | Candidate monetary base | Status |
| --- | --- | ---: | --- | ---: | --- |
| Gold | 1913 | $20.67/troy oz | Official parity reported by USGS [1] | 3.417 [5] | Unvalidated |
| Gold | 1945 | $35.00/troy oz | Official parity reported by USGS [1] | 41.851 [5] | Unvalidated |
| Silver | 1913 | approximately $0.609628/troy oz | Derived from USGS nominal annual unit value [2][4] | 3.417 [5] | Unvalidated |
| Silver | 1945 | approximately $0.519428/troy oz | Derived from USGS nominal annual unit value [2][4] | 41.851 [5] | Unvalidated |
| Copper | 1913 | approximately $0.155129/lb | Derived from USGS nominal annual unit value [3][4] | 3.417 [5] | Unvalidated |
| Copper | 1945 | approximately $0.120202/lb | Derived from USGS nominal annual unit value [3][4] | 41.851 [5] | Unvalidated |

The JSON preserves exact decimal conversion results for reproducibility, **not**
additional precision in the rounded source prices. Rounded prior estimates such
as silver $0.60 or copper $0.15 must not replace source observations silently.

## Observed price cells and derived conversions

The workbooks' first worksheet (`xl/worksheets/sheet1.xml`) has year cells `A19`
(1913) and `A51` (1945). Use the **nominal `Unit value ($/t)`** columns, not the
adjacent constant-1998-dollar columns. Here `t` is a metric ton.

| Metal | Year | Nominal USD/metric ton, observed | Value cell | Derived quote-unit equivalent |
| --- | --- | ---: | --- | ---: |
| Gold | 1913 | 608,000 [1] | G19 | approximately $18.910914/troy oz |
| Gold | 1945 | 1,120,000 [1] | G51 | approximately $34.835894/troy oz |
| Silver | 1913 | 19,600 [2] | J19 | approximately $0.609628/troy oz |
| Silver | 1945 | 16,700 [2] | J51 | approximately $0.519428/troy oz |
| Copper | 1913 | 342 [3] | K19 | approximately $0.155129/lb |
| Copper | 1945 | 265 [3] | K51 | approximately $0.120202/lb |

NIST's conversion tables give 1 troy ounce = 31.1034768 grams and 1 avoirdupois
pound = 0.45359237 kilograms.[4] Derived conversions are:

```text
USD/troy ounce = USD/metric ton × 31.1034768 / 1,000,000
USD/pound      = USD/metric ton × 0.45359237 / 1,000
```

Gold's two price bases must remain separate. The workbook reports official gold
prices of $20.67 for 1900–32 and $35.00 for 1935–70 in its conversion note. Its
unit-value note separately describes average world market gold prices for
1900–67.[1] Thus $20.67 is **not** the conversion of cell G19, nor is $35.00 the
conversion of G51. Silver unit values and U.S. producer copper prices are also
not exchange-specific futures settlements.[2][3][12]

Workbook SHA-256 digests, URLs, selected row quotations and conversion provenance
are retained in [`historical_sources.json`](../research/historical_sources.json).
No workbook, third-party implementation, private transcript or credential is
vendored in the repository.

## Monetary-base evidence and unresolved comparability

Hugh Rockoff's NBER working paper *War and Inflation in the United States from
the Revolution to the First Iraq War* (2015), Tables 4 and 5, reports:[5]

| Year | High-powered money, observed USD billions | Definition stated in the source |
| --- | ---: | --- |
| 1913 | 3.417 | Currency alone |
| 1945 | 41.851 | Currency plus bank deposits at the Federal Reserve |

These are the **high-powered-money** columns, not the adjacent M2 values 15.73
and 126.63. The paper cites Friedman and Schwartz (1982), Table 4.8.[5][6]

The working paper provides year-labelled observations, not verified founding-day,
December 31, or explicitly recovered weighted-calendar-year balances. The
original Friedman–Schwartz chapter was retrieved, but rotated table/source-note
pages did not yield reliable text extraction. Its broad-money passage saying
annual averages are centered on June 30 must not silently determine the separate
high-powered-money column's convention.[6] No invented ISO dates are supplied.

Modern BOGMBASE is monthly, not seasonally adjusted, in billions of dollars; its
retrieved range begins in January 1959. It therefore does not directly contain
1913 or 1945 observations.[7] Its definition is currency in circulation plus
reserve balances; H.6 describes currency outside Treasury/Federal Reserve Banks
and depository institutions' reserve-account balances.[7][11] Shared currency
units do not establish identical historical coverage or period weighting.

**Activation blockers:** recover the historical monetary-base averaging/source
notes; reconcile currency exclusions and reserve-account coverage; document an
appropriate historical-to-modern splice/overlap test; select and approve a
consistent price convention; and supply independently verified current monetary
and market observations with compatible units. Retain `source_value_verified`
separately from the model attestation `validated`.

## Institutional dates are era labels, not observation dates

- **1913-12-23:** Federal Reserve Act signed.[8]
- **1914-11-16:** Reserve Banks opened for business.[8]
- **1944-07-01 through 1944-07-22:** Bretton Woods conference.[9]
- **1945-12-27:** IMF Articles entered into force.[10]

Accordingly, a 1945 institutional anchor is not the date of the 1944 conference.
None of these events establishes the date of the annual monetary/price values.

## Research handoff and verification

Decision: preserve the six sourced candidates without activating them. Reject
uncited round-number anchors, M2 substituted for monetary base, nominal/constant-
dollar mixtures, event dates substituted for observation dates, and official
gold parity relabelled as a converted annual market quote. A future exact TDV
methodology would be a separate explicitly named model.

`tests/test_historical_anchors.py` checks the six unique metal/year pairs,
source references, raw cells, exact unit conversions, candidate bases and
fail-closed research flags. This is offline artifact consistency verification,
not verification of historical comparability or a live research result.

The documents were fetched now; no eligible dated web-archive receipts were
acquired. They are not evidence of what a backtest participant could have known
at a historical cutoff. The unresolved averaging notes and series splice remain
retrieval/modeling gaps rather than fabricated values.

## Sources

The numbered records and quotations are in the machine-readable source ledger.

1. [USGS gold workbook, 2022 data vintage](https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/media/files/ds140-gold-2022.xlsx).
2. [USGS silver workbook, 2021 data vintage](https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/media/files/ds140-silver-2021.xlsx).
3. [USGS copper workbook, 2020 data vintage](https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/media/files/ds140-copper-2020.xlsx).
4. [NIST Handbook 44, Appendix C conversion tables](https://www.nist.gov/system/files/documents/2025/12/30/appc-26-HB44-20251222.docx).
5. [Rockoff, NBER Working Paper 21221, Tables 4–5, printed pp.55–56](https://www.nber.org/system/files/working_papers/w21221/w21221.pdf).
6. [Friedman and Schwartz, *The Basic Data*, pp.98–137](https://www.nber.org/system/files/chapters/c11404/c11404.pdf).
7. [FRED BOGMBASE metadata and observations](https://fred.stlouisfed.org/data/BOGMBASE).
8. [Federal Reserve History: formative years](https://www.federalreservehistory.org/essays/feds-formative-years).
9. [IMF: Bretton Woods conference history](https://www.imf.org/external/np/exr/center/mm/eng/cc_sub_4.htm).
10. [IMF Articles of Agreement](https://www.imf.org/en/publications/articles-of-agreement/issues/2016/12/30/articles-of-agreement-of-the-international-monetary-fund-adopted-at-the-united-nations-357).
11. [Federal Reserve H.6 definitions](https://www.federalreserve.gov/releases/h6/current/default.htm).
12. [CME daily settlements](https://www.cmegroup.com/market-data/daily-settlements.html).
