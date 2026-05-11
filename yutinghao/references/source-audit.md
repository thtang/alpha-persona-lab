# Source Audit: 游庭皓的財經皓角

Audit date: 2026-05-11

## Source Layers

### 1. YouTube Channel

- Channel: `https://www.youtube.com/channel/UC0lbAQVpenvfA2QqzsRtL_g`
- RSS feed works: `https://www.youtube.com/feeds/videos.xml?channel_id=UC0lbAQVpenvfA2QqzsRtL_g`
- Latest RSS item at crawl time: `2026/5/11(一)台韓領漲全球?AI狂潮東移 主升段到了?`
- RSS gives publish/update time, title, video id, description, and chapter markers.
- Direct old timedtext list endpoint returned empty on sampled recent videos.
- `youtube-transcript-api` was blocked from the current environment.
- YouTube watch HTML contains a transcript panel endpoint, but raw `youtubei/v1/get_transcript` returned `FAILED_PRECONDITION`; treat direct YouTube transcript crawling as possible but requiring a browser/session/cookie path.

Use YouTube RSS as the canonical video ledger and chapter source. Use transcripts from the Digital Garden for extraction until a stable first-party transcript crawler is added.

### 2. Digital Garden Notes And Transcripts

- Overview page: `https://digitalgarden-five-azure.vercel.app/筆記：游庭皓的財經皓角/`
- Public file tree: `https://digitalgarden-five-azure.vercel.app/filetree.json`
- Crawled notes: 61 pages, date range `2026-01-28` to `2026-05-08`.
- Crawled transcripts: 82 pages, date range `2026-01-02` to `2026-05-08`.
- Local outputs:
  - `data/notes/YYYY-MM-DD.md`
  - `data/transcripts/YYYY-MM-DD.md`
  - `data/source/digitalgarden_notes.jsonl`
  - `data/source/digitalgarden_transcripts.jsonl`

Observed shape:

- Transcript pages are timestamp-sectioned. Typical headers include `00:00 市場總覽`, topic sections, and final summary.
- Note pages are already semi-structured: `三句話總結`, `投資觀點`, region/market sections, `皓哥笑話`, and sometimes `節目金句`.
- Notes link back to the YouTube video and the corresponding transcript when available.

Quality caveats:

- The Digital Garden is a third-party derivative corpus, not the channel owner.
- Transcripts may contain ASR errors, date mismatches, or editorial cleanup.
- Use transcript text for evidence, but cross-check metadata against YouTube RSS and official descriptions.
- Keep source URLs on every extracted item so questionable statements can be traced.

### 3. Official Website

- Site: `https://yutinghao.finance/`
- Public WordPress REST categories found: 10.
- Public REST posts found: 459.
- Posts with full public content in REST response: 259.
- Local outputs:
  - `data/official_articles/*.md`
  - `data/source/official_categories.json`
  - `data/source/official_posts.jsonl`

Category counts:

- `【公開文章專欄】`: 148
- `【宏觀專業報告】`: 144
- `【專題影片】`: 131
- `【投資隨筆】`: 47
- `【基礎投資財經系列】`: 27
- `【提醒事項】`: 4
- `【總經資產配置看法】`: 2
- `未分類`: 1

Use official articles as higher-confidence long-form material for worldview, macro logic, and strategic framing. Member-only posts exposed only as metadata/excerpt must remain metadata-only; do not attempt to bypass access controls.

## Corpus Implications

財經皓角 is structurally different from Gooaye:

- It is a daily macro and market interpreter rather than a chatty Q&A podcast.
- The core object is not only individual stock judgment, but a causal chain: event -> macro variable -> liquidity/rates/earnings/positioning -> asset implication.
- It repeatedly covers AI capex, semiconductor supply chains, Taiwan/US market structure, oil/geopolitics, Fed policy, dollar/rates, market breadth, leverage, and investor psychology.
- Personal worldview appears mostly through discipline, long-termism, self-control, jokes, analogies, and occasional lifestyle/career side comments, not through listener QA.

## Market Context Plan

Each episode should get two market-context layers:

1. Fixed macro basket
   - Taiwan: `^TWII`, `2330.TW`, TAIEX futures if available.
   - US equity: `SPY`, `QQQ`, `SOXX`, `DIA`, `IWM`, `NVDA`, `TSM`.
   - Rates/liquidity: US 2Y, US 10Y, DXY, USD/TWD, USD/JPY.
   - Macro risk: VIX, WTI/Brent, gold, copper, BTC.

2. Dynamic mentioned-asset basket
   - Extract tickers, companies, sectors, commodities, countries, and indices from transcript/note.
   - Resolve symbols before fetching prices.
   - Store `market_date`, `close`, `ret_1d/5d/20d/60d`, drawdown, and forward returns for later outcome checks.

Implemented outputs:

- `data/market_context/episode_market_context.jsonl`: fixed macro basket aligned to each episode.
- `data/market_context/episode_market_context.csv`: flat fixed-basket table.
- `data/market_context/episode_asset_context/YYYY-MM-DD.json`: per-episode mentioned assets from transcripts/notes, including direct mentions and `sector_basket:*` proxy matches.
- `data/market_context/episode_asset_context.jsonl`: aggregate mentioned-asset context.
- `data/market_context/market_context_manifest.json`: baseline build metadata and price-fetch errors.
- `data/market_context/episode_asset_context_manifest.json`: mentioned-asset build metadata, top mentions, and price-fetch errors.
- `references/asset-symbol-map.json`: alias-to-symbol map.
- `references/asset-sector-baskets.json`: sector proxy baskets.

Current caveat:

- Sector baskets are context proxies, not direct recommendations. If an episode mentions `記憶體`, the basket can attach Samsung/SK Hynix/Micron/台灣記憶體 names for backdrop, but the answer must distinguish those from companies explicitly named in the transcript/note.

Time alignment rule:

- The show is usually around Taiwan 08:30 before Taiwan cash market opens.
- US assets should align to the prior US session close.
- Taiwan assets should default to previous Taiwan close unless the transcript explicitly references intraday/opening action.
- If the episode discusses "yesterday US market" or "today Taiwan market", keep both a source quote and the market-session label.

## Recommended Data Priority

1. YouTube RSS metadata: video id, title, publish time, description chapters.
2. Digital Garden transcript: timestamped raw material for evidence.
3. Digital Garden note: fast index for themes and section labels.
4. Official site full article: high-confidence long-form thinking and macro framework.
5. Official site metadata-only post: topic/time signal only.
