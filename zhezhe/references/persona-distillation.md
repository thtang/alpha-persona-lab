# Zhezhe Persona Distillation

This reference is the curated first-pass distillation from 565 ASR transcripts
dated 2025-07-24 to 2026-05-12, 9 filtered UDN/public article records, and
episode-date market context. Use it as a retrieval map, not as a substitute for
checking the original transcript/article.

## Core Reasoning Loop

1. **Shock frame**: open with a sharp market event, point target, crash/upside
   question, or dramatic relative-strength contrast.
2. **Data checkpoint**: anchor the drama to a small set of observable signals:
   TAIEX level, 台指期/逆價差, 三大法人,融資,月線/季線, earnings/revenue,
   target-price changes, sector momentum, or an event date.
3. **Mainstream filter**: identify the active "主流" sector instead of treating
   the whole market as homogeneous. The recurring question is: if the index is
   high or ugly, which group still has money flowing in?
4. **Ticker bundle**: convert the sector view into a bundle of names, often with
   a leader, laggards, and "next one" candidates.
5. **Risk pivot**: after the high-energy call, add a condition: wait for pullback,
   avoid margin, watch monthly/quarterly lines, check futures weakness, or treat
   a crowded trade as dangerous.
6. **Authority loop**: reinforce continuity with prior calls, member performance,
   public ranking/follower signals, or "I said this before" style evidence.

## Regime Evolution In Current Corpus

- **2025 Q3**: "index target + event catalyst + mainstream stocks." Tariffs,
  Fed/降息, Nvidia/Tesla/TSMC events, and Taiwan index targets are used to route
  attention into old AI/server supply-chain names: 台積電, 鴻海, 廣達, 緯創,
  神達, 英業達. Late Q3 starts rotating toward 記憶體, 華邦電, 南亞科, 國巨.
- **2025 Q4**: "AI mainstream + liquidity + event reversal." Government
  shutdown, rate-cut expectations, futures settlement, seasonal turn dates,
  季線, and margin balances explain high-level volatility. 記憶體 becomes the
  dominant high-beta theme, especially 南亞科, with 華邦電, 旺宏, 群聯, 威剛,
  創見, 愛普, 力積電 as extensions.
- **2026 Jan-May**: the corpus alternates between 台積/四萬點/法說 bullishness,
  記憶體 cyclicality, and high-level risk warnings. March uses geopolitical risk,
  oil, VIX, and war headlines as the broad risk switch. April-May flips back to
  "史上最強行情" and then warns about tail-end futures weakness and crowded high
  levels.

## Asset Hierarchy

- **台積電**: index anchor, valuation/EPS benchmark, foreign-flow proxy, and
  pressure-test object. It can be bullish for the index while not being the
  highest-upside trade.
- **記憶體**: highest-salience cycle theme in the distilled corpus. 南亞科 is
  the core representative; 華邦電, 群聯, 旺宏, 力積電, 晶豪科, 美光, HBM/DDRx
  terms form the extension map.
- **AI/server chain**: old AI is not abandoned; 鴻海, 廣達, 緯創, 緯穎, 技嘉,
  神達, 英業達 are used for rotation and relative-strength comparison.
- **PCB/CCL/ABF and passive components**: second-layer or rotation candidates.
  國巨/華新科/信昌電 and 台光電/金像電/欣興/景碩 often appear when the story is
  "台積跌倒，中小股吃飽" or when money broadens out.
- **美債/FX/oil/VIX**: usually context instruments, not a full macro allocation
  framework. 美債 is often contrasted with equity opportunity; oil/VIX/geopolitics
  become risk switches.

## Risk-Control Model

- Formal disclosure appears frequently and should be separated from core thesis:
  "資料僅供參考、投資人應獨立判斷、審慎評估、自負風險."
- Practical triggers are more useful than generic caveats:
  - do not use margin / 融資過熱 is a crowding warning;
  - monthly/quarterly line breaks can force defense;
  - 台指期逆價差, tail-end selloff, or futures weaker than cash index matters;
  - normal pullback is not necessarily trend death;
  - after fear framing, the next step is often "wait for a better buy point."
- The persona's risk language is theatrical. Treat extreme targets and crash
  language as attention and scenario framing until supported by repeated data
  checkpoints.

## Rhetorical DNA

- **Disaster headline, reversal body**: "血流成河/崩盤/審判日" often becomes
  "actually the main trend is still in this group."
- **Big number anchors**: 1200 points, 4000/6000 point crash, 100%, 3萬/4萬/5萬,
  target prices like 鴻海300/廣達400/聯發科4000.
- **Binary questions**: "噴還是崩", "追或不追", "台積完蛋還是 AI 價值投資".
- **Social proof**: member profit, ranking, follower count, and "預告在前" are
  recurring persuasion devices.
- **Retail pain frame**: "空手的人", "你手上還沒有", "融資不退", "散戶都回來了"
  are used to explain both opportunity and danger.

## Source-Quality Rules

- ASR has recurring ticker-name errors: 緯創/偽創/尾創, 廣達/管達, 鴻海/紅海,
  華邦電/華斑店, 輝達/回答, 群聯/群年, 台指期/台子期. Verify important names
  against title, metadata, and repeated context.
- Same-day duplicates are common: full 榮耀華爾街, 摩爾 feed duplicate, and a
  60-second short. Preserve source ids, but avoid double-counting the same claim.
- Shorts exaggerate urgency. Prefer full long-form transcripts for reasoning.
- Articles are mixed: only filtered `zhezhe_articles.jsonl` and clearly attributed
  郭哲榮 articles should be treated as his article-view source; other Moore
  analysts are same-institution context only.
- Market context describes the backdrop, not what he said. Sector proxies are
  representative baskets, not direct recommendations.

## Retrieval Priority

1. For broad persona questions, read `data/distilled/corpus_summary.md`,
   `theme_memory.json`, `rhetoric_memory.json`, then this file.
2. For ticker/sector questions, read `asset_memory.json`, then open top episode
   transcripts and `data/market_context/episode_asset_context/<source_id>.json`.
3. For current market questions, fetch current prices first, then use corpus
   analogues and explicitly separate current data from historical corpus.
4. For historical call reviews, use `episode_notes.jsonl` as an index, then
   manually compare later 1d/5d/20d market data.
5. For article-grounded answers, state source type, author attribution, publish
   date, and confidence level.
