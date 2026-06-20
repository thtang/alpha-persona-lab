# ThemeMiner Coverage Audit

Generated at: 2026-06-16T13:56:32.725097+00:00

## Summary

- Stocks: 2403
- Concept-stock edges: 6687
- Price-correlation edges: 5194
- Product nodes: 609
- Supply-layer nodes: 56
- Concept supply-chain edges: 279
- Product-stock edges: 15837
- Layer-stock edges: 2496
- Same-product peer edges: 9718
- Same-layer peer edges: 1999
- Profile status: {'profiled': 85, 'auto_yahoo_search': 27, 'official_sec_profile': 350, 'market_metadata_profile': 94, 'official_tw_exchange_profile': 1846, 'discovered_exchange_rules': 1}
- Profile quality: {'curated': 85, 'auto_yahoo_search': 27, 'official_sec_profile': 350, 'market_metadata_profile': 94, 'official_tw_exchange_profile': 1846, 'discovered_exchange_rules': 1}
- Usable business profiles with source refs: 2403 / 2403
- Markets: {'US': 429, 'JP': 37, 'KR': 6, 'TW': 1872, 'CN': 44, 'HK': 15}

## Node Types

stock=2403, product=609, concept=156, supply_layer=56, category=8

## Edge Types

same_concept_cross_market=36334, product_stock=15837, same_product_peer=9718, concept_stock=6687, stock_downstream_concept=6191, price_correlation=5194, upstream_concept_stock=4136, layer_stock=2496, same_supply_layer_peer=1999, concept_supply_chain=279, product_concept=223, category_concept=156, layer_concept=56

## Top Theme Coverage

| Theme | Score | Stocks | Curated/Profiled | Usable Business Profiles | Products | Layers | Up | Down | Corr Edges |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 晶片電阻 `chip_resistor` | 80.4 | 5 | 3 (60%) | 5 (100%) | 4 | 1 | 2 | 3 | 2 |
| 高壓MLCC `high_voltage_mlcc` | 76.6 | 12 | 7 (58%) | 12 (100%) | 3 | 1 | 3 | 4 | 30 |
| HDD冷資料/長期記憶 `hdd_cold_storage` | 75.1 | 3 | 2 (67%) | 3 (100%) | 4 | 1 | 1 | 4 | 1 |
| KV Cache/RAG記憶體 `kv_cache_memory` | 71.8 | 4 | 3 (75%) | 4 (100%) | 4 | 1 | 6 | 2 | 3 |
| 外延/MOCVD設備 `epitaxy_equipment` | 71.1 | 1 | 1 (100%) | 1 (100%) | 0 | 0 | 0 | 1 | 0 |
| 企業級SSD/eSSD `enterprise_ssd` | 68.5 | 6 | 4 (67%) | 6 (100%) | 4 | 1 | 3 | 5 | 3 |
| 鉭電容 `tantalum_capacitor` | 68.5 | 2 | 2 (100%) | 2 (100%) | 0 | 0 | 0 | 0 | 0 |
| IC-DRAM製造 `dram_manufacturing` | 67.1 | 9 | 1 (11%) | 9 (100%) | 3 | 1 | 2 | 6 | 23 |
| Agentic AI系統級基建 `agentic_ai_infrastructure` | 63.0 | 2 | 1 (50%) | 2 (100%) | 3 | 1 | 4 | 5 | 0 |
| 精密感測/量測 `precision_sensing` | 62.6 | 1 | 1 (100%) | 1 (100%) | 0 | 0 | 0 | 2 | 0 |
| 固態鋁電容/SP-Cap `aluminum_polymer_cap` | 61.0 | 10 | 8 (80%) | 10 (100%) | 4 | 1 | 2 | 4 | 11 |
| HBM `hbm` | 56.5 | 12 | 4 (33%) | 12 (100%) | 2 | 1 | 6 | 2 | 25 |
| 薄膜電容 `film_capacitor` | 56.4 | 3 | 1 (33%) | 3 (100%) | 3 | 1 | 3 | 4 | 0 |
| 電感/扼流圈 `inductor_choke` | 54.5 | 8 | 6 (75%) | 8 (100%) | 4 | 1 | 2 | 3 | 9 |
| IC-製造 `ic_manufacturing` | 53.5 | 1 | 1 (100%) | 1 (100%) | 0 | 0 | 0 | 0 | 0 |
| 手機製造 `smartphone_manufacturing` | 53.5 | 1 | 0 (0%) | 1 (100%) | 0 | 0 | 0 | 0 | 0 |
| SOI晶圓 `soi_wafer` | 52.8 | 2 | 2 (100%) | 2 (100%) | 0 | 0 | 0 | 1 | 1 |
| Host DRAM/上下文記憶 `host_dram` | 51.1 | 2 | 1 (50%) | 2 (100%) | 4 | 1 | 5 | 4 | 0 |
| 記憶體IC設計 `memory_ic_design` | 50.5 | 8 | 2 (25%) | 8 (100%) | 0 | 0 | 0 | 2 | 11 |
| 矽光子/SiPh `silicon_photonics` | 50.2 | 7 | 7 (100%) | 7 (100%) | 3 | 1 | 3 | 3 | 4 |
| CPU Socket/測試座/插槽 `cpu_socket` | 49.7 | 5 | 3 (60%) | 5 (100%) | 4 | 1 | 3 | 2 | 1 |
| AI PC `ai_pc` | 49.3 | 5 | 2 (40%) | 5 (100%) | 0 | 0 | 2 | 0 | 1 |
| AI測試/Probe Card/Interface `ai_test_probe_interface` | 48.9 | 10 | 4 (40%) | 10 (100%) | 5 | 1 | 2 | 4 | 4 |
| PCB-材料設備 `pcb_material_equipment` | 48.4 | 9 | 0 (0%) | 9 (100%) | 4 | 1 | 4 | 5 | 7 |
| 銀行 `banks` | 47.3 | 186 | 0 (0%) | 186 (100%) | 3 | 1 | 2 | 4 | 90 |
| Legacy記憶體 `legacy_memory` | 45.9 | 3 | 0 (0%) | 3 (100%) | 0 | 0 | 0 | 0 | 1 |
| IP/ASIC `ip_asic` | 45.0 | 10 | 5 (50%) | 10 (100%) | 0 | 0 | 1 | 3 | 7 |
| 無人機 `drone` | 44.5 | 10 | 0 (0%) | 10 (100%) | 0 | 0 | 1 | 0 | 5 |
| 保險 `insurance` | 44.4 | 71 | 0 (0%) | 71 (100%) | 3 | 1 | 2 | 1 | 90 |
| HVDC功率半導體 `hvdc_power_semiconductor` | 43.9 | 7 | 6 (86%) | 7 (100%) | 5 | 1 | 6 | 5 | 7 |
| 金控 `financial_holding` | 43.8 | 46 | 0 (0%) | 46 (100%) | 0 | 0 | 3 | 0 | 90 |
| InP磷化銦光子 `inp_photonics` | 43.1 | 9 | 8 (89%) | 9 (100%) | 4 | 1 | 2 | 3 | 11 |
| 二次電池 `battery_secondary` | 42.5 | 3 | 3 (100%) | 3 (100%) | 0 | 0 | 0 | 0 | 2 |
| ABF `abf_substrate` | 42.3 | 7 | 0 (0%) | 7 (100%) | 3 | 1 | 3 | 4 | 7 |
| CoWoS `cowos` | 41.7 | 5 | 2 (40%) | 5 (100%) | 0 | 0 | 0 | 0 | 3 |
| 被動元件 `passive_components` | 40.9 | 230 | 16 (7%) | 230 (100%) | 4 | 1 | 3 | 6 | 90 |
| 玻璃陶瓷 `glass_ceramics` | 40.6 | 9 | 1 (11%) | 9 (100%) | 0 | 0 | 0 | 2 | 3 |
| GPU加速器 `gpu_accelerator` | 39.7 | 7 | 4 (57%) | 7 (100%) | 0 | 0 | 3 | 0 | 5 |
| 銅/銅箔 `copper` | 39.7 | 32 | 0 (0%) | 32 (100%) | 3 | 1 | 1 | 9 | 90 |
| 電源管理IC/PMIC `power_management_ic` | 39.1 | 4 | 0 (0%) | 4 (100%) | 5 | 1 | 2 | 6 | 5 |
| 紙業 `paper` | 39.0 | 7 | 0 (0%) | 7 (100%) | 0 | 0 | 0 | 0 | 9 |
| 金屬製品 `metal_parts` | 38.6 | 57 | 0 (0%) | 57 (100%) | 0 | 0 | 0 | 9 | 90 |
| 軍工/國防 `defense` | 38.4 | 29 | 2 (7%) | 29 (100%) | 4 | 1 | 2 | 1 | 32 |
| CPO/光通訊 `cpo_optical` | 38.0 | 18 | 18 (100%) | 18 (100%) | 4 | 1 | 6 | 4 | 42 |
| CPU-Memory Interface/CXL `memory_interface` | 37.6 | 1 | 0 (0%) | 1 (100%) | 4 | 1 | 4 | 3 | 0 |

## Missing Business/Profile Refs

- All stocks have a business profile and at least one source ref.
