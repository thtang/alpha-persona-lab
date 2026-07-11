---
name: thememiner
description: |
  Fine-grained real-time cross-market theme mining skill. Use when the user asks to discover
  market themes, concept stocks, 題材挖掘, 概念股, 細粒度類股, cross-market stock relation graphs,
  or asks to update a theme library and map US/Japan/Taiwan/China/HK/Korea related equities.
metadata:
  short-description: 即時跨市場細粒度題材挖掘與股票關聯圖
---

# ThemeMiner

ThemeMiner maintains a fine-grained theme library and cross-market stock relation graph. It is the upstream sensor for `lagradar`: ThemeMiner discovers and refreshes themes; Lagradar evaluates diffusion, laggards, and historical edge.

## Mandatory Refresh

Every time this skill is used for a market answer, update the theme library and stock graph first:

```bash
python3 thememiner/scripts/discover_market_universe.py --markets US,TW,TWO,KR --agent-mode auto
python3 thememiner/scripts/update_theme_graph.py --refresh-prices --refresh-news
python3 thememiner/scripts/build_company_thesis_cards.py --agent-mode auto
python3 thememiner/scripts/build_semantic_relation_index.py --backend auto
```

The discovery step scans broad exchange universes, proposes candidate concepts from product/supply-chain rules, and writes `data/discovered_universe.json`. When `THEMEMINER_AGENT_API_KEY` or `OPENAI_API_KEY` is available, `discover_market_universe.py --agent-mode auto` uses the agentic concept judge as the authority and the keyword/rule layer becomes candidate retrieval only. Without an agent, outputs are explicitly marked `match_authority=rule_fallback` and must be treated as lower confidence. Seed watchlists are only high-trust overrides, not the boundary of the graph. The refresh also adds price-correlation / lead-lag edges between stocks that share a theme, using daily-return correlation over the fetched price window. Use this to verify that a business-defined peer group is actually moving together instead of trusting concept labels blindly.

Agentic semantic judgment is preferred over hard matching:

```bash
export THEMEMINER_AGENT_API_KEY=...
export THEMEMINER_AGENT_MODEL=gpt-5-mini
python3 thememiner/scripts/discover_market_universe.py --markets US,TW,TWO,KR --agent-mode auto
python3 thememiner/scripts/build_company_thesis_cards.py --agent-mode auto
```

Without an API key, use the local Codex agent backend:

```bash
python3 thememiner/scripts/discover_market_universe.py --markets US,TW,TWO,KR --agent-mode on --agent-provider codex --agent-workers 3 --agent-batch-size 16
python3 thememiner/scripts/build_company_thesis_cards.py --agent-mode on --agent-provider codex --agent-workers 3 --agent-batch-size 12
python3 thememiner/scripts/run_codex_agent_refresh.py --workers 3 --markets US,TW,TWO,KR
```

Rules and keyword lists are allowed only as recall-oriented candidate generators or offline fallback. Do not present `rule_fallback` / `openai_agent_unavailable_no_api_key/codex_agent_unavailable_no_cli` cards as high-conviction business reasoning.

Hard-list audit:

- `data/product_supply_chain_rules.json`, taxonomy aliases, and Taiwan exchange industry maps are recall hints only. They may propose candidate concepts but cannot approve a stock-theme relation.
- `scrapling_source_fetcher.py` records raw term hits as `retrieval_matched_concepts` / `retrieval_matched_terms`. `matched_concepts` should be treated as authoritative only when `match_authority=agentic_source_judge`.
- `build_company_thesis_cards.py` is the final business-thesis gate. Prefer `agent_status=agent_applied` or `manual_override`; fallback summaries are backlog, not tradable conviction.
- `build_semantic_relation_index.py` writes `output/relation_judgments.json`, a stock-theme authority layer with `relation_quality_score`, `relation_authority`, `semantic_similarity`, and warnings. Lagradar consumes this file and penalizes fallback relations directly in candidate scoring.
- `THEME_TO_CONCEPTS` in graph/lagradar scripts is a legacy theme-id bridge, not a stock-business classifier.
- `ROLE_ALIASES` in lagradar only normalizes old seed roles such as `leader` or `supplier`; it is not concept evidence.
- `lagradar` consumes these authority flags and should penalize fallback rows instead of using label wordlists to decide whether a company is specific enough.

For company-profile upgrades and brittle/dynamic public pages, prefer the optional Scrapling runtime when `.venv` is available:

```bash
.venv/bin/python scripts/scrapling_smoke.py
.venv/bin/python thememiner/scripts/scrapling_source_fetcher.py --no-fetch
.venv/bin/python thememiner/scripts/scrapling_source_fetcher.py --limit 40 --agent-mode auto
.venv/bin/python thememiner/scripts/merge_source_evidence.py
```

Use Scrapling for official company pages, exchange pages, dynamic/news pages, and adaptive selectors; keep the existing cached Yahoo/exchange paths for fast broad scans.

For local embedding/reranker experiments, use `config/semantic_retrieval.json`. On a 16GB Apple Silicon machine, prefer Qwen3 0.6B MLX embedding/reranker for daily refreshes and reserve 4B for offline rebuilds. The semantic index script must keep lexical fallback enabled so the graph remains reproducible without model downloads.

Local MLX embedding backend:

```bash
.venv/bin/python -m pip install -r requirements-mlx.txt
.venv/bin/python thememiner/scripts/build_semantic_relation_index.py --backend mlx-local --embedding-model mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ
```

`--backend mlx-local` loads the MLX model in-process and caches vectors under `output/cache/semantic_embeddings/`. `--backend mlx-http` expects an OpenAI-compatible `/v1/embeddings` adapter and is useful for long-running local servers. `--backend auto` remains conservative unless `THEMEMINER_EMBEDDING_BACKEND=mlx-local` or `THEMEMINER_USE_LOCAL_EMBEDDINGS=1` is set. Always keep `lexical_similarity` in the output as explanation/fallback; do not use embedding scores alone as trade conviction.

The graph is a layered knowledge graph, not only a concept-stock table:

- `category -> concept` keeps the taxonomy navigable.
- `concept -> concept` supply-chain edges encode upstream/downstream diffusion paths.
- `product -> concept`, `product -> stock`, `layer -> concept`, and `layer -> stock` encode product specialization and supply-chain layer.
- `same_product_peer` and `same_supply_layer_peer` connect cross-market peers that can be used for laggard discovery.
- `price_correlation` is a market-behavior validation layer, not the source of truth.

For a faster check during conversation:

```bash
python3 thememiner/scripts/discover_market_universe.py --markets US,TW,TWO,KR --max-symbols 2500
python3 thememiner/scripts/update_theme_graph.py --max-concepts 80
```

Then query:

```bash
python3 thememiner/scripts/query_theme_graph.py --top 20
python3 thememiner/scripts/query_theme_graph.py --concept hbm
python3 thememiner/scripts/query_theme_graph.py --market TW --top 20
```

Build a local browser visualization:

```bash
python3 thememiner/scripts/build_theme_graph_html.py
open thememiner/output/theme_graph.html
```

Audit missing profile/correlation coverage:

```bash
python3 thememiner/scripts/audit_graph_coverage.py
```

Audit the source plan for proactive theme mining:

```bash
python3 thememiner/scripts/audit_data_source_registry.py
```

## Data Layout

- `data/data_source_registry_seed.json`: machine-readable registry of sources needed for proactive theme mining. It ranks official filings, exchange data, flow/chip data, physical supply-chain sources, macro data, and weak social leads by evidence tier, cadence, lead time, access method, parser strategy, and integration priority.
- `data/fine_theme_taxonomy_seed.json`: fine-grained taxonomy inspired by Taiwan 類股/概念股 pages, including 傳產, 電子上游/中游/下游, 軟體, 金融, 生技醫療, 原物料能源, logistics, and global concept tags.
- `data/cross_market_watchlist_seed.json`: initial US/Japan/Taiwan/China/HK/Korea stocks mapped to fine concepts.
- `data/kr_market_universe_seed.json`: curated Korea KOSPI/KOSDAQ universe bridge with Yahoo-compatible tickers, market proxies, business profiles, and concept hints for Samsung/SK Hynix memory, Samsung SDI/LGES batteries, power grid, defense, shipbuilding, healthcare, software/platform, and financials.
- `data/company_profiles_seed.json`: company-level background, product specialization, platform/customer exposure, constraint, risk flag, concept exposure, optional `bottleneck_profile`, and source evidence. Use this to explain why a company belongs to a theme instead of treating all concept stocks as interchangeable.
- `data/company_thesis_overrides.json`: curated high-priority thesis-card overrides for names whose raw exchange/profile mapping is too broad for trading reasoning, such as 華通 being high-layer PCB/HDI rather than passive components.
- `data/product_supply_chain_rules.json`: broad-universe product keyword rules that map exchange-listed companies into concept, product, upstream, and downstream supply-chain layers.
- `data/discovered_universe.json`: latest broad-market discovery output. This is generated from exchange lists and merged into the graph before curated profile overrides.
- `output/theme_library.json`: refreshed theme library with live news/price evidence.
- `output/cross_market_stock_graph.json`: concept-stock and stock-stock relation graph.
- `output/company_profiles.json`: normalized company profiles used in the latest graph build.
- `output/company_thesis_cards.json`: generated per-company trade-reasoning cards with thesis label, business segments, AI-chain position, non-AI drivers, catalysts, leader indicators, peer symbols, relation confidence, and risks. Lagradar reads this before ranking or recommending candidates.
- `output/relation_judgments.json`: stock-theme relation judgments used by Lagradar to adjust scores by business-fit authority instead of raw keyword overlap.
- `output/semantic_retrieval_report.md`: audit report for relation authority, low-quality fallback backlog, and high-quality relation examples.
- `output/theme_candidates.json`: ranked active themes.
- `output/news_evidence.jsonl`: headline evidence.
- `output/theme_report.md`: compact report.
- `output/theme_graph.html`: self-contained local HTML visualization for the theme-stock relation graph.
- `output/theme_correlations.json`: same-theme price-correlation and lead-lag edges.
- `output/relation_index.json`: concept-centric traversal index with upstream/downstream concepts, products, layers, stock members, same-product peers, same-layer peers, and correlation edge counts.
- `output/coverage_report.md`: profile coverage, fallback-profile backlog, and correlation coverage by theme.
- `output/profile_upgrade_queue.json`: Scrapling-backed queue of company profiles that most need official/source-page evidence, prioritized by Lagradar candidates, hot themes, profile gaps, and source coverage.
- `output/source_pages/`: cached raw Scrapling source pages with extracted text, retrieval term hits, agent source-judge output, and page-level metadata.
- `output/company_source_evidence.jsonl`: compact per-source evidence rows used by official profile upgraders. Inspect `match_authority`, `agent_status`, `agent_summary`, and `retrieval_matched_*` before trusting a concept link.
- `output/source_fetch_report.md`: source-fetch and queue audit report.
- `output/update_manifest.json`: refresh metadata.
- `output/cache/`: API cache, ignored by git.
- `references/data_source_strategy.md`: human-readable strategy explaining which data sources are needed to find potential explosive themes before they become obvious.

## Operating Rules

- When proactively mining themes, start with `data/data_source_registry_seed.json`: use weak/social sources only as leads, medium trade sources as early direction, and strong official/market/flow sources as proof.
- Prefer fine-grained concept labels over broad sectors. Use `ABF`, `HBM`, `散熱零組件`, `電線電纜`, `CDMO`, `GLP-1`, `航運/油輪`, `金融/保險`, etc. before using broad buckets like 電子 or 傳產.
- Every actionable stock must have a company profile when possible: primary business, products/specializations, platform/customer path, constraints, and risk flags. If the profile is missing, label the relation lower confidence and avoid presenting it as a high-conviction link.
- After profile refresh, build `company_thesis_cards.json`. A company profile says what the company does; a thesis card says why it belongs to this trade, what should lead it, which peers challenge it, and what invalidates the thesis.
- Prefer `agent_status=agent_applied` or `manual_override` for actionable reasoning. If a card says `openai_agent_unavailable_no_api_key/codex_agent_unavailable_no_cli`, it is a fallback summary, not an agent-verified thesis.
- Treat `profile_status=fallback_from_concepts` as a backlog item, not a real company profile. It prevents blank UI fields, but actionable reasoning should prefer `profiled` names with source refs.
- Use correlation edges as a second-pass check: business fit says what the company does; correlation/lead-lag says whether the market is currently trading it with that basket. Strong business fit plus weak correlation can mean early laggard, wrong mapping, or idiosyncratic risk.
- Use `relation_index.json` for autonomous exploration. Start from a hot concept, walk upstream/downstream, expand same-product and same-layer peers, then validate with price/volume/correlation before presenting a tradable watchlist.
- For AI infrastructure bottleneck work, prefer the physical constraint chain over generic AI labels: architecture shift -> bottleneck layer -> supplier -> scarcity -> substitutability -> discovery state -> price/volume confirmation. Treat `ai_photonics_bottleneck_stack`, `inp_photonics`, `silicon_photonics`, `soi_wafer`, `epitaxy_equipment`, `specialty_glass_fiber`, and `optical_interposer_packaging` as fine concepts, not as synonyms for broad optical stocks.
- Every theme must carry evidence: price move, headline/news count, related markets, and at least one relation path.
- Separate `sector` from `concept`: sector says what a company is; concept says why it is moving now.
- A cross-market relation is useful only if it links at least two markets, such as US -> TW, JP -> TW, KR -> CN/TW, CN/HK -> TW, commodity -> miners/materials, rates -> banks/insurers.
- Do not call a one-stock move a theme. Mark it as single-name until breadth appears.
- If news evidence is stale or failed to refresh, say so and rely on price/graph evidence only.

## Answer Pattern

```text
先更新：theme_library + cross_market_stock_graph 已刷新到 ...

Active themes:
- concept: why active, markets involved, leader/follower candidates, evidence

New/changed concepts:
- concept: source headline / price move / related stocks

Cross-market graph:
- leader market -> concept -> follower markets

Next step:
- feed selected concept into lagradar for laggard/backtest/risk validation
```

## Common Commands

```bash
python3 thememiner/scripts/update_theme_graph.py --refresh-prices --refresh-news
python3 thememiner/scripts/build_company_thesis_cards.py --agent-mode auto
python3 thememiner/scripts/build_semantic_relation_index.py --backend auto
python3 thememiner/scripts/build_semantic_relation_index.py --backend mlx-local --embedding-model mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ
python3 thememiner/scripts/discover_market_universe.py --markets US,TW,TWO,KR
python3 thememiner/scripts/discover_market_universe.py --markets US,TW,TWO,KR --agent-mode auto --agent-limit 300
python3 thememiner/scripts/update_theme_graph.py --max-concepts 40 --news-per-query 4
python3 thememiner/scripts/query_theme_graph.py --top 30
python3 thememiner/scripts/query_theme_graph.py --concept optical
python3 thememiner/scripts/query_theme_graph.py --market JP --top 20
python3 thememiner/scripts/build_theme_graph_html.py
python3 thememiner/scripts/audit_graph_coverage.py
python3 thememiner/scripts/audit_data_source_registry.py
.venv/bin/python thememiner/scripts/scrapling_source_fetcher.py --no-fetch
.venv/bin/python thememiner/scripts/scrapling_source_fetcher.py --limit 40
.venv/bin/python thememiner/scripts/scrapling_source_fetcher.py --limit 0 --stream-evidence --shard 0/6 --queue-output thememiner/output/profile_upgrade_queue.shard0of6.json --evidence-output thememiner/output/company_source_evidence.shard0of6.jsonl --report-output thememiner/output/source_fetch_report.shard0of6.md
.venv/bin/python thememiner/scripts/merge_source_evidence.py --inputs 'thememiner/output/company_source_evidence.shard*of6.jsonl'
.venv/bin/python thememiner/scripts/upgrade_company_profiles_official.py --include-curated --source-evidence thememiner/output/company_source_evidence.jsonl --shard 0/6 --output thememiner/data/profile_upgrades/source_evidence_full_shard0of6.json
.venv/bin/python thememiner/scripts/merge_company_profile_shards.py --base thememiner/data/company_profiles_autofill.json --shards 'thememiner/data/profile_upgrades/source_evidence_full_shard*of6.json' --output thememiner/data/company_profiles_official_autofill.json
python3 thememiner/scripts/update_theme_graph.py --auto-profiles thememiner/data/company_profiles_official_autofill.json
```
