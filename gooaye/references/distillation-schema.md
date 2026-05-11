# Distillation Schema

The canonical schema for `data/distilled/episode_notes/EP###.json`. This file is the **single source of truth**; the distillation prompt embeds and references this spec.

The schema was designed bottom-up from a map-reduce discovery pass over all 659 episodes (5 regime-spanning chunks). Field shapes resist over-engineering: enums and per-item structure are added only where data showed clear, recurring need across multiple regimes.

`schema_version` is currently `"v2"`. Future revisions bump this and require A/B dry-run on the existing 5 sample episodes before full re-distillation.

---

## Top-level shape

```json
{
  "schema_version": "v2",
  "episode": 150,
  "date": "2021-06-19",

  "episode_archetype": { ... },
  "segment_breakdown": { ... },

  "market_regime": { ... },
  "topics": ["..."],

  "host_state": { ... },

  "investment_logic": [ ... ],
  "trade_observations": [ ... ],
  "qa_views": [ ... ],

  "catalysts": [ ... ],
  "narrative_threads": [ ... ],
  "view_changes": [ ... ],
  "principles": [ ... ],
  "mantras_or_catchphrases": [ ... ],
  "warnings": [ ... ],
  "references": [ ... ],
  "non_tradeable_insights": [ ... ],
  "open_questions": [ ... ]
}
```

All array fields default to `[]` when an episode has no relevant content. Object fields are required (use `null` inside if a sub-field is missing). **Do not omit fields.**

---

## Field specifications

### Episode shape

#### `episode_archetype` (object, required)

```json
{
  "primary": "market_commentary",
  "secondary": ["qa_heavy", "single_stock_deep_dive"]
}
```

A single primary label is too coarse — episodes commonly mix formats (e.g. EP66 = Neuralink + 館長 + 族群輪動). Use `primary` for the dominant shape and `secondary[]` for additional formats present (≥ ~15% of runtime each).

`primary`/`secondary[]` enum:

| value | description |
|---|---|
| `market_commentary` | 市場行情評論 + 個股觀察 |
| `qa_heavy` | 聽眾 QA 為主（≥40%） |
| `single_stock_deep_dive` | 單一個股 / 公司 / 事件深度（≥30%） |
| `industry_supply_chain` | 產業綜覽 / 供應鏈解析 / 多題並陳 |
| `philosophy` | 心法 / 觀念 / 書籍 / 大師備忘錄專集 |
| `interview` | 嘉賓訪談 / 公司參訪 |
| `event_response` | 事件型快評（黑天鵝、政策、戰爭、崩盤、危機應對） |
| `milestone_or_retrospective` | 里程碑 / 特集 / 年度檢討 / Podcast 圈 / 創作心得 |
| `lifestyle` | 純閒聊 / 生活 / 育兒 / 旅行 / 興趣（投資成分稀薄） |
| `cautionary_tale` | 詐騙 / 鬼故事 / 散戶悲歌警世 |
| `business_or_sponsorship` | 贊助 / 事業 / 實業投資 |

`secondary[]` may be empty.

#### `segment_breakdown` (object, required)

```json
{ "market_pct": 60, "qa_pct": 25, "life_or_aside_pct": 10, "ads_pct": 3, "principles_pct": 2 }
```

Integer percentages summing to ~100 (±5 tolerance). Used downstream to weight retrieval and to flag low-investment-density episodes.

---

### Market context

#### `market_regime` (object, required)

```json
{
  "phase_label": "升息預期轉鷹 + 多頭末段第一次修正",
  "narrative": "Fed 點陣圖將升息預期由 2024 提前至 2023，TSM 1日 -2.80%、SOXX 1日 -2.39%，美股科技短線回調；但 ^TWII 20日 +7.96%、60日 +7.77% 仍處多頭。",
  "geopolitical_factors": ["美中科技戰", "台灣三級警戒"],
  "regime_tags": ["升息週期", "估值殺", "鷹派轉向"]
}
```

- `phase_label`: 短標籤（≤ 20 字）。需在跨集間具有可對齊性（同階段該用相似標籤），這樣助理才能跨集做 regime-similarity 檢索。
- `narrative`: 1-2 句中文，**必須引用 market_context 提供的具體數值**。
- `geopolitical_factors[]`: 非市場驅動因子（戰爭/制裁/封城/選舉/政策變動）。沒有就 `[]`。
- `regime_tags[]`: 額外可檢索標籤，與 phase_label 互補。

#### `topics[]` (array, required)

3-8 個中文標籤。flat string array。用於模糊搜尋。

---

### Host state

主播自身的部位、自評、生活事件是節目的第二條敘事弧。Discovery pass 在 5 個 regime chunk 都命中此維度——獨立成欄而不是塞進 trade_observations，因為「他自己在做什麼」與「他建議市場做什麼」是可以背離的訊號。

#### `host_state` (object, required)

```json
{
  "leverage_state": "降到 1.3 倍",
  "disclosed_positions": [
    {
      "asset": "Square (SQ)",
      "stance": "重倉但已大幅虧損",
      "reasoning": "違紀重押、學費教訓"
    }
  ],
  "self_critique": [
    {
      "target": "賣飛 NVDA 太早",
      "assessment": "短期看錯但策略沒變",
      "tone": "self_deprecating"
    }
  ],
  "personal_arc_markers": [
    {
      "event": "兒子健檢出狀況",
      "impact_on_trades": "降槓桿、減倉",
      "domain": "family"
    }
  ]
}
```

四個子欄位都是 optional（缺省 `null` 或 `[]`）。

- `leverage_state`: 自由文字。他公開報槓桿水位時填。
- `disclosed_positions[]`: 他自承的部位，stance 自由文字（重倉 / 套牢檢討 / 抄底進場 / 違紀加碼…）。
- `self_critique[]`: 戰術自評。`tone` 同 trade_observations 的 tone enum。
- `personal_arc_markers[]`: 生活事件對交易的影響。`domain` enum: `family` / `health` / `work` / `relationships` / `hobbies` / `other`.

→ 助理被問「股癌目前自己在做什麼？」「他承認過什麼錯？」走這條。

---

### Investment claims & observations

#### `investment_logic[]`

```json
[
  {
    "claim": "重壓單一標的最大的風險不是營收不如預期，而是黑天鵝事件造成毀滅式傷害，應該分散",
    "trigger": "投資人集中持股單一公司、押注關鍵題材股",
    "is_conditional": false,
    "condition": null,
    "action_bias": "size-down",
    "risk_control": "分散持股以避開低機率但傷害巨大的事件",
    "risk_control_type": "diversify",
    "evidence": "EP150 2021-06-19 摘述：他以聽眾天鈺爆賺、世芯踩雷對比",
    "source_type": "host_framework",
    "confidence": "high"
  }
]
```

| 欄位 | 規則 |
|---|---|
| `claim` | 一句話陳述決策規則或信念 |
| `trigger` | 觸發條件 |
| `is_conditional` (bool) | 是否「if X then Y」式條件規則 |
| `condition` (str / null) | 若 is_conditional=true，X 部分。例：「SPX 跌破 4100」 |
| `action_bias` (enum) | `buy` / `sell` / `hold` / `hedge` / `wait` / `size-up` / `size-down` / `trim` / `scale-out` / `scale-in` / `stop-out` / `pyramid` / `rotate` / `unknown` |
| `risk_control` | 自由文字 |
| `risk_control_type` (enum) | `stop-loss` / `position-size` / `diversify` / `liquidity` / `time-bound` / `none` |
| `evidence` | `EP{n} {date} 摘述：...` 短摘 |
| `source_type` (enum) | `host_framework` / `earnings_call` / `site_visit` / `industry_contact` / `media_report` / `personal_test` / `channel_check` / `social_rumor` / `expert_quote(<name>)` |
| `confidence` (enum) | `high` (明確且重複講) / `medium` (明確講一次) / `low` (推論) |

#### `trade_observations[]`

```json
[
  {
    "asset_or_sector": "台積電",
    "asset_symbol": "2330.TW",
    "asset_type": "stock",
    "view": {
      "short_term": "neutral",
      "medium_term": "bullish",
      "long_term": "bullish"
    },
    "primary_horizon": "medium-term",
    "reasoning": "Fed 轉鷹估值受壓但基本面未變，台股電子族群已轉強",
    "industry_nodes": ["7nm", "5nm"],
    "catalyst_anchor": "2021-Q3-earnings",
    "consensus_level": "consensus",
    "market_alignment": "2330.TW 收 552.16、20日 +6.79%、60日 +2.45%；TSM 1日 -2.80%。",
    "tone": "serious"
  }
]
```

| 欄位 | 規則 |
|---|---|
| `asset_or_sector` | 中文名稱 |
| `asset_symbol` | 已追蹤代碼（`2330.TW` / `TSM` / `^TWII` / `^GSPC` / `QQQ` / `SOXX` / `NVDA` / `TSLA` / `BTC-USD`）或 `null` |
| `asset_type` (enum) | `stock` / `sector` / `index` / `theme` / `crypto` / `macro` / `commodity` |
| `view` (object) | 三個 enum 欄位：`bullish` / `bearish` / `neutral` / `conditional` / `unstated`；不講的維度填 `unstated` |
| `primary_horizon` (enum) | `intraday` / `swing` / `medium-term` / `long-term` / `unclear`（他主要強調的時間框架） |
| `reasoning` | 一句話 |
| `industry_nodes[]` | 技術節點標籤（CoWoS-S/L/P、HBM3e/HBM4、EMIB、玻璃基板、HVDC、3DXP…）。沒有就 `[]` |
| `catalyst_anchor` (str / null) | 綁定的事件 id（對應 `catalysts[].id`），或 `null` |
| `consensus_level` (enum) | `consensus` / `contrarian` / `crowded` / `overlooked` / `unclear` |
| `market_alignment` | 用 market_context 數值描述 |
| `tone` (enum) | `serious` / `self_deprecating` / `sarcastic` / `warning` / `joke` / `promotional` |

#### `qa_views[]`

```json
[
  {
    "category": "personal_finance",
    "question_theme": "新手 10% 現金水位",
    "viewpoint": "新手保留約 10% 現金應急是合理的，比例取決於現金流穩定度",
    "principle": "現金水位決策應該配合自己現金流穩定度，而不是套用通用比例",
    "tone": "practical",
    "evidence": "EP150 2021-06-19 摘述：他回答工作一年的小菜雞...",
    "asker_persona": "工作 1 年新手"
  }
]
```

| 欄位 | 規則 |
|---|---|
| `category` (enum) | `investment_operation` / `personal_finance` / `career` / `family` / `relationships` / `lifestyle` / `ethics` / `tools_platforms` / `health_mental` |
| `question_theme` | 自由文字短標 |
| `viewpoint` | 他的立場 |
| `principle` | 可推廣的信念 |
| `tone` | 自由文字（直白 / 憤世 / 實用 / 溫暖 / 玩笑 / 嘲諷 / 激動 / 勸誡…） |
| `evidence` | `EP{n} {date} 摘述：...` |
| `asker_persona` | 提問者描述（`"全職爸爸"` / `"30 歲將買房"` / `"工作 10 年"`），可 `null` |

---

### Catalysts & threads

#### `catalysts[]`

```json
[
  {
    "id": "fomc-2021-07",
    "event": "FOMC 7 月會議",
    "expected_date": "2021-07-28",
    "category": "monetary_policy",
    "expected_impact": "可能釋出更明確縮表時程",
    "linked_assets": ["^GSPC", "QQQ", "^TWII"]
  }
]
```

| 欄位 | 規則 |
|---|---|
| `id` | snake_case 唯一識別（用於 trade_observations.catalyst_anchor 連結）；建議格式 `<event>-<YYYY-MM>` |
| `event` | 中文事件名 |
| `expected_date` (str) | `YYYY-MM-DD` 或 `YYYY-MM` 或 `next-week` 等模糊描述 |
| `category` (enum) | `monetary_policy` / `earnings` / `macro_data` / `regulation` / `product_launch` / `conference` / `election` / `black_swan` / `IPO_or_listing` / `merger_acquisition` / `other` |
| `expected_impact` | 一句話 |
| `linked_assets[]` | 已追蹤代碼，沒有就 `[]` |

#### `narrative_threads[]`

```json
[
  {
    "thread_id": "musk-buys-twitter-2022",
    "label": "馬斯克收購推特",
    "this_episode_role": "follow_up",
    "prior_episode_refs": [233, 239]
  }
]
```

| 欄位 | 規則 |
|---|---|
| `thread_id` | snake_case 跨集穩定 id；建議 `<topic>-<year>` |
| `label` | 中文短標 |
| `this_episode_role` (enum) | `originating` / `follow_up` / `update` / `resolution` / `aside` |
| `prior_episode_refs[]` | 前情集數整數陣列，可 `[]`（萃取時不一定能精準回憶） |

→ 之後可由腳本聚合同 thread_id 集數，做事件演進時間軸。

#### `view_changes[]`

```json
[
  {
    "subject": "美股短期方向",
    "previous_view": "上週仍偏多",
    "current_view": "本週改為短期看空",
    "why_changed": "Fed 點陣圖出來後 risk-off",
    "previous_episode_ref": 149
  }
]
```

只在他**明確自述改口**時記錄。推論的不算。

---

### Principles, mantras, warnings

#### `principles[]`

```json
[
  {
    "principle": "聖母峰兩點下山",
    "explanation": "登頂後不能戀棧，到時間就要走",
    "category": "exit_discipline",
    "evidence": "EP154 2021-07-XX..."
  }
]
```

`category` enum: `position_sizing` / `exit_discipline` / `entry_discipline` / `risk_management` / `sentiment_reading` / `contrarian` / `longterm_outlook` / `mental_health` / `lifestyle_balance`.

整集型 `philosophy` archetype 的核心觀念集中放這。其他集偶爾講到的也放。

#### `mantras_or_catchphrases[]`

```json
["跑得快不會死", "見機行事", "三段論"]
```

口頭禪短列表。每集出現的，都列。

#### `warnings[]`

```json
[
  {
    "type": "instrument_trap",
    "target": "富邦 VIX (00677U)",
    "warning": "結構性扣血，不適合長期持有避險",
    "evidence": "EP15 2020-..."
  },
  {
    "type": "rumor_debunk",
    "target": "CoWoS 砍單傳聞",
    "actual": "他訪廠後判斷未砍單，是市場小作文",
    "evidence": "EP457 2024-..."
  }
]
```

`type` enum: `instrument_trap`（衍生品/結構陷阱）/ `anti_pattern`（散戶常犯錯）/ `rumor_debunk`（拆小作文）/ `scam_alert`（詐騙警示）.

`actual` 只在 `rumor_debunk` 時填，其他 type 省略此欄。

---

### References & insights

#### `references[]`

```json
[
  {
    "type": "book",
    "title": "致股東的信",
    "author": "Warren Buffett",
    "context": "熊市時讀，視野會變"
  }
]
```

`type` enum: `book` / `article` / `podcast_or_video` / `report` / `expert_quote`.

#### `non_tradeable_insights[]`

```json
[
  {
    "insight": "SpaceX 訪後感受 NASA 已經被超越",
    "domain": "tech_industry"
  }
]
```

`domain` enum: `tech_industry` / `macro_trend` / `society` / `personal_finance` / `lifestyle` / `management`.

公司參訪 / 產業考察 / 社會觀察 等不對應可交易標的的洞察。

---

### Open questions

#### `open_questions[]`

萃取時發現的模糊處或值得跨集對照的問題。

---

## Filling rules (strict)

1. **Language**: content fields Traditional Chinese; enums use exact English / lowercase_with_underscores values listed.
2. **Paraphrase only**, excerpts ≤ 200 chars. Third-person 「他」, never impersonate.
3. **Empty arrays are correct**. Don't fabricate. Don't omit fields.
4. **Confidence ladder**: `high` = explicit + repeated; `medium` = explicit once; `low` = your inference.
5. **Tone enum coverage**:
   - `serious`: 認真分析
   - `self_deprecating`: 自嘲（「我又賣飛了」）
   - `sarcastic`: 吐槽 / 諷刺
   - `warning`: 警世口吻（「你不要去玩」）
   - `joke`: 純玩笑、跑題
   - `promotional`: 業配 / 自薦持股
6. **Source type defaults**:
   - 他自己的觀察分析 → `host_framework`
   - 引述 Buffett/Marks/Druckenmiller/Pabrai 等 → `expert_quote(<name>)`
   - 朋友/業界大哥 → `industry_contact`
   - 自己訪廠 → `site_visit`
   - 其他依情境
7. **Asset symbol mapping**: 只當資產**明確對應**已追蹤代碼時填，否則 `null`。「美國成長股／大型科技股」這類 group reference 不要硬塞。
8. **Catalyst anchor consistency**: 同一集中如果 `trade_observation.catalyst_anchor` 引用某事件 id，該事件**必須**也出現在同集 `catalysts[]` 中（id 配對）。
9. **Single-pass extraction**: 萃取流程只讀逐字稿一次；所有頂層欄位在同一輪填齊，不要為了不同欄位多次讀同一份逐字稿。

---

## Worked example: EP150 (skeleton)

```json
{
  "schema_version": "v2",
  "episode": 150,
  "date": "2021-06-19",
  "episode_archetype": {
    "primary": "market_commentary",
    "secondary": ["qa_heavy"]
  },
  "segment_breakdown": { "market_pct": 50, "qa_pct": 35, "life_or_aside_pct": 12, "ads_pct": 3, "principles_pct": 0 },
  "market_regime": {
    "phase_label": "Fed 點陣圖轉鷹 + 多頭末段修正",
    "narrative": "Fed 升息預期由 2024 提前至 2023，TSM 1日 -2.80%、SOXX 1日 -2.39% 美股科技短線回調；^TWII 20日 +7.96%、60日 +7.77% 仍多頭。",
    "geopolitical_factors": ["台灣三級警戒"],
    "regime_tags": ["升息預期", "鷹派轉向", "估值殺"]
  },
  "topics": ["Fed 升息預期", "鴿派轉鷹", "估值與本益比", "原物料回調", "金融股利差", "重壓單一標的風險"],
  "host_state": {
    "leverage_state": null,
    "disclosed_positions": [],
    "self_critique": [],
    "personal_arc_markers": []
  },
  "investment_logic": [/* ... */],
  "trade_observations": [/* ... */],
  "qa_views": [/* ... */],
  "catalysts": [
    { "id": "fomc-2021-07", "event": "下次 FOMC", "expected_date": "2021-07-28", "category": "monetary_policy", "expected_impact": "確認升息時程", "linked_assets": ["^GSPC","QQQ","^TWII"] }
  ],
  "narrative_threads": [],
  "view_changes": [],
  "principles": [],
  "mantras_or_catchphrases": ["保險思維是用來防小機率高傷害事件"],
  "warnings": [
    { "type": "anti_pattern", "target": "用兆豐金除息策略 all-in", "warning": "做價差不算保守策略，真正保守是指數型 ETF", "evidence": "EP150 ..." }
  ],
  "references": [
    { "type": "podcast_or_video", "title": "第二聲鈴響", "author": "Netflix（西班牙劇）", "context": "封城調劑身心" }
  ],
  "non_tradeable_insights": [],
  "open_questions": ["若 Fed 真的進入密集升息階段，台灣電子股的估值能維持多久？"]
}
```

---

## Cross-Episode Principle (aggregation shape)

When a script aggregates a recurring rule across many episodes (e.g. for a theme rollup), use this shape:

```json
{
  "principle": "concise reusable rule",
  "category": "valuation | trend | macro | position sizing | sentiment | career | life | relationships | other",
  "supporting_episodes": ["EP1 2020-02-27", "EP2 2020-02-29"],
  "counterexamples": ["episodes where he qualifies or reverses this"],
  "regime_dependency": "when this rule seems to apply or stop applying",
  "confidence": "high | medium | low"
}
```

This is a **derived** shape — produced by `query_assistant.py` and similar tools, not by the per-episode extractor.

---

## Evidence rules

- Anchor every serious claim to episode number and date.
- Treat episode summaries as navigation aids, not proof. Verify against transcript text before finalizing a principle.
- Separate what he says he personally does (`host_state`) from rules he advocates (`investment_logic`) from advice he gives listeners (`qa_views`) from jokes (`tone`).
- Mark a principle low confidence until it appears across multiple episodes or is stated explicitly.
- Do not infer performance from market alignment. Align to market data to understand the setup, not to claim that he was right (decision cards, not episode notes, do that — see `decision-card-schema.md`).
