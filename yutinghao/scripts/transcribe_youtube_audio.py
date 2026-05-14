#!/usr/bin/env python3
"""Transcribe the newest missing Yu Ting-Hao YouTube episode with mlx-whisper."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
INITIAL_PROMPT = (
    "以下是台灣財經節目《游庭皓的財經皓角》早晨財經速解讀的繁體中文逐字稿。"
    "常見詞包含台積電、輝達、費半、美債殖利率、美元、台幣、通膨、關稅、AI、記憶體、台韓。"
)


def eprint(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path} line {lineno}: {exc}") from exc
        if isinstance(row, dict):
            rows.append(row)
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        for row in rows:
            tmp.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            tmp.write("\n")
    tmp_path.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def video_date(row: dict[str, Any]) -> str:
    title = str(row.get("title") or "")
    match = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", title)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    for key in ("published", "updated"):
        value = str(row.get(key) or "")
        if len(value) >= 10 and value[4:5] == "-" and value[7:8] == "-":
            return value[:10]
    return "unknown-date"


def transcript_path(row: dict[str, Any]) -> Path:
    return DATA / "transcripts" / f"{video_date(row)}.md"


def manifest_path() -> Path:
    return DATA / "source" / "youtube_audio_manifest.jsonl"


def manifest_by_id() -> dict[str, dict[str, Any]]:
    return {str(row.get("video_id") or ""): row for row in read_jsonl(manifest_path()) if row.get("video_id")}


def upsert_manifest(row: dict[str, Any], status: dict[str, Any]) -> None:
    video_id = str(row.get("video_id") or "")
    rows = read_jsonl(manifest_path())
    kept = [item for item in rows if str(item.get("video_id") or "") != video_id]
    record = {
        "video_id": video_id,
        "date": video_date(row),
        "title": row.get("title"),
        "url": row.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        "published": row.get("published"),
        "updated": row.get("updated"),
        "source": "youtube_audio_asr",
        **status,
    }
    kept.append(record)
    kept.sort(key=lambda item: str(item.get("published") or item.get("date") or ""), reverse=True)
    write_jsonl(manifest_path(), kept)


def load_youtube_rows(data_dir: Path) -> list[dict[str, Any]]:
    path = data_dir / "source" / "youtube_recent.json"
    if not path.exists():
        return []
    rows = read_json(path)
    return [row for row in rows if isinstance(row, dict) and row.get("video_id")] if isinstance(rows, list) else []


def is_done(row: dict[str, Any]) -> bool:
    path = transcript_path(row)
    if path.exists():
        return True
    existing = manifest_by_id().get(str(row.get("video_id") or ""), {})
    value = existing.get("transcript_path")
    if value:
        other_path = Path(str(value))
        other_path = other_path if other_path.is_absolute() else ROOT / other_path
        return other_path.exists()
    return False


def pending_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    existing = manifest_by_id()
    pending: list[dict[str, Any]] = []
    for row in rows:
        video_id = str(row.get("video_id") or "")
        if args.video_id and video_id != args.video_id:
            continue
        if is_done(row) and not args.force:
            status = {
                "asr_status": "done",
                "transcript_path": str(transcript_path(row).relative_to(ROOT)),
            }
            asr_at = existing.get(video_id, {}).get("asr_at")
            if asr_at:
                status["asr_at"] = asr_at
            upsert_manifest(
                row,
                status,
            )
            continue
        status = str(existing.get(video_id, {}).get("asr_status") or "").lower()
        if status == "running" and not args.force:
            continue
        if status == "error" and not (args.retry_errors or args.force):
            continue
        pending.append(row)
    return pending[: args.limit] if args.limit is not None else pending


def ensure_ffmpeg_on_path() -> None:
    if shutil.which("ffmpeg"):
        return
    try:
        imageio_ffmpeg = importlib.import_module("imageio_ffmpeg")
    except ImportError:
        return
    ffmpeg_path = Path(str(imageio_ffmpeg.get_ffmpeg_exe()))
    if not ffmpeg_path.exists():
        return
    bin_dir = DATA / ".runtime" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    link_path = bin_dir / "ffmpeg"
    if not link_path.exists():
        try:
            link_path.symlink_to(ffmpeg_path)
        except OSError:
            shutil.copy2(ffmpeg_path, link_path)
            link_path.chmod(0o755)
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def latest_audio_file(audio_dir: Path, video_id: str) -> Path | None:
    candidates = [
        path
        for path in audio_dir.glob(f"{video_id}.*")
        if path.is_file() and not path.name.endswith((".part", ".ytdl", ".json"))
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def download_with_python_yt_dlp(url: str, outtmpl: str) -> None:
    try:
        yt_dlp = importlib.import_module("yt_dlp")
    except ImportError:
        raise RuntimeError("yt-dlp Python package is not installed") from None
    options = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
    }
    with yt_dlp.YoutubeDL(options) as ydl:  # type: ignore[attr-defined]
        ydl.download([url])


def download_with_cli_yt_dlp(url: str, outtmpl: str) -> None:
    exe = shutil.which("yt-dlp") or shutil.which("youtube-dl")
    if not exe:
        raise RuntimeError("yt-dlp CLI is not installed")
    completed = subprocess.run(
        [exe, "--no-playlist", "-f", "bestaudio/best", "-o", outtmpl, url],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"yt-dlp failed: {completed.stderr.strip() or completed.stdout.strip()}")


def download_audio(row: dict[str, Any]) -> Path:
    video_id = str(row["video_id"])
    url = str(row.get("url") or f"https://www.youtube.com/watch?v={video_id}")
    audio_dir = DATA / "audio" / "youtube"
    audio_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(audio_dir / f"{video_id}.%(ext)s")
    try:
        download_with_python_yt_dlp(url, outtmpl)
    except RuntimeError as python_exc:
        try:
            download_with_cli_yt_dlp(url, outtmpl)
        except RuntimeError as cli_exc:
            raise RuntimeError(
                "Unable to download YouTube audio. Install yt-dlp with "
                "`python3 -m pip install yt-dlp` or make the yt-dlp CLI available. "
                f"Python error: {python_exc}; CLI error: {cli_exc}"
            ) from cli_exc
    audio_path = latest_audio_file(audio_dir, video_id)
    if audio_path is None:
        raise RuntimeError(f"yt-dlp finished but no audio file was found for {video_id}")
    return audio_path


def try_python_api(audio_path: Path, model: str, initial_prompt: str) -> dict[str, Any] | None:
    try:
        mlx_whisper = importlib.import_module("mlx_whisper")
    except ImportError:
        return None
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=model,
        language="zh",
        initial_prompt=initial_prompt or None,
        word_timestamps=False,
    )
    if not isinstance(result, dict):
        raise RuntimeError("mlx_whisper.transcribe returned a non-dict result")
    return result


def try_cli(audio_path: Path, model: str) -> dict[str, Any] | None:
    exe = shutil.which("mlx-whisper") or shutil.which("mlx_whisper")
    if exe is None:
        return None
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        commands = [
            [
                exe,
                str(audio_path),
                "--model",
                model,
                "--language",
                "zh",
                "--output-dir",
                str(output_dir),
                "--output-format",
                "json",
            ],
            [
                exe,
                str(audio_path),
                "--path-or-hf-repo",
                model,
                "--language",
                "zh",
                "--output-dir",
                str(output_dir),
                "--output-format",
                "json",
            ],
        ]
        errors: list[str] = []
        for cmd in commands:
            completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
            if completed.returncode:
                errors.append(completed.stderr.strip() or completed.stdout.strip())
                continue
            json_files = sorted(output_dir.glob("*.json"))
            if json_files:
                return read_json(json_files[0])
            try:
                result = json.loads(completed.stdout)
            except json.JSONDecodeError:
                errors.append("mlx-whisper CLI produced no JSON output")
                continue
            if isinstance(result, dict):
                return result
        raise RuntimeError("mlx-whisper CLI failed: " + " | ".join(errors))


def transcribe(audio_path: Path, model: str, initial_prompt: str) -> dict[str, Any]:
    ensure_ffmpeg_on_path()
    result = try_python_api(audio_path, model, initial_prompt)
    if result is not None:
        return result
    result = try_cli(audio_path, model)
    if result is not None:
        return result
    raise RuntimeError("mlx-whisper is not available. Install mlx-whisper or make its CLI available on PATH.")


def timestamp(seconds: Any) -> str:
    try:
        total = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        total = 0
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def markdown_transcript(row: dict[str, Any], model: str, result: dict[str, Any]) -> str:
    title = str(row.get("title") or row.get("video_id") or "Yu Ting-Hao episode")
    date = video_date(row)
    video_id = str(row.get("video_id") or "")
    url = str(row.get("url") or f"https://www.youtube.com/watch?v={video_id}")
    lines = [
        "---",
        "source: youtube_audio_asr",
        "kind: transcript",
        f"date: {date}",
        f"video_id: {video_id}",
        f"url: {url}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"asr_model: {model}",
        f"asr_at: {utc_now()}",
        "---",
        "",
        f"# 逐字稿：游庭皓的財經皓角 {date}",
        "",
        f"# {title}",
        "",
        "> Source: YouTube audio ASR fallback.",
        "> Note: This transcript is machine-generated and should be spot-checked before quoting.",
        "",
    ]
    chapters = row.get("chapters")
    if isinstance(chapters, list) and chapters:
        lines.extend(["# 章節", ""])
        for item in chapters:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                lines.append(f"- #{item[0]} {item[1]}")
        lines.append("")
    lines.extend(["# Transcript", ""])
    segments = result.get("segments")
    if isinstance(segments, list) and segments:
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            text = re.sub(r"\s+", " ", str(segment.get("text") or "")).strip()
            if text:
                lines.append(f"[{timestamp(segment.get('start'))}] {text}")
    else:
        text = re.sub(r"\s+", " ", str(result.get("text") or "")).strip()
        if text:
            lines.append(text)
    return "\n".join(lines).rstrip() + "\n"


def process_one(row: dict[str, Any], args: argparse.Namespace) -> bool:
    video_id = str(row["video_id"])
    upsert_manifest(row, {"asr_status": "running", "asr_started_at": utc_now(), "asr_model": args.model})
    audio_path: Path | None = None
    try:
        eprint(f"{video_id}: downloading YouTube audio")
        audio_path = download_audio(row)
        audio_sha = sha256_file(audio_path)
        eprint(f"{video_id}: transcribing with {args.model}")
        result = transcribe(audio_path, args.model, args.initial_prompt)

        raw_path = DATA / "asr" / "raw" / f"youtube_{video_id}.json"
        write_json(raw_path, {"video": row, "model": args.model, "created_at": utc_now(), "result": result})

        target_path = transcript_path(row)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(markdown_transcript(row, args.model, result), encoding="utf-8")

        upsert_manifest(
            row,
            {
                "asr_status": "done",
                "asr_model": args.model,
                "asr_at": utc_now(),
                "audio_sha256": audio_sha,
                "transcript_path": str(target_path.relative_to(ROOT)),
                "raw_asr_path": str(raw_path.relative_to(ROOT)),
            },
        )
        eprint(f"{video_id}: wrote {target_path.relative_to(ROOT)}")
        return True
    except Exception as exc:  # noqa: BLE001 - keep batch mode resumable.
        upsert_manifest(
            row,
            {
                "asr_status": "error",
                "asr_error": str(exc),
                "asr_model": args.model,
                "asr_at": utc_now(),
            },
        )
        eprint(f"{video_id}: ERROR: {exc}")
        return False
    finally:
        if audio_path and audio_path.exists() and not args.keep_audio:
            audio_path.unlink(missing_ok=True)
            eprint(f"{video_id}: removed local audio")


def main() -> int:
    global ROOT, DATA

    parser = argparse.ArgumentParser(description="Transcribe missing Yu Ting-Hao YouTube audio with mlx-whisper.")
    parser.add_argument("--skill-dir", type=Path, default=ROOT)
    parser.add_argument("--video-id", help="Transcribe only this YouTube video id.")
    parser.add_argument("--limit", type=int, default=1, help="Maximum newest missing videos to transcribe.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--force", action="store_true", help="Overwrite existing transcript file for the selected video.")
    parser.add_argument("--retry-errors", action="store_true", help="Retry videos previously marked as ASR errors.")
    parser.add_argument("--keep-audio", action="store_true", help="Keep downloaded audio after transcription.")
    parser.add_argument("--initial-prompt", default=INITIAL_PROMPT)
    args = parser.parse_args()

    ROOT = args.skill_dir.resolve()
    DATA = ROOT / "data"

    rows = load_youtube_rows(DATA)
    if not rows:
        eprint("No YouTube RSS rows found. Run crawl_sources.py first.")
        return 1
    targets = pending_rows(rows, args)
    if not targets:
        eprint("No missing Yu Ting-Hao YouTube transcript requires ASR.")
        return 0

    failures = 0
    for row in targets:
        if not process_one(row, args):
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
