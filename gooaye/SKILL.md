---
name: gooaye
description: Distill Gooaye/股癌 Podcast transcripts into evidence-based investment, trading, and life/QA worldview analysis. Use when Codex needs to search or update the local Gooaye transcript corpus, check whatmkreallysaid.com and SoundOn RSS for new episodes, run ASR fallback for episodes without public transcripts, align episode commentary with contemporaneous market conditions, extract recurring trading logic, summarize personal views from listener QA, or answer questions about Gooaye episodes without impersonating the podcaster.
---

# Gooaye

Analyze Gooaye/股癌 as a source corpus and decision framework, not as a roleplay target. Start from structured per-episode notes when available, then corpus-wide memory, then local transcripts, episode dates, and market context when relevant.

## Quick Start

- Daily Freshness Contract: on the first Gooaye activation of each local day, run `python3 gooaye/scripts/sync_daily_sources.py` without `--no-auto-asr`. The goal is to keep the local corpus current every day: canonical transcript first, SoundOn RSS/audio inventory second, and one newest-episode ASR fallback when the transcript site is behind. Use `--no-auto-asr` only when the user explicitly asks for a fast metadata-only check.
- At the start of each Gooaye skill activation, run `python3 gooaye/scripts/sync_daily_sources.py` before answering. It checks `https://whatmkreallysaid.com/` for canonical transcripts, checks the SoundOn RSS feed for newer episode metadata and MP3 URLs, reconciles any existing ASR transcripts into the manifest, and automatically ASRs the newest missing SoundOn episode when the canonical transcript site is behind. It refreshes market alignment when transcripts changed and rebuilds both investment and life/QA memory.
- Use the transcript source ladder in this order: `whatmkreallysaid.com` transcript first; SoundOn RSS metadata + existing local ASR transcript second; SoundOn MP3 + `mlx-whisper` ASR as the latest-episode fallback. Pass `--no-auto-asr` only when a fast metadata-only sync is needed.
- The ASR script downloads the MP3 into `data/audio/`, writes raw ASR JSON under `data/asr/raw/`, stores the transcript as `data/transcripts/EP###.md`, updates the manifest/index/source metadata, then deletes the MP3 unless `--keep-audio` is passed.
- If the daily sync cannot reach the website, disclose that the local corpus may be stale and continue from the latest local data instead of blocking the answer.
- Prefer `data/distilled/episode_notes/EP###.json` for serious Gooaye-style reasoning. These are the canonical per-episode notes generated from `references/distillation-schema.md`.
- If distilled episode notes are missing or stale, use Codex subagents with disjoint episode ranges to read transcripts and write `data/distilled/episode_notes/EP###.json` directly from `references/distillation-schema.md`. Do not use external LLM APIs unless the user explicitly asks for that path. Validate outputs with `python3 gooaye/scripts/distill_episodes.py validate`.
- Treat `data/structured/episode_notes.jsonl` as legacy v1 extraction output. Use it only when canonical distilled notes are unavailable.
- Check `data/transcripts_manifest.json`; if it is missing, run `python3 gooaye/scripts/fetch_transcripts.py`.
- For investing questions, read `references/investment-assistant.md` first.
- If the user asks for `aggressive mode`, `積極 mode`, `交易員模式`, or phrases such as `追就是追`, answer investment questions with the Aggressive Trader Mode in `references/investment-assistant.md`: decisive verdict first, compact trigger/invalidation, no long caveat stack.
- Retrieve corpus-wide context with `python3 gooaye/scripts/retrieve_investment_context.py <question terms>`.
- For life, relationship, work, family, or other QA-worldview questions, read `references/life-qa-assistant.md` first.
- Retrieve corpus-wide life/QA context with `python3 gooaye/scripts/retrieve_life_context.py <question terms>`.
- Search local transcripts with `python3 gooaye/scripts/search_corpus.py <terms> --limit 20` only after using the distilled memory, or when exact episode evidence is needed. Raw transcript search is newest-first by default; start from the largest episode numbers unless the task is explicitly about historical evolution.
- For investing or trading analysis, build baseline market alignment with `python3 gooaye/scripts/align_market_context.py`.
- For ticker or sector questions, prefer `data/market_context/episode_asset_context/EP###.json` over generic baseline context. Rebuild it with `python3 gooaye/scripts/build_episode_asset_context.py`; it maps transcript aliases and `trade_observations.asset_symbol` to episode-date prices, plus clearly labeled sector proxy baskets.
- Rebuild the corpus memory with `python3 gooaye/scripts/build_investment_memory.py` after transcript or market updates.
- Rebuild the life/QA memory with `python3 gooaye/scripts/build_life_memory.py` after transcript updates.
- Read `references/research-workflow.md` for deeper multi-pass work.
- Use `references/distillation-schema.md` for structured extraction.
- Use `references/market-alignment.md` when interpreting market-dependent commentary.

## Data Layout

- `data/source/episodes.json`: episode metadata from `whatmkreallysaid.com`.
- `data/source/pack_manifest.json`: upstream transcript pack version metadata.
- `data/source/soundon_feed_snapshot_954689a5-3096-43a4-a80b-7810b219cef3.xml`: latest SoundOn RSS snapshot for Gooaye.
- `data/source/soundon_episodes.jsonl`: SoundOn episode metadata, MP3 URLs, dates, durations, GUIDs, and ASR status.
- `data/source/soundon_fetch_summary.json`: compact RSS fetch summary, latest episode, and pending ASR list.
- `data/audio_manifest.jsonl`: one SoundOn audio/ASR tracking record per episode.
- `data/transcripts/EP###.md`: local episode markdown transcripts with stable filenames.
- `data/transcripts_manifest.json`: source filename, URL, local path, byte size, and SHA-256 for each stored transcript.
- `data/transcripts_index.jsonl`: one compact lookup record per episode.
- `data/.runtime/daily_transcript_check.json`: local daily sync state; this prevents repeated website checks after the first Gooaye activation of the day.
- `data/.runtime/daily_source_check.json`: combined canonical-transcript, SoundOn RSS, ASR, and derived-data sync status.
- `data/audio/`: temporary MP3 downloads for ASR; ignored by git and normally emptied after transcription.
- `data/asr/raw/`: raw `mlx-whisper` JSON outputs; ignored by git because they are reproducible and bulky.
- `data/distilled/episode_notes/EP###.json`: canonical per-episode distillation notes. Each file follows `references/distillation-schema.md` and includes `schema_version`, `episode_archetype`, `segment_breakdown`, `market_regime`, `host_state`, `investment_logic`, `trade_observations`, `qa_views`, `catalysts`, `narrative_threads`, `view_changes`, `principles`, `warnings`, `references`, `non_tradeable_insights`, and `open_questions`.
- `data/structured/episode_notes.jsonl`: legacy v1 per-episode semantic extraction notes, when the older LLM extraction pass has been run.
- `data/structured/episode_note_inputs.jsonl`: legacy generated LLM input records for missing/stale structured notes.
- `data/market_context/episode_market_context.jsonl`: baseline episode-date market snapshots from `align_market_context.py`.
- `data/market_context/episode_asset_context/EP###.json`: per-episode mentioned-asset market context from transcript aliases, distilled `asset_symbol`, and sector proxy baskets.
- `data/market_context/episode_asset_context.jsonl`: aggregate mentioned-asset context.
- `data/market_context/episode_asset_context_manifest.json`: mentioned-asset build manifest, symbols, source, and fetch errors.
- `references/asset-symbol-map.json`: aliases to ticker symbols used by `build_episode_asset_context.py`.
- `references/asset-sector-baskets.json`: representative proxy baskets for generic sectors such as AI supply chain, semiconductors, passive components, shipping, memory, financials, and EV supply chain.
- `data/distilled/theme_memory.json`: corpus-wide Gooaye investment themes and top evidence episodes.
- `data/distilled/episode_investment_memory.jsonl`: per-episode investment themes, snippets, and market regime.
- `data/distilled/latest_market_snapshot.json`: latest price snapshot from the configured market symbols.
- `data/distilled/life_theme_memory.json`: corpus-wide Gooaye life/QA themes, year distribution, dense episodes, and recent episodes.
- `data/distilled/episode_life_memory.jsonl`: per-episode life/QA themes and snippets.

If a canonical local transcript is missing or stale, rerun `fetch_transcripts.py`. If SoundOn is ahead of the canonical transcript site, run `fetch_podcast_feed.py` to record metadata first, then `transcribe_audio.py` or `sync_daily_sources.py --run-asr` to backfill the missing transcript. ASR transcripts are machine-generated; verify important quotes against audio or later canonical transcripts before treating them as exact wording.

## Research Workflow

1. Run the daily source sync first: `python3 gooaye/scripts/sync_daily_sources.py`. This is mandatory on the first Gooaye trigger of each local day because `whatmkreallysaid.com` updates irregularly and SoundOn can be ahead of the public transcript pack.
2. Identify the user question type: live investment decision, allocation planning, single episode, theme, ticker/sector history, relationship/life QA, work/family QA, or broader worldview.
3. Use canonical distilled episode notes first when available:
   - `market_regime.phase_label`, `market_regime.narrative`, and `regime_tags` for similar-regime retrieval.
   - `host_state` for his disclosed positions, leverage, self-critique, and personal events that affected trading.
   - `investment_logic` for decision rules such as stop loss, sizing, add, hedge, wait, pyramid, scale-in/out, and rotation.
   - `trade_observations` for ticker/sector timelines, short/medium/long horizon views, industry nodes, consensus level, catalyst anchors, and future decision-card joins.
   - `qa_views` for work, family, relationship, ethics, tools/platforms, personal finance, and lifestyle questions.
   - `warnings`, `principles`, `mantras_or_catchphrases`, `view_changes`, and `narrative_threads` for cross-episode synthesis.
4. For live investing/trading decisions, use `references/investment-assistant.md`, `data/distilled/episode_notes/`, and `data/distilled/theme_memory.json` before searching raw transcripts.
5. For life/QA questions, use `references/life-qa-assistant.md`, `data/distilled/episode_notes/`, and `data/distilled/life_theme_memory.json` before searching raw transcripts. Prefer answers that include both corpus-wide patterns and recent QA evidence when available.
6. Search metadata summaries and distilled memory to locate likely episodes, then verify important claims against transcript text.
   - When searching raw transcript text, start from the newest/highest episode numbers and move backward.
   - Use `--oldest-first` only when reconstructing how a view developed from early episodes.
7. For investing/trading claims, align each episode date with market data before inferring the logic.
   - Use `episode_market_context.jsonl` for the broad regime.
   - Use `episode_asset_context/EP###.json` for stocks or sectors actually mentioned around that episode.
   - Treat `sector_basket:*` sources as representative proxies only; say so explicitly and do not present a basket member as a direct Gooaye stock mention unless `sources` includes `transcript` or `trade_observations.asset_symbol`.
8. Extract claims into episode notes using `references/distillation-schema.md` as the single source of truth. Fill every top-level field, keep content in Traditional Chinese, use exact English enum values, paraphrase evidence under 200 Chinese characters, and never omit arrays just because they are empty.
9. Compare across episodes and regimes before stating a general principle.
10. Cite episode number and date. Quote only short excerpts when necessary; otherwise paraphrase.

## Analysis Rules

- Do not claim to be Gooaye or answer as the podcaster. Say "依逐字稿脈絡，他的觀點看起來是..." when modeling his view.
- Distinguish direct statements, jokes, listener-question answers, and your own inference.
- Treat episode summaries as hints only. Verify important claims in the transcript markdown.
- Treat market data as context, not proof of correctness.
- For sector baskets, distinguish direct mentions from proxy context. A basket can explain the market backdrop of a sector, but it is not evidence that he endorsed every component stock.
- Mark confidence as high only when the same principle is explicit or repeated across episodes.
- Do not answer live investment questions from the first transcript hits alone. Start from the full-corpus memory and use transcript search as verification.
- Do not answer life/relationship QA from the first transcript hits alone. Start from the life/QA memory and include recent evidence if the top dense episodes are mostly old.
- Do not treat keyword memory as final semantic extraction. If structured notes are unavailable, say that the answer is based on distilled keyword memory plus transcript verification.
- For financial outputs, include a brief note that this is historical/analytical context, not investment advice.
- Aggressive Trader Mode changes output style, not evidence standards: still run the daily sync, use corpus memory before transcript search, check current market data when needed, and avoid pretending any trade is certain.

## Common Commands

```bash
python3 gooaye/scripts/sync_daily_sources.py
python3 gooaye/scripts/sync_daily_sources.py --no-auto-asr
python3 gooaye/scripts/sync_daily_sources.py --run-asr --asr-limit 1
python3 gooaye/scripts/sync_daily_transcripts.py
python3 gooaye/scripts/fetch_podcast_feed.py
python3 gooaye/scripts/transcribe_audio.py --limit 1
python3 gooaye/scripts/distill_episodes.py validate
python3 gooaye/scripts/fetch_transcripts.py
python3 gooaye/scripts/build_investment_memory.py
python3 gooaye/scripts/build_life_memory.py
python3 gooaye/scripts/build_episode_asset_context.py
python3 gooaye/scripts/retrieve_investment_context.py 台積電 下週 買進 估值 趨勢 部位
python3 gooaye/scripts/retrieve_life_context.py 遠距離 戀愛 是否 繼續
python3 gooaye/scripts/search_corpus.py 本益比 停損 抄底 --limit 30
python3 gooaye/scripts/search_corpus.py 遠距 感情 --limit 20
python3 gooaye/scripts/search_corpus.py 遠距 感情 --limit 20 --oldest-first
python3 gooaye/scripts/search_corpus.py 台積電 --episode 1 --episode 2
python3 gooaye/scripts/align_market_context.py
```

## Deliverable Patterns

- **Single episode**: episode/date, market setup, investment claims, QA views, uncertainties.
- **Theme distillation**: principle, supporting episodes, counterexamples, regime dependency, confidence.
- **Ticker or sector**: timeline of mentions, market context around each mention, stance shifts, what triggered changes.
- **Aggressive trade call**: verdict enum, one-line reason, trigger, invalidation, max size, one supporting Gooaye rule.
- **QA worldview**: recurring values, examples by episode, where his stance changes by listener constraints.
