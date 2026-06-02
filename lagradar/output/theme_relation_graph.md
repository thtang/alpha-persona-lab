# Lagradar Cross-Market Theme Relation Graph

Generated from `lagradar/data/cross_market_theme_seed.json`. This is a trading map, not a full company encyclopedia.

## Signal Flow

```mermaid
flowchart LR
  Shock["Leader shock
price / earnings / policy / commodity / rates"] --> Relation["Relation graph
same industry / supply chain / macro exposure"]
  Relation --> Heat["Theme heat
leader 20D/60D + breadth"]
  Heat --> Gap["Laggard gap
leader move - follower move"]
  Gap --> Turn["Turn confirmation
3D/5D/10D + volume + MA reclaim + breakout"]
  Turn --> Diffusion["Diffusion breadth
multiple peers confirm"]
  Diffusion --> Overheat["Overheat check
20D MA distance / crowded volume / climax"]
  Overheat --> Candidate["Improving laggard watchlist
trigger + invalidation + size cap"]
```

## Cross-Market Map

```mermaid
flowchart LR
  subgraph LeaderMarkets["Leader / Shock Markets"]
    USL["US
ETFs, mega caps, commodities, rates"]
    JPL["Japan
components, materials, banks, defense"]
    KRL["Korea
memory, biotech, defense"]
    CNL["China/HK
policy, commodities, shipping, banks"]
    TWL["Taiwan
local leaders, supply-chain beta"]
  end

  subgraph Themes["Theme Layer"]
    passive_components["被動元件/MLCC/電阻電容"]
    power_grid_transformer["重電/變壓器/電網"]
    memory_hbm["記憶體/HBM/儲存"]
    ai_server_power_thermal["AI伺服器/電源/散熱"]
    pcb_abf_ccl["PCB/ABF/CCL"]
    optical_800g_cpo["光通訊/800G/CPO"]
    copper_industrial_metals["銅/工業金屬/線纜"]
    energy_oil_lng["能源/油氣/LNG"]
    shipping_freight["航運/貨櫃/散裝/油輪"]
    defense_aerospace["軍工/航太/造船"]
    healthcare_glp1_cdmo["醫藥/GLP-1/CDMO"]
    banks_rates_insurance["金融/銀行/保險/利率"]
  end

  subgraph FollowerMarkets["Follower / Laggard Markets"]
    TWF["Taiwan
chips, components, shipping, financials, biotech"]
    CNF["China A
materials, policy, equipment, healthcare"]
    HKF["Hong Kong
China proxies, banks, energy, CRO/CDMO"]
    JPF["Japan
materials, banks, machinery, defense"]
    KRF["Korea
memory, defense, biotech"]
    USF["US second-line
ETF constituents / small-mid peers"]
  end
  ai_server_power_thermal --> CNF
  banks_rates_insurance --> CNF
  copper_industrial_metals --> CNF
  defense_aerospace --> CNF
  energy_oil_lng --> CNF
  healthcare_glp1_cdmo --> CNF
  memory_hbm --> CNF
  optical_800g_cpo --> CNF
  passive_components --> CNF
  pcb_abf_ccl --> CNF
  power_grid_transformer --> CNF
  shipping_freight --> CNF
  ai_server_power_thermal --> HKF
  banks_rates_insurance --> HKF
  copper_industrial_metals --> HKF
  energy_oil_lng --> HKF
  healthcare_glp1_cdmo --> HKF
  shipping_freight --> HKF
  banks_rates_insurance --> JPF
  copper_industrial_metals --> JPF
  defense_aerospace --> JPF
  energy_oil_lng --> JPF
  healthcare_glp1_cdmo --> JPF
  optical_800g_cpo --> JPF
  passive_components --> JPF
  pcb_abf_ccl --> JPF
  power_grid_transformer --> JPF
  shipping_freight --> JPF
  defense_aerospace --> KRF
  healthcare_glp1_cdmo --> KRF
  memory_hbm --> KRF
  ai_server_power_thermal --> TWF
  banks_rates_insurance --> TWF
  copper_industrial_metals --> TWF
  defense_aerospace --> TWF
  energy_oil_lng --> TWF
  healthcare_glp1_cdmo --> TWF
  memory_hbm --> TWF
  optical_800g_cpo --> TWF
  passive_components --> TWF
  pcb_abf_ccl --> TWF
  power_grid_transformer --> TWF
  shipping_freight --> TWF
  defense_aerospace --> USF
  memory_hbm --> USF
  optical_800g_cpo --> USF
  shipping_freight --> USF
  TWL --> ai_server_power_thermal
  USL --> ai_server_power_thermal
  CNL --> banks_rates_insurance
  JPL --> banks_rates_insurance
  USL --> banks_rates_insurance
  CNL --> copper_industrial_metals
  JPL --> copper_industrial_metals
  USL --> copper_industrial_metals
  CNL --> defense_aerospace
  JPL --> defense_aerospace
  KRL --> defense_aerospace
  USL --> defense_aerospace
  CNL --> energy_oil_lng
  JPL --> energy_oil_lng
  USL --> energy_oil_lng
  JPL --> healthcare_glp1_cdmo
  KRL --> healthcare_glp1_cdmo
  USL --> healthcare_glp1_cdmo
  CNL --> memory_hbm
  KRL --> memory_hbm
  USL --> memory_hbm
  CNL --> optical_800g_cpo
  JPL --> optical_800g_cpo
  TWL --> optical_800g_cpo
  USL --> optical_800g_cpo
  JPL --> passive_components
  TWL --> passive_components
  USL --> passive_components
  CNL --> pcb_abf_ccl
  JPL --> pcb_abf_ccl
  TWL --> pcb_abf_ccl
  CNL --> power_grid_transformer
  JPL --> power_grid_transformer
  USL --> power_grid_transformer
  CNL --> shipping_freight
  JPL --> shipping_freight
  TWL --> shipping_freight
  USL --> shipping_freight
```

## Theme Adjacency

| Theme | Leader markets | Follower markets | Typical path |
|---|---|---|---|
| 被動元件/MLCC/電阻電容 | JP, TW, US | CN, JP, TW | leader shock -> lag gap -> turn confirmation -> overheat check |
| 重電/變壓器/電網 | CN, JP, US | CN, JP, TW | leader shock -> lag gap -> turn confirmation -> overheat check |
| 記憶體/HBM/儲存 | CN, KR, US | CN, KR, TW, US | leader shock -> lag gap -> turn confirmation -> overheat check |
| AI伺服器/電源/散熱 | TW, US | CN, HK, TW | leader shock -> lag gap -> turn confirmation -> overheat check |
| PCB/ABF/CCL | CN, JP, TW | CN, JP, TW | leader shock -> lag gap -> turn confirmation -> overheat check |
| 光通訊/800G/CPO | CN, JP, TW, US | CN, JP, TW, US | leader shock -> lag gap -> turn confirmation -> overheat check |
| 銅/工業金屬/線纜 | CN, JP, US | CN, HK, JP, TW | leader shock -> lag gap -> turn confirmation -> overheat check |
| 能源/油氣/LNG | HK, JP, US | CN, HK, JP, TW | leader shock -> lag gap -> turn confirmation -> overheat check |
| 航運/貨櫃/散裝/油輪 | CN, JP, TW, US | CN, HK, JP, TW, US | leader shock -> lag gap -> turn confirmation -> overheat check |
| 軍工/航太/造船 | CN, JP, KR, US | CN, JP, KR, TW, US | leader shock -> lag gap -> turn confirmation -> overheat check |
| 醫藥/GLP-1/CDMO | JP, KR, US | CN, HK, JP, KR, TW | leader shock -> lag gap -> turn confirmation -> overheat check |
| 金融/銀行/保險/利率 | CN, HK, JP, US | CN, HK, JP, TW | leader shock -> lag gap -> turn confirmation -> overheat check |

## Current Backtest Read-Through

- Stronger historical diffusion buckets so far: optical/CPO, memory/HBM, PCB/ABF/CCL, passive components, AI server power/thermal, copper/industrial metals.
- Weaker or more conditional buckets so far: energy/oil/LNG and shipping/freight. They need stricter commodity/freight-rate and macro controls before promotion.
- All backtest rows are raw research signals; the next layer should neutralize market, sector, country, FX, rates, commodity, and own momentum.
