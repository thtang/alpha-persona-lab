# Market Alignment Guide

Podcast commentary is time-dependent. Always interpret a market view against what listeners likely knew near the episode date.

## Default Market Lens

Use `scripts/align_market_context.py` to create `data/market_context/episode_market_context.jsonl` from daily Yahoo Finance chart data. This is the broad-regime lens. The default symbols cover Taiwan, broad US equities, rates/volatility/currency, semiconductors, a few frequently discussed single names, and Bitcoin:

- `^TWII`: Taiwan Weighted Index
- `^GSPC`, `^IXIC`, `QQQ`: US broad/growth indices
- `^VIX`, `^TNX`, `TWD=X`: volatility, US 10-year yield, and USD/TWD context
- `2330.TW`: Taiwan Semi local shares
- `SOXX`, `TSM`, `NVDA`: semiconductor context
- `TSLA`: high-beta retail favorite
- `BTC-USD`: crypto risk appetite

## Mentioned Asset Lens

Use `scripts/build_episode_asset_context.py` to create per-episode files in `data/market_context/episode_asset_context/`. This is the ticker/sector lens and should be preferred when the user asks about a specific stock or industry.

The script combines:

- transcript alias matches from `references/asset-symbol-map.json`;
- explicit `trade_observations.asset_symbol` values from canonical episode notes;
- representative sector baskets from `references/asset-sector-baskets.json`;
- Yahoo Finance daily closes aligned to the episode date.

Each `EP###.json` contains `baseline_market_context`, `mentioned_assets`, `sector_basket_matches`, and `unresolved_mentions`. Each asset includes `sources`, so distinguish:

- `transcript`: the ticker/name appeared in the transcript;
- `trade_observations.asset_symbol`: the canonical distillation directly tagged that symbol;
- `sector_basket:<name>`: representative proxy context for a sector phrase.

Sector baskets are context, not direct recommendations. If a stock appears only through `sector_basket:*`, say it was used as a proxy for the sector backdrop.

## Alignment Rules

- Use the episode `date` from `data/source/episodes.json`.
- If the episode date is not a trading day, use the nearest prior trading close.
- Summarize the setup with 1-day, 5-day, 20-day, and 60-day returns when available.
- For Taiwan-specific claims, prioritize `^TWII`; for US tech or risk appetite, prioritize `^IXIC`, `QQQ`, `SOXX`, and relevant stocks.
- For stock/sector-specific claims, read the matching `episode_asset_context/EP###.json` and use `pricing_status` before citing price action.
- If `unresolved_mentions` contains the sector you need, the asset map is incomplete; either add an explicit mapping/basket or state that only broad market context is available.
- If a statement mentions a recent event, search nearby episodes and external primary/news sources as needed. Distinguish verified context from inference.
- If network data is unavailable, ask for or use a user-provided market CSV and state that the market context is incomplete.

## Interpretation Pattern

For each investment or trade claim, answer:

1. What had just happened in the relevant market?
2. Was he reacting to price action, valuation, macro news, sentiment, liquidity, or listener psychology?
3. Did he propose an action, a risk-control rule, or simply a narrative?
4. Is the rule stable across later episodes, or specific to that market regime?

Avoid turning one episode into a timeless rule unless later episodes confirm it.
