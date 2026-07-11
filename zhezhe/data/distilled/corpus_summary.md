# Zhezhe Corpus Summary

- built_at: 2026-07-10T23:33:23Z
- transcript_count: 571
- transcript_date_range: 2025-07-24 to 2026-07-03
- market_regime_counts: {'mixed / range': 262, 'risk-on / momentum': 291, 'weak / corrective': 18}

## High-Level Read

這份 deterministic memory 先把 ASR 逐字稿轉成可檢索索引；它適合做問題路由、找 evidence、抓高頻框架。真正回答時仍要回讀 transcript/article 原文，並把當日 market context 對齊後再下結論。

## Dominant Themes

- 台積電估值與權值股拖拉: episodes=488, hits=16849, top_terms={'台積': 5914, '台積電': 5483, '營收': 1496, '外資': 1360, 'EPS': 1033, '本益比': 844}
- 台股/台指方向: episodes=564, hits=14463, top_terms={'台股': 3539, '創新高': 2190, '大盤': 1836, '萬點': 1709, '拉回': 1400, '崩盤': 1048}
- 績效/會員/權威敘事: episodes=443, hits=12726, top_terms={'會員': 4614, '賺錢': 2728, '獲利': 1567, '投資長': 1519, '績效': 918, '冠軍': 600}
- AI伺服器與供應鏈: episodes=520, hits=9765, top_terms={'AI': 7428, '鴻海': 957, '廣達': 641, '伺服器': 345, '輝達': 202, '緯創': 110}
- 記憶體循環: episodes=438, hits=8121, top_terms={'記憶體': 4654, '南亞科': 2803, '群聯': 201, '美光': 176, 'HBM': 90, 'DDR4': 64}
- 風險控制與進出紀律: episodes=490, hits=6677, top_terms={'獲利': 1567, '拉回': 1400, '注意': 1393, '風險': 945, '回檔': 802, '下車': 194}
- 美債/匯率/資金面: episodes=428, hits=5605, top_terms={'美債': 1855, '台幣': 1004, '降息': 971, '資金': 761, '利率': 410, '美元': 343}
- PCB/CCL/ABF: episodes=226, hits=879, top_terms={'PCB': 395, '景碩': 171, '載板': 164, 'ABF': 129, '金像電': 7, '欣興': 6}
- 被動元件: episodes=120, hits=544, top_terms={'被動元件': 252, '國巨': 155, '華新科': 131, 'MLCC': 6}
- 航運與景氣循環股: episodes=141, hits=482, top_terms={'航運': 195, '陽明': 124, '長榮': 57, '萬海': 42, '貨櫃': 38, '海運': 14}

## Top Assets And Sectors

- 台積電 2330.TW: episodes=440, hits=11565, aliases={'台積': 5914, '台積電': 5483, '2330': 157, 'TSMC': 11}
- 加權指數 ^TWII: episodes=547, hits=8822, aliases={'台股': 3539, '台灣股市': 3406, '大盤': 1836, '加權指數': 41}
- ai_supply_chain : episodes=477, hits=8037, aliases={'AI': 7428, '伺服器': 345, 'AI伺服器': 215, '人工智慧': 35, 'GB300': 14}
- memory : episodes=376, hits=4848, aliases={'記憶體': 4654, 'HBM': 90, 'DDR4': 64, 'DDR5': 32, 'DRAM': 8}
- taiwan_etf_bond : episodes=391, hits=4043, aliases={'美債': 1855, '台灣50': 1176, 'ETF': 955, '債券': 57}
- 南亞科 2408.TW: episodes=404, hits=3104, aliases={'南亞科': 2803, '2408': 299, '南科': 2}
- 元大台灣50 0050.TW: episodes=311, hits=1941, aliases={'台灣50': 1176, '0050': 762, '元大台灣50': 3}
- 聯發科 2454.TW: episodes=143, hits=1249, aliases={'聯發科': 1092, '發哥': 98, '2454': 59}
- USD/TWD TWD=X: episodes=154, hits=1134, aliases={'台幣': 1004, '匯率': 99, '新台幣': 31}
- 鴻海 2317.TW: episodes=298, hits=1006, aliases={'鴻海': 957, '2317': 49}
- 廣達 2382.TW: episodes=246, hits=755, aliases={'廣達': 641, '2382': 114}
- pcb_ccl : episodes=184, hits=691, aliases={'PCB': 395, '載板': 164, 'ABF': 129, 'CCL': 2, '銅箔基板': 1}
- Nasdaq 100 ETF QQQ: episodes=161, hits=533, aliases={'納斯達克': 484, '那斯達克': 25, 'QQQ': 22, 'NASDAQ': 2}
- NVIDIA NVDA: episodes=112, hits=315, aliases={'輝達': 202, '黃仁勳': 88, 'NVIDIA': 25}
- passive_components : episodes=85, hits=258, aliases={'被動元件': 252, 'MLCC': 6}
- 華邦電 2344.TW: episodes=130, hits=252, aliases={'2344': 117, '華邦': 86, '華邦電': 49}
- shipping : episodes=91, hits=251, aliases={'航運': 195, '貨櫃': 38, '海運': 14, '貨櫃三雄': 4}
- 國巨 2327.TW: episodes=78, hits=213, aliases={'國巨': 155, '2327': 58}

## Rhetorical DNA

- 二分對照與轉折 (contrast): episodes=508, hits=36929
- 績效榜單與會員見證 (authority): episodes=408, hits=7249
- 散戶焦慮與踏空痛點 (fear_control): episodes=423, hits=6632
- 財富畫面與漲幅承諾 (social_proof): episodes=475, hits=5655
- 數據節點驗證 (authority): episodes=439, hits=4801
- 驚嚇式標題開場 (urgency): episodes=375, hits=1926

## Retrieval Rules

- Live trade questions: fetch current market data, then use `theme_memory.json` and `asset_memory.json` to locate analogous episodes; never answer from old transcript alone.
- Single ticker/sector questions: start from `asset_memory.json`, then open top episode transcripts and `episode_asset_context/<source_id>.json`.
- Style/persona questions: start from `rhetoric_memory.json`, then verify with short transcript snippets.
- Historical call review: use `episode_notes.jsonl` for candidate calls, then compare with later price data manually.
- ASR caveat: duplicate SoundOn feeds can create same-date duplicate transcripts; preserve both source ids but avoid double-counting identical claims in final prose.
