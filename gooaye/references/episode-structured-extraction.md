# Episode Structured Extraction

Use this prompt shape when turning one Gooaye episode into a reusable structured note. This is not a summary task. The goal is to classify messy spoken discussion into fields that future `$gooaye` answers can retrieve and join.

## Inputs

Each episode extraction receives exactly these inputs:

- Transcript: `data/transcripts/EP###.md`
- Episode metadata: episode number, date, title, official summary
- Market context: pre-aligned snapshots for `^TWII`, `2330.TW`, `TSM`, `SOXX`, `QQQ`, and `NVDA`, each with `market_date`, `close`, `ret_1d_pct`, `ret_5d_pct`, `ret_20d_pct`, and `ret_60d_pct`

## Output Contract

Return one JSON object matching `schemas/episode_note.schema.json`:

- `episode`: copy the episode number from metadata.
- `date`: copy the date from metadata.
- `title`: copy the title from metadata.
- `market_regime`: one sentence describing the objective market setup using market-context numbers first, then the episode's mood as secondary context.
- `topics`: 3-8 retrieval labels only.
- `investment_logic`: decision rules, each with `claim`, `trigger`, `action_bias`, `risk_control`, `evidence`, and `confidence`.
- `trade_observations`: directional views on assets or sectors, each with `asset_or_sector`, `view`, `time_horizon`, `reasoning`, `market_alignment`, and `is_joke_or_aside`.
- `qa_views`: non-investing views from listener QA or personal discussion, each with `question_theme`, `viewpoint`, `principle`, `tone`, and `evidence`.
- `open_questions`: unresolved issues that later episodes can answer or revise.

## Enum Rules

`investment_logic[].action_bias` must be one of:

```text
buy, sell, hold, hedge, wait, size-down, rotate, unknown
```

`trade_observations[].view` must be one of:

```text
bullish, bearish, neutral, conditional
```

`trade_observations[].time_horizon` must be one of:

```text
intraday, swing, medium-term, long-term, unclear
```

`investment_logic[].confidence` must be one of:

```text
high, medium, low
```

## Red Lines

- Do not impersonate Gooaye. Write in third person: "他..." or "依本集脈絡，他..."
- Do not make claims that are not in the transcript. Empty arrays are better than invented content.
- Do not treat jokes, sponsor-like asides, or throwaway comments as serious views. Set `is_joke_or_aside: true` when a trade observation is playful or incidental.
- Paraphrase heavily. `evidence` must be under 200 Chinese characters and cite episode/date.
- Separate his own positioning from listener advice, jokes, and market descriptions.
- `market_regime` must not be "he felt..." only. Start from the objective market numbers.
- Topics are retrieval tags only; do not use them to sneak in long reasoning.

## Prompt Template

```text
You are extracting one structured Gooaye episode note.

Task:
Convert the transcript into one JSON object that matches the provided schema. This is not a summary. Classify reusable investment rules, asset/sector observations, non-investing QA views, and open questions.

Inputs:
EPISODE_METADATA:
{episode_metadata_json}

MARKET_CONTEXT:
{market_context_json}

TRANSCRIPT:
{transcript_text}

Rules:
1. Output JSON only. No Markdown.
2. Do not impersonate the speaker. Use third person wording.
3. Use market-context numbers in `market_regime`; the transcript mood can only supplement them.
4. The top-level object must include `episode`, `date`, and `title` copied exactly from metadata.
5. `topics` must contain 3-8 short retrieval labels.
6. `investment_logic[].action_bias` must be exactly one of: buy, sell, hold, hedge, wait, size-down, rotate, unknown.
7. `trade_observations[].view` must be exactly one of: bullish, bearish, neutral, conditional.
8. `trade_observations[].time_horizon` must be exactly one of: intraday, swing, medium-term, long-term, unclear.
9. Mark jokes/asides/sponsor-like comments with `is_joke_or_aside: true`.
10. Evidence must cite episode/date and stay under 200 Chinese characters.
11. If a category has no real content, return an empty array. Do not fill fields by guessing.
```

## Retrieval Intent

This shape supports future assistant queries:

- Stop loss, add, size, leverage: search `investment_logic.claim`, `trigger`, and `risk_control`
- Crash behavior: filter `market_regime`, then read `investment_logic`
- TSMC or ticker evolution: filter `trade_observations.asset_or_sector`, sort by date, compare `view`
- Life similarity: search `qa_views.viewpoint` and `principle`
- Similar current markets: match numeric market context to historical `market_regime`, then read those episodes' `investment_logic`
- Accuracy review: join `trade_observations` with future return decision cards
