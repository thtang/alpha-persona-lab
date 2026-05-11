# Gooaye Research Workflow

Use this workflow for deeper requests such as "distill his trading logic", "what does he think about career choices", or "compare his 2020 crash logic with 2022 bear-market comments".

## Corpus Setup

1. On the first Gooaye skill activation of each local day, run:

```bash
python3 gooaye/scripts/sync_daily_transcripts.py
```

This checks `https://whatmkreallysaid.com/` for new or changed transcripts, stores them in `data/transcripts/`, refreshes baseline and mentioned-asset market context when transcripts changed, and rebuilds the distilled investment and life/QA memories.
2. Confirm `data/source/episodes.json` and `data/transcripts_manifest.json` exist.
3. If missing or stale after the daily sync, run:

```bash
python3 gooaye/scripts/fetch_transcripts.py
```

4. Search local transcripts with:

```bash
python3 gooaye/scripts/search_corpus.py 台積電 估值 停損 --limit 20
```

5. Build market context when the task involves investing or trading:

```bash
python3 gooaye/scripts/align_market_context.py
python3 gooaye/scripts/build_episode_asset_context.py
```

Use `episode_market_context.jsonl` for the broad regime, and `episode_asset_context/EP###.json` for stocks or sectors actually mentioned in the episode. Treat `sector_basket:*` sources as proxy context, not direct stock recommendations.

6. For semantic per-episode distillation, use Codex subagents with disjoint episode ranges. Each worker reads the transcript, metadata, market context, and `references/distillation-schema.md`, then writes canonical notes to `data/distilled/episode_notes/EP###.json`. Do not use external LLM APIs unless the user explicitly requests that path.

```bash
python3 gooaye/scripts/distill_episodes.py validate
```

## Distillation Passes

Use multiple passes instead of one giant summary:

- **Episode pass**: for each episode, fill every top-level field in `distillation-schema.md`, including market regime, host state, investment logic, trade observations, QA views, catalysts, warnings, principles, references, non-tradeable insights, and open questions.
- **Validation pass**: run `distill_episodes.py validate` over the completed range and fix schema/enum/evidence issues before using the notes.
- **Theme pass**: group notes by theme such as valuation, trend following, position sizing, macro, individual stocks, career, consumption, family, and relationships.
- **Counterexample pass**: search for episodes where the same topic appears under a different market regime.
- **Principle pass**: write reusable principles only after checking multiple episodes.

## Search Seeds

Investment and trading:

- `本益比`, `估值`, `便宜`, `錯殺`, `停損`, `停利`, `減碼`, `加碼`, `抄底`, `空頭`, `多頭`, `趨勢`, `技術分析`
- `台股`, `美股`, `半導體`, `台積電`, `特斯拉`, `ETF`, `比特幣`, `匯率`, `利率`, `通膨`

Risk and psychology:

- `韭菜`, `散戶`, `恐慌`, `貪婪`, `凹單`, `紀律`, `槓桿`, `融資`, `避險`

QA and life views:

- `工作`, `薪水`, `轉職`, `創業`, `買房`, `租房`, `婚姻`, `交往`, `家庭`, `小孩`, `朋友`, `焦慮`

## Output Style

- Write in Traditional Chinese unless the user asks otherwise.
- Use "他在 EP/date 的脈絡下..." rather than claiming timeless intent.
- Label confidence and unresolved ambiguity.
- Keep quotes short and cite episode/date. Prefer paraphrase for transcript content.
- Do not present the output as financial advice or as Gooaye speaking directly.
