# Zhezhe Corpus Summary

- built_at: 2026-06-15T17:53:20Z
- transcript_count: 569
- transcript_date_range: 2025-07-24 to 2026-06-15
- market_regime_counts: {'mixed / range': 262, 'risk-on / momentum': 289, 'weak / corrective': 18}

## High-Level Read

這份 deterministic memory 先把 ASR 逐字稿轉成可檢索索引；它適合做問題路由、找 evidence、抓高頻框架。真正回答時仍要回讀 transcript/article 原文，並把當日 market context 對齊後再下結論。

## Dominant Themes

- 台積電估值與權值股拖拉: episodes=486, hits=16839, top_terms={'台積': 5912, '台積電': 5481, '營收': 1496, '外資': 1360, 'EPS': 1027, '本益比': 844}
- 台股/台指方向: episodes=562, hits=14415, top_terms={'台股': 3524, '創新高': 2176, '大盤': 1834, '萬點': 1708, '拉回': 1387, '崩盤': 1048}
- 績效/會員/權威敘事: episodes=441, hits=12700, top_terms={'會員': 4605, '賺錢': 2724, '獲利': 1564, '投資長': 1515, '績效': 917, '冠軍': 599}
- AI伺服器與供應鏈: episodes=518, hits=9747, top_terms={'AI': 7410, '鴻海': 957, '廣達': 641, '伺服器': 345, '輝達': 202, '緯創': 110}
- 記憶體循環: episodes=436, hits=8093, top_terms={'記憶體': 4651, '南亞科': 2784, '群聯': 196, '美光': 175, 'HBM': 90, 'DDR4': 64}
- 風險控制與進出紀律: episodes=488, hits=6651, top_terms={'獲利': 1564, '注意': 1391, '拉回': 1387, '風險': 941, '回檔': 802, '下車': 191}
- 美債/匯率/資金面: episodes=426, hits=5571, top_terms={'美債': 1855, '台幣': 1004, '降息': 964, '資金': 760, '利率': 407, '美元': 333}
- PCB/CCL/ABF: episodes=226, hits=879, top_terms={'PCB': 395, '景碩': 171, '載板': 164, 'ABF': 129, '金像電': 7, '欣興': 6}
- 被動元件: episodes=118, hits=538, top_terms={'被動元件': 251, '國巨': 150, '華新科': 131, 'MLCC': 6}
- 航運與景氣循環股: episodes=141, hits=482, top_terms={'航運': 195, '陽明': 124, '長榮': 57, '萬海': 42, '貨櫃': 38, '海運': 14}

## Top Assets And Sectors

- 台積電 2330.TW: episodes=439, hits=11561, aliases={'台積': 5912, '台積電': 5481, '2330': 157, 'TSMC': 11}
- 加權指數 ^TWII: episodes=545, hits=8783, aliases={'台股': 3524, '台灣股市': 3384, '大盤': 1834, '加權指數': 41}
- ai_supply_chain : episodes=475, hits=8019, aliases={'AI': 7410, '伺服器': 345, 'AI伺服器': 215, '人工智慧': 35, 'GB300': 14}
- memory : episodes=374, hits=4845, aliases={'記憶體': 4651, 'HBM': 90, 'DDR4': 64, 'DDR5': 32, 'DRAM': 8}
- taiwan_etf_bond : episodes=389, hits=4036, aliases={'美債': 1855, '台灣50': 1170, 'ETF': 954, '債券': 57}
- 南亞科 2408.TW: episodes=403, hits=3085, aliases={'南亞科': 2784, '2408': 299, '南科': 2}
- 元大台灣50 0050.TW: episodes=310, hits=1931, aliases={'台灣50': 1170, '0050': 758, '元大台灣50': 3}
- 聯發科 2454.TW: episodes=142, hits=1248, aliases={'聯發科': 1091, '發哥': 98, '2454': 59}
- USD/TWD TWD=X: episodes=154, hits=1134, aliases={'台幣': 1004, '匯率': 99, '新台幣': 31}
- 鴻海 2317.TW: episodes=298, hits=1006, aliases={'鴻海': 957, '2317': 49}
- 廣達 2382.TW: episodes=246, hits=755, aliases={'廣達': 641, '2382': 114}
- pcb_ccl : episodes=184, hits=691, aliases={'PCB': 395, '載板': 164, 'ABF': 129, 'CCL': 2, '銅箔基板': 1}
- Nasdaq 100 ETF QQQ: episodes=160, hits=528, aliases={'納斯達克': 479, '那斯達克': 25, 'QQQ': 22, 'NASDAQ': 2}
- NVIDIA NVDA: episodes=112, hits=315, aliases={'輝達': 202, '黃仁勳': 88, 'NVIDIA': 25}
- passive_components : episodes=84, hits=257, aliases={'被動元件': 251, 'MLCC': 6}
- shipping : episodes=91, hits=251, aliases={'航運': 195, '貨櫃': 38, '海運': 14, '貨櫃三雄': 4}
- 華邦電 2344.TW: episodes=129, hits=250, aliases={'2344': 115, '華邦': 86, '華邦電': 49}
- 景碩 3189.TW: episodes=122, hits=212, aliases={'景碩': 171, '3189': 41}

## Rhetorical DNA

- 二分對照與轉折 (contrast): episodes=506, hits=36787
- 績效榜單與會員見證 (authority): episodes=406, hits=7233
- 散戶焦慮與踏空痛點 (fear_control): episodes=421, hits=6621
- 財富畫面與漲幅承諾 (social_proof): episodes=473, hits=5632
- 數據節點驗證 (authority): episodes=437, hits=4795
- 驚嚇式標題開場 (urgency): episodes=375, hits=1926

## Retrieval Rules

- Live trade questions: fetch current market data, then use `theme_memory.json` and `asset_memory.json` to locate analogous episodes; never answer from old transcript alone.
- Single ticker/sector questions: start from `asset_memory.json`, then open top episode transcripts and `episode_asset_context/<source_id>.json`.
- Style/persona questions: start from `rhetoric_memory.json`, then verify with short transcript snippets.
- Historical call review: use `episode_notes.jsonl` for candidate calls, then compare with later price data manually.
- ASR caveat: duplicate SoundOn feeds can create same-date duplicate transcripts; preserve both source ids but avoid double-counting identical claims in final prose.
