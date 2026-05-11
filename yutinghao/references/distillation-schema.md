# Distillation Schema: 財經皓角

Goal: extract 游庭皓's market reasoning system, not a plain summary.

The assistant should answer future questions by retrieving: market regime, macro transmission chain, asset/sector view, allocation/risk rule, and rhetorical/persona cues, all traceable to source evidence.

## Episode Input

Each episode input should include:

- `transcript`: `data/transcripts/YYYY-MM-DD.md`
- `note`: `data/notes/YYYY-MM-DD.md` if available
- `youtube_metadata`: from `data/source/youtube_recent.json` or full video ledger
- `official_related_articles`: official posts near the date or linked topic
- `market_context`
  - fixed macro basket
  - dynamic mentioned assets
  - session alignment notes

## Episode Output Shape

```json
{
  "episode_id": "yutinghao-2026-05-08",
  "date": "2026-05-08",
  "title": "2026/5/8(五) AI 狂牛 誰會是輸家？...",
  "source_urls": {
    "youtube": "https://www.youtube.com/watch?v=...",
    "transcript": "https://digitalgarden-five-azure.vercel.app/yutinghao-transcripts/YYYY-MM-DD/",
    "note": "https://digitalgarden-five-azure.vercel.app/yutinghao-notes/YYYY-MM-DD/"
  },
  "market_regime": {},
  "episode_thesis": [],
  "macro_transmission_chains": [],
  "asset_views": [],
  "allocation_logic": [],
  "risk_flags": [],
  "industry_maps": [],
  "policy_geopolitics": [],
  "market_psychology": [],
  "jokes_and_asides": [],
  "rhetorical_cues": [],
  "open_questions": []
}
```

## 1. `market_regime`

One compact description of the market condition, grounded in market context plus episode tone.

Fields:

- `label`: short regime label.
- `summary`: one sentence.
- `objective_context`: numbers from market context.
- `host_tone`: bullish, cautious, warning, skeptical, mixed.
- `regime_tags`: enum array.
- `evidence`: source + timestamp/section.

Suggested `regime_tags`:

- `risk_on`
- `risk_off`
- `ai_capex_cycle`
- `liquidity_driven`
- `earnings_revision`
- `rates_sensitive`
- `oil_geopolitical_shock`
- `usd_cycle`
- `semiconductor_supercycle`
- `market_breadth_narrowing`
- `leverage_euphoria`
- `policy_pivot`
- `supply_chain_rewiring`

## 2. `episode_thesis[]`

Three to six thesis bullets. This is the highest-level retrieval layer.

Fields:

- `claim`
- `why_it_matters`
- `scope`: global, US, Taiwan, China, sector, asset, behavior
- `evidence`

## 3. `macro_transmission_chains[]`

Core field. Extract how he maps macro events into tradable implications.

Fields:

- `trigger`: observed event or condition.
- `mechanism`: causal path.
- `affected_assets`: assets/sectors/countries.
- `market_implication`: expected market effect.
- `action_bias`: enum.
- `time_horizon`: enum.
- `risk_control`: what can invalidate or reduce the thesis.
- `evidence`: timestamp/section + short paraphrase.
- `confidence`: high, medium, low.

Example:

```json
{
  "trigger": "AI data center capex remains aggressive while compute supply is still scarce",
  "mechanism": "CSPs keep buying chips/cloud capacity; upstream semiconductor and memory suppliers gain pricing power",
  "affected_assets": ["SOXX", "TSM", "2330.TW", "HBM", "DRAM", "Korea semiconductors"],
  "market_implication": "AI hardware beneficiaries can stay bid even when broader macro data is noisy",
  "action_bias": "overweight",
  "time_horizon": "medium_term",
  "risk_control": "watch for capex cuts, customer concentration, or market breadth breakdown",
  "confidence": "high"
}
```

## 4. `asset_views[]`

Directional views on a specific asset, sector, market, country, or factor.

Fields:

- `asset_or_sector`
- `symbol_candidates`
- `asset_type`: stock, ETF, index, sector, commodity, rate, fx, crypto, country, theme
- `view`: enum
- `action_bias`: enum
- `time_horizon`: enum
- `reasoning`
- `market_alignment`: objective numbers and context.
- `catalysts`
- `invalidation`
- `is_joke_or_aside`: boolean
- `evidence`

`view` enum:

- `bullish`
- `bearish`
- `neutral`
- `conditional`

`action_bias` enum:

- `overweight`
- `underweight`
- `add_on_dip`
- `hold`
- `take_profit`
- `hedge`
- `avoid`
- `reduce_leverage`
- `watch`
- `no_trade`

`time_horizon` enum:

- `intraday`
- `swing`
- `medium_term`
- `long_term`
- `cycle`
- `unclear`

## 5. `allocation_logic[]`

Portfolio and behavior rules, especially ETF vs single stock, leverage, cash, concentration, and timing.

Fields:

- `rule`
- `trigger`
- `action_bias`
- `sizing_hint`
- `risk_control`
- `applies_to`
- `evidence`
- `confidence`

Common expected rule families:

- Use ETF when winner selection is uncertain.
- Do not expand leverage late in a crowded bull market.
- Keep dry powder for low-position or high-maintenance-rate moments.
- Distinguish secular capex cycle from short-term overheat.
- Market may ignore geopolitics unless it hits inflation, rates, earnings, or supply.

## 6. `risk_flags[]`

Extract risks even when the episode is constructive.

Fields:

- `risk`
- `risk_type`: valuation, liquidity, leverage, policy, geopolitics, customer_concentration, legal, execution, supply_chain, positioning, macro_data
- `trigger`
- `affected_assets`
- `severity`: high, medium, low
- `evidence`

## 7. `industry_maps[]`

財經皓角 often explains supply chains and "who sells shovels".

Fields:

- `theme`
- `upstream`
- `midstream`
- `downstream`
- `beneficiaries`
- `losers`
- `bottlenecks`
- `contract_structure`
- `evidence`

## 8. `policy_geopolitics[]`

Use for tariffs, Fed, oil wars, China/US, Middle East, export controls, elections, fiscal policy.

Fields:

- `event`
- `actors`
- `policy_direction`
- `market_channel`
- `assets_affected`
- `host_interpretation`
- `evidence`

## 9. `market_psychology[]`

Capture how he describes investor behavior.

Fields:

- `behavior_pattern`
- `market_condition`
- `danger`
- `recommended_discipline`
- `evidence`

## 10. `rhetorical_cues[]`

Keep jokes, analogies, and catchphrases separate from serious logic.

Fields:

- `cue_type`: joke, analogy, metaphor, quote, aside
- `text_paraphrase`
- `timestamp`
- `is_investment_relevant`
- `meaning`
- `evidence`

Rules:

- Do not use jokes as trading signals unless he explicitly converts them into a rule.
- Mark jokes and romantic/sexual asides as `is_joke_or_aside: true`.

## 11. `jokes_and_asides[]`

財經皓角的笑話不是雜訊。它們有三個用途:

- persona: 保留他的說話節奏、荒謬轉折、諧音、情色邊線、歷史梗。
- analogy: 有些笑話其實包著投資類比，例如新手投資人、牛市誘惑、自律。
- safety: 回答時要分清楚這是笑話、比喻、還是嚴肅投資規則。

Fields:

- `setup`: 笑話鋪陳或類比背景。
- `punchline_paraphrase`: 笑點轉折，短 paraphrase，不長抄。
- `timestamp`: e.g. `08:10`.
- `source_kinds`: `note`, `transcript`, or both.
- `confidence`: `high` when a note anchor and transcript context agree, `medium` for strong transcript-only humor signals, `low` for weak transcript-only candidates that need review.
- `topic_link`: linked market topic if any.
- `humor_type`: enum.
- `persona_signal`: 這個笑話展現的語氣或人設。
- `investment_relevance`: enum.
- `serious_takeaway`: 如果笑話後面接了認真結論，寫這裡；沒有就空字串。
- `is_sensitive`: boolean for sex/relationship/politics/body/gender jokes.
- `evidence`
- `dedupe_key`: normalized-text fingerprint used to avoid repeated jokes.

`humor_type` enum:

- `absurd_history`
- `sexual_pun`
- `romance_pun`
- `self_deprecating`
- `industry_absurdity`
- `political_irony`
- `meme`
- `analogy`
- `wordplay`
- `other`

`investment_relevance` enum:

- `none`
- `weak_style_only`
- `analogy_for_behavior`
- `direct_rule_wrapper`

Extraction and dedupe rules:

- Extract jokes from both notes and transcripts.
- Notes are high-precision anchors when a section is explicitly labeled `皓哥笑話`.
- Transcripts provide evidence and catch unlabeled candidates when they contain explicit humor markers, absurd/pun turns, or strong persona markers.
- Merge note and transcript records only when date matches and timestamp/windowed text similarity confirms they are the same segment.
- Do not merge adjacent but distinct jokes just because timestamps are close; note headings and normalized text must also be similar.
- Classify weak transcript-only detections conservatively. Keep them reviewable, but do not let them override note-labeled evidence.

Example:

```json
{
  "setup": "TOTO 半導體零組件受惠 AI 需求，不只是衛浴公司",
  "punchline_paraphrase": "他把 TOTO 半導體知識轉成約會聊天梗，說連馬桶都飛上天",
  "timestamp": "08:10",
  "topic_link": "AI supply chain / semiconductor equipment",
  "humor_type": "industry_absurdity",
  "persona_signal": "用生活荒謬感把產業知識講得好記",
  "investment_relevance": "weak_style_only",
  "serious_takeaway": "AI 供應鏈擴散到非典型受惠者",
  "is_sensitive": false
}
```

## 12. `open_questions[]`

Questions to track across later episodes.

Fields:

- `question`
- `why_it_matters`
- `follow_up_assets`
- `follow_up_data`

## Extraction Rules

- Do not impersonate. Use third person: "他認為", "游庭皓的框架是".
- Do not over-summarize. Extract decision rules and causal mechanisms.
- Separate host view from third-party quoted views. If he cites Dimon, Fink, Goldman, etc., store `speaker: third_party` unless he endorses it.
- Evidence must be short paraphrase plus timestamp/section. Avoid long verbatim copying.
- If a field is not supported, leave it empty.
- Notes are indexes; transcripts are evidence. Official articles can raise confidence when the same logic appears there.
- Market context must not be decorative. Every directional `asset_view` should include at least one objective alignment field when price data exists.
- Do not treat a historical view as current advice. Current answers must retrieve historical analogues and then compare with fresh market context.

## Prompt Skeleton

```text
You are extracting Yu Ting-Hao / 財經皓角 investment reasoning.

Inputs:
- episode metadata
- timestamped transcript
- optional note summary
- aligned market context
- related official article snippets

Task:
Return valid JSON matching the schema. Do not summarize the episode as prose. Extract:
1. market_regime
2. episode_thesis
3. macro_transmission_chains
4. asset_views
5. allocation_logic
6. risk_flags
7. industry_maps
8. policy_geopolitics
9. market_psychology
10. jokes_and_asides
11. rhetorical_cues
12. open_questions

Hard rules:
- Third person only; do not impersonate.
- Mark jokes/asides.
- Separate host endorsement from quoted third-party claims.
- Use short evidence references with timestamp/section.
- Leave unsupported fields empty.
- Use only allowed enums.
```
