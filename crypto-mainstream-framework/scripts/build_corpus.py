#!/usr/bin/env python3
"""
Build a local Bonnie Blockchain corpus from yt-dlp metadata and subtitles.

Inputs:
  data/source/youtube_flat_all.jsonl
  data/subtitles/*.vtt or *.srt

Outputs:
  data/transcripts/*.md
  data/source/videos.csv
  data/source/corpus_manifest.json
"""

from __future__ import annotations

import csv
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = DATA / "source"
SUBTITLES = DATA / "subtitles"
TRANSCRIPTS = DATA / "transcripts"

METADATA_FILE = SOURCE / "youtube_flat_all.jsonl"

LANG_PRIORITY = [
    "zh-Hant",
    "zh-Hans",
    "zh",
    "zh-TW",
    "zh-CN",
    "en-orig",
    "en",
]

TOPIC_PATTERNS = {
    "bitcoin": r"(?i)\bbitcoin\b|\bbtc\b|比特幣|比特币",
    "stablecoin": r"(?i)stablecoin|stablecoins|穩定幣|稳定币|USDT|USDC|GENIUS",
    "institutional": r"(?i)institution|institutions|ETF|ETP|BlackRock|Franklin|MSTR|MicroStrategy|Saylor|機構|机构|貝萊德|贝莱德",
    "tokenization": r"(?i)tokenization|tokenized|token|on-chain|on chain|鏈上|链上|代幣化|代币化",
    "security": r"(?i)cold wallet|wallet|hack|security|custody|冷錢包|冷钱包|駭客|黑客|安全|託管|托管",
    "macro": r"(?i)dollar|money printing|inflation|rate|fed|treasury|美元|印鈔|印钞|通膨|通胀|利率|美債|美债|聯準會|联准会",
    "trading": r"(?i)cycle|bull|bear|DCA|price|market|牛市|熊市|週期|周期|定投|價格|价格|市場|市场",
}


def load_videos() -> list[dict]:
    videos = []
    with METADATA_FILE.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            videos.append(
                {
                    "playlist_index": item.get("playlist_index"),
                    "id": item["id"],
                    "title": item.get("title") or "",
                    "duration": item.get("duration"),
                    "duration_string": item.get("duration_string") or "",
                    "url": item.get("webpage_url") or f"https://www.youtube.com/watch?v={item['id']}",
                }
            )
    return videos


def parse_subtitle_name(path: Path) -> tuple[str, str] | None:
    # yt-dlp output: 012-videoid-title.zh-Hant.vtt
    match = re.match(
        r"^\d{3}-([A-Za-z0-9_-]{11})-.*\.(zh-Hant|zh-Hans|zh|zh-TW|zh-CN|en-orig|en)\.(?:vtt|srt)$",
        path.name,
    )
    if not match:
        return None
    return match.group(1), match.group(2)


def clean_subtitle_text(raw: str) -> str:
    raw = raw.replace("\ufeff", "")
    raw = re.sub(r"^WEBVTT.*?(?:\n\n|\r\n\r\n)", "", raw, flags=re.DOTALL)
    raw = re.sub(r"(?ms)^NOTE\b.*?(?:\n\n|\Z)", "", raw)
    raw = re.sub(r"(?ms)^STYLE\b.*?(?:\n\n|\Z)", "", raw)

    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if "-->" in line:
            continue
        if re.match(r"^[0-9a-fA-F-]{8,}$", line):
            continue
        line = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", line)
        line = re.sub(r"</?c(?:\.[^>]*)?>", "", line)
        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line).strip()
        if line:
            lines.append(line)

    deduped: list[str] = []
    for line in lines:
        if deduped and line == deduped[-1]:
            continue
        # Auto captions sometimes emit a short partial line followed by a fuller one.
        if deduped and line.startswith(deduped[-1]) and len(line) - len(deduped[-1]) < 80:
            deduped[-1] = line
            continue
        if deduped and deduped[-1].startswith(line) and len(deduped[-1]) - len(line) < 80:
            continue
        deduped.append(line)

    paragraphs: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in deduped:
        current.append(line)
        current_len += len(line)
        if current_len >= 900 or re.search(r"[。！？!?]\s*$", line):
            paragraphs.append(" ".join(current))
            current = []
            current_len = 0
    if current:
        paragraphs.append(" ".join(current))

    return "\n\n".join(paragraphs).strip()


def topic_tags(title: str, transcript: str = "") -> list[str]:
    haystack = f"{title}\n{transcript[:5000]}"
    tags = [name for name, pattern in TOPIC_PATTERNS.items() if re.search(pattern, haystack)]
    return tags or ["general"]


def safe_filename(index: int | None, video_id: str) -> str:
    prefix = f"{index:03d}" if isinstance(index, int) else "000"
    return f"{prefix}-{video_id}.md"


def choose_subtitles() -> dict[str, tuple[str, Path]]:
    by_video: dict[str, dict[str, Path]] = defaultdict(dict)
    for path in SUBTITLES.glob("*"):
        if path.suffix.lower() not in {".vtt", ".srt"}:
            continue
        parsed = parse_subtitle_name(path)
        if not parsed:
            continue
        video_id, lang = parsed
        by_video[video_id][lang] = path

    selected = {}
    for video_id, lang_map in by_video.items():
        for lang in LANG_PRIORITY:
            if lang in lang_map:
                selected[video_id] = (lang, lang_map[lang])
                break
    return selected


def write_videos_csv(videos: list[dict], selected: dict[str, tuple[str, Path]], tags_by_id: dict[str, list[str]]) -> None:
    out = SOURCE / "videos.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "playlist_index",
                "video_id",
                "title",
                "duration_string",
                "url",
                "has_transcript",
                "subtitle_language",
                "topic_tags",
            ],
        )
        writer.writeheader()
        for video in videos:
            video_id = video["id"]
            lang = selected.get(video_id, ("", Path()))[0]
            writer.writerow(
                {
                    "playlist_index": video["playlist_index"],
                    "video_id": video_id,
                    "title": video["title"],
                    "duration_string": video["duration_string"],
                    "url": video["url"],
                    "has_transcript": "yes" if video_id in selected else "no",
                    "subtitle_language": lang,
                    "topic_tags": "|".join(tags_by_id.get(video_id, [])),
                }
            )


def main() -> None:
    if not METADATA_FILE.exists():
        raise SystemExit(f"Missing metadata file: {METADATA_FILE}")

    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)

    videos = load_videos()
    video_by_id = {video["id"]: video for video in videos}
    selected = choose_subtitles()

    built = []
    tags_by_id: dict[str, list[str]] = {}
    language_counts = Counter()
    topic_counts = Counter()

    for video_id, (lang, subtitle_path) in sorted(
        selected.items(), key=lambda item: video_by_id.get(item[0], {}).get("playlist_index") or 999999
    ):
        video = video_by_id.get(video_id)
        if not video:
            continue
        raw = subtitle_path.read_text(encoding="utf-8", errors="ignore")
        transcript = clean_subtitle_text(raw)
        tags = topic_tags(video["title"], transcript)
        tags_by_id[video_id] = tags
        for tag in tags:
            topic_counts[tag] += 1
        language_counts[lang] += 1

        out_path = TRANSCRIPTS / safe_filename(video.get("playlist_index"), video_id)
        body = [
            "---",
            f"video_id: {video_id}",
            f"playlist_index: {video.get('playlist_index')}",
            f"title: {json.dumps(video['title'], ensure_ascii=False)}",
            f"url: {video['url']}",
            f"duration_string: {video.get('duration_string')}",
            f"subtitle_language: {lang}",
            f"subtitle_file: {subtitle_path.relative_to(ROOT)}",
            f"topic_tags: {json.dumps(tags, ensure_ascii=False)}",
            "---",
            "",
            f"# {video['title']}",
            "",
            transcript,
            "",
        ]
        out_path.write_text("\n".join(body), encoding="utf-8")
        built.append(str(out_path.relative_to(ROOT)))

    for video in videos:
        if video["id"] not in tags_by_id:
            tags_by_id[video["id"]] = topic_tags(video["title"])
            for tag in tags_by_id[video["id"]]:
                topic_counts[tag] += 1

    write_videos_csv(videos, selected, tags_by_id)

    missing = [
        {
            "playlist_index": video.get("playlist_index"),
            "video_id": video["id"],
            "title": video["title"],
            "url": video["url"],
        }
        for video in videos
        if video["id"] not in selected
    ]

    manifest = {
        "channel": "邦妮區塊鏈 Bonnie Blockchain",
        "channel_url": "https://www.youtube.com/@BonnieBlockchain",
        "channel_id": "UCjlPLMYEsq0pjgLL1q24mSg",
        "videos_total": len(videos),
        "subtitle_files_total": len(list(SUBTITLES.glob("*.*"))),
        "transcripts_built": len(built),
        "missing_transcripts": len(missing),
        "language_counts": dict(language_counts),
        "topic_counts": dict(topic_counts),
        "built_files": built,
        "missing": missing,
    }
    (SOURCE / "corpus_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Videos: {len(videos)}")
    print(f"Transcripts built: {len(built)}")
    print(f"Missing transcripts: {len(missing)}")
    print(f"Manifest: {SOURCE / 'corpus_manifest.json'}")


if __name__ == "__main__":
    main()
