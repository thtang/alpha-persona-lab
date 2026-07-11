# Source Audit

## Current Corpus Status

Generated on 2026-06-20 from public YouTube metadata and available subtitles. Completed on 2026-06-21 with YouTube transcript API supplementation and local MLX Whisper ASR.

- Channel: 邦妮區塊鏈 Bonnie Blockchain
- YouTube URL: https://www.youtube.com/@BonnieBlockchain
- Channel ID: `UCjlPLMYEsq0pjgLL1q24mSg`
- Channel description from metadata: "金融懶人包 X 階級翻轉 X 區塊鏈新手 X 世界大神訪談"
- Metadata snapshot: `data/source/youtube_flat_all.jsonl`
- Total videos in snapshot: 381
- Cleaned transcripts built: 381
- Raw subtitle/VTT files available: 454
- Missing transcripts: 0
- ASR transcripts generated locally: 306 unique videos, using `mlx-community/whisper-large-v3-turbo`

The corpus is now complete at the video level for this 381-video snapshot. Source quality is mixed: some transcripts come from public YouTube captions, some from `youtube-transcript-api`, and videos with disabled or unavailable captions were transcribed from downloaded audio with local MLX Whisper ASR.

## Important Limitation

It is now fair to say "the local corpus has transcripts for all 381 videos in the snapshot." Do not imply all transcripts are official captions or human-verified. For exact quotes, names, tickers, numbers, or legally sensitive claims, verify against the source video because ASR can misrecognize fast Chinese, English names, acronyms, and bilingual passages.

## Update Commands

Fetch full metadata:

```bash
.venv/bin/yt-dlp --flat-playlist --dump-json 'https://www.youtube.com/@BonnieBlockchain/videos' > crypto-mainstream-framework/data/source/youtube_flat_all.jsonl
```

Fetch subtitles in a throttled continuation run:

```bash
.venv/bin/yt-dlp \
  --sleep-requests 5 --sleep-interval 8 --max-sleep-interval 20 \
  --write-subs --write-auto-subs \
  --sub-langs 'zh-Hant,zh-Hans,zh,en.*' \
  --sub-format 'vtt/srt/best' \
  --skip-download --ignore-errors \
  --download-archive crypto-mainstream-framework/data/source/subtitle_archive.txt \
  -o 'crypto-mainstream-framework/data/subtitles/%(playlist_index)03d-%(id)s-%(title).80s.%(ext)s' \
  'https://www.youtube.com/@BonnieBlockchain/videos'
```

Supplement through YouTube transcript API:

```bash
python3 crypto-mainstream-framework/scripts/fetch_youtube_transcripts.py --sleep 0.75
```

Generate local ASR for videos with no subtitle file:

```bash
python3 crypto-mainstream-framework/scripts/asr_missing_transcripts.py \
  --model mlx-community/whisper-large-v3-turbo \
  --sleep-requests 3
```

Rebuild transcript corpus:

```bash
python3 crypto-mainstream-framework/scripts/build_corpus.py
```

Search corpus:

```bash
python3 crypto-mainstream-framework/scripts/search_corpus.py 比特幣 ETF --limit 10
python3 crypto-mainstream-framework/scripts/search_corpus.py 穩定幣 --tag stablecoin --limit 10
python3 crypto-mainstream-framework/scripts/search_corpus.py 主流 adoption --limit 10
```

## External Reality-Check Sources

- SEC spot Bitcoin ETP approval statement: https://www.sec.gov/newsroom/speeches-statements/gensler-statement-spot-bitcoin-011023
- BlackRock iShares Bitcoin Trust ETF product page: https://www.ishares.com/us/products/333011/ishares-bitcoin-trust-etf
- Visa Onchain Analytics Dashboard: https://visaonchainanalytics.com/
- DefiLlama stablecoin market cap dashboard: https://defillama.com/stablecoins
- Chainalysis 2025 Global Crypto Adoption Index: https://www.chainalysis.com/blog/2025-global-crypto-adoption-index/
- White House GENIUS Act fact sheet: https://www.whitehouse.gov/fact-sheets/2025/07/fact-sheet-president-donald-j-trump-signs-genius-act-into-law/
- U.S. Treasury GENIUS Act implementation proposal: https://home.treasury.gov/news/press-releases/sb0435
- Federal Reserve FEDS Note on stablecoins in 2025: https://www.federalreserve.gov/econres/notes/feds-notes/stablecoins-in-2025-developments-and-financial-stability-implications-20260408.html
- BIS Annual Economic Report 2025, next-generation monetary system: https://www.bis.org/publ/arpdf/ar2025e3.htm
- FSB crypto-assets and global stablecoins page: https://www.fsb.org/work-of-the-fsb/financial-innovation-and-structural-change/crypto-assets-and-global-stablecoins/
