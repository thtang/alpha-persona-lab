# Zhezhe Corpus Summary

- built_at: 2026-05-14T18:23:07Z
- transcript_count: 566
- transcript_date_range: 2025-07-24 to 2026-05-14
- market_regime_counts: {'mixed / range': 262, 'risk-on / momentum': 286, 'weak / corrective': 18}

## High-Level Read

這份 deterministic memory 先把 ASR 逐字稿轉成可檢索索引；它適合做問題路由、找 evidence、抓高頻框架。真正回答時仍要回讀 transcript/article 原文，並把當日 market context 對齊後再下結論。

## Dominant Themes

- 台積電估值與權值股拖拉: episodes=483, hits=16799, top_terms={'台積': 5897, '台積電': 5466, '營收': 1496, '外資': 1354, 'EPS': 1025, '本益比': 842}
- 台股/台指方向: episodes=559, hits=14339, top_terms={'台股': 3505, '創新高': 2174, '大盤': 1828, '萬點': 1697, '拉回': 1361, '崩盤': 1047}
- 績效/會員/權威敘事: episodes=439, hits=12625, top_terms={'會員': 4578, '賺錢': 2698, '獲利': 1562, '投資長': 1506, '績效': 913, '冠軍': 597}
- AI伺服器與供應鏈: episodes=515, hits=9639, top_terms={'AI': 7308, '鴻海': 955, '廣達': 641, '伺服器': 342, '輝達': 201, '緯創': 110}
- 記憶體循環: episodes=433, hits=8060, top_terms={'記憶體': 4633, '南亞科': 2780, '群聯': 186, '美光': 175, 'HBM': 89, 'DDR4': 64}
- 風險控制與進出紀律: episodes=485, hits=6600, top_terms={'獲利': 1562, '注意': 1389, '拉回': 1361, '風險': 935, '回檔': 800, '下車': 191}
- 美債/匯率/資金面: episodes=423, hits=5552, top_terms={'美債': 1855, '台幣': 1004, '降息': 956, '資金': 754, '利率': 407, '美元': 332}
- PCB/CCL/ABF: episodes=226, hits=879, top_terms={'PCB': 395, '景碩': 171, '載板': 164, 'ABF': 129, '金像電': 7, '欣興': 6}
- 被動元件: episodes=117, hits=536, top_terms={'被動元件': 249, '國巨': 150, '華新科': 131, 'MLCC': 6}
- 航運與景氣循環股: episodes=141, hits=482, top_terms={'航運': 195, '陽明': 124, '長榮': 57, '萬海': 42, '貨櫃': 38, '海運': 14}

## Top Assets And Sectors

- 台積電 2330.TW: episodes=437, hits=11531, aliases={'台積': 5897, '台積電': 5466, '2330': 157, 'TSMC': 11}
- 加權指數 ^TWII: episodes=542, hits=8733, aliases={'台股': 3505, '台灣股市': 3360, '大盤': 1828, '加權指數': 40}
- ai_supply_chain : episodes=472, hits=7912, aliases={'AI': 7308, '伺服器': 342, 'AI伺服器': 213, '人工智慧': 35, 'GB300': 14}
- memory : episodes=371, hits=4826, aliases={'記憶體': 4633, 'HBM': 89, 'DDR4': 64, 'DDR5': 32, 'DRAM': 8}
- taiwan_etf_bond : episodes=387, hits=4021, aliases={'美債': 1855, '台灣50': 1163, 'ETF': 946, '債券': 57}
- 南亞科 2408.TW: episodes=402, hits=3080, aliases={'南亞科': 2780, '2408': 298, '南科': 2}
- 元大台灣50 0050.TW: episodes=307, hits=1918, aliases={'台灣50': 1163, '0050': 752, '元大台灣50': 3}
- 聯發科 2454.TW: episodes=140, hits=1239, aliases={'聯發科': 1083, '發哥': 98, '2454': 58}
- USD/TWD TWD=X: episodes=154, hits=1134, aliases={'台幣': 1004, '匯率': 99, '新台幣': 31}
- 鴻海 2317.TW: episodes=297, hits=1003, aliases={'鴻海': 955, '2317': 48}
- 廣達 2382.TW: episodes=246, hits=755, aliases={'廣達': 641, '2382': 114}
- pcb_ccl : episodes=184, hits=691, aliases={'PCB': 395, '載板': 164, 'ABF': 129, 'CCL': 2, '銅箔基板': 1}
- Nasdaq 100 ETF QQQ: episodes=159, hits=526, aliases={'納斯達克': 477, '那斯達克': 25, 'QQQ': 22, 'NASDAQ': 2}
- NVIDIA NVDA: episodes=111, hits=314, aliases={'輝達': 201, '黃仁勳': 88, 'NVIDIA': 25}
- passive_components : episodes=83, hits=255, aliases={'被動元件': 249, 'MLCC': 6}
- shipping : episodes=91, hits=251, aliases={'航運': 195, '貨櫃': 38, '海運': 14, '貨櫃三雄': 4}
- 華邦電 2344.TW: episodes=129, hits=250, aliases={'2344': 115, '華邦': 86, '華邦電': 49}
- 景碩 3189.TW: episodes=122, hits=212, aliases={'景碩': 171, '3189': 41}

## Rhetorical DNA

- 二分對照與轉折 (contrast): episodes=503, hits=36507
- 績效榜單與會員見證 (authority): episodes=404, hits=7190
- 散戶焦慮與踏空痛點 (fear_control): episodes=418, hits=6555
- 財富畫面與漲幅承諾 (social_proof): episodes=470, hits=5622
- 數據節點驗證 (authority): episodes=434, hits=4785
- 驚嚇式標題開場 (urgency): episodes=374, hits=1924

## Retrieval Rules

- Live trade questions: fetch current market data, then use `theme_memory.json` and `asset_memory.json` to locate analogous episodes; never answer from old transcript alone.
- Single ticker/sector questions: start from `asset_memory.json`, then open top episode transcripts and `episode_asset_context/<source_id>.json`.
- Style/persona questions: start from `rhetoric_memory.json`, then verify with short transcript snippets.
- Historical call review: use `episode_notes.jsonl` for candidate calls, then compare with later price data manually.
- ASR caveat: duplicate SoundOn feeds can create same-date duplicate transcripts; preserve both source ids but avoid double-counting identical claims in final prose.
