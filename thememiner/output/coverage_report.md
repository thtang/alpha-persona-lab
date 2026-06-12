# ThemeMiner Coverage Audit

Generated at: 2026-06-12T06:22:53.856777+00:00

## Summary

- Stocks: 2402
- Concept-stock edges: 6682
- Price-correlation edges: 3129
- Product nodes: 604
- Supply-layer nodes: 56
- Concept supply-chain edges: 279
- Product-stock edges: 15820
- Layer-stock edges: 2493
- Same-product peer edges: 9711
- Same-layer peer edges: 1997
- Profile status: {'profiled': 84, 'fallback_from_concepts': 26, 'official_sec_profile': 350, 'market_metadata_profile': 94, 'official_tw_exchange_profile': 1846, 'auto_yahoo_search': 1, 'discovered_exchange_rules': 1}
- Profile quality: {'curated': 84, 'fallback': 26, 'official_sec_profile': 350, 'market_metadata_profile': 94, 'official_tw_exchange_profile': 1846, 'auto_yahoo_search': 1, 'discovered_exchange_rules': 1}
- Usable business profiles with source refs: 2376 / 2402
- Markets: {'US': 428, 'JP': 37, 'KR': 6, 'TW': 1872, 'CN': 44, 'HK': 15}

## Node Types

stock=2402, product=604, concept=156, supply_layer=56, category=8

## Edge Types

same_concept_cross_market=36021, product_stock=15820, same_product_peer=9711, concept_stock=6682, stock_downstream_concept=6183, upstream_concept_stock=4130, price_correlation=3129, layer_stock=2493, same_supply_layer_peer=1997, concept_supply_chain=279, product_concept=223, category_concept=156, layer_concept=56

## Top Theme Coverage

| Theme | Score | Stocks | Curated/Profiled | Usable Business Profiles | Products | Layers | Up | Down | Corr Edges |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 薄膜電容 `film_capacitor` | 72.1 | 3 | 1 (33%) | 3 (100%) | 3 | 1 | 3 | 4 | 0 |
| 電感/扼流圈 `inductor_choke` | 70.9 | 8 | 6 (75%) | 8 (100%) | 4 | 1 | 2 | 3 | 0 |
| Agentic AI系統級基建 `agentic_ai_infrastructure` | 69.7 | 2 | 1 (50%) | 2 (100%) | 3 | 1 | 4 | 5 | 0 |
| 鉭電容 `tantalum_capacitor` | 68.5 | 2 | 2 (100%) | 2 (100%) | 0 | 0 | 0 | 0 | 0 |
| 晶片電阻 `chip_resistor` | 67.5 | 5 | 3 (60%) | 5 (100%) | 4 | 1 | 2 | 3 | 0 |
| TPU Cloud/ASIC算力 `tpu_cloud` | 59.5 | 7 | 4 (57%) | 7 (100%) | 0 | 0 | 1 | 0 | 1 |
| 高壓MLCC `high_voltage_mlcc` | 58.4 | 12 | 7 (58%) | 12 (100%) | 3 | 1 | 3 | 4 | 1 |
| AI算力Capex `ai_capex` | 54.7 | 13 | 9 (69%) | 13 (100%) | 0 | 0 | 15 | 1 | 1 |
| 雲端資安/SASE/CNAPP `cloud_security_sase` | 54.4 | 8 | 4 (50%) | 6 (75%) | 5 | 1 | 4 | 2 | 0 |
| IP/ASIC `ip_asic` | 54.0 | 9 | 4 (44%) | 9 (100%) | 0 | 0 | 1 | 3 | 0 |
| 紙業 `paper` | 51.6 | 7 | 0 (0%) | 7 (100%) | 0 | 0 | 0 | 0 | 2 |
| HVDC功率半導體 `hvdc_power_semiconductor` | 50.4 | 7 | 6 (86%) | 7 (100%) | 5 | 1 | 6 | 5 | 0 |
| 特殊玻纖/光纖耦合 `specialty_glass_fiber` | 49.4 | 6 | 6 (100%) | 6 (100%) | 0 | 0 | 0 | 1 | 1 |
| CPO/光通訊 `cpo_optical` | 49.4 | 17 | 17 (100%) | 17 (100%) | 4 | 1 | 6 | 4 | 8 |
| 雲端/AI軟體 `cloud_ai` | 48.8 | 95 | 9 (9%) | 87 (92%) | 0 | 0 | 7 | 10 | 54 |
| AI應用軟體/創作工具 `ai_application_software` | 48.0 | 17 | 0 (0%) | 3 (18%) | 5 | 1 | 2 | 3 | 1 |
| InP磷化銦光子 `inp_photonics` | 47.8 | 9 | 8 (89%) | 9 (100%) | 4 | 1 | 2 | 3 | 3 |
| 固態鋁電容/SP-Cap `aluminum_polymer_cap` | 47.6 | 10 | 8 (80%) | 10 (100%) | 4 | 1 | 2 | 4 | 2 |
| HBM `hbm` | 46.9 | 12 | 4 (33%) | 12 (100%) | 2 | 1 | 6 | 2 | 2 |
| IC-DRAM製造 `dram_manufacturing` | 46.9 | 9 | 1 (11%) | 9 (100%) | 3 | 1 | 2 | 6 | 2 |
| 金控 `financial_holding` | 46.3 | 46 | 0 (0%) | 46 (100%) | 0 | 0 | 3 | 0 | 46 |
| EMS `ems` | 45.6 | 104 | 2 (2%) | 104 (100%) | 0 | 0 | 1 | 0 | 6 |
| Host DRAM/上下文記憶 `host_dram` | 45.3 | 2 | 1 (50%) | 2 (100%) | 4 | 1 | 5 | 4 | 0 |
| 電線電纜 `wire_cable` | 44.5 | 31 | 4 (13%) | 31 (100%) | 0 | 0 | 1 | 1 | 14 |
| 資安 `cybersecurity` | 44.0 | 56 | 6 (11%) | 51 (91%) | 0 | 0 | 5 | 1 | 34 |
| AI PC `ai_pc` | 43.8 | 5 | 2 (40%) | 5 (100%) | 0 | 0 | 2 | 0 | 0 |
| Vera Rubin `vera_rubin` | 43.4 | 6 | 5 (83%) | 6 (100%) | 0 | 0 | 0 | 0 | 1 |
| 系統整合 `system_integration` | 43.1 | 85 | 0 (0%) | 79 (93%) | 0 | 0 | 4 | 0 | 63 |
| CoWoS `cowos` | 42.9 | 5 | 2 (40%) | 5 (100%) | 0 | 0 | 0 | 0 | 0 |
| 化學工業 `chemicals` | 42.6 | 54 | 1 (2%) | 54 (100%) | 0 | 0 | 1 | 11 | 15 |
| 金屬製品 `metal_parts` | 42.4 | 57 | 0 (0%) | 57 (100%) | 0 | 0 | 0 | 9 | 84 |
| 保險 `insurance` | 42.1 | 71 | 0 (0%) | 71 (100%) | 3 | 1 | 2 | 1 | 90 |
| 航運 `shipping` | 42.0 | 50 | 0 (0%) | 50 (100%) | 3 | 1 | 2 | 1 | 32 |
| 企業級SSD/eSSD `enterprise_ssd` | 41.3 | 6 | 4 (67%) | 6 (100%) | 4 | 1 | 3 | 5 | 1 |
| 銀行 `banks` | 41.1 | 186 | 0 (0%) | 186 (100%) | 3 | 1 | 2 | 4 | 90 |
| 物流 `logistics` | 40.3 | 39 | 0 (0%) | 39 (100%) | 0 | 0 | 1 | 0 | 29 |
| 新藥 `new_drug` | 40.2 | 166 | 0 (0%) | 166 (100%) | 0 | 0 | 1 | 2 | 52 |
| CDMO/CRO `cdmo_cro` | 40.2 | 165 | 0 (0%) | 165 (100%) | 4 | 1 | 1 | 3 | 52 |
| 電源供應器 `power_supply` | 40.1 | 98 | 2 (2%) | 98 (100%) | 4 | 1 | 15 | 3 | 4 |
| 銅/銅箔 `copper` | 40.0 | 32 | 0 (0%) | 32 (100%) | 3 | 1 | 1 | 9 | 27 |
| 玻璃陶瓷 `glass_ceramics` | 40.0 | 9 | 1 (11%) | 9 (100%) | 0 | 0 | 0 | 2 | 0 |
| 消費電子 `consumer_electronics` | 39.9 | 128 | 0 (0%) | 128 (100%) | 0 | 0 | 4 | 0 | 5 |
| 證券 `securities` | 39.5 | 41 | 0 (0%) | 41 (100%) | 0 | 0 | 0 | 0 | 45 |
| 被動元件 `passive_components` | 39.5 | 230 | 16 (7%) | 230 (100%) | 4 | 1 | 3 | 6 | 90 |
| 被動元件通路 `passive_component_distribution` | 39.1 | 38 | 2 (5%) | 38 (100%) | 0 | 0 | 0 | 0 | 3 |

## Missing Business/Profile Refs

| Symbol | Market | Status | Concepts | Business |
|---|---|---|---|---|
| 002230.SZ | CN | fallback_from_concepts | ai_agent_apps, ai_application_software, cloud_ai | 科大訊飛 is tracked as a AI Agent應用/工作流 / AI應用軟體/創作工具 / 雲端/AI軟體 theme node. Full company profile pending. |
| 300454.SZ | CN | fallback_from_concepts | cloud_security_sase, cybersecurity, system_integration | 深信服 is tracked as a 雲端資安/SASE/CNAPP / 資安 / 系統整合 theme node. Full company profile pending. |
| 600588.SS | CN | fallback_from_concepts | cloud_ai, enterprise_saas_workflow, system_integration | 用友網絡 is tracked as a 雲端/AI軟體 / 企業SaaS/工作流 / 系統整合 theme node. Full company profile pending. |
| 688111.SS | CN | fallback_from_concepts | ai_application_software, cloud_ai, enterprise_saas_workflow | 金山辦公 is tracked as a AI應用軟體/創作工具 / 雲端/AI軟體 / 企業SaaS/工作流 theme node. Full company profile pending. |
| 0700.HK | HK | fallback_from_concepts | ai_application_software, cloud_ai, fintech_payments_software, gaming | Tencent is tracked as a AI應用軟體/創作工具 / 雲端/AI軟體 / 金融科技/支付軟體 / 遊戲 theme node. Full company profile pending. |
| 1024.HK | HK | fallback_from_concepts | ai_application_software, ecommerce | Kuaishou is tracked as a AI應用軟體/創作工具 / 電商 theme node. Full company profile pending. |
| 3690.HK | HK | fallback_from_concepts | ai_application_software, ecommerce, fintech_payments_software | Meituan is tracked as a AI應用軟體/創作工具 / 電商 / 金融科技/支付軟體 theme node. Full company profile pending. |
| 9888.HK | HK | fallback_from_concepts | ai_agent_apps, ai_application_software, autonomous_driving, cloud_ai | Baidu is tracked as a AI Agent應用/工作流 / AI應用軟體/創作工具 / 自動駕駛/ADAS / 雲端/AI軟體 theme node. Full company profile pending. |
| 9988.HK | HK | fallback_from_concepts | ai_agent_apps, ai_data_platform, cloud_ai, ecommerce | Alibaba is tracked as a AI Agent應用/工作流 / AI資料平台/湖倉 / 雲端/AI軟體 / 電商 theme node. Full company profile pending. |
| 3697.T | JP | fallback_from_concepts | enterprise_saas_workflow, observability_devops, system_integration | SHIFT is tracked as a 企業SaaS/工作流 / Observability/DevOps / 系統整合 theme node. Full company profile pending. |
| 4684.T | JP | fallback_from_concepts | enterprise_saas_workflow, system_integration | OBIC is tracked as a 企業SaaS/工作流 / 系統整合 theme node. Full company profile pending. |
| 4751.T | JP | fallback_from_concepts | ai_application_software, ecommerce, gaming | CyberAgent is tracked as a AI應用軟體/創作工具 / 電商 / 遊戲 theme node. Full company profile pending. |
| 6701.T | JP | fallback_from_concepts | ai_data_platform, communication_equipment, cybersecurity, system_integration | NEC is tracked as a AI資料平台/湖倉 / 通訊設備 / 資安 / 系統整合 theme node. Full company profile pending. |
| 9613.T | JP | fallback_from_concepts | cloud_ai, enterprise_saas_workflow, system_integration | NTT DATA Group is tracked as a 雲端/AI軟體 / 企業SaaS/工作流 / 系統整合 theme node. Full company profile pending. |
| 6741.TW | TW | fallback_from_concepts | ai_application_software, ecommerce, fintech_payments_software | 91APP-KY is tracked as a AI應用軟體/創作工具 / 電商 / 金融科技/支付軟體 theme node. Full company profile pending. |
| ADBE | US | fallback_from_concepts | ai_application_software, cloud_ai, enterprise_saas_workflow | Adobe is tracked as a AI應用軟體/創作工具 / 雲端/AI軟體 / 企業SaaS/工作流 theme node. Full company profile pending. |
| APP | US | fallback_from_concepts | ai_application_software, ecommerce, gaming | AppLovin is tracked as a AI應用軟體/創作工具 / 電商 / 遊戲 theme node. Full company profile pending. |
| DUOL | US | fallback_from_concepts | ai_application_software, ecommerce | Duolingo is tracked as a AI應用軟體/創作工具 / 電商 theme node. Full company profile pending. |
| FTNT | US | fallback_from_concepts | cloud_security_sase, cybersecurity, networking | Fortinet is tracked as a 雲端資安/SASE/CNAPP / 資安 / 網通 theme node. Full company profile pending. |
| GTLB | US | fallback_from_concepts | cybersecurity, enterprise_saas_workflow, observability_devops | GitLab is tracked as a 資安 / 企業SaaS/工作流 / Observability/DevOps theme node. Full company profile pending. |
| INTU | US | fallback_from_concepts | ai_application_software, enterprise_saas_workflow, fintech_payments_software | Intuit is tracked as a AI應用軟體/創作工具 / 企業SaaS/工作流 / 金融科技/支付軟體 theme node. Full company profile pending. |
| OKTA | US | fallback_from_concepts | cybersecurity, enterprise_saas_workflow, identity_security | Okta is tracked as a 資安 / 企業SaaS/工作流 / 身份安全/IAM theme node. Full company profile pending. |
| PATH | US | fallback_from_concepts | ai_agent_apps, enterprise_saas_workflow | UiPath is tracked as a AI Agent應用/工作流 / 企業SaaS/工作流 theme node. Full company profile pending. |
| SHOP | US | fallback_from_concepts | ai_application_software, ecommerce, fintech_payments_software | Shopify is tracked as a AI應用軟體/創作工具 / 電商 / 金融科技/支付軟體 theme node. Full company profile pending. |
| TEAM | US | fallback_from_concepts | ai_agent_apps, enterprise_saas_workflow, observability_devops | Atlassian is tracked as a AI Agent應用/工作流 / 企業SaaS/工作流 / Observability/DevOps theme node. Full company profile pending. |
| U | US | fallback_from_concepts | ai_application_software, gaming | Unity Software is tracked as a AI應用軟體/創作工具 / 遊戲 theme node. Full company profile pending. |
