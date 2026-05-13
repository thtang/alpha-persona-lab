# Zhezhe Source Strategy

The corpus should be rich before it is clever.

## Source Priority

1. SoundOn RSS metadata: episode id, title, publish time, duration, description, MP3 URL.
2. ASR transcript from SoundOn MP3: generated raw speech corpus, stored with model and audio provenance.
3. UDN public article body: edited public article source, often cleaner than podcast metadata.
4. Other public Moore pages when available.
5. Third-party reposts or commentary: metadata only unless directly needed for external perception.

## Podcast Filtering

The configured SoundOn sources are:

- 摩爾證券投顧: `https://feeds.soundon.fm/podcasts/7c9b0925-29e2-472c-8120-15b13e70b377.xml`
- 榮耀華爾街: `https://feeds.soundon.fm/podcasts/35eb55b5-8669-418b-9a08-dc13c482809a.xml`

The 摩爾證券投顧 feed is not 郭哲榮-only. Filter with:

- title includes `郭哲榮`, `哲榮`, or `哲哲`;
- description/keywords includes known 郭哲榮 links or labels;
- title starts with `郭哲榮分析師`;
- reject episodes clearly centered on other analysts unless 郭哲榮 appears as a meaningful co-mention.

The 榮耀華爾街 feed is authored by `郭哲榮 投資長`; keep the full feed, including short 60-second clips, and use duration/title to distinguish short clips from long commentary.

## Audio Policy

- Store MP3 URLs for every filtered episode.
- Download only when ASR is requested or when a transcript is missing and needed.
- Delete local MP3 after ASR by default while keeping hash, URL, raw ASR JSON, and transcript. Use `--keep-audio` only for debugging.

## Market Alignment

Most Moore podcast releases are after Taiwan cash close. For Taiwan-focused calls:

- if published at or after 13:35 Asia/Taipei, align Taiwan market to same-date close;
- if published before 13:35 or on a non-trading day, use nearest prior close;
- US assets use nearest close on or before the local publication date, which effectively maps to prior US session for after-Taiwan-close content.

Always label broad index context separately from mentioned-asset context.
