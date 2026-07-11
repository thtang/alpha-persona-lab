#!/usr/bin/env python3
"""
Transcribe videos that have no YouTube subtitle file.

The script downloads one audio file at a time, runs MLX Whisper, writes a VTT
file compatible with build_corpus.py, and removes the audio by default. It is
safe to rerun: videos with any existing subtitle file are skipped.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import mlx_whisper


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = DATA / "source"
SUBTITLES = DATA / "subtitles"
AUDIO = DATA / "audio"
LOGS = DATA / "logs"
METADATA_FILE = SOURCE / "youtube_flat_all.jsonl"

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
YTDLP_FORMATS = [
    "bestaudio[ext=m4a]/bestaudio",
    "18/best[ext=mp4][height<=360]/best[height<=360]/best",
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


def normalize_lang(language: str | None) -> str:
    lang = (language or "").lower()
    if lang.startswith("zh") or lang in {"chinese", "mandarin"}:
        return "zh"
    if lang.startswith("en") or lang == "english":
        return "en"
    return "en"


def format_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def segments_to_vtt(segments: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for idx, segment in enumerate(segments, start=1):
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        lines.extend(
            [
                str(idx),
                f"{format_timestamp(float(segment['start']))} --> {format_timestamp(float(segment['end']))}",
                text.replace("\n", " "),
                "",
            ]
        )
    return "\n".join(lines)


def output_path(video: dict, lang: str) -> Path:
    index = video.get("playlist_index") or 0
    video_id = video["id"]
    return SUBTITLES / f"{index:03d}-{video_id}-{safe_title(video.get('title') or '')}.{lang}.vtt"


def video_url(video: dict) -> str:
    return video.get("webpage_url") or f"https://www.youtube.com/watch?v={video['id']}"


def find_audio(video_id: str) -> Path | None:
    matches = sorted(AUDIO.glob(f"{video_id}.*"))
    return matches[0] if matches else None


def clear_audio(video_id: str) -> None:
    for path in AUDIO.glob(f"{video_id}.*"):
        path.unlink(missing_ok=True)


def run_ytdlp(video: dict, sleep_requests: float, format_selector: str) -> None:
    cmd = [
        str(ROOT.parent / ".venv" / "bin" / "yt-dlp"),
        "--quiet",
        "--no-progress",
        "--no-warnings",
        "--no-playlist",
        "-f",
        format_selector,
        "--sleep-requests",
        str(sleep_requests),
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        "-o",
        str(AUDIO / "%(id)s.%(ext)s"),
        video_url(video),
    ]
    subprocess.run(cmd, check=True)


def download_audio(video: dict, sleep_requests: float) -> Path:
    last_error: subprocess.CalledProcessError | None = None
    for format_selector in YTDLP_FORMATS:
        clear_audio(video["id"])
        try:
            run_ytdlp(video, sleep_requests, format_selector)
            existing = find_audio(video["id"])
            if existing:
                return existing
        except subprocess.CalledProcessError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError(f"yt-dlp completed but no audio file found for {video['id']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sleep-requests", type=float, default=3.0)
    parser.add_argument("--keep-audio", action="store_true")
    args = parser.parse_args()

    for path in (SUBTITLES, AUDIO, LOGS):
        path.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = ROOT / "bin"
    os.environ["PATH"] = str(ffmpeg_bin) + os.pathsep + os.environ.get("PATH", "")

    videos = load_videos()
    existing = subtitle_video_ids()
    pending = [video for video in videos if video["id"] not in existing]
    if args.limit:
        pending = pending[: args.limit]

    run_log = LOGS / f"asr_internal_{time.strftime('%Y%m%d_%H%M%S')}.log"
    manifest_path = SOURCE / "asr_manifest.jsonl"

    print(
        f"videos={len(videos)} existing_subtitle_videos={len(existing)} pending={len(pending)} model={args.model}",
        flush=True,
    )

    completed = 0
    failed = 0
    started_at = time.time()

    with run_log.open("a", encoding="utf-8") as internal_log, manifest_path.open("a", encoding="utf-8") as manifest:
        for offset, video in enumerate(pending, start=1):
            video_id = video["id"]
            item_started = time.time()
            audio_path: Path | None = None
            try:
                audio_path = find_audio(video_id) or download_audio(video, args.sleep_requests)
                with contextlib.redirect_stdout(internal_log), contextlib.redirect_stderr(internal_log):
                    result = mlx_whisper.transcribe(
                        str(audio_path),
                        path_or_hf_repo=args.model,
                        verbose=False,
                    )
                lang = normalize_lang(result.get("language"))
                out = output_path(video, lang)
                out.write_text(segments_to_vtt(result.get("segments") or []), encoding="utf-8")
                elapsed = time.time() - item_started
                record = {
                    "status": "ok",
                    "playlist_index": video.get("playlist_index"),
                    "video_id": video_id,
                    "language": result.get("language"),
                    "normalized_language": lang,
                    "duration": video.get("duration"),
                    "elapsed_seconds": round(elapsed, 2),
                    "subtitle_path": str(out.relative_to(ROOT)),
                }
                manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                manifest.flush()
                completed += 1
                print(f"[{offset}/{len(pending)}] ok {video_id} lang={lang} elapsed={elapsed:.1f}s", flush=True)
            except Exception as exc:
                elapsed = time.time() - item_started
                record = {
                    "status": "error",
                    "playlist_index": video.get("playlist_index"),
                    "video_id": video_id,
                    "title": video.get("title") or "",
                    "url": video_url(video),
                    "elapsed_seconds": round(elapsed, 2),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                manifest.flush()
                failed += 1
                print(f"[{offset}/{len(pending)}] error {video_id} {type(exc).__name__}: {exc}", flush=True)
            finally:
                if audio_path and audio_path.exists() and not args.keep_audio:
                    audio_path.unlink()

    summary = {
        "completed": completed,
        "failed": failed,
        "elapsed_seconds": round(time.time() - started_at, 2),
        "model": args.model,
        "internal_log": str(run_log.relative_to(ROOT)),
        "manifest": str(manifest_path.relative_to(ROOT)),
    }
    (SOURCE / "asr_fetch_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    sys.exit(main())
