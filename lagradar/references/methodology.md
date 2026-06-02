# Lagradar Methodology

Use this reference when the user asks to refine the model, design a backtest, explain whether a theme is diffusing, or distinguish a real laggard from a weak stock.

## Core Definition

Lagradar studies 5D, 10D, 20D, and 1M slow information diffusion:

```text
leader shock
-> economically related follower
-> follower has not fully reflected the shock
-> follower begins to confirm through price, volume, flow, or breadth
-> candidate survives cost, liquidity, FX, factor, and risk checks
```

It does not primarily trade minute-level lead-lag, one-day timezone reactions, or "this stock has not gone up yet" guesses.

## Evidence Chain

Require these layers before calling something a tradable laggard:

1. Shock: leader basket, ETF, commodity, policy, earnings, guidance, price index, or product-cycle move.
2. Relation: same industry, supply chain, customer-supplier, upstream/downstream, same product, segment exposure, ETF co-holding, or data-driven historical lead-lag.
3. Lag gap: predicted move implied by leaders minus follower actual move.
4. Turn confirmation: 3D/5D/10D strength, volume expansion, moving-average reclaim, 20D high proximity, or breakout.
5. Adoption: institutional flow, chip data, northbound/southbound flow, fund flow, analyst estimate revisions, or media/search attention.
6. Diffusion breadth: multiple related names move, not just one stock.
7. Overheat check: avoid names already in retail climax, limit-up clusters, stretched from 20D MA, or leader rollover.

If layers 1-3 exist but layer 4 is absent, label it `sleeping_laggard`, not a clean entry. If layer 4 exists but overheat is high, label it as catch-up/late-stage.

## Theme Lifecycle

| Stage | Label | Typical Evidence | Action |
|---:|---|---|---|
| 0 | latent/cold | news exists but leaders and followers are not strong | build graph, no trade |
| 1 | overseas validated | US/JP/KR/CN leaders show 5D/20D strength, local basket quiet | build local watchlist |
| 2 | local initial move | 1-3 local core stocks reclaim MAs or break 20D highs | small starter, define invalidation |
| 3 | diffusion confirmation | breadth, volume, and institutional adoption improve | hold core, search second-line laggards |
| 4 | retail climax/overheat | media heat, stretched 5D/20D returns, limit-up cluster, crowded volume | stop adding, trail or rotate |
| 5 | late catch-up/fade | leaders roll over while lower-quality followers still pop | reduce risk |

Best risk/reward is usually stage 2 -> stage 3.

## Signal Families

### AI supply-chain bottleneck arbitrage

This is for cases where the first-order winners are already obvious and crowded, so the research target moves to the physical constraint that gates the next architecture step:

```text
architecture shift
-> physical bottleneck layer
-> qualified supplier set
-> capacity gap / long lead time
-> low substitutability
-> not fully discovered by market
-> price, volume, order, or language confirmation
```

Use it for second/third-layer AI infrastructure work such as `InP磷化銦光子`, `矽光子/SiPh`, `SOI晶圓`, `外延/MOCVD設備`, `特殊玻纖/光纖耦合`, `光互連/光學中介層`, and `CPO/光通訊`. Do not promote a stock only because it says "AI" or "optical"; it needs a concrete gate: material, process tool, coupling precision, test capacity, packaging interface, or qualified supply slot.

### Big-to-small industry lag

```text
Signal[j,t] = value-weighted return of large-cap leaders in same subindustry over k days
Follower = smaller or lower-attention names in the same theme
```

Test `k` and holding horizons across 5D, 10D, 20D, and 1M.

### Customer-supplier momentum

```text
Signal[supplier_j,t] =
  sum(customer_weight[i,j,t] * customer_return[i,t-k:t])
```

If revenue share is unavailable, use equal-weighted customers, centrality weights, co-mention weights, or product exposure.

### Cross-industry spillover

```text
Signal[industry_B,t] =
  sum(relation_weight[A,B] * industry_A_return[t-k:t])
```

Useful for oil -> oil services, copper/grid -> electrical equipment, HBM -> substrate/packaging/equipment, rates -> banks/REITs.

### Cross-country same-industry

```text
Signal[country_c,industry_s,t] =
  US_or_global_industry_return[s,t-k:t]
```

Control local market, local sector, FX, global market, commodity, and rates.

### Segment/complicated-firm lag

```text
Signal[firm_j,t] =
  sum(pure_play_return[p,t-k:t] * segment_exposure[p,j,t])
```

Useful when a pure-play stock moves first and a conglomerate with the same hidden segment reprices later.

### Data-driven cross-stock momentum

```text
Signal[j,t] =
  sum(link_strength[i,j] * return[i,t-k:t])
```

Only keep asymmetric links after removing common factor, sector, and ordinary momentum components.

## Practical Scoring

Current MVP components:

```text
theme_heat = leader 20D/60D strength + leader breadth + leader near-high ratio
diffusion_score = follower positive breadth + near-high breadth + breakout breadth + volume breadth - overheat breadth
laggard_gap = leader max/median move - follower move
turning_score = short-term strength + MA reclaim + volume + near-high/breakout
overheat_score = stretched 5D/20D return + distance from 20D MA + crowded volume + breakout extension
candidate_score = theme_heat + diffusion_score + laggard_gap + turning_score + exposure - overheat
```

For bottleneck themes, add a small `bottleneck_profile.score` bonus only after the company profile identifies:

```text
layer + scarcity + substitutability + discovery_state + relation path
```

This keeps the model from treating a downstream module assembler and a non-substitutable upstream material supplier as identical concept stocks.

For Taiwan, add chip score when data is available:

```text
chip_score =
  trust consecutive buying
  + foreign buying or selling-pressure reduction
  + dealer alignment
  + margin not overheated
  + flow as % of volume
```

For China/Hong Kong, add policy/news and northbound/southbound flow when available.

## Backtest Standard

Minimum research design:

```text
Universe: US, Japan, Taiwan, China/HK, Korea theme nodes
Signals: leader shock, relation weight, laggard gap, turning, diffusion, overheat
Horizons: 5D, 10D, 20D, 1M
Controls: market, sector, country, FX, rates, commodity, own momentum, size, liquidity, volatility
Validation: rolling/out-of-sample, subsample by country/theme/regime
Costs: bid-ask, tax, slippage, limit-up/down, holiday calendars, liquidity cap
Exit: half lag gap closed, 10D MA lost, leader basket rolls over, breadth collapses, flow turns negative
```

Do not call the edge real until after-cost results survive controls for ordinary momentum and sector beta.

## Common Mistakes

- Treating any underperformer as a laggard.
- Using today's supply-chain map to backtest old periods.
- Ignoring own momentum and sector beta.
- Buying stage 4 media climax as if it were stage 2 initial adoption.
- Ignoring FX and local holidays in cross-market comparisons.
- Calling a single-stock move theme diffusion before breadth appears.
