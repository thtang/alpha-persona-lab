# zhezhe 文章與市場脈絡研究備忘錄

本 memo 只作語料蒸餾與檢索規則建議，不模仿或代言郭哲榮本人。

## 資料概況

- `zhezhe/data/articles` 共有 20 篇 UDN money 文章，日期約為 2024-11-27 至 2026-03-17；其中可明確歸入郭哲榮署名或標題/內文指向的文章約 9 篇，其餘多為摩爾投顧其他分析師（江國中、蔡慶龍、謝晨彥等）的個股/產業文章。
- `zhezhe/data/source/zhezhe_articles.jsonl` 有 9 筆作者頁 metadata，基本對應郭哲榮相關文章，欄位含標題、URL、作者、發布時間、關鍵字、摘要、local_path。
- `episode_market_context.jsonl` 與 `episode_asset_context.jsonl` 各 1710 筆，時間約 2020-12-01 至 2026-05-12；其中 1701 筆為 episode，9 筆為 article context。episode 多數 ASR 狀態為 pending，只有 1 筆有 transcript_path。

## 文章來源補足 podcast transcript 的地方

文章比 podcast metadata 更像「已整理過的論點切片」：標題直接揭示主張，內文通常包含觸發事件、推論鏈、風險判斷與操作語言。它補上三類 transcript 難以穩定提供的訊號：

- 明確主題與命名：關稅、台幣急貶、台積電月營收、記憶體、CPO、AI 供應鏈等，可作為主題檢索 seed。
- 可引用的時間戳與 URL：文章有發布/修改時間、來源頁、作者欄位，適合回答「當時怎麼看」與建立時序索引。
- 結構化論證風格：常見「先反駁市場恐慌，再提出關鍵訊號，再轉成操作判準」的框架，可萃取成 persona 的分析模式，但不能當成即時建議。

但文章集不是純郭哲榮 corpus：20 篇 markdown 中約 11 篇是其他摩爾投顧分析師個股研究，應標記為「同機構/非本人」，只用來補產業敘事與題材語彙，不可混入郭哲榮個人觀點。

## 市場脈絡使用方式

market context 應當作「當時市場背景校準器」，而不是發言內容本身。它提供同日或前一交易日的價格狀態，包括台股、櫃買、台積電、聯發科、TSM、NVDA、SOXX、QQQ、SPY、VIX、美元指數、台幣、日圓、美債殖利率、原油、黃金、BTC 等。回答時可用它判斷文章/節目是在強勢、回檔、避險升溫、匯率急變或類股輪動中的哪個位置。

asset context 可補上直接提及資產、類股 proxy 與 sector basket，但 proxy 命中很寬，像台灣 ETF/債券、被動元件、PCB/CCL、航運、AI 供應鏈常大量出現。使用時要區分「直接點名」與「類股代理」，避免把 basket proxy 誤寫成節目或文章真的推薦過。

## 來源品質 caveats

- Podcast context 目前多為 metadata 與市場資料，ASR/transcript 覆蓋極低；若沒有 transcript，不應推斷逐字內容。
- UDN 文章 metadata 與本地 markdown 不完全等價：JSONL 只有 9 筆，markdown 有 20 篇，且混入非郭哲榮署名文章。
- 文章常有強烈標題與投顧行銷語氣，適合萃取「當時主張與理由」，不適合直接當投資結論。
- 部分文章有「首刊於某日」「相關行情以當時為主」等編按；檢索與回答必須使用原始發表/首刊日期，不可用修改日期替代觀點時間。
- 市場 context 是事後整理的價格窗格，能描述同日/近 5/20/60 日表現，但不能證明發言者當時知道所有後續結果。

## 建議 retrieval rules

1. 先以作者與來源分層：`zhezhe_articles.jsonl` 與明確郭哲榮署名文章優先；其他摩爾投顧分析師文章只能作同機構產業背景，答案需明示非本人來源。
2. 對「當時怎麼看」問題，必須同時取文章/episode 日期前後最近的 market context，並用 `session_alignment` 決定是同日收盤後還是前一交易日資料。
3. 對個股或類股問題，直接提及資產優先於 sector proxy；proxy 只用來補板塊氣氛，不能寫成明確點名或建議。
4. 對沒有 transcript 的 episode，只可使用 title、description、keywords、market/asset context 做低信心摘要；不得生成逐字說法或具體口吻。
5. 回答需保留時間性與不確定性：標出文章日期、來源類型、是否本人署名，並把 market context 表述為背景校準，不把過去投顧文章延伸成現在的投資建議。
