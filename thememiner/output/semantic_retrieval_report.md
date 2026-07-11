# Semantic Relation Index Report

Generated at: 2026-07-11T06:11:01.400171+00:00
Backend: mlx_local (mlx_local_embeddings_ready:cache=9906)
Judgments: 6795

## Authority Mix

| Authority | Count |
|---|---:|
| agent_verified | 6072 |
| fallback_recall_only | 461 |
| manual_override | 130 |
| semantic_supported | 111 |
| needs_review | 21 |

## Warning Mix

| Warning | Count |
|---|---:|
| fallback_or_unknown_source_quality | 278 |
| market_metadata_profile | 252 |
| relation_index_membership_without_path | 171 |

## High-Quality Examples

| Symbol | Theme | Authority | Quality | Similarity |
|---|---|---|---:|---:|
| `2421.TW` 建準 | GB200 | manual_override | 1.00 | 0.47 |
| `2421.TW` 建準 | GB300 | manual_override | 1.00 | 0.43 |
| `2421.TW` 建準 | 散熱零組件 | manual_override | 1.00 | 0.57 |
| `3029.TW` 零壹科技股份有限公司 | 雲端資安/SASE/CNAPP | manual_override | 1.00 | 0.44 |
| `3029.TW` 零壹科技股份有限公司 | 資安 | manual_override | 1.00 | 0.38 |
| `3029.TW` 零壹科技股份有限公司 | 系統整合 | manual_override | 1.00 | 0.35 |
| `3533.TW` 嘉澤 | CPU Socket/測試座/插槽 | manual_override | 1.00 | 0.67 |
| `3533.TW` 嘉澤 | 高速連接器/線纜 | manual_override | 1.00 | 0.63 |
| `6689.TW` 伊雲谷數位科技股份有限公司 | AI資料平台/湖倉 | manual_override | 1.00 | 0.45 |
| `6689.TW` 伊雲谷數位科技股份有限公司 | 雲端/AI軟體 | manual_override | 1.00 | 0.49 |
| `6689.TW` 伊雲谷數位科技股份有限公司 | 系統整合 | manual_override | 1.00 | 0.40 |
| `8046.TW` 南電 | AI Server PCB/ABF/基板 | manual_override | 1.00 | 0.36 |
| `AXTI` AXT | InP磷化銦光子 | manual_override | 1.00 | 0.62 |
| `AXTI` AXT | 晶圓材料 | manual_override | 1.00 | 0.52 |
| `CRM` Salesforce | AI Agent應用/工作流 | manual_override | 1.00 | 0.71 |
| `CRM` Salesforce | AI資料平台/湖倉 | manual_override | 1.00 | 0.58 |
| `CRM` Salesforce | 企業SaaS/工作流 | manual_override | 1.00 | 0.69 |
| `CRWD` CrowdStrike | AI Agent應用/工作流 | manual_override | 1.00 | 0.34 |
| `CRWD` CrowdStrike | 雲端資安/SASE/CNAPP | manual_override | 1.00 | 0.58 |
| `CRWD` CrowdStrike | 資安 | manual_override | 1.00 | 0.55 |

## Low-Quality Backlog Examples

| Symbol | Theme | Authority | Quality | Warnings |
|---|---|---|---:|---|
| `2327.TW` 國巨 | 晶片電阻 | fallback_recall_only | 0.18 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `2327.TW` 國巨 | 鉭電容 | fallback_recall_only | 0.18 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `6762.T` TDK | 高功率圓柱電池 | fallback_recall_only | 0.18 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `6762.T` TDK | 二次電池 | fallback_recall_only | 0.18 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `2472.TW` 立隆電 | 被動元件 | fallback_recall_only | 0.19 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `002484.SZ` 江海股份 | 被動元件 | fallback_recall_only | 0.19 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `3090.TW` 日電貿 | 電子元件通路 | fallback_recall_only | 0.19 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `6752.T` Panasonic Holdings | 二次電池 | fallback_recall_only | 0.21 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `TTDKY` TDK ADR | 二次電池 | fallback_recall_only | 0.21 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `TTDKY` TDK ADR | 高功率圓柱電池 | fallback_recall_only | 0.21 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `6435.TWO` 大中 | IC-設計 | fallback_recall_only | 0.22 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `229200.KS` KODEX KOSDAQ 150 | IC-半導體設備 | fallback_recall_only | 0.22 | fallback_or_unknown_source_quality |
| `^KQ11` KOSDAQ Composite | CDMO/CRO | fallback_recall_only | 0.22 | fallback_or_unknown_source_quality |
| `6449.TW` 鈺邦 | Vera Rubin | fallback_recall_only | 0.22 | fallback_or_unknown_source_quality |
| `^KQ11` KOSDAQ Composite | 新藥 | fallback_recall_only | 0.22 | fallback_or_unknown_source_quality |
| `2472.TW` 立隆電 | Vera Rubin | fallback_recall_only | 0.22 | fallback_or_unknown_source_quality |
| `^KQ11` KOSDAQ Composite | 遊戲 | fallback_recall_only | 0.22 | fallback_or_unknown_source_quality |
| `TSLA` Tesla | 電動車 | fallback_recall_only | 0.22 | fallback_or_unknown_source_quality, relation_index_membership_without_path |
| `229200.KS` KODEX KOSDAQ 150 | 新藥 | fallback_recall_only | 0.22 | fallback_or_unknown_source_quality |
| `^KQ11` KOSDAQ Composite | IC-半導體設備 | fallback_recall_only | 0.22 | fallback_or_unknown_source_quality |
| `^KS11` KOSPI Composite | 軍工/國防 | fallback_recall_only | 0.23 | fallback_or_unknown_source_quality |
| `2327.TW` 國巨 | 固態鋁電容/SP-Cap | fallback_recall_only | 0.23 | fallback_or_unknown_source_quality |
| `9888.HK` Baidu, Inc. | 自動駕駛/ADAS | fallback_recall_only | 0.23 | market_metadata_profile |
| `EWY` iShares MSCI South Korea ETF | 銀行 | fallback_recall_only | 0.23 | fallback_or_unknown_source_quality |
| `6762.T` TDK | 高壓MLCC | fallback_recall_only | 0.23 | fallback_or_unknown_source_quality |
| `229200.KS` KODEX KOSDAQ 150 | 遊戲 | fallback_recall_only | 0.23 | fallback_or_unknown_source_quality |
| `2327.TW` 國巨 | 被動元件 | fallback_recall_only | 0.23 | fallback_or_unknown_source_quality |
| `2327.TW` 國巨 | 高壓MLCC | fallback_recall_only | 0.23 | fallback_or_unknown_source_quality |
| `^KS11` KOSPI Composite | 銀行 | fallback_recall_only | 0.23 | fallback_or_unknown_source_quality |
| `9888.HK` Baidu, Inc. | 雲端/AI軟體 | fallback_recall_only | 0.23 | market_metadata_profile |
