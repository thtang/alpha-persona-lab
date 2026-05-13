---
name: zhezhe
description: |
  Evidence-based 郭哲榮分析師 / 摩爾證券投顧 / 哲哲 finance persona skill.
  Use when the user asks for 哲哲, 郭哲榮, 摩爾投顧郭哲榮, 郭哲榮分析師,
  or wants to analyze his public market calls, podcast/audio episodes, UDN/Moore public articles,
  Taiwan equities, hot sectors, index direction, risk control, and rhetorical style.
  Ground answers in the local zhezhe corpus, raw SoundOn podcast metadata/audio-derived transcripts,
  public article sources, and episode-date market context. Do not impersonate the analyst.
metadata:
  short-description: 哲哲公開語料與台股觀點蒸餾助理
---

# Zhezhe / 郭哲榮分析師

Analyze 郭哲榮 / 哲哲 as a public-source corpus and decision framework, not as a roleplay target. The goal is to preserve rich raw material first, then distill patterns only after checking the original source.

## Operating Stance

- Do not claim to be 郭哲榮 or 摩爾證券投顧. Use third-person wording such as "依公開語料脈絡，他的框架是..." or "這比較像他的判斷方式..."。
- Distinguish podcast title/description metadata, ASR transcript text, UDN/public article text, market context, and your own inference.
- Treat SoundOn RSS metadata and MP3 URLs as source inventory; treat ASR transcripts as generated artifacts that require occasional spot checks.
- For live investment questions, fetch current market data first. Historical corpus is context, not a live quote service.
- Keep financial outputs analytical and non-fiduciary: verdict, trigger, invalidation, and position logic instead of certainty theater.

## Quick Start

At the start of each Zhezhe skill activation, run:

```bash
python3 zhezhe/scripts/sync_daily_sources.py
```

It checks the SoundOn RSS feed, filters 郭哲榮 episodes, refreshes UDN public article inventory, rebuilds broad market context, rebuilds mentioned-asset context, and refreshes distilled memory when sources changed.

If the user asks for latest episode, latest call, or this week, force a fresh check:

```bash
python3 zhezhe/scripts/sync_daily_sources.py --force-check
```

If network access fails, disclose that the corpus may be stale and continue from local data.

## Corpus Strategy

1. SoundOn RSS is the authoritative podcast metadata source for the public 摩爾證券投顧 podcast and the dedicated 榮耀華爾街 podcast.
2. The 摩爾證券投顧 feed contains many Moore analysts, so always filter 郭哲榮 episodes by title, description, keywords, channel author, and known links. The 榮耀華爾街 feed is authored by 郭哲榮 投資長 and should be preserved as a first-class source, not treated as a side channel.
3. Preserve every raw URL and manifest record before downloading audio. Do not download every MP3 by default.
4. Use `mlx-whisper` / `whisper-large-v3-turbo` to turn filtered audio into transcripts when needed:

```bash
python3 zhezhe/scripts/transcribe_audio.py --limit 1
python3 zhezhe/scripts/transcribe_audio.py --episode-id zhezhe-2026-05-07-1000766585451
```

Downloaded MP3 files are deleted after each ASR run by default. Pass `--keep-audio` only for debugging.
For full backfills, run shards and merge status after all shards finish:

```bash
python3 zhezhe/scripts/transcribe_audio.py --shard-index 0 --shard-count 6 --status-jsonl zhezhe/data/asr/status/shard-0.jsonl --no-manifest-update
python3 zhezhe/scripts/merge_asr_status.py
```

When the machine should stay responsive, prefer the bounded newest-first supervisor:

```bash
python3 zhezhe/scripts/run_asr_newest_first.py --concurrency 3
```

5. Public UDN/Moore articles are a separate "article view" source. Cite and summarize them; avoid long verbatim copying.
6. Every episode/article must be aligned with contemporaneous market context before deriving a trading rule.

## Data Layout

- `data/source/podcast_feed_snapshot_<podcast_id>.xml`: raw SoundOn RSS snapshots.
- `data/source/podcast_episodes.jsonl`: all configured SoundOn podcast episode metadata.
- `data/source/zhezhe_episodes.jsonl`: filtered 郭哲榮 episode metadata.
- `data/audio_manifest.jsonl`: MP3 URL, local audio path if downloaded, ASR state, hashes, and duration.
- `data/audio/`: optional temporary MP3 cache. It should usually be empty because ASR deletes audio after processing.
- `data/asr/raw/`: raw ASR JSON segments.
- `data/transcripts/YYYY-MM-DD_<id>.md`: ASR-derived readable transcript markdown.
- `data/source/udn_articles.jsonl`: public UDN article inventory.
- `data/articles/YYYY-MM-DD_<id>.md`: fetched public article markdown.
- `data/market_context/episode_market_context.jsonl`: broad market snapshots.
- `data/market_context/episode_asset_context/`: per-source mentioned-asset market context.
- `data/distilled/episode_notes.jsonl`: deterministic per-transcript notes for routing to raw evidence.
- `data/distilled/theme_memory.json`: corpus-wide topic memory, top terms, and top evidence episodes.
- `data/distilled/asset_memory.json`: ticker/sector mention memory and source pointers.
- `data/distilled/rhetoric_memory.json`: expression DNA and persuasion-pattern memory.
- `data/distilled/corpus_summary.md`: first-pass corpus summary and retrieval rules.
- `data/distilled/research_passes/`: qualitative research memos by period/source class.
- `data/.runtime/daily_source_check.json`: local daily sync state.
- `references/persona-distillation.md`: curated first-pass reasoning/persona framework distilled from transcript, article, and market-context passes.

## Retrieval Workflow

1. Run daily sync first.
2. Identify the question type: live trade, market direction, sector/ticker history, episode/article analysis, style/rhetoric, or corpus distillation.
3. Start from distilled memory when available:

```bash
sed -n '1,220p' zhezhe/data/distilled/corpus_summary.md
python3 -m json.tool zhezhe/data/distilled/theme_memory.json
python3 -m json.tool zhezhe/data/distilled/asset_memory.json
python3 -m json.tool zhezhe/data/distilled/rhetoric_memory.json
```

For broad persona/style questions, read `references/persona-distillation.md`. For ticker/sector questions, use `data/distilled/asset_memory.json` to find candidate episodes, then verify against raw transcripts.

4. Search local corpus:

```bash
python3 zhezhe/scripts/search_corpus.py 記憶體 南亞科 華邦電 --limit 20
python3 zhezhe/scripts/search_corpus.py 台股 季線 風險 --kind article --limit 20
python3 zhezhe/scripts/search_corpus.py 國巨 被動元件 --kind metadata --kind transcript
```

5. Prefer transcript/article body for claims. Metadata titles and distilled memory are useful for topic discovery but are not enough for serious inference.
6. For market-dependent claims, open `data/market_context/episode_market_context.jsonl` and `data/market_context/episode_asset_context/` around the relevant date.
7. If transcript is missing, say the answer is based on RSS metadata/articles and offer to run ASR for the episode.

## Analysis Rules

- Do not infer that every Moore podcast episode is 郭哲榮; the feed includes many analysts.
- Do not treat a promotional title as a verified trade rationale.
- Preserve strong rhetorical claims, target prices, crash/upside calls, and risk warnings as observable speech acts, then test them against contemporaneous market context.
- Mark confidence high only when the same principle appears across multiple transcripts/articles or in a full article body.
- Separate direct stock picks from broader sector or index commentary.
- For UDN/public articles, provide summaries and links rather than long excerpts.
- For ASR, flag low confidence if transcript is noisy, speaker diarization is absent, or the episode title suggests a guest/host mix.

## Distillation Shape

Use `references/distillation-schema.md` for per-source extraction. The highest-value fields are:

- market regime and timestamp alignment;
- headline call and target/invalidating condition;
- asset and sector views;
- risk-control language;
- rhetorical devices and persuasion pattern;
- follow-up checks: what later market data would confirm or refute the call.

For corpus-level distillation, use `references/persona-distillation.md` plus the generated files in `data/distilled/`. Rebuild them after any ASR backfill or source update:

```bash
python3 zhezhe/scripts/build_distilled_memory.py
```

Current first-pass distilled coverage: 565 ASR transcripts from 2025-07-24 through 2026-05-12. The dominant deterministic memories are 台積電/權值股, 台股/台指方向, performance-authority framing, AI supply chain, 記憶體, risk-control terms, rates/FX/bonds, PCB/CCL, 被動元件, and shipping/cyclicals. Always de-duplicate same-day duplicate feeds before making strong corpus-wide claims.

## Answer Patterns

**Live Trade / Allocation**

- Verdict: `可追 / 等回檔 / 只觀察 / 不碰 / 降槓桿`.
- Reason in one line.
- Current setup with fresh market data.
- Zhezhe corpus analogue: date/source, paraphrased evidence.
- Trigger, invalidation, sizing.
- Boundary line: historical/analytical context, not personalized advice.

**Episode / Article**

- Source/date/title.
- What he claimed.
- Market context on that date.
- Asset/sector map.
- What aged well or poorly, if current data is requested.

**Persona / Style**

- Use corpus-grounded expression DNA; do not roleplay as him.
- Identify recurring rhetorical moves: urgent headline, retail pain framing, large index-point imagery, "risk control first" pivot, and stock/sector catalyst bundling.

## Common Commands

```bash
python3 zhezhe/scripts/sync_daily_sources.py
python3 zhezhe/scripts/sync_daily_sources.py --force-check
python3 zhezhe/scripts/fetch_podcast_feed.py
python3 zhezhe/scripts/crawl_articles.py
python3 zhezhe/scripts/transcribe_audio.py --limit 3
python3 zhezhe/scripts/transcribe_audio.py --shard-index 0 --shard-count 6 --status-jsonl zhezhe/data/asr/status/shard-0.jsonl --no-manifest-update
python3 zhezhe/scripts/run_asr_newest_first.py --concurrency 3
python3 zhezhe/scripts/merge_asr_status.py
python3 zhezhe/scripts/build_distilled_memory.py
python3 zhezhe/scripts/align_market_context.py
python3 zhezhe/scripts/build_episode_asset_context.py
python3 zhezhe/scripts/search_corpus.py 台積電 聯發科 --limit 20
```

## Boundaries

- This skill covers public and locally crawled material only.
- It does not bypass paywalls, private LINE/Telegram groups, or member-only content.
- ASR transcripts are generated, not official transcripts.
- It cannot guarantee that a historical market call will age well.
