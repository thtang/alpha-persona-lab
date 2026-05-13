#!/usr/bin/env python3
"""Transcribe pending Zhezhe podcast audio with mlx-whisper.

The script reads data/audio_manifest.jsonl, finds filtered 郭哲榮 episodes whose
ASR status is not done, downloads missing audio when allowed, stores raw ASR
JSON plus a readable Markdown transcript, and updates the manifest in place.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = DATA / "audio_manifest.jsonl"
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path} line {lineno}: {exc}") from exc
        if not isinstance(item, dict):
            raise SystemExit(f"Invalid manifest row in {path} line {lineno}: expected object")
        rows.append(item)
    return rows


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        for row in rows:
            tmp.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            tmp.write("\n")
    tmp_path.replace(path)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def episode_id(row: dict[str, Any]) -> str:
    for key in ("episode_id", "id", "guid"):
        value = row.get(key)
        if value:
            return str(value)
    raise ValueError(f"Manifest row has no episode_id/id/guid: {row}")


def transcript_exists(row: dict[str, Any], eid: str) -> bool:
    value = row.get("transcript_path")
    if value:
        path = Path(str(value))
        path = path if path.is_absolute() else ROOT / path
        if path.exists():
            return True
    return any((DATA / "transcripts").glob(f"*_{eid}.md"))


def episode_date(row: dict[str, Any]) -> str:
    for key in ("date", "local_date", "published_date", "published_at", "pub_date", "pubDate", "pub_date_utc"):
        value = row.get(key)
        if not value:
            continue
        text = str(value)
        if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
            return text[:10]
    return "unknown-date"


def is_filtered_zhezhe(row: dict[str, Any]) -> bool:
    values = [
        row.get("is_zhezhe"),
        row.get("is_zhezhe_episode"),
        row.get("zhezhe"),
        row.get("filtered"),
        row.get("is_filtered"),
        row.get("filter_score"),
        row.get("speaker"),
        row.get("analyst"),
        row.get("creator"),
        row.get("source_kind"),
        row.get("kind"),
    ]
    eid = str(row.get("episode_id") or "")
    joined = " ".join(str(value) for value in values if value is not None).lower()
    title_desc = " ".join(
        str(row.get(key) or "") for key in ("title", "description", "description_text", "summary", "keywords")
    )
    if any(value is True for value in values):
        return True
    if eid.startswith("zhezhe-"):
        return True
    if "zhezhe" in joined or "郭哲榮" in title_desc or "哲哲" in title_desc:
        return True
    if str(row.get("source_file") or "").endswith("zhezhe_episodes.jsonl"):
        return True
    return False


def done_ids_from_status(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    done: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("episode_id") and item.get("asr_status") == "done":
            done.add(str(item["episode_id"]))
    return done


def pending_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[tuple[int, dict[str, Any]]]:
    done_ids = done_ids_from_status(args.status_jsonl)
    pending: list[tuple[int, dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        try:
            eid = episode_id(row)
        except ValueError:
            continue
        if args.shard_count > 1 and idx % args.shard_count != args.shard_index:
            continue
        if args.episode_id and eid != args.episode_id:
            continue
        if not is_filtered_zhezhe(row):
            continue
        if not args.force and eid in done_ids:
            continue
        if not args.force and str(row.get("asr_status") or "").lower() == "done":
            continue
        if not args.force and transcript_exists(row, eid):
            continue
        pending.append((idx, row))
    return pending[: args.limit] if args.limit is not None else pending


def local_audio_path(row: dict[str, Any], eid: str) -> Path:
    for key in ("audio_path", "local_audio_path", "downloaded_audio_path"):
        value = row.get(key)
        if value:
            path = Path(str(value))
            return path if path.is_absolute() else ROOT / path
    return DATA / "audio" / f"{eid}.mp3"


def audio_url(row: dict[str, Any]) -> str | None:
    for key in ("audio_url", "enclosure_url", "mp3_url", "media_url", "url"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def download_audio(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "zhezhe-skill-asr/1.0"})
    try:
        with urlopen(request, timeout=120) as response, tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, delete=False
        ) as tmp:
            tmp_path = Path(tmp.name)
            shutil.copyfileobj(response, tmp)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Failed to download audio from {url}: {exc}") from exc
    tmp_path.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    ffmpeg_link = bin_dir / "ffmpeg"
    if not ffmpeg_link.exists():
        try:
            ffmpeg_link.symlink_to(ffmpeg_path)
        except OSError:
            shutil.copy2(ffmpeg_path, ffmpeg_link)
            ffmpeg_link.chmod(0o755)
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def try_python_api(audio_path: Path, model: str) -> dict[str, Any] | None:
    try:
        mlx_whisper = importlib.import_module("mlx_whisper")
    except ImportError:
        return None
    result = mlx_whisper.transcribe(str(audio_path), path_or_hf_repo=model, language="zh")
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
            if completed.returncode != 0:
                errors.append(
                    f"command: {' '.join(cmd)}\n"
                    f"stdout: {completed.stdout.strip()}\n"
                    f"stderr: {completed.stderr.strip()}"
                )
                continue
            json_files = sorted(output_dir.glob("*.json"))
            if json_files:
                return json.loads(json_files[0].read_text(encoding="utf-8"))
            try:
                result = json.loads(completed.stdout)
            except json.JSONDecodeError:
                errors.append(f"command produced no JSON file/stdout: {' '.join(cmd)}")
                continue
            if isinstance(result, dict):
                return result
            errors.append(f"command returned non-object JSON: {' '.join(cmd)}")
        raise RuntimeError("mlx-whisper CLI failed\n" + "\n\n".join(errors))


def transcribe(audio_path: Path, model: str) -> dict[str, Any]:
    ensure_ffmpeg_on_path()
    result = try_python_api(audio_path, model)
    if result is not None:
        return result
    result = try_cli(audio_path, model)
    if result is not None:
        return result
    raise RuntimeError(
        "mlx-whisper is not available. Install it first, for example:\n"
        "  pip install mlx-whisper\n"
        "or make the mlx-whisper CLI available on PATH."
    )


def segment_timestamp(seconds: Any) -> str:
    try:
        total = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        total = 0
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def markdown_transcript(row: dict[str, Any], eid: str, model: str, result: dict[str, Any]) -> str:
    title = str(row.get("title") or eid)
    date = episode_date(row)
    source_url = str(row.get("source_url") or row.get("player_url") or row.get("link") or "")
    lines = [
        "---",
        f"episode_id: {eid}",
        f"date: {date}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"asr_model: {model}",
        f"asr_at: {utc_now()}",
    ]
    if source_url:
        lines.append(f"source_url: {json.dumps(source_url, ensure_ascii=False)}")
    lines.extend(["---", "", f"# {title}", ""])
    segments = result.get("segments")
    if isinstance(segments, list) and segments:
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            text = str(segment.get("text") or "").strip()
            if not text:
                continue
            lines.append(f"[{segment_timestamp(segment.get('start'))}] {text}")
    else:
        text = str(result.get("text") or "").strip()
        if text:
            lines.append(text)
    lines.append("")
    return "\n".join(lines)


def update_row(row: dict[str, Any], eid: str, audio_path: Path, model: str, transcript_path: Path) -> None:
    row["asr_status"] = "done"
    row.pop("asr_error", None)
    row["transcript_path"] = str(transcript_path.relative_to(ROOT))
    row["asr_model"] = model
    row["asr_at"] = utc_now()
    row["audio_sha256"] = sha256_file(audio_path)
    row["audio_path"] = str(audio_path.relative_to(ROOT))


def status_snapshot(row: dict[str, Any], eid: str) -> dict[str, Any]:
    keys = [
        "episode_id",
        "asr_status",
        "asr_error",
        "asr_model",
        "asr_at",
        "transcript_path",
        "audio_sha256",
        "audio_path",
        "title",
        "local_date",
        "podcast_id",
        "channel_title",
        "player_url",
        "audio_url",
    ]
    snapshot = {key: row.get(key) for key in keys if row.get(key) not in (None, "")}
    snapshot.setdefault("episode_id", eid)
    return snapshot


def process_one(row: dict[str, Any], args: argparse.Namespace) -> None:
    eid = episode_id(row)
    audio_path = local_audio_path(row, eid)
    if not audio_path.exists():
        url = audio_url(row)
        if not url:
            raise RuntimeError(f"{eid}: audio file is missing and manifest has no audio_url")
        eprint(f"{eid}: downloading audio")
        download_audio(url, audio_path)

    try:
        eprint(f"{eid}: transcribing with {args.model}")
        result = transcribe(audio_path, args.model)

        raw_path = DATA / "asr" / "raw" / f"{eid}.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        transcript_path = DATA / "transcripts" / f"{episode_date(row)}_{eid}.md"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(markdown_transcript(row, eid, args.model, result), encoding="utf-8")

        update_row(row, eid, audio_path, args.model, transcript_path)
        eprint(f"{eid}: wrote {transcript_path.relative_to(ROOT)}")
    finally:
        if not args.keep_audio:
            audio_path.unlink(missing_ok=True)
            row.pop("audio_path", None)
            eprint(f"{eid}: removed local audio")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-id", help="Transcribe only this episode id.")
    parser.add_argument("--limit", type=int, help="Maximum episodes to process.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--download-audio",
        action="store_true",
        help="Download missing audio before ASR. Missing audio is downloaded by default when audio_url exists.",
    )
    parser.add_argument("--keep-audio", action="store_true", help="Keep audio downloaded during this run.")
    parser.add_argument("--force", action="store_true", help="Re-transcribe rows whose asr_status is done.")
    parser.add_argument("--shard-index", type=int, default=0, help="Zero-based shard index for parallel ASR.")
    parser.add_argument("--shard-count", type=int, default=1, help="Total shard count for parallel ASR.")
    parser.add_argument("--status-jsonl", type=Path, help="Per-shard status file for merge/resume.")
    parser.add_argument("--no-manifest-update", action="store_true", help="Do not write shared audio_manifest.jsonl.")
    args = parser.parse_args()
    if args.shard_count < 1:
        raise SystemExit("--shard-count must be >= 1")
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        raise SystemExit("--shard-index must be between 0 and shard-count - 1")

    rows = read_jsonl(MANIFEST)
    if not rows:
        eprint(f"No audio manifest found at {MANIFEST.relative_to(ROOT)}. Run source sync first.")
        return 1

    targets = pending_rows(rows, args)
    if not targets:
        eprint("No pending filtered Zhezhe episodes found.")
        return 0

    failures = 0
    for idx, row in targets:
        eid = "unknown"
        try:
            eid = episode_id(row)
            process_one(row, args)
            if args.status_jsonl:
                append_jsonl(args.status_jsonl, status_snapshot(row, eid))
        except Exception as exc:  # noqa: BLE001 - command-line batch tool should keep reporting rows.
            failures += 1
            row["asr_status"] = "error"
            row["asr_error"] = str(exc)
            row["asr_at"] = utc_now()
            if args.status_jsonl:
                append_jsonl(args.status_jsonl, status_snapshot(row, eid))
            try:
                eprint(f"{episode_id(row)}: ERROR: {exc}")
            except ValueError:
                eprint(f"manifest row {idx}: ERROR: {exc}")
    if not args.no_manifest_update:
        write_jsonl_atomic(MANIFEST, rows)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
