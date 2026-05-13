# Zhezhe Corpus Summary

- built_at: 2026-05-13T11:57:06Z
- transcript_count: 565
- transcript_date_range: 2025-07-24 to 2026-05-12
- market_regime_counts: {'mixed / range': 262, 'risk-on / momentum': 285, 'weak / corrective': 18}

## High-Level Read

這份 deterministic memory 先把 ASR 逐字稿轉成可檢索索引；它適合做問題路由、找 evidence、抓高頻框架。真正回答時仍要回讀 transcript/article 原文，並把當日 market context 對齊後再下結論。

## Dominant Themes

- 台積電估值與權值股拖拉: episodes=482, hits=16758, top_terms={'台積': 5896, '台積電': 5466, '營收': 1479, '外資': 1354, 'EPS': 1002, '本益比': 842}
- 台股/台指方向: episodes=558, hits=14324, top_terms={'台股': 3504, '創新高': 2169, '大盤': 1828, '萬點': 1696, '拉回': 1358, '崩盤': 1047}
- 績效/會員/權威敘事: episodes=438, hits=12438, top_terms={'會員': 4474, '賺錢': 2657, '獲利': 1560, '投資長': 1498, '績效': 891, '冠軍': 591}
- AI伺服器與供應鏈: episodes=514, hits=9617, top_terms={'AI': 7288, '鴻海': 955, '廣達': 639, '伺服器': 342, '輝達': 201, '緯創': 110}
- 記憶體循環: episodes=432, hits=8012, top_terms={'記憶體': 4618, '南亞科': 2767, '美光': 175, '群聯': 166, 'HBM': 89, 'DDR4': 64}
- 風險控制與進出紀律: episodes=484, hits=6583, top_terms={'獲利': 1560, '注意': 1383, '拉回': 1358, '風險': 931, '回檔': 800, '下車': 191}
- 美債/匯率/資金面: episodes=422, hits=5551, top_terms={'美債': 1855, '台幣': 1004, '降息': 956, '資金': 754, '利率': 406, '美元': 332}
- PCB/CCL/ABF: episodes=226, hits=879, top_terms={'PCB': 395, '景碩': 171, '載板': 164, 'ABF': 129, '金像電': 7, '欣興': 6}
- 被動元件: episodes=116, hits=533, top_terms={'被動元件': 246, '國巨': 150, '華新科': 131, 'MLCC': 6}
- 航運與景氣循環股: episodes=140, hits=481, top_terms={'航運': 194, '陽明': 124, '長榮': 57, '萬海': 42, '貨櫃': 38, '海運': 14}

## Top Assets And Sectors

- 台積電 2330.TW: episodes=436, hits=11530, aliases={'台積': 5896, '台積電': 5466, '2330': 157, 'TSMC': 11}
- 加權指數 ^TWII: episodes=541, hits=8730, aliases={'台股': 3504, '台灣股市': 3358, '大盤': 1828, '加權指數': 40}
- ai_supply_chain : episodes=471, hits=7892, aliases={'AI': 7288, '伺服器': 342, 'AI伺服器': 213, '人工智慧': 35, 'GB300': 14}
- memory : episodes=370, hits=4811, aliases={'記憶體': 4618, 'HBM': 89, 'DDR4': 64, 'DDR5': 32, 'DRAM': 8}
- taiwan_etf_bond : episodes=386, hits=4007, aliases={'美債': 1855, '台灣50': 1158, 'ETF': 937, '債券': 57}
- 南亞科 2408.TW: episodes=401, hits=3066, aliases={'南亞科': 2767, '2408': 297, '南科': 2}
- 元大台灣50 0050.TW: episodes=306, hits=1912, aliases={'台灣50': 1158, '0050': 751, '元大台灣50': 3}
- 聯發科 2454.TW: episodes=139, hits=1230, aliases={'聯發科': 1075, '發哥': 97, '2454': 58}
- USD/TWD TWD=X: episodes=154, hits=1134, aliases={'台幣': 1004, '匯率': 99, '新台幣': 31}
- 鴻海 2317.TW: episodes=297, hits=1003, aliases={'鴻海': 955, '2317': 48}
- 廣達 2382.TW: episodes=245, hits=753, aliases={'廣達': 639, '2382': 114}
- pcb_ccl : episodes=184, hits=691, aliases={'PCB': 395, '載板': 164, 'ABF': 129, 'CCL': 2, '銅箔基板': 1}
- Nasdaq 100 ETF QQQ: episodes=158, hits=522, aliases={'納斯達克': 474, '那斯達克': 25, 'QQQ': 21, 'NASDAQ': 2}
- NVIDIA NVDA: episodes=111, hits=314, aliases={'輝達': 201, '黃仁勳': 88, 'NVIDIA': 25}
- passive_components : episodes=82, hits=252, aliases={'被動元件': 246, 'MLCC': 6}
- 華邦電 2344.TW: episodes=129, hits=250, aliases={'2344': 115, '華邦': 86, '華邦電': 49}
- shipping : episodes=90, hits=250, aliases={'航運': 194, '貨櫃': 38, '海運': 14, '貨櫃三雄': 4}
- 景碩 3189.TW: episodes=122, hits=212, aliases={'景碩': 171, '3189': 41}

## Rhetorical DNA

- 二分對照與轉折 (contrast): episodes=502, hits=36393
- 績效榜單與會員見證 (authority): episodes=403, hits=7066
- 散戶焦慮與踏空痛點 (fear_control): episodes=417, hits=6533
- 財富畫面與漲幅承諾 (social_proof): episodes=469, hits=5609
- 數據節點驗證 (authority): episodes=433, hits=4744
- 驚嚇式標題開場 (urgency): episodes=373, hits=1922

## Retrieval Rules

- Live trade questions: fetch current market data, then use `theme_memory.json` and `asset_memory.json` to locate analogous episodes; never answer from old transcript alone.
- Single ticker/sector questions: start from `asset_memory.json`, then open top episode transcripts and `episode_asset_context/<source_id>.json`.
- Style/persona questions: start from `rhetoric_memory.json`, then verify with short transcript snippets.
- Historical call review: use `episode_notes.jsonl` for candidate calls, then compare with later price data manually.
- ASR caveat: duplicate SoundOn feeds can create same-date duplicate transcripts; preserve both source ids but avoid double-counting identical claims in final prose.
