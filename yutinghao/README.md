# Yu Ting-Hao / 財經皓角 Distillation

This project prepares source collection and schema design for distilling 游庭皓的財經皓角 into a finance persona assistant.

## Skill Package

This folder is also an AgentSkills-compatible skill:

- `SKILL.md` is the skill entrypoint.
- `agents/openai.yaml` contains UI metadata.
- `references/` contains the source audit and distillation schema.
- `scripts/` contains refresh, search, and joke/asides extraction helpers.

Example prompts:

```text
$yutinghao 這週美股追 AI 還是等回檔？
$yutinghao 台積電和韓國記憶體股的差別，他會怎麼拆？
$yutinghao 找出他用笑話講投資紀律的例子
```

## Current Source Inventory

- Digital Garden notes: `data/notes/` with 61 public note pages, 2026-01-28 to 2026-05-08.
- Digital Garden transcripts: `data/transcripts/` with 82 public transcript pages, 2026-01-02 to 2026-05-08.
- Official site posts: `data/official_articles/` plus `data/source/official_posts.jsonl`; 459 public REST posts, 259 with full public content.
- YouTube RSS: `data/source/youtube_recent.json`; recent videos, publish timestamps, descriptions, and chapter markers.
- Jokes/asides: `data/source/jokes_inventory.jsonl`; merged from note sections named `皓哥笑話` and timestamped transcript candidates, then deduped by date, timestamp proximity, and normalized text similarity.
- Market context:
  - `data/market_context/episode_market_context.jsonl` broad episode-date macro basket aligned to the nearest prior close before the Taiwan morning episode.
  - `data/market_context/episode_asset_context/YYYY-MM-DD.json` assets explicitly mentioned in transcripts/notes plus labeled sector proxy baskets.

## Files

- `scripts/crawl_sources.py` crawls public sources and builds local inventory.
- `scripts/extract_note_jokes.py` extracts joke/asides inventory from both notes and transcripts, with raw candidates in `data/source/jokes_candidates_raw.jsonl` and summary counts in `data/source/jokes_summary.json`.
- `scripts/align_market_context.py` fetches fixed-basket market data and aligns it to each episode.
- `scripts/build_episode_asset_context.py` scans transcripts/notes for mentioned assets and builds per-episode market context.
- `scripts/search_corpus.py` searches transcripts, notes, official articles, and jokes newest-first.
- `references/source-audit.md` records source quality, coverage, and caveats.
- `references/distillation-schema.md` defines the first-pass extraction schema for LLM distillation.

## Refresh

```bash
python3 yutinghao/scripts/crawl_sources.py --out-dir yutinghao
python3 yutinghao/scripts/extract_note_jokes.py
python3 yutinghao/scripts/align_market_context.py
python3 yutinghao/scripts/build_episode_asset_context.py
python3 yutinghao/scripts/search_corpus.py AI 記憶體 台韓 --limit 10
```

This does not bypass paywalls or login-only content. It only reads public pages and public WordPress REST responses.
