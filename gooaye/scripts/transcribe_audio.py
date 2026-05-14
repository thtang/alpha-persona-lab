#!/usr/bin/env python3
"""Transcribe missing Gooaye SoundOn episodes with mlx-whisper."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
USER_AGENT = "gooaye-skill-asr/1.0"
INITIAL_PROMPT = (
    "以下是台灣財經 Podcast 股癌 Gooaye 的繁體中文逐字稿。常見詞包含台積電、聯發科、"
    "國巨、被動元件、ASIC、CoWoS、AI、輝達、AMD、Palantir、ETF、Q&A。"
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def episode_number(row: dict[str, Any]) -> int:
    return int(row["number"])


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_ffmpeg_on_path(data_dir: Path) -> None:
    if shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg  # type: ignore
    except Exception as exc:  # noqa: BLE001 - surface a useful setup error.
        raise RuntimeError("ffmpeg is not on PATH and imageio_ffmpeg is unavailable") from exc

    ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
    bin_dir = data_dir / ".runtime" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    link_path = bin_dir / "ffmpeg"
    if not link_path.exists():
        try:
            link_path.symlink_to(ffmpeg_path)
        except OSError:
            shutil.copy2(ffmpeg_path, link_path)
            link_path.chmod(0o755)
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def download_audio(url: str, path: Path, retries: int = 3, timeout: int = 120) -> dict[str, Any]:
    last_error: Exception | None = None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as response:
                data = response.read()
            tmp_path.write_bytes(data)
            tmp_path.replace(path)
            return {"bytes": len(data), "sha256": sha256_bytes(data)}
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(3 * attempt, 12))
    raise RuntimeError(f"failed to download audio: {last_error}")


def format_timestamp(value: float | int | None) -> str:
    total = int(value or 0)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def markdown_transcript(row: dict[str, Any], result: dict[str, Any], model: str) -> str:
    title = row.get("display_title") or row.get("title") or f"EP{episode_number(row):03d}"
    lines = [
        f"# EP{episode_number(row):03d} {title}",
        "",
        "> Source: SoundOn RSS audio ASR fallback.",
        f"> Episode date: {row.get('date') or 'unknown'}",
        f"> Source URL: {row.get('player_url') or row.get('audio_url') or 'unknown'}",
        f"> ASR model: {model}",
        "> Note: This transcript is machine-generated and should be spot-checked before quoting.",
        "",
    ]
    description_text = (row.get("description_text") or "").strip()
    if description_text:
        lines.extend(["## Episode Metadata", "", description_text, ""])

    lines.extend(["## Transcript", ""])
    segments = result.get("segments") or []
    if segments:
        for segment in segments:
            text = re.sub(r"\s+", " ", str(segment.get("text") or "")).strip()
            if not text:
                continue
            lines.append(f"[{format_timestamp(segment.get('start'))}] {text}")
    else:
        text = re.sub(r"\s+", " ", str(result.get("text") or "")).strip()
        if text:
            lines.append(text)
    return "\n".join(lines).rstrip() + "\n"


def upsert_records(records: list[dict[str, Any]], row: dict[str, Any]) -> list[dict[str, Any]]:
    number = episode_number(row)
    by_number = {int(record["number"]): record for record in records}
    by_number[number] = row
    return [by_number[key] for key in sorted(by_number)]


def update_transcripts_manifest(data_dir: Path, row: dict[str, Any], transcript_text: str, model: str) -> None:
    manifest_path = data_dir / "transcripts_manifest.json"
    manifest: dict[str, Any]
    if manifest_path.exists():
        manifest = read_json(manifest_path)
    else:
        manifest = {"source": "mixed", "records": [], "errors": []}

    number = episode_number(row)
    record = {
        "number": number,
        "date": row.get("date"),
        "title": row.get("title"),
        "display_title": row.get("display_title") or row.get("title"),
        "summary": row.get("summary"),
        "source_filename": f"soundon:{row.get('guid') or number}",
        "source_url": row.get("player_url") or row.get("audio_url"),
        "local_path": f"transcripts/EP{number:03d}.md",
        "bytes": len(transcript_text.encode("utf-8")),
        "sha256": sha256_text(transcript_text),
        "status": "asr",
        "transcript_source": "soundon_asr",
        "audio_url": row.get("audio_url"),
        "guid": row.get("guid"),
        "asr_model": model,
        "asr_at": now_utc(),
    }
    manifest["records"] = upsert_records(manifest.get("records", []), record)
    manifest["stored_count"] = len(manifest["records"])
    manifest["episode_count"] = max(int(manifest.get("episode_count") or 0), len(manifest["records"]))
    manifest["selected_count"] = max(int(manifest.get("selected_count") or 0), len(manifest["records"]))
    manifest["fetched_at"] = now_utc()
    manifest.setdefault("errors", [])
    write_json(manifest_path, manifest)
    write_jsonl(data_dir / "transcripts_index.jsonl", manifest["records"])


def episode_source_record(row: dict[str, Any]) -> dict[str, Any]:
    number = episode_number(row)
    date = row.get("date")
    parsed_date = None
    if date:
        try:
            parsed_date = datetime.fromisoformat(str(date))
        except ValueError:
            parsed_date = None
    title = row.get("display_title") or row.get("title") or f"EP{number:03d}"
    record: dict[str, Any] = {
        "number": number,
        "title": title,
        "filename": f"EP{number:03d}_soundon_asr.md",
        "description": row.get("description_text") or row.get("description") or "",
        "display_title": title,
        "summary": row.get("summary"),
        "date": date,
        "source": "soundon_asr",
        "source_url": row.get("player_url") or row.get("audio_url"),
        "audio_url": row.get("audio_url"),
        "guid": row.get("guid"),
    }
    if parsed_date:
        record.update(
            {
                "year": parsed_date.year,
                "month": parsed_date.month,
                "day": parsed_date.day,
                "month_name": parsed_date.strftime("%B"),
                "date_display": parsed_date.strftime("%b %d, %Y"),
                "date_short": parsed_date.strftime("%b %Y"),
            }
        )
    return record


def update_source_episodes(data_dir: Path, row: dict[str, Any]) -> None:
    path = data_dir / "source" / "episodes.json"
    episodes: list[dict[str, Any]] = read_json(path) if path.exists() else []
    by_number = {int(item["number"]): item for item in episodes if item.get("number") is not None}
    number = episode_number(row)
    existing = by_number.get(number, {})
    if existing.get("source") != "soundon_asr":
        merged = {**existing, **episode_source_record(row)}
    else:
        merged = {**existing, **episode_source_record(row)}
    by_number[number] = merged
    write_json(path, [by_number[key] for key in sorted(by_number)])


def update_audio_manifest(data_dir: Path, target_row: dict[str, Any]) -> None:
    manifest_path = data_dir / "audio_manifest.jsonl"
    rows = read_jsonl(manifest_path)
    by_number = {episode_number(row): row for row in rows}
    by_number[episode_number(target_row)] = target_row
    write_jsonl(manifest_path, [by_number[key] for key in sorted(by_number)])


def pending_rows(data_dir: Path, *, episode: int | None, force: bool) -> list[dict[str, Any]]:
    rows = read_jsonl(data_dir / "audio_manifest.jsonl")
    selected: list[dict[str, Any]] = []
    for row in rows:
        number = episode_number(row)
        if episode is not None and number != episode:
            continue
        transcript_path = data_dir / "transcripts" / f"EP{number:03d}.md"
        if transcript_path.exists() and not force:
            continue
        if not row.get("audio_url"):
            continue
        selected.append(row)
    return sorted(selected, key=episode_number, reverse=True)


def transcribe_one(row: dict[str, Any], data_dir: Path, model: str, keep_audio: bool, force: bool, initial_prompt: str) -> None:
    number = episode_number(row)
    audio_path = data_dir / "audio" / f"EP{number:03d}.mp3"
    transcript_path = data_dir / "transcripts" / f"EP{number:03d}.md"
    raw_path = data_dir / "asr" / "raw" / f"EP{number:03d}.json"
    if transcript_path.exists() and not force:
        row["asr_status"] = "done"
        row["local_transcript_path"] = str(transcript_path.relative_to(data_dir))
        update_audio_manifest(data_dir, row)
        print(f"EP{number:03d} already has a transcript; skipping.", flush=True)
        return

    row["asr_status"] = "running"
    row["asr_started_at"] = now_utc()
    row["asr_model"] = model
    update_audio_manifest(data_dir, row)

    try:
        print(f"Downloading EP{number:03d} audio", flush=True)
        audio_meta = download_audio(str(row["audio_url"]), audio_path)
        row["audio_bytes"] = audio_meta["bytes"]
        row["audio_sha256"] = audio_meta["sha256"]

        ensure_ffmpeg_on_path(data_dir)
        import mlx_whisper  # type: ignore

        print(f"Transcribing EP{number:03d} with {model}", flush=True)
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=model,
            language="zh",
            initial_prompt=initial_prompt or None,
            word_timestamps=False,
        )
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            raw_path,
            {
                "episode": number,
                "source": row,
                "model": model,
                "created_at": now_utc(),
                "result": result,
            },
        )

        transcript_text = markdown_transcript(row, result, model)
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(transcript_text, encoding="utf-8")
        update_transcripts_manifest(data_dir, row, transcript_text, model)
        update_source_episodes(data_dir, row)

        row["asr_status"] = "done"
        row["asr_completed_at"] = now_utc()
        row["local_transcript_path"] = str(transcript_path.relative_to(data_dir))
        row["raw_asr_path"] = str(raw_path.relative_to(data_dir))
        row.pop("asr_error", None)
        print(f"EP{number:03d} transcript stored at {transcript_path}", flush=True)
    except Exception as exc:  # noqa: BLE001 - preserve the failed episode and continue batch.
        row["asr_status"] = "error"
        row["asr_error"] = str(exc)
        row["asr_failed_at"] = now_utc()
        print(f"EP{number:03d} ASR failed: {exc}", file=sys.stderr, flush=True)
        raise
    finally:
        if audio_path.exists() and not keep_audio:
            audio_path.unlink()
            print(f"Deleted EP{number:03d} audio after ASR", flush=True)
        update_audio_manifest(data_dir, row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe missing Gooaye SoundOn episodes with mlx-whisper.")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--episode", type=int, default=None, help="only transcribe one episode number")
    parser.add_argument("--limit", type=int, default=1, help="transcribe at most N newest pending episodes; 0 means all")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--force", action="store_true", help="overwrite existing transcript files")
    parser.add_argument("--keep-audio", action="store_true", help="keep downloaded MP3 files after transcription")
    parser.add_argument("--initial-prompt", default=INITIAL_PROMPT)
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    rows = pending_rows(data_dir, episode=args.episode, force=args.force)
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("No pending Gooaye SoundOn episodes require ASR.", flush=True)
        return 0

    for row in rows:
        transcribe_one(row, data_dir, args.model, args.keep_audio, args.force, args.initial_prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
