# Lagradar

Lagradar is a cross-market theme diffusion and laggard radar. It is built for medium-horizon setups where a theme first heats up in one market, then diffuses over 5 trading days to 3 months into related regions and second-line companies across the US, Japan, Taiwan, China/Hong Kong, and Korea.

It is not only an electronics radar. The seed graph includes semiconductors/components plus non-electronics such as industrial metals, energy, shipping, defense/aerospace, healthcare/CDMO, and banks/insurance/rates.

Lagradar automatically syncs ThemeMiner's latest upstream graph from `../thememiner/output/` when `scan_laggards.py` runs. It merges `relation_index.json`, `theme_library.json`, `company_profiles.json`, and `company_thesis_cards.json`, so candidates carry primary business, specialization, customer/platform path, thesis label, AI-chain position, peer symbols, leader indicators, risks, agent status, source evidence, and optional bottleneck-layer metadata instead of relying on a flat ticker-to-theme mapping.

The goal is not to buy the weakest stock. The goal is to find an **improving laggard**:

```text
leader shock + relation graph + lag gap + turn confirmation + diffusion breadth - overheat
```

## Run

```bash
python3 thememiner/scripts/discover_market_universe.py --markets US,TW,TWO,KR --agent-mode auto
python3 thememiner/scripts/build_company_thesis_cards.py --agent-mode auto
python3 thememiner/scripts/build_semantic_relation_index.py --backend auto
python3 lagradar/scripts/scan_laggards.py
python3 lagradar/scripts/build_lagradar_html.py
python3 lagradar/scripts/query_laggards.py --top 15
python3 lagradar/scripts/select_trade_candidates.py --market TW --top 10
```

No API key is required if local Codex is available:

```bash
python3 thememiner/scripts/run_codex_agent_refresh.py --workers 3 --markets US,TW,TWO,KR
```

For semantic matching, set an OpenAI-compatible agent key before ThemeMiner refresh:

```bash
export THEMEMINER_AGENT_API_KEY=...
export THEMEMINER_AGENT_MODEL=gpt-5-mini
python3 thememiner/scripts/discover_market_universe.py --markets US,TW,TWO,KR --agent-mode auto
python3 thememiner/scripts/build_company_thesis_cards.py --agent-mode auto
```

For no-key local semantic relation scoring, use the optional MLX embedding backend:

```bash
.venv/bin/python -m pip install -r requirements-mlx.txt
.venv/bin/python thememiner/scripts/build_semantic_relation_index.py --backend mlx-local --embedding-model mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ
python3 lagradar/scripts/scan_laggards.py
```

`mlx-local` loads the embedding model in-process and caches vectors under `thememiner/output/cache/semantic_embeddings/`. `mlx-http` is also available when a local adapter exposes OpenAI-compatible `/v1/embeddings`. In both cases, Lagradar treats embedding similarity as one relation-quality input alongside manual overrides, thesis cards, authority, price/volume, and peer challenge.

Keyword/product rules are now candidate retrieval, not final authority. Rows with `match_authority=rule_fallback`, `agent_status=openai_agent_unavailable_no_api_key/codex_agent_unavailable_no_cli`, or `relation_authority=fallback_recall_only` are fallback evidence and receive lower scanner/selector weight.
Do not patch ranking with concept label wordlists; fix the upstream source evidence or thesis-card agent input so the selector can use `agent_status`, `match_authority`, `relation_quality_score`, relation confidence, peer challenge, and price/volume signals.

Before making a one-stock recommendation, run the selector or reproduce its peer challenge:

```bash
python3 lagradar/scripts/select_trade_candidates.py --market TW --symbols 2421.TW,2313.TW,3533.TW --write-md lagradar/output/peer_challenge_latest.md
```

Disable the ThemeMiner sync only for debugging:

```bash
python3 lagradar/scripts/scan_laggards.py --no-sync-thememiner
```

Refresh chart cache:

```bash
python3 lagradar/scripts/scan_laggards.py --refresh-history
```

Query one theme:

```bash
python3 lagradar/scripts/query_laggards.py --theme passive
python3 lagradar/scripts/query_laggards.py --theme power_grid
```

Fetch 20-year daily history and run a research backtest:

```bash
python3 lagradar/scripts/fetch_backtest_history.py --years 20
python3 lagradar/scripts/backtest_theme_diffusion.py
python3 lagradar/scripts/backtest_theme_diffusion.py --output-dir lagradar/output/backtests_turn_confirmed --turn-threshold-pct 0
```

## Outputs

- `output/company_metrics.jsonl`: company-level return, volume, moving average, and breakout metrics.
- `output/synced_theme_seed.json`: generated seed after ThemeMiner concepts and profiles are merged into Lagradar.
- `output/theme_scores.json`: theme heat and leader context.
- `output/laggard_candidates.json`: ranked laggard candidates with relation paths, relation authority/quality, semantic similarity, thesis labels, AI-chain position, leader indicators, peer symbols, and thesis risks when a company thesis card exists.
- `output/peer_challenge_latest.md`: optional selector output with "why this, why not peers" challenger tables.
- `output/theme_report.md`: readable daily report.
- `output/build_manifest.json`: scan metadata.
- `output/backtests/theme_lead_lag_summary.csv`: raw leader-to-follower backtest summary.
- `output/backtests/theme_lead_lag_events.jsonl`: event-level historical signals and forward returns.
- `output/backtests/backtest_report.md`: compact backtest report.

## Model

Lagradar computes:

- `theme_heat`: leader strength over 20/60 trading days, breadth, and near-high behavior.
- `diffusion_score`: follower breadth, 20-day-high proximity, breakout breadth, volume expansion, and overheat breadth.
- `lifecycle_stage`: latent/cold, overseas validated, local initial move, diffusion confirmation, overheat, or fade.
- `laggard_gap`: difference between leader strength and candidate strength.
- `turning_score`: 3/5/10 day improvement, volume expansion, moving-average reclaim, and near-breakout state.
- `overheat_score`: stretched 5D/20D return, distance from 20D MA, crowded volume, and breakout extension.
- `candidate_score`: weighted sum of theme heat, diffusion, lag gap, turning evidence, exposure, and relation quality minus overheat.
- `bottleneck_profile`: for themes such as `ai_photonics_bottleneck_stack`, identifies the physical chokepoint layer, scarcity, substitutability, discovery state, and score before ranking a stock as more than a broad sympathy move.
- `selection_score`: selector score that adjusts candidate score by thesis-card quality, manual override confidence, overheat, and turn confirmation before the final peer challenge.

The highest-value bucket is `improving_laggard`, not `weak_not_laggard`.

The final recommendation must survive peer challenge. If two candidates share a theme, compare business fit, leader indicators, lag gap, turning score, overheat, agent/manual thesis quality, and trigger/invalidation before choosing. Broad auto mappings must be corrected by thesis cards: 華通 is a PCB/HDI thesis, 建準 is thermal/fan/cooling, and 嘉澤 is CPU socket/high-speed connector.

For the deeper research framework, see `references/methodology.md`.
