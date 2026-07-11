#!/usr/bin/env python3
"""
Fetch YouTube subtitle transcripts through youtube-transcript-api.

This complements yt-dlp: some videos expose captions to the transcript API even
when a long yt-dlp playlist run is rate-limited. Videos with captions disabled
are recorded for a later audio-ASR pass.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = DATA / "source"
SUBTITLES = DATA / "subtitles"
METADATA_FILE = SOURCE / "youtube_flat_all.jsonl"

LANG_PRIORITY = [
    "zh-Hant",
    "zh-Hans",
    "zh",
    "zh-TW",
    "zh-CN",
    "en",
]


def load_videos() -> list[dict]:
    videos = []
    with METADATA_FILE.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                videos.append(json.loads(line))
    return videos


def subtitle_video_ids() -> set[str]:
    ids: set[str] = set()
    for path in SUBTITLES.glob("*"):
        if path.suffix.lower() not in {".vtt", ".srt"}:
            continue
        match = re.match(r"^\d{3}-([A-Za-z0-9_-]{11})-.*\.(?:vtt|srt)$", path.name)
        if match:
            ids.add(match.group(1))
    return ids


def safe_title(title: str) -> str:
    title = re.sub(r"[\\/:*?\"<>|]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:80] or "untitled"


def format_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def snippets_to_vtt(snippets) -> str:
    lines = ["WEBVTT", ""]
    for idx, item in enumerate(snippets, start=1):
        start = float(item.start)
        end = start + float(item.duration or 0.0)
        text = item.text.replace("\n", " ").strip()
        if not text:
            continue
        lines.extend(
            [
                str(idx),
                f"{format_timestamp(start)} --> {format_timestamp(end)}",
                text,
                "",
            ]
        )
    return "\n".join(lines)


def choose_transcript(transcript_list):
    available = list(transcript_list)
    by_lang = {item.language_code: item for item in available}
    for lang in LANG_PRIORITY:
        if lang in by_lang:
            return by_lang[lang]

    manual = [item for item in available if not item.is_generated]
    if manual:
        return manual[0]

    generated = [item for item in available if item.is_generated]
    if generated:
        return generated[0]

    raise NoTranscriptFound("", [], [])


def output_path(video: dict, lang: str) -> Path:
    index = video.get("playlist_index") or 0
    video_id = video["id"]
    title = safe_title(video.get("title") or "")
    return SUBTITLES / f"{index:03d}-{video_id}-{title}.{lang}.vtt"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sleep", type=float, default=1.5)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    SUBTITLES.mkdir(parents=True, exist_ok=True)
    videos = load_videos()
    existing = subtitle_video_ids()
    pending = [video for video in videos if video["id"] not in existing]
    if args.limit:
        pending = pending[: args.limit]

    api = YouTubeTranscriptApi()
    fetched = []
    unavailable = []
    errors = []

    print(f"videos={len(videos)} existing_subtitle_videos={len(existing)} pending={len(pending)}")

    for offset, video in enumerate(pending, start=1):
        video_id = video["id"]
        try:
            transcript = choose_transcript(api.list(video_id))
            snippets = transcript.fetch()
            out = output_path(video, transcript.language_code)
            out.write_text(snippets_to_vtt(snippets), encoding="utf-8")
            fetched.append(
                {
                    "playlist_index": video.get("playlist_index"),
                    "video_id": video_id,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                    "path": str(out.relative_to(ROOT)),
                }
            )
            print(f"[{offset}/{len(pending)}] fetched {video_id} {transcript.language_code}")
        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as exc:
            unavailable.append(
                {
                    "playlist_index": video.get("playlist_index"),
                    "video_id": video_id,
                    "title": video.get("title") or "",
                    "url": video.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}",
                    "reason": type(exc).__name__,
                }
            )
            print(f"[{offset}/{len(pending)}] unavailable {video_id} {type(exc).__name__}")
        except Exception as exc:  # Keep the batch resumable under intermittent API failures.
            errors.append(
                {
                    "playlist_index": video.get("playlist_index"),
                    "video_id": video_id,
                    "title": video.get("title") or "",
                    "url": video.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}",
                    "reason": type(exc).__name__,
                    "message": str(exc),
                }
            )
            print(f"[{offset}/{len(pending)}] error {video_id} {type(exc).__name__}: {exc}")

        if args.sleep:
            time.sleep(args.sleep)

    summary = {
        "videos_total": len(videos),
        "existing_subtitle_videos_before": len(existing),
        "pending_attempted": len(pending),
        "fetched": len(fetched),
        "unavailable": len(unavailable),
        "errors": len(errors),
        "fetched_items": fetched,
        "unavailable_items": unavailable,
        "error_items": errors,
    }
    (SOURCE / "transcript_api_fetch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (SOURCE / "transcript_api_unavailable.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in unavailable),
        encoding="utf-8",
    )
    (SOURCE / "transcript_api_errors.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in errors),
        encoding="utf-8",
    )
    print(json.dumps({k: summary[k] for k in summary if not k.endswith("_items")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
