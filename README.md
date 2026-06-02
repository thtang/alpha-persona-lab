<div align="center">

<h1>Alpha Persona Lab.skill</h1>


> *「擦鞋童從 1 萬點擦到 4 萬點，擦鞋童自己都已經開鞋店了。」-謝孟恭* <br>
> *「健康的四大秘訣，少油、少鹽、少糖、少婦。」-游庭皓*

<p>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <a href="https://chatgpt.com/codex/"><img alt="Codex Skill" src="https://img.shields.io/badge/Codex-Skill-blue"></a>
  <a href="https://claude.com/download"><img alt="Claude Desktop Skill" src="https://img.shields.io/badge/Claude%20Desktop-Skill-blueviolet"></a>
  <a href="https://skills.sh"><img alt="skills.sh Compatible" src="https://img.shields.io/badge/skills.sh-Compatible-green"></a>
</p>

<br>

<p>
  <strong>把財經創作者蒸餾成可安裝的 Agent Skill，讓模型用他們的市場語感、部位邏輯和人生吐槽來分析你的問題。</strong>
</p>

<br>

<p>
  目前包含 <code>gooaye</code> 股癌 Podcast、<code>yutinghao</code> 游庭皓的財經皓角、<code>zhezhe</code> 郭哲榮分析師 / 摩爾證券投顧、<code>thememiner</code> 即時細粒度跨市場題材挖掘，以及 <code>lagradar</code> 美日台中跨市場題材傳導雷達。<br>
  股癌 659 集逐字稿；財經皓角 82 篇逐字稿、61 篇筆記、459 篇官方公開文章；哲哲 565 篇 ASR 逐字稿、SoundOn metadata、20 篇 UDN 公開文章。<br>
  不是復讀語錄，是把創作者的判斷方式接上 market context、結構化資料和可更新 scripts。
</p>

<p>
  <a href="#效果示例">看效果</a> ·
  <a href="#安裝">安裝</a> ·
  <a href="#clone-後快速復現">復現</a> ·
  <a href="#手機版安裝-lightweight-instructions">手機版</a> ·
  <a href="#使用範例">使用範例</a> ·
  <a href="#更新資料">更新資料</a> ·
  <a href="#原始資料與風險提示">原始資料與風險提示</a>
</p>

</div>

---

## 效果示例

```text
使用者  ❯ $gooaye 依近期語料跟現在盤面，給我未來能買的股票

gooaye  ❯ 先把後視鏡拿掉：近一個月漲最多的，不等於現在最該買。
          依近期語料，他的框架會先找「強主線回檔不死」和
          「同邏輯還沒完全補漲」的標的。

          Watchlist 會分三層：
          1. CPU 外溢：嘉澤這種還沒像 AMD / Intel 噴爛的延伸題材。
          2. 二軍輪動：世界先進、環球晶這類成熟製程 / 矽晶圓候選。
          3. 軟體 AI 回流：NET、PLTR 這種沒有跟半導體一起高潮的標的。

          買法不是市價亂追，而是等站回短線均線、放量轉強，
          或回測不破再小部位。失效條件也要先寫好：
          主線破線、族群退潮、或只是單日補漲沒延續，就不要硬凹。

使用者  ❯ $yutinghao 國巨現在能不能追？

yutinghao ❯ 結論：等回檔，不是完全不碰。
            被動元件要看的是銀價、報價、庫存循環和台股風險偏好
            是否同時站在你這邊。若只是看到族群漲了才追，
            你買到的可能是行情後段的波動，不是產業轉折。
            觸發條件是報價續強、族群輪動沒散、回檔不破前波支撐。

使用者  ❯ $zhezhe 被動元件現在能不能追？

zhezhe   ❯ 依公開語料脈絡，他會先把問題拆成大盤位置、主流題材、
            外資與台幣方向，再看族群裡的報價與指標股是否同時配合。
            可以研究，但不能只因為國巨或華新科漲了就追。
            比較像他的框架是：台股多頭結構還在、AI/記憶體主流未散、
            被動元件補漲有量，才用小部位跟；若大盤轉弱或族群破線，
            先把風險控下來。

使用者  ❯ $gooaye 要不要為了更高薪轉職？

gooaye  ❯ 可以談，但不要只看薪水。
          如果新工作給的是薪資上升、能力上升、人脈上升，
          那值得認真考慮；如果只是多一點錢，換來更高工時、
          更差主管和更低可替代性，那其實是把人生槓桿開錯地方。

使用者  ❯ $yutinghao 隨便講個笑話

yutinghao ❯ 很多人一開始買股票，只有下跌才虧錢。
            後來學會做空，上漲也虧錢。
            後來學會期貨，價格不變、波動損耗也虧錢。
            後來學會選擇權，十倍速虧錢。
            最早只會炒台股，上班才虧錢；
            後來學會美股，晚上睡覺也虧錢。
            好不容易學會炒幣，週末也虧錢。
            最後乾脆去融資，沒錢也虧錢。

            這個梗收在 2026-02-26 的「YoYoYo」段落。
            前面在講交易和投資的心態差異，
            最後落點是：心態不對，怎麼做都會虧。
```

這不是語錄搜尋器。`gooaye` 會把股癌的部位、追高、停損和生活 QA 框架拿來判斷你的問題；`yutinghao` 會把財經皓角的宏觀 regime、資金流、產業鏈和笑話類比拿來重建推理；`zhezhe` 會把郭哲榮公開語料裡的大盤方向、主流族群、權值股、績效敘事與風控語氣拆成可查證的分析框架。

## 即時細粒度 ThemeMiner

`thememiner` 是 `lagradar` 的上游感測器，用來維護細粒度題材庫和跨市場股票關聯圖。每次使用 skill 時，都會先刷新題材庫、新聞證據、價格異動與 US/JP/TW/CN/HK/KR 股票關聯，再把高分題材丟給 `lagradar` 做 lead-lag、補漲和風控驗證。

```bash
python3 thememiner/scripts/update_theme_graph.py --refresh-prices --refresh-news
python3 thememiner/scripts/query_theme_graph.py --top 20
python3 thememiner/scripts/query_theme_graph.py --concept hbm
python3 thememiner/scripts/build_theme_graph_html.py
open thememiner/output/theme_graph.html
```

輸出會落在 [`thememiner/output`](thememiner/output)，核心資料包含 [`thememiner/data/fine_theme_taxonomy_seed.json`](thememiner/data/fine_theme_taxonomy_seed.json)、[`thememiner/data/cross_market_watchlist_seed.json`](thememiner/data/cross_market_watchlist_seed.json) 和 [`thememiner/data/company_profiles_seed.json`](thememiner/data/company_profiles_seed.json)。`company_profiles_seed.json` 會記錄公司主業、專業項目、平台/客戶路徑、約束、風險與 source，讓 graph edge 能說清楚「為什麼這家公司屬於這個題材」。AI 光子鏈另外有 `bottleneck_profile`：缺貨層級、稀缺度、替代難度、發現狀態與 bottleneck score，用來找 InP、矽光子、SOI、外延設備、特殊玻纖、CPO 這種第二/第三層瓶頸。

## 跨市場 Laggard Radar

`lagradar` 是一個新的交易研究 persona，用來捕捉美、日、台、中/港、韓之間的中期題材擴散。它不是只看電子業；seed graph 也涵蓋銅與工業金屬、能源、航運、軍工航太、醫藥/CDMO、金融利率等非電子題材。核心是找 `improving laggard`：leader shock 已驗證、關係圖說得通、候選股仍有 lag gap，且 3/5/10 日、量價、突破、籌碼或資金流開始確認，同時避開過熱高潮。

候選股會讀取 ThemeMiner 的公司 profile，因此輸出除了價格/量能，也會附上 business、specialization、relation path 和 bottleneck layer；缺少 profile 的股票只能視為低信心概念連結。

```bash
python3 lagradar/scripts/scan_laggards.py
python3 lagradar/scripts/query_laggards.py --top 15
python3 lagradar/scripts/query_laggards.py --theme pcb
```

輸出會落在 [`lagradar/output`](lagradar/output)，設計細節見 [`lagradar/README.md`](lagradar/README.md)，完整方法論見 [`lagradar/references/methodology.md`](lagradar/references/methodology.md)。

## 底層抓取 Runtime

ThemeMiner / Lagradar 可以選配 [Scrapling](https://github.com/D4Vinci/Scrapling) 來提升公開網頁抓取品質。Scrapling 支援 adaptive selector、HTTP fetcher、stealth browser fetcher、dynamic browser fetcher 和 spider crawl，適合用在公司官網、交易所公司頁、新聞頁、供應鏈資料頁這類容易改版或有動態內容的來源。

本 repo 使用專案內 `.venv`，避免污染系統 Python。Scrapling 需要 Python 3.10+：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-scraping.txt
.venv/bin/scrapling install
.venv/bin/python scripts/scrapling_smoke.py
```

如果本機預設 `python3` 低於 3.10，請改用 Codex bundled Python 或其他 Python 3.10+。目前底層腳本仍能用原本的 `urllib` / Yahoo cache 跑；接入 Scrapling 時優先用於「官方公司 profile 升級、動態頁、容易改版的 selector」，不要拿來無限制重爬來源站。

建立 profile 補強隊列，或抓取少量高優先級 source evidence：

```bash
.venv/bin/python thememiner/scripts/scrapling_source_fetcher.py --no-fetch
.venv/bin/python thememiner/scripts/scrapling_source_fetcher.py --limit 40
```

輸出會落在 `thememiner/output/profile_upgrade_queue.json`、`thememiner/output/source_pages/`、`thememiner/output/company_source_evidence.jsonl` 和 `thememiner/output/source_fetch_report.md`。`upgrade_company_profiles_official.py` 會讀取 `company_source_evidence.jsonl`，把高品質 source evidence 掛回 profile 的 source refs 和 official metadata。

全量補強時用 shard 避免單一程序慢站點拖死，也避免多 worker 寫同一個 evidence 檔：

```bash
.venv/bin/python thememiner/scripts/scrapling_source_fetcher.py --limit 0 --stream-evidence --shard 0/6 --queue-output thememiner/output/profile_upgrade_queue.shard0of6.json --evidence-output thememiner/output/company_source_evidence.shard0of6.jsonl --report-output thememiner/output/source_fetch_report.shard0of6.md
.venv/bin/python thememiner/scripts/merge_source_evidence.py --inputs 'thememiner/output/company_source_evidence.shard*of6.jsonl'
.venv/bin/python thememiner/scripts/upgrade_company_profiles_official.py --include-curated --source-evidence thememiner/output/company_source_evidence.jsonl --shard 0/6 --output thememiner/data/profile_upgrades/source_evidence_full_shard0of6.json
.venv/bin/python thememiner/scripts/merge_company_profile_shards.py --base thememiner/data/company_profiles_autofill.json --shards 'thememiner/data/profile_upgrades/source_evidence_full_shard*of6.json' --output thememiner/data/company_profiles_official_autofill.json
python3 thememiner/scripts/update_theme_graph.py --auto-profiles thememiner/data/company_profiles_official_autofill.json
python3 thememiner/scripts/build_theme_graph_html.py
```

## 安裝

先安裝支援 Skills 的桌面 App，再直接用自然語言安裝。Codex 和 Claude Desktop 都先走這條；如果安裝器不支援 multi-skill repo 的子資料夾，再用手動 symlink。

### App 下載連結

- Codex App: [Codex 官方入口](https://chatgpt.com/codex/) / [ChatGPT Desktop 下載頁](https://chatgpt.com/download/)
- Claude Desktop App: [Claude 官方下載頁](https://claude.com/download)

### Codex App: 自然語言安裝

在 Codex 裡直接說：

```text
請從 https://github.com/thtang/alpha-persona-lab 安裝 gooaye skill
請從 https://github.com/thtang/alpha-persona-lab 安裝 yutinghao skill
請從 https://github.com/thtang/alpha-persona-lab 安裝 zhezhe skill
請從 https://github.com/thtang/alpha-persona-lab 安裝 thememiner skill
請從 https://github.com/thtang/alpha-persona-lab 安裝 lagradar skill
```

安裝後重開 Codex session，或重新載入 skills。之後可用：

```text
$gooaye ...
$yutinghao ...
$zhezhe ...
$thememiner ...
$lagradar ...
```

如果自然語言安裝沒有正確抓到子資料夾，改用下面的手動 symlink。

### Claude Desktop App: 自然語言安裝

Claude Desktop App 也可以直接用自然語言要求下載安裝：

```text
請從 https://github.com/thtang/alpha-persona-lab 安裝 gooaye skill
請從 https://github.com/thtang/alpha-persona-lab 安裝 yutinghao skill
請從 https://github.com/thtang/alpha-persona-lab 安裝 zhezhe skill
請從 https://github.com/thtang/alpha-persona-lab 安裝 thememiner skill
請從 https://github.com/thtang/alpha-persona-lab 安裝 lagradar skill
```

安裝後重開 Claude Desktop，或重新載入 skills。之後可用：

```text
$gooaye ...
$yutinghao ...
$zhezhe ...
$thememiner ...
$lagradar ...
```

如果 App 安裝器沒有正確處理 multi-skill repo 的子資料夾，改用下面的手動 symlink。

### 手機版安裝: lightweight instructions

手機版通常不能像 Codex / Claude Desktop 一樣掛本地 skill folder、讀逐字稿或執行 scripts。若要在 ChatGPT / Claude 手機 app 使用，可以改貼 lightweight instruction：

- 單獨使用股癌：複製 [`mobile-instructions/gooaye.mobile.md`](mobile-instructions/gooaye.mobile.md)
- 單獨使用財經皓角：複製 [`mobile-instructions/yutinghao.mobile.md`](mobile-instructions/yutinghao.mobile.md)
- 同時使用兩個 persona：複製 [`mobile-instructions/combined.finance-persona.mobile.md`](mobile-instructions/combined.finance-persona.mobile.md)

如果 App 的 instruction 欄位長度有限，優先貼單一 persona 版；`combined` 版比較適合 Claude Project Instructions 或較長的專案指令欄位。
`zhezhe` 目前建議使用桌面版 skill，因為它依賴本地 ASR 逐字稿、SoundOn metadata、文章語料與 market context 檢索。

使用方式：

```text
打開 ChatGPT / Claude 手機 App
進入 Custom Instructions / Project Instructions
貼上對應的 .mobile.md 內容
之後用 $gooaye 或 $yutinghao 提問
```

手機版是輕量行為規則，不會自動讀取本 repo 的 corpus、market context 或 scripts。需要引用歷史逐字稿或結構化資料時，請改用桌面版 skill，或把相關片段貼進對話。

### 手動安裝: fallback

先 clone repo：

```bash
git clone git@github.com:thtang/alpha-persona-lab.git
cd alpha-persona-lab
```

如果你沒有設定 GitHub SSH，也可以用 HTTPS：

```bash
git clone https://github.com/thtang/alpha-persona-lab.git
cd alpha-persona-lab
```

最快的安裝方式是直接跑 repo 內的 installer：

```bash
# 安裝到 Codex
bash scripts/install-skills.sh --codex

# 或同時安裝到 Codex + Claude
bash scripts/install-skills.sh --all-targets
```

installer 會把五個 skill 以 symlink 掛到本機 skills folder。之後只要在 repo 內 `git pull`，下次開新 session 就會讀到新版 skill 與資料。

#### Codex

推薦用 symlink，之後在 repo 裡 `git pull` 就能更新 skill：

```bash
mkdir -p ~/.codex/skills
ln -sfn "$PWD/gooaye" ~/.codex/skills/gooaye
ln -sfn "$PWD/yutinghao" ~/.codex/skills/yutinghao
ln -sfn "$PWD/zhezhe" ~/.codex/skills/zhezhe
ln -sfn "$PWD/thememiner" ~/.codex/skills/thememiner
ln -sfn "$PWD/lagradar" ~/.codex/skills/lagradar
```

重開 Codex session，或重新載入 skills。

#### Claude Desktop / Claude Code

```bash
mkdir -p ~/.claude/skills
ln -sfn "$PWD/gooaye" ~/.claude/skills/gooaye
ln -sfn "$PWD/yutinghao" ~/.claude/skills/yutinghao
ln -sfn "$PWD/zhezhe" ~/.claude/skills/zhezhe
ln -sfn "$PWD/thememiner" ~/.claude/skills/thememiner
ln -sfn "$PWD/lagradar" ~/.claude/skills/lagradar
```

重開 Claude Desktop / Claude Code，或重新載入 skills。

如果你偏好複製而不是 symlink：

```bash
mkdir -p ~/.claude/skills ~/.codex/skills
cp -R gooaye ~/.claude/skills/gooaye
cp -R yutinghao ~/.claude/skills/yutinghao
cp -R zhezhe ~/.claude/skills/zhezhe
cp -R thememiner ~/.claude/skills/thememiner
cp -R lagradar ~/.claude/skills/lagradar
cp -R gooaye ~/.codex/skills/gooaye
cp -R yutinghao ~/.codex/skills/yutinghao
cp -R zhezhe ~/.codex/skills/zhezhe
cp -R thememiner ~/.codex/skills/thememiner
cp -R lagradar ~/.codex/skills/lagradar
```

複製安裝的缺點是之後 repo 更新時要重新複製一次。

## Clone 後快速復現

這個 repo 是 multi-skill bundle。別的帳號 clone 後，最小復現流程如下：

```bash
git clone https://github.com/thtang/alpha-persona-lab.git
cd alpha-persona-lab
bash scripts/install-skills.sh --codex
bash scripts/bootstrap-theme-stack.sh
```

`bootstrap-theme-stack.sh` 會用 repo 內已提交的 seed/profile/output snapshot 重建 ThemeMiner 與 Lagradar：

- `thememiner/output/theme_graph.html`
- `lagradar/output/lagradar_theme_graph.html`
- `lagradar/output/laggard_candidates.json`

預設模式是 light bootstrap：用已提交的 ThemeMiner graph snapshot 重建 HTML，並更新 Lagradar 的候選輸出。這是為了讓另一個帳號 clone 後能快速復現。

如果要重新計算 ThemeMiner 底層 graph：

```bash
bash scripts/bootstrap-theme-stack.sh --rebuild-graph
```

如果要刷新即時價格、新聞與 laggard history：

```bash
bash scripts/bootstrap-theme-stack.sh --fresh
```

如果要重掃 US / TW / TPEX 股票 universe，並用可用的 agent provider 做語義判斷：

```bash
bash scripts/bootstrap-theme-stack.sh --discover --fresh --agent-mode auto --agent-workers 2
```

如果要完全不限制 discovered stocks / price symbols，跑全量重建：

```bash
bash scripts/bootstrap-theme-stack.sh --full --fresh --agent-mode auto --agent-workers 2
```

如果要重建 20 年題材擴散回測，需要先安裝 Python 依賴：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PYTHON=.venv/bin/python bash scripts/bootstrap-theme-stack.sh --backtest
```

Scrapling 是選配抓取 runtime，只在需要補官方公司 profile、source evidence 或動態頁時安裝：

```bash
.venv/bin/python -m pip install -r requirements-scraping.txt
.venv/bin/scrapling install
```

資料策略是：可直接使用的 seed/profile/HTML/report 會跟 repo 一起提交；音訊、ASR 暫存、cache、logs、20 年 history raw cache 會被 `.gitignore` 排除。這樣 clone 後能先復現核心 skill，想追最新資料再跑 refresh。

## 使用範例

### Gooaye / 股癌

投資與交易：

```text
$gooaye 依近期語料跟現在盤面，給我未來能買的股票
$gooaye 不要看後視鏡，幫我找下一批可能補漲的 watchlist
$gooaye 把近期主線拆成：能買、等回檔、不要追，並給觸發跟失效條件
$gooaye 幫我從 CPU、被動元件、ASIC、軟體 AI 裡挑未來候選股，順便講部位怎麼控
```

生活與 QA：

```text
$gooaye 新手爸爸要怎麼平衡育兒、工作跟投資？
$gooaye 要不要為了更高薪轉職？
$gooaye 買房跟租房怎麼取捨？
$gooaye 小孩教育要不要砸很多錢？
```

研究與查證：

```text
$gooaye 找出他近年談台積電估值與追高的邏輯
$gooaye 整理他對停損、加碼、槓桿的共同原則
$gooaye 他在 QA 裡怎麼看職涯選擇？
```

### Yutinghao / 財經皓角

宏觀與市場：

```text
$yutinghao 這週美股追 AI 還是等回檔？
$yutinghao 台韓股市都在漲，這是 AI 主升段還是過熱？
$yutinghao 台積電、三星、SK 海力士這條 AI 記憶體鏈怎麼拆？
$yutinghao 美債殖利率跟美元現在對科技股是助攻還是壓力？
```

特定集數與產業：

```text
$yutinghao 2026-05-08 這集的 AI 狂牛邏輯是什麼？
$yutinghao 找出他講 TOTO、半導體材料、賣鏟子的段落
$yutinghao 他怎麼看記憶體長約和供應鏈重組？
```

笑話與表達 DNA：

```text
$yutinghao 找出他用笑話講投資紀律的例子
$yutinghao 唐僧女兒國那段到底是在講什麼投資規則？
$yutinghao 他有哪些常用的荒謬類比？
```

### Zhezhe / 郭哲榮分析師

台股與族群：

```text
$zhezhe 台股創高後還能追嗎？
$zhezhe 國巨、華新科、被動元件這波怎麼看？
$zhezhe 台積電、鴻海、廣達誰比較符合他的主流股框架？
$zhezhe 記憶體漲到這裡，南亞科跟華邦電該怎麼拆？
```

公開語料與風格：

```text
$zhezhe 找出他近期談台股萬點、崩盤、拉回的共同邏輯
$zhezhe 他怎麼把會員績效、外資方向和主流題材串在一起？
$zhezhe 用他的公開語料拆解「風險控制」到底是什麼訊號
```

### 交叉比較

```text
用 $gooaye 和 $yutinghao 分別判斷：NVDA 現在能不能追？
用 $gooaye 和 $yutinghao 比較他們對槓桿、追高、停損的差異
用 $gooaye、$yutinghao、$zhezhe 分別判斷：國巨這波是補漲還是追高？
```

## 更新資料

### Gooaye

逐字稿來源是 `https://whatmkreallysaid.com/`。`gooaye` skill 觸發時會先做每日同步檢查。

手動更新：

```bash
python3 gooaye/scripts/sync_daily_transcripts.py --force-check
python3 gooaye/scripts/align_market_context.py
python3 gooaye/scripts/build_episode_asset_context.py
python3 gooaye/scripts/build_investment_memory.py
python3 gooaye/scripts/build_life_memory.py
```

### Yutinghao

資料來源包含 Digital Garden 筆記/逐字稿、YouTube RSS、官方網站公開文章。`yutinghao` skill 觸發時也會先做每日同步檢查。

手動更新：

```bash
python3 yutinghao/scripts/sync_daily_sources.py --force-check
```

### Zhezhe

資料來源包含 SoundOn RSS metadata、郭哲榮集數 ASR 逐字稿、UDN/摩爾公開文章與 market context。`zhezhe` skill 觸發時會先做每日同步檢查；MP3 只作為 ASR 暫存，轉完預設刪除。

手動更新：

```bash
python3 zhezhe/scripts/sync_daily_sources.py --force-check
```

### ThemeMiner + Lagradar

`thememiner` 和 `lagradar` 是一組上下游 skill：ThemeMiner 更新題材庫、公司 business profile、跨市場股票關聯圖；Lagradar 讀 ThemeMiner 的 graph 和 thesis cards，產生題材擴散分數、leader/laggard、觸發與失效條件。

手動更新：

```bash
python3 thememiner/scripts/update_theme_graph.py --refresh-prices --refresh-news --max-discovered 0
python3 thememiner/scripts/build_company_thesis_cards.py --agent-mode auto --agent-workers 2
python3 thememiner/scripts/build_theme_graph_html.py
python3 lagradar/scripts/scan_laggards.py --refresh-history
python3 lagradar/scripts/build_lagradar_html.py
```

或直接用 repo 級 bootstrap：

```bash
bash scripts/bootstrap-theme-stack.sh --fresh
```

## Market Context

三個 skill 都使用 episode-date market context 輔助理解，不把歷史逐字稿當成即時建議。

### Baseline Context

固定 basket 用來理解每集大環境，例如：

- 台股、台積電、S&P 500、QQQ、SOXX、NVDA、TSM
- VIX、美債殖利率、DXY、USD/TWD、USD/JPY
- 油、金、銅、BTC

### Mentioned-Asset Context

逐字稿或筆記提到的公司/產業會另外掃 alias map：

- direct mention: 逐字稿/筆記真的點名的公司或 ticker
- sector proxy: 提到「記憶體」「AI 伺服器」「被動元件」等產業時，用 basket 補背景

回答時必須區分 direct mention 和 sector proxy，不能把 proxy basket 說成創作者直接推薦。

## 結構

```text
alpha-persona-lab/
  gooaye/
    SKILL.md
    agents/openai.yaml
    data/
    references/
    scripts/
  yutinghao/
    SKILL.md
    agents/openai.yaml
    data/
    references/
    scripts/
  zhezhe/
    SKILL.md
    agents/openai.yaml
    data/
    references/
    scripts/
  thememiner/
    SKILL.md
    agents/openai.yaml
    data/
    output/
    scripts/
  lagradar/
    SKILL.md
    agents/openai.yaml
    data/
    output/
    references/
    scripts/
  scripts/
    install-skills.sh
    bootstrap-theme-stack.sh
```

## 常用指令

```bash
# Gooaye
python3 gooaye/scripts/search_corpus.py 台積電 估值 --limit 20
python3 gooaye/scripts/retrieve_investment_context.py 台積電 下週 買進 趨勢 部位
python3 gooaye/scripts/retrieve_life_context.py 育兒 小孩 家庭 工作 平衡
python3 gooaye/scripts/distill_episodes.py validate

# Yutinghao
python3 yutinghao/scripts/search_corpus.py AI 記憶體 台韓 --limit 20
python3 yutinghao/scripts/search_corpus.py 唐僧 自律 槓桿 --kind joke --limit 10
python3 -m json.tool yutinghao/data/market_context/episode_asset_context_manifest.json

# Zhezhe
python3 zhezhe/scripts/search_corpus.py 國巨 被動元件 --kind metadata --kind transcript --limit 20
python3 zhezhe/scripts/search_corpus.py 台股 季線 風險 --kind article --limit 20
python3 -m json.tool zhezhe/data/distilled/asset_memory.json

# ThemeMiner
python3 thememiner/scripts/query_theme_graph.py --top 20
python3 thememiner/scripts/query_theme_graph.py --concept cpo
python3 thememiner/scripts/audit_graph_coverage.py

# Lagradar
python3 lagradar/scripts/query_laggards.py --top 15
python3 lagradar/scripts/select_trade_candidates.py --top 10
```

## Notes

- 這是分析與研究工具，不是投資顧問。
- Current market questions still need fresh prices, earnings dates, and news.
- Quotes from transcripts should be short; prefer paraphrase plus episode/date citation.
- Included data is for local analysis and reproducibility.

## 原始資料與風險提示

### 引用的原始資料

- Gooaye / 股癌逐字稿與集數 metadata: 來自 `https://whatmkreallysaid.com/` 的公開逐字稿、集數日期、標題與摘要。
- 財經皓角 Digital Garden: 來自 `https://digitalgarden-five-azure.vercel.app/筆記：游庭皓的財經皓角/` 與其公開 file tree 的筆記、逐字稿與整理頁。
- 財經皓角 YouTube metadata: 來自公開 YouTube RSS 的影片 id、標題、發布時間、描述與章節資訊。
- 財經皓角官方公開文章: 來自 `yutinghao.finance` 公開 WordPress REST API / 公開文章頁的文章內容、摘要、分類與 metadata。
- 哲哲 / 郭哲榮 SoundOn metadata 與 ASR 逐字稿: 來自公開 SoundOn RSS feed 的 episode metadata、MP3 URL 與本地 ASR 生成逐字稿。ASR transcript 是衍生資料，使用時應回看來源 metadata 與必要的上下文。
- 哲哲 / 郭哲榮公開文章: 來自 UDN 理財作者頁與摩爾證券投顧公開頁的文章 inventory、連結、摘要與可抓取正文。
- 市場行情資料: 來自 Yahoo Finance chart API 的日線價格資料，包含指數、股票、ETF、匯率、利率、商品與 crypto proxy。episode market context 以節目日期對齊最近可用收盤價，並計算 `ret_1d / 5d / 20d / 60d` 等衍生欄位。
- 專案自建 reference data: asset alias map、sector basket、distillation schema、joke/asides inventory、investment/life memory 都是本專案為檢索與分析建立的衍生資料，不代表原作者或資料來源直接背書。

### 授權範圍

本專案原創的程式碼、scripts、schema、skill 指令與文件以 [MIT License](LICENSE) 授權。

第三方逐字稿、筆記、文章、音訊 metadata、影片 metadata、行情資料，以及基於這些資料生成的 ASR transcript、結構化萃取與 market context，不包含在本專案 MIT 授權範圍內；相關權利仍屬原作者、平台或資料提供方。

### 風險提示

本專案僅供研究、學習、文本蒸餾與個人知識管理使用，不構成投資建議、交易建議、財務規劃、法律建議或稅務建議。所有回答都應被視為「基於歷史語料與行情背景的分析」，不是保證獲利或避免虧損的操作指令。

本專案與股癌、游庭皓、財經皓角、郭哲榮、摩爾證券投顧、whatmkreallysaid.com、SoundOn、YouTube、Yahoo Finance 或任何資料提供方皆無官方關係，也未取得其背書。逐字稿、筆記、文章、音訊 metadata、影片 metadata 與行情資料的著作權、商標權與資料權利屬於各自權利人；本 repo 中的本地副本只用於可重現的個人研究與 skill 測試。

市場資料可能延遲、缺漏、調整或與券商/交易所資料不同；歷史節目中的觀點也可能已不適用於現在。實際投資前請自行查證最新價格、財報、法說、重大新聞與個人風險承受度，並為自己的決策負責。
