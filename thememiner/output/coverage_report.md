# ThemeMiner Coverage Audit

Generated at: 2026-07-11T06:11:40.503299+00:00

## Summary

- Stocks: 2468
- Concept-stock edges: 6912
- Price-correlation edges: 5353
- Product nodes: 714
- Supply-layer nodes: 58
- Concept supply-chain edges: 293
- Product-stock edges: 16613
- Layer-stock edges: 2637
- Same-product peer edges: 12262
- Same-layer peer edges: 2466
- Profile status: {'profiled': 101, 'official_sec_profile': 368, 'market_metadata_profile': 110, 'official_tw_exchange_profile': 1856, 'auto_yahoo_search': 1, 'discovered_exchange_rules': 32}
- Profile quality: {'curated': 101, 'official_sec_profile': 368, 'market_metadata_profile': 110, 'official_tw_exchange_profile': 1856, 'auto_yahoo_search': 1, 'discovered_exchange_rules': 32}
- Usable business profiles with source refs: 2468 / 2468
- Markets: {'US': 440, 'DE': 1, 'JP': 38, 'KR': 50, 'TW': 1880, 'CN': 44, 'HK': 15}

## Node Types

stock=2468, product=714, concept=140, supply_layer=58, category=8

## Edge Types

same_concept_cross_market=46916, product_stock=16613, same_product_peer=12262, concept_stock=6912, stock_downstream_concept=6534, price_correlation=5353, upstream_concept_stock=4371, layer_stock=2637, same_supply_layer_peer=2466, concept_supply_chain=293, product_concept=232, category_concept=140, layer_concept=58

## Top Theme Coverage

| Theme | Score | Stocks | Curated/Profiled | Usable Business Profiles | Products | Layers | Up | Down | Corr Edges |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| HDD冷資料/長期記憶 `hdd_cold_storage` | 41.0 | 3 | 2 (67%) | 3 (100%) | 4 | 1 | 1 | 4 | 1 |
| SOI晶圓 `soi_wafer` | 40.3 | 2 | 2 (100%) | 2 (100%) | 0 | 0 | 0 | 1 | 1 |
| HVDC功率半導體 `hvdc_power_semiconductor` | 40.2 | 10 | 9 (90%) | 10 (100%) | 5 | 1 | 6 | 5 | 13 |
| AI PC `ai_pc` | 38.2 | 5 | 2 (40%) | 5 (100%) | 0 | 0 | 2 | 0 | 1 |
| AI資料中心BBU `data_center_bbu` | 37.3 | 15 | 10 (67%) | 15 (100%) | 5 | 1 | 6 | 5 | 25 |
| 企業級SSD/eSSD `enterprise_ssd` | 36.6 | 6 | 4 (67%) | 6 (100%) | 4 | 1 | 3 | 5 | 3 |
| GB300 `gb300` | 35.7 | 6 | 2 (33%) | 6 (100%) | 0 | 0 | 1 | 0 | 3 |
| AI算力Capex `ai_capex` | 34.4 | 13 | 9 (69%) | 13 (100%) | 0 | 0 | 17 | 1 | 17 |
| 功率分立元件/MOSFET `power_discrete_semiconductor` | 33.8 | 10 | 6 (60%) | 10 (100%) | 6 | 1 | 3 | 7 | 14 |
| CoWoS `cowos` | 33.4 | 5 | 2 (40%) | 5 (100%) | 0 | 0 | 0 | 0 | 3 |
| 雲端/AI軟體 `cloud_ai` | 32.6 | 103 | 10 (10%) | 103 (100%) | 0 | 0 | 8 | 10 | 90 |
| 保險 `insurance` | 32.3 | 75 | 0 (0%) | 75 (100%) | 3 | 1 | 2 | 1 | 90 |
| 金控 `financial_holding` | 32.2 | 49 | 0 (0%) | 49 (100%) | 0 | 0 | 3 | 0 | 90 |
| GPU加速器 `gpu_accelerator` | 31.9 | 7 | 4 (57%) | 7 (100%) | 0 | 0 | 3 | 0 | 5 |
| 雲端資安/SASE/CNAPP `cloud_security_sase` | 31.5 | 8 | 4 (50%) | 8 (100%) | 5 | 1 | 4 | 2 | 8 |
| KV Cache/RAG記憶體 `kv_cache_memory` | 30.9 | 5 | 3 (60%) | 5 (100%) | 4 | 1 | 6 | 2 | 5 |
| GLP-1/減重藥 `glp1_obesity` | 30.6 | 11 | 0 (0%) | 11 (100%) | 3 | 1 | 3 | 1 | 2 |
| CPO/光通訊 `cpo_optical` | 30.4 | 18 | 18 (100%) | 18 (100%) | 4 | 1 | 6 | 4 | 33 |
| GB200 `gb200` | 30.3 | 10 | 2 (20%) | 10 (100%) | 0 | 0 | 1 | 0 | 8 |
| CDMO/CRO `cdmo_cro` | 30.2 | 167 | 1 (1%) | 167 (100%) | 4 | 1 | 1 | 3 | 90 |
| 新藥 `new_drug` | 29.8 | 172 | 2 (1%) | 172 (100%) | 0 | 0 | 1 | 2 | 90 |
| 銀行 `banks` | 29.6 | 193 | 3 (2%) | 193 (100%) | 3 | 1 | 2 | 4 | 90 |
| AI應用軟體/創作工具 `ai_application_software` | 29.4 | 19 | 0 (0%) | 19 (100%) | 5 | 1 | 2 | 3 | 17 |
| 電商 `ecommerce` | 28.5 | 10 | 1 (10%) | 10 (100%) | 0 | 0 | 2 | 0 | 5 |
| 高功率圓柱電池 `high_power_cylindrical_battery` | 28.4 | 6 | 5 (83%) | 6 (100%) | 5 | 1 | 2 | 4 | 3 |
| 無人機 `drone` | 27.9 | 10 | 0 (0%) | 10 (100%) | 0 | 0 | 1 | 0 | 5 |
| 物流 `logistics` | 27.5 | 40 | 0 (0%) | 40 (100%) | 0 | 0 | 1 | 0 | 90 |
| 證券 `securities` | 27.5 | 44 | 0 (0%) | 44 (100%) | 0 | 0 | 0 | 0 | 90 |
| 記憶體IC設計 `memory_ic_design` | 27.5 | 8 | 2 (25%) | 8 (100%) | 0 | 0 | 0 | 2 | 11 |
| 油氣/LNG `oil_lng` | 27.4 | 181 | 0 (0%) | 181 (100%) | 4 | 1 | 1 | 4 | 90 |
| IP/ASIC `ip_asic` | 27.3 | 10 | 5 (50%) | 10 (100%) | 0 | 0 | 1 | 3 | 9 |
| 航運 `shipping` | 27.1 | 54 | 1 (2%) | 54 (100%) | 3 | 1 | 2 | 1 | 90 |
| 化學工業 `chemicals` | 25.7 | 58 | 1 (2%) | 58 (100%) | 0 | 0 | 1 | 12 | 77 |
| 遊戲 `gaming` | 25.5 | 9 | 2 (22%) | 9 (100%) | 0 | 0 | 1 | 0 | 11 |
| AI資料平台/湖倉 `ai_data_platform` | 25.5 | 12 | 8 (67%) | 12 (100%) | 6 | 1 | 3 | 7 | 23 |
| 系統整合 `system_integration` | 25.2 | 91 | 0 (0%) | 91 (100%) | 0 | 0 | 4 | 0 | 90 |
| HBM `hbm` | 25.1 | 17 | 9 (53%) | 17 (100%) | 2 | 1 | 6 | 2 | 52 |
| AI先進製程/產能瓶頸 `ai_foundry_capacity` | 25.0 | 5 | 2 (40%) | 5 (100%) | 0 | 0 | 2 | 0 | 3 |
| InP磷化銦光子 `inp_photonics` | 24.6 | 9 | 8 (89%) | 9 (100%) | 4 | 1 | 2 | 3 | 9 |
| 資安 `cybersecurity` | 24.4 | 58 | 6 (10%) | 58 (100%) | 0 | 0 | 5 | 1 | 90 |
| 身份安全/IAM `identity_security` | 24.3 | 2 | 1 (50%) | 2 (100%) | 5 | 1 | 1 | 5 | 1 |
| AI測試/Probe Card/Interface `ai_test_probe_interface` | 24.2 | 10 | 4 (40%) | 10 (100%) | 5 | 1 | 2 | 4 | 6 |
| 半導體元件 `semiconductor_components` | 24.0 | 218 | 16 (7%) | 218 (100%) | 5 | 1 | 3 | 7 | 90 |
| Observability/DevOps `observability_devops` | 23.9 | 5 | 2 (40%) | 5 (100%) | 6 | 1 | 3 | 2 | 6 |
| 金融科技/支付軟體 `fintech_payments_software` | 23.9 | 13 | 1 (8%) | 13 (100%) | 4 | 1 | 2 | 3 | 5 |

## Missing Business/Profile Refs

- All stocks have a business profile and at least one source ref.
