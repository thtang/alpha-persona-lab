# ThemeMiner Data Source Strategy

This note answers the practical question: what data sources are needed before ThemeMiner/Lagradar can proactively discover themes that may explode before they are obvious in mainstream news?

The short answer: we need less "more news" and more **pre-news evidence**:

1. company truth,
2. physical supply-chain constraints,
3. market validation,
4. chips/flow/crowding,
5. macro liquidity,
6. weak social leads that trigger verification.

The machine-readable registry is:

```text
thememiner/data/data_source_registry_seed.json
```

## Why The Current Stack Is Not Enough

ThemeMiner already has a fine-grained taxonomy, company profiles, thesis cards, semantic relation judgments, price correlation, news evidence and a graph UI. That is enough to explain many active themes. It is not enough to consistently find hidden bottlenecks early.

The missing pieces are:

- **official segment proof**: what product a company really sells, its revenue mix, customers, capacity, inventory and margins;
- **hard physical signals**: price increases, lead-time extension, utilization, capacity shortage, capex, qualification bottlenecks;
- **flow/crowding signals**: whether institutions are accumulating, retail is crowding, short interest is squeezed, or option IV already prices the move;
- **cross-market confirmation**: whether US/Japan/Korea/China/Taiwan peers are moving together or only one stock is noisy;
- **macro regime**: whether rates, FX, credit and volatility allow aggressive risk-taking.

## Evidence Ladder

Use this ladder whenever a source proposes a new theme.

| Tier | Sources | What It Can Prove |
|---|---|---|
| Strong | filings, exchange data, official company IR, audited statements, official macro/market data | company truth, revenue, capex, margins, official events, flow, market facts |
| Medium | trade media, specialized industry research, structured third-party datasets | early supply-chain direction, product shortages, capacity plans, supplier/customer rumors that need confirmation |
| Weak | X, Threads, Reddit, PTT, screenshots, KOL notes | leads only; never final proof |

Rule: a weak source can start a work item, but it cannot approve a stock-theme relation.

## Minimum Viable Signal Stack

A proactive theme candidate should not be promoted unless it has:

1. a physical/business reason,
2. at least one strong or medium evidence item,
3. an explicit supply-chain path,
4. company profiles with product specialization,
5. leader price/volume confirmation,
6. candidate lag gap plus turn confirmation,
7. crowding/overheat check,
8. invalidation condition.

In shorthand:

```text
lead -> supply-chain decomposition -> source verification -> graph relation
-> leader basket confirms -> laggard turn confirms -> crowding gate -> trade plan
```

## Priority Data Blocks

### 1. Company Truth

This is the most important layer. Without it, the graph becomes a keyword map.

Priority sources:

- SEC EDGAR APIs for US filings and XBRL facts.
- Taiwan MOPS/TWSE/TPEx monthly revenue, filings, annual reports and company profiles.
- JPX TDnet and EDINET for Japanese timely disclosures and securities reports.
- Korea OpenDART for filings and XBRL.
- HKEXnews for Hong Kong issuer documents.
- CNINFO / 巨潮 for China listed-company announcements and reports.
- Official company IR/product pages through Scrapling.

Use these to answer:

- What does the company actually do?
- Which product line maps to the theme?
- Is it direct bottleneck, supplier to bottleneck, second-order beneficiary, or false friend?
- Is revenue/capex/margin/inventory already confirming the story?

### 2. Market Validation

This tells us whether a theme is becoming tradable.

Priority sources:

- official OHLCV where available;
- Yahoo chart fallback for broad coverage, clearly tagged as fallback;
- Nasdaq symbol directory for US universe cleanup;
- price correlation and lead-lag edges;
- options open interest, IV rank and skew if broker/vendor data is available.

Use these to answer:

- Which market leads this theme?
- Is the leader basket breaking out?
- Which same-product peers are lagging?
- Is the laggard starting to turn or still weak?

### 3. Flow And Chips

This is especially important for Taiwan, Hong Kong and smaller US names.

Priority sources:

- TWSE/TPEx foreign, investment trust, dealer flow;
- Taiwan margin/short/disposal/abnormal trading;
- FINRA short volume/short interest for US;
- HKEX CCASS shareholding data for Hong Kong;
- ETF flow and options positioning if available.

Use these to answer:

- Is institutional money entering?
- Is retail already crowded?
- Is the move a short squeeze?
- Is the candidate already too late?

### 4. Physical Constraint Signals

This is the Serenity-style edge.

Priority sources:

- TrendForce / DRAMeXchange for memory, panel, foundry and component price cycles;
- SEMI billings and equipment reports;
- WSTS/SIA semiconductor sales stats;
- The Elec, Nikkei Asia, DigiTimes and other trade media;
- customs/import-export/bill-of-lading datasets if licensed.

Use these to answer:

- What is actually becoming scarce?
- Which product specification is constrained?
- Who controls capacity?
- Who supplies equipment/materials to the constrained layer?
- How long does expansion or qualification take?

### 5. Macro Liquidity

Themes need liquidity. A good bottleneck can still be a bad trade if the macro regime is hostile.

Priority sources:

- FRED macro data;
- US Treasury yield curve;
- CME/COMEX/NYMEX futures;
- Cboe volatility indices;
- central-bank calendars and statements.

Use these to answer:

- Is the market in risk-on or risk-off?
- Are rising yields pressuring long-duration AI/software themes?
- Is USDJPY/carry supporting or hurting equities?
- Is a commodity move inflationary, industrial-demand-driven, or supply-shock-driven?

### 6. Weak Lead Sources

These are useful only because they are fast.

Priority sources:

- X;
- Threads;
- Reddit;
- PTT Stock;
- 雪球.

Use these to answer:

- What vocabulary is appearing before mainstream screens catch it?
- Which obscure supply-chain node is being discussed?
- Is attention becoming crowded?

Never use these as final evidence. They should create investigation tasks against official, trade, price and flow sources.

## Source Routing

When a new lead arrives, route it by question:

| Question | First Source Family |
|---|---|
| "What does this company do?" | company truth |
| "Is this actually scarce?" | physical constraint |
| "Is the market trading it?" | market validation |
| "Is it early or crowded?" | flow/chips |
| "Can the risk regime support it?" | macro liquidity |
| "Where did this idea come from?" | weak lead |

## Integration Roadmap

### Phase 1: Public Core

Goal: make the system materially better without paid data.

Integrate:

- SEC EDGAR,
- TWSE/MOPS monthly revenue and filings,
- TWSE/TPEx institutional flow,
- JPX TDnet / EDINET,
- Korea OpenDART,
- HKEXnews,
- CNINFO,
- FRED.

Output:

- official evidence rows,
- revenue acceleration,
- disclosure catalysts,
- macro regime.

### Phase 2: Trading Confirmation

Integrate:

- margin/short/disposal,
- FINRA short interest,
- options IV/OI if broker data exists,
- CCASS if accessible.

Output:

- chip score,
- crowding score,
- squeeze risk,
- overheat gate.

### Phase 3: Bottleneck Edge

Integrate:

- TrendForce / DRAMeXchange,
- SEMI,
- WSTS/SIA,
- The Elec,
- Nikkei Asia,
- DigiTimes,
- optional customs/shipping datasets.

Output:

- product-level price and shortage signals,
- capacity/lead-time evidence,
- supplier/customer triples,
- physical bottleneck confidence.

### Phase 4: Social Smoke Detector

Integrate:

- X / Threads / Reddit / PTT / 雪球 as weak-lead queues.

Output:

- lead queue,
- source-corroboration checklist,
- crowding heat.

## How This Changes Theme Discovery

Old weak pattern:

```text
headline mentions BBU -> keyword maps BBU stocks -> rank by price
```

Desired pattern:

```text
social/trade lead mentions BBU shortage
-> agent decomposes: AI rack power density -> rack-level BBU -> 21700 high-power cells -> pack assembler
-> official/trade evidence confirms Samsung SDI/Panasonic/Simplo path
-> graph maps direct, supplier, second-order and false-friend nodes
-> leaders move, laggards are checked for turn
-> chips/crowding gate decides whether it is still early
```

This is the path from "concept stock list" to actual proactive theme mining.
