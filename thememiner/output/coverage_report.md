# ThemeMiner Coverage Audit

Generated at: 2026-05-23T18:14:24.752292+00:00

## Summary

- Stocks: 2362
- Concept-stock edges: 6646
- Price-correlation edges: 3392
- Product nodes: 462
- Supply-layer nodes: 45
- Concept supply-chain edges: 220
- Product-stock edges: 15638
- Layer-stock edges: 2464
- Same-product peer edges: 9927
- Same-layer peer edges: 2032
- Profile status: {'profiled': 72, 'official_sec_profile': 350, 'market_metadata_profile': 94, 'official_tw_exchange_profile': 1846}
- Profile quality: {'curated': 72, 'official_sec_profile': 350, 'market_metadata_profile': 94, 'official_tw_exchange_profile': 1846}
- Usable business profiles with source refs: 2362 / 2362
- Markets: {'US': 404, 'JP': 32, 'KR': 6, 'TW': 1870, 'CN': 40, 'HK': 10}

## Node Types

stock=2362, product=462, concept=145, supply_layer=45, category=8

## Edge Types

same_concept_cross_market=33539, product_stock=15638, same_product_peer=9927, concept_stock=6646, stock_downstream_concept=5940, upstream_concept_stock=3895, price_correlation=3392, layer_stock=2464, same_supply_layer_peer=2032, concept_supply_chain=220, product_concept=165, category_concept=145, layer_concept=45

## Top Theme Coverage

| Theme | Score | Stocks | Curated/Profiled | Usable Business Profiles | Products | Layers | Up | Down | Corr Edges |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 鉭電容 `tantalum_capacitor` | 89.1 | 2 | 2 (100%) | 2 (100%) | 0 | 0 | 0 | 0 | 0 |
| 高壓MLCC `high_voltage_mlcc` | 88.4 | 12 | 7 (58%) | 12 (100%) | 3 | 1 | 3 | 4 | 6 |
| 晶片電阻 `chip_resistor` | 88.3 | 5 | 3 (60%) | 5 (100%) | 4 | 1 | 2 | 3 | 1 |
| AI PC `ai_pc` | 76.4 | 3 | 2 (67%) | 3 (100%) | 0 | 0 | 2 | 0 | 0 |
| 手機製造 `smartphone_manufacturing` | 75.2 | 1 | 0 (0%) | 1 (100%) | 0 | 0 | 0 | 0 | 0 |
| 固態鋁電容/SP-Cap `aluminum_polymer_cap` | 73.9 | 10 | 8 (80%) | 10 (100%) | 4 | 1 | 2 | 4 | 10 |
| GPU加速器 `gpu_accelerator` | 69.9 | 7 | 4 (57%) | 7 (100%) | 0 | 0 | 3 | 0 | 1 |
| ABF `abf_substrate` | 68.6 | 7 | 1 (14%) | 7 (100%) | 3 | 1 | 3 | 4 | 3 |
| 牛角/大型鋁電容 `snap_in_capacitor` | 66.0 | 6 | 4 (67%) | 6 (100%) | 3 | 1 | 2 | 3 | 1 |
| Vera Rubin `vera_rubin` | 64.6 | 9 | 5 (56%) | 9 (100%) | 0 | 0 | 0 | 0 | 4 |
| PCB-材料設備 `pcb_material_equipment` | 61.1 | 9 | 1 (11%) | 9 (100%) | 4 | 1 | 4 | 5 | 3 |
| IP/ASIC `ip_asic` | 60.4 | 9 | 4 (44%) | 9 (100%) | 0 | 0 | 1 | 3 | 4 |
| HVDC功率半導體 `hvdc_power_semiconductor` | 59.4 | 11 | 7 (64%) | 11 (100%) | 4 | 1 | 3 | 5 | 2 |
| GB300 `gb300` | 53.6 | 6 | 2 (33%) | 6 (100%) | 0 | 0 | 1 | 0 | 1 |
| InP磷化銦光子 `inp_photonics` | 51.4 | 9 | 8 (89%) | 9 (100%) | 4 | 1 | 2 | 3 | 4 |
| TPU Cloud/ASIC算力 `tpu_cloud` | 49.9 | 6 | 3 (50%) | 6 (100%) | 0 | 0 | 1 | 0 | 3 |
| IC-代工 `foundry` | 49.8 | 211 | 10 (5%) | 211 (100%) | 2 | 1 | 5 | 6 | 90 |
| AI算力Capex `ai_capex` | 49.5 | 12 | 9 (75%) | 12 (100%) | 0 | 0 | 14 | 1 | 8 |
| CoWoS `cowos` | 49.4 | 5 | 2 (40%) | 5 (100%) | 0 | 0 | 0 | 0 | 2 |
| 物流 `logistics` | 48.9 | 39 | 0 (0%) | 39 (100%) | 0 | 0 | 1 | 0 | 15 |
| IC-DRAM製造 `dram_manufacturing` | 48.1 | 9 | 1 (11%) | 9 (100%) | 3 | 1 | 2 | 6 | 6 |
| 企業級SSD/eSSD `enterprise_ssd` | 47.9 | 5 | 4 (80%) | 5 (100%) | 4 | 1 | 3 | 4 | 0 |
| 被動元件 `passive_components` | 47.7 | 233 | 18 (8%) | 233 (100%) | 4 | 1 | 3 | 6 | 90 |
| 高速連接器/線纜 `high_speed_connector` | 47.2 | 6 | 4 (67%) | 6 (100%) | 4 | 1 | 3 | 3 | 0 |
| 晶圓材料 `wafer_materials` | 46.2 | 207 | 10 (5%) | 207 (100%) | 0 | 0 | 0 | 6 | 90 |
| 半導體元件 `semiconductor_components` | 45.9 | 211 | 11 (5%) | 211 (100%) | 5 | 1 | 3 | 6 | 90 |
| IC-半導體設備 `semicap_equipment` | 45.9 | 210 | 10 (5%) | 210 (100%) | 5 | 1 | 2 | 8 | 90 |
| 電線電纜 `wire_cable` | 45.3 | 31 | 4 (13%) | 31 (100%) | 0 | 0 | 1 | 1 | 0 |
| 連接元件 `connectors` | 45.2 | 216 | 12 (6%) | 216 (100%) | 0 | 0 | 0 | 2 | 90 |
| 航運 `shipping` | 44.5 | 50 | 0 (0%) | 50 (100%) | 3 | 1 | 2 | 1 | 16 |
| LED及光元件 `led_opto` | 44.3 | 120 | 3 (2%) | 120 (100%) | 0 | 0 | 0 | 0 | 90 |
| IC-設計 `ic_design` | 43.5 | 207 | 8 (4%) | 207 (100%) | 4 | 1 | 1 | 6 | 90 |
| 記憶體IC設計 `memory_ic_design` | 43.4 | 8 | 2 (25%) | 8 (100%) | 0 | 0 | 0 | 2 | 6 |
| AI Server PCB/ABF/基板 `server_pcb_abf` | 42.9 | 8 | 2 (25%) | 8 (100%) | 4 | 1 | 7 | 3 | 10 |
| IC-封測 `ic_packaging_testing` | 42.4 | 204 | 7 (3%) | 204 (100%) | 0 | 0 | 3 | 1 | 90 |
| PCB-製造 `pcb_manufacturing` | 41.7 | 218 | 9 (4%) | 218 (100%) | 3 | 1 | 3 | 4 | 90 |
| 光學鏡片 `optical_lens` | 41.5 | 118 | 1 (1%) | 118 (100%) | 0 | 0 | 0 | 0 | 90 |
| 被動元件通路 `passive_component_distribution` | 41.5 | 38 | 2 (5%) | 38 (100%) | 0 | 0 | 0 | 0 | 79 |
| HBM `hbm` | 40.4 | 12 | 4 (33%) | 12 (100%) | 2 | 1 | 6 | 2 | 4 |
| LCD-TFT面板 `lcd_tft` | 40.4 | 117 | 0 (0%) | 117 (100%) | 0 | 0 | 0 | 0 | 90 |
| 主機板 `motherboard` | 39.8 | 111 | 2 (2%) | 111 (100%) | 0 | 0 | 0 | 0 | 90 |
| 筆記型電腦 `notebook_pc` | 39.8 | 111 | 2 (2%) | 111 (100%) | 0 | 0 | 0 | 0 | 90 |
| DRAM銷售 `dram_distribution` | 39.5 | 1 | 1 (100%) | 1 (100%) | 0 | 0 | 0 | 0 | 0 |
| 銀行 `banks` | 39.5 | 186 | 0 (0%) | 186 (100%) | 3 | 1 | 1 | 4 | 90 |
| 電子元件通路 `electronics_distribution` | 39.2 | 249 | 9 (4%) | 249 (100%) | 0 | 0 | 0 | 0 | 90 |

## Missing Business/Profile Refs

- All stocks have a business profile and at least one source ref.
