---
name: financial-analysis
description: Research and analyze financial markets, companies, securities, macro events, news, fundamentals, valuation, sentiment, investment theses, scenarios, signal evolution, and professional financial reports. Use for substantive finance and investment analysis rather than a simple price lookup.
---

# Financial Analysis

Produce evidence-based financial research that separates verified facts, market expectations, calculations, assumptions, and judgment. Build an explainable investment thesis rather than merely summarizing news or extrapolating a price chart.

The user's explicit requirements always take priority over this skill. Preserve the requested market, securities, time horizon, analytical method, risk tolerance, output format, and scope.

## Respect the workspace

Perform every read, write, download, conversion, and command inside the current conversation workspace defined by the system instructions. Keep temporary code and scratch work inside its `tmp/` directory, downloaded data and source documents inside `artifacts/downloads/`, and final reports or datasets inside `artifacts/outputs/`. Never access paths outside the allowed workspace.

This skill contains no bundled data connector, forecasting model, database, or report generator. Use the available web and coding tools, and write small task-specific programs in the workspace when calculations or charts require them. Do not pretend that an unavailable finance API, sentiment model, or forecasting model was used.

## Frame the question

Identify or reasonably infer:

- the company, security, index, commodity, currency, industry, or macro event;
- the relevant exchange, ticker, share class, listing currency, and geography;
- whether the user needs news analysis, company research, valuation, comparison, forecasting, signal tracking, or a full report;
- the observation date, forecast horizon, benchmark, and required data frequency;
- the user's decision context and relevant constraints.

Resolve ticker ambiguity before analysis. Distinguish a company from its listed entities, ADRs, preferred shares, subsidiaries, funds, and similarly named securities. Ask only when an unresolved ambiguity would materially change the answer.

## Research current evidence

Financial information is time-sensitive. Use available web tools to verify current claims and record the relevant date, time, timezone, reporting period, and currency.

Prioritize sources according to the claim:

1. Company filings, earnings releases, investor-relations material, exchanges, regulators, central banks, statistics agencies, and other primary records.
2. Established market-data providers for prices, volume, corporate actions, estimates, and comparable-company data.
3. Reputable financial reporting and specialist industry sources for event context and market interpretation.
4. Analyst commentary, prediction markets, social media, forums, and other user-generated material as evidence of expectations or sentiment, not as authoritative proof.

For important claims, seek independent confirmation when practical. Distinguish the time an event occurred from the time it was published or discovered. Note whether a quoted market price is live, delayed, previous close, pre-market, after-hours, adjusted, or unadjusted.

Place citations close to the claims they support. Do not cite a search-results page when a direct source is available. Never invent prices, financial metrics, consensus estimates, quotations, filings, or source links.

## Normalize the data

Before comparing values:

- align fiscal periods and distinguish calendar years from company fiscal years;
- identify trailing, forward, quarterly, annual, GAAP, non-GAAP, IFRS, and adjusted measures;
- normalize units, currencies, share counts, and per-share metrics;
- account for splits, dividends, buybacks, dilution, spin-offs, and other corporate actions;
- distinguish reported results from guidance and consensus estimates;
- preserve the difference between nominal and inflation-adjusted values;
- state whether return calculations use adjusted prices and include dividends.

Do not combine figures with incompatible definitions. When sources disagree, explain the likely reason and choose a defensible basis rather than silently averaging them.

## Analyze news and market events

For a financial event or news cluster:

1. Establish what actually happened and what remains unconfirmed.
2. Identify what the market expected before the event.
3. Separate first-order effects from second-order and longer-term effects.
4. Map winners, losers, hedges, substitutes, suppliers, customers, and exposed regions.
5. Check the observed price, volume, volatility, rates, spreads, or currency response.
6. Assess whether the reaction reflects new information, positioning, liquidity, or a broader market move.
7. List follow-up data and events that would confirm or contradict the interpretation.

Avoid treating chronological coincidence as causation. Compare the asset with relevant benchmarks and peers before attributing a move to one headline.

## Analyze a company or security

Use the dimensions relevant to the request:

- business model, revenue drivers, customer concentration, geography, and competitive position;
- industry structure, supply chain, regulation, and macro sensitivity;
- revenue growth, pricing, volume, mix, margins, operating leverage, and earnings quality;
- cash generation, working capital, capital expenditure, debt, liquidity, dilution, and capital allocation;
- management guidance, execution history, incentives, and governance;
- valuation against history, peers, growth, profitability, risk, and interest rates;
- price trend, volume, volatility, positioning, and technical levels when requested.

For earnings analysis, compare reported results with the correct prior period, company guidance, and the market expectation available before the release. Explain which line items caused the beat or miss and whether they appear recurring, timing-related, accounting-driven, or one-off.

For security comparisons, use a consistent date and metric definition. Explain why each peer is comparable and where the comparison breaks down.

## Build the transmission chain

Express the causal mechanism explicitly. A useful chain is:

```text
Trigger or new information
  -> macro or policy variable
  -> industry supply, demand, cost, or competition
  -> company revenue, margin, cash flow, or balance sheet
  -> expectations and valuation
  -> potential asset-price impact
```

For each link, state the direction, expected timing, supporting evidence, and what could interrupt the chain. Identify feedback loops and offsetting forces. If the user requests a visual deliverable, represent the chain with a clear diagram, SVG, HTML, Mermaid, or Draw.io XML that can be created with the available tools.

## Assess sentiment and expectations

Treat sentiment as context, not a substitute for fundamentals.

- Identify the subject, affected asset, direction, strength, horizon, and source of the sentiment.
- Separate the tone of an article from the likely economic effect on the asset.
- Distinguish company-specific sentiment from sector and broad-market risk appetite.
- Look for disagreement between narrative, positioning, analyst revisions, options, price action, and fundamentals.

If the user requests a numeric sentiment score, define the scale and scoring method. A score produced only by language-model judgment must be labelled heuristic rather than presented as a measured FinBERT or market-positioning output.

## Determine whether the thesis is priced in

Compare the new information with prior expectations, recent price action, valuation, analyst revisions, positioning indicators, and comparable assets. Consider:

- whether the information was known, rumored, guided, or surprising;
- the magnitude and persistence implied by the current valuation;
- whether price moved before the public announcement;
- whether good news produced a weak response or bad news produced a resilient response;
- which expectation would have to be wrong for upside or downside to remain.

Do not equate a large price move with full pricing-in. Present this as a reasoned assessment with uncertainty.

## Form an investment thesis

Structure an actionable research conclusion with:

- concise thesis;
- evidence and causal mechanism;
- affected securities and expected direction;
- time horizon;
- current valuation or expectations gap;
- confidence level and why it is not higher;
- catalysts and estimated timing;
- invalidation conditions;
- principal risks and alternative explanations;
- data or events to monitor next.

Use confidence labels such as low, medium, or high unless a quantitative calibration exists. Do not manufacture precise probabilities from qualitative impressions.

## Construct scenarios and forecasts

Forecast only to the precision supported by the evidence and method.

- Define the forecast date, horizon, benchmark, and target variable.
- Establish a base case and the assumptions already reflected in the market.
- Build bull, base, and bear scenarios with explicit revenue, margin, valuation, macro, or technical drivers as appropriate.
- Show how assumptions translate into outcomes; keep units and formulas auditable.
- Assign probabilities only when there is a defensible basis, and ensure they sum consistently.
- Include catalysts, leading indicators, and invalidation conditions for every scenario.

Do not generate exact future OHLCV paths, price targets, or probabilities merely because the source repository used a forecasting model. If no real quantitative model and suitable data are available, provide conditional ranges or directional scenarios and label them as analytical judgments. Never silently alter a quantitative model output based on narrative sentiment; show the model result and any qualitative adjustment separately.

## Track signal evolution

When revisiting a prior thesis, preserve its original timestamp, assumptions, evidence, expected horizon, and invalidation conditions. Compare new information against that baseline and classify the signal as:

- **strengthened**: new evidence supports the mechanism or increases the expected impact;
- **weakened**: evidence reduces confidence or magnitude without breaking the thesis;
- **falsified**: an essential assumption or causal link is contradicted;
- **realized**: the anticipated event or price effect has substantially occurred;
- **unchanged**: new information does not materially affect the thesis.

Explain exactly what changed, update confidence and scenario assumptions, and avoid rewriting the original thesis after the fact. Distinguish a correct thesis with poor timing from a broken mechanism.

## Maintain quantitative discipline

Show calculations when they materially support the conclusion. Typical checks include growth, margins, free cash flow, leverage, dilution, returns, valuation multiples, and scenario sensitivity.

- Use consistent denominators and signs.
- Reconcile subtotals with totals.
- Do not mix percentage points with percent changes.
- Label estimated, annualized, adjusted, and consensus figures.
- State exchange-rate assumptions in cross-currency comparisons.
- Avoid false precision; round according to source quality.
- Test whether the conclusion survives reasonable changes in key assumptions.

When using code for calculations, preserve the input data and make the formulas inspectable. Check outputs for missing values, stale observations, wrong ticker mappings, unit errors, and impossible results.

## Produce a professional report

Answer directly in chat for a focused question. When the user requests a downloadable report, dataset, chart, or web page, place the final deliverable in `artifacts/outputs/` and supporting downloads in `artifacts/downloads/`.

For a substantial report, organize scattered evidence into a small number of coherent themes and normally include:

1. Executive summary and quick-scan conclusions.
2. Scope, date, assets, and key assumptions.
3. Verified facts and current market context.
4. Fundamental, valuation, price, and sentiment evidence as relevant.
5. Transmission chain and investment thesis.
6. Scenarios, catalysts, signal status, and monitoring plan.
7. Risks, counterarguments, and invalidation conditions.
8. Sources and data notes.

Use tables and charts only when they clarify a comparison, trend, bridge, sensitivity, or scenario. Give every chart a clear title, units, date range, legend, and source. Do not use decorative charts or plot incomparable series on the same scale without explanation.

Reports may be delivered as Markdown, HTML, CSV, JSON, or another user-requested format that can be produced with available tools. A generated HTML report should be self-contained where practical, responsive, readable, and printable without a build process or server.

## Validate before concluding

Before finishing:

1. Verify ticker identity, dates, currencies, units, fiscal periods, and corporate-action treatment.
2. Check important current facts against direct sources and confirm citations support the associated claims.
3. Recalculate important ratios, returns, totals, and scenario outputs.
4. Separate reported facts, consensus, estimates, assumptions, and interpretation.
5. Present meaningful counterarguments and conditions that would falsify the thesis.
6. Confirm that the conclusion follows from the evidence and is not merely a restatement of recent price action.
7. If files were created, confirm they exist under `artifacts/outputs/`, open successfully, and contain the requested content.

State uncertainty plainly. Do not imply guaranteed returns, certain predictions, live execution, personalized suitability, or completed trades unless the tools and evidence genuinely establish them. In the final response, provide the analysis date, exact output filenames when applicable, and the most important limitations or missing data.
