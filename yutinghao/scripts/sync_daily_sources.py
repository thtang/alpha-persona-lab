#!/usr/bin/env python3
"""Check Yu Ting-Hao public sources once per local day and refresh derived data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_GLOBS = [
    "notes/*.md",
    "transcripts/*.md",
    "official_articles/*.md",
]

SOURCE_FILES = [
    "source/crawl_summary.json",
    "source/digitalgarden_index.json",
    "source/digitalgarden_notes.jsonl",
    "source/digitalgarden_transcripts.jsonl",
    "source/youtube_recent.json",
    "source/official_categories.json",
    "source/official_posts.jsonl",
    "source/official_posts_index.json",
]

DERIVED_FILES = [
    "source/jokes_inventory.jsonl",
    "source/jokes_candidates_raw.jsonl",
    "source/jokes_summary.json",
    "market_context/episode_market_context.jsonl",
    "market_context/episode_market_context.csv",
    "market_context/market_context_manifest.json",
    "market_context/episode_asset_context.jsonl",
    "market_context/episode_asset_context_manifest.json",
]

DEFAULT_ASR_MODEL = "mlx-community/whisper-large-v3-turbo"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def local_today() -> str:
    return datetime.now().astimezone().date().isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_paths(data_dir: Path) -> list[Path]:
    paths: set[Path] = set()
    for relative in SOURCE_FILES:
        path = data_dir / relative
        if path.exists():
            paths.add(path)
    for pattern in SOURCE_GLOBS:
        paths.update(path for path in data_dir.glob(pattern) if path.is_file())
    return sorted(paths)


def source_signature(data_dir: Path) -> dict[str, str]:
    signature: dict[str, str] = {}
    for path in source_paths(data_dir):
        signature[str(path.relative_to(data_dir))] = sha256_file(path)
    return signature


def missing_source_files(data_dir: Path) -> list[str]:
    return [relative for relative in SOURCE_FILES if not (data_dir / relative).exists()]


def missing_derived_files(data_dir: Path) -> list[str]:
    return [relative for relative in DERIVED_FILES if not (data_dir / relative).exists()]


def changed_paths(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    before_paths = set(before)
    after_paths = set(after)
    return {
        "added": sorted(after_paths - before_paths),
        "changed": sorted(path for path in before_paths & after_paths if before[path] != after[path]),
        "removed": sorted(before_paths - after_paths),
    }


def video_date(row: dict[str, Any]) -> str | None:
    title = str(row.get("title") or "")
    match = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", title)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    for key in ("published", "updated"):
        value = row.get(key)
        if isinstance(value, str) and len(value) >= 10 and value[4:5] == "-" and value[7:8] == "-":
            return value[:10]
    return None


def transcript_exists_for_video(data_dir: Path, row: dict[str, Any]) -> bool:
    date = video_date(row)
    if date and (data_dir / "transcripts" / f"{date}.md").exists():
        return True
    manifest_rows = read_jsonl(data_dir / "source" / "youtube_audio_manifest.jsonl")
    video_id = str(row.get("video_id") or "")
    for item in manifest_rows:
        if str(item.get("video_id") or "") != video_id:
            continue
        transcript_path = item.get("transcript_path")
        if transcript_path:
            path = Path(str(transcript_path))
            path = path if path.is_absolute() else data_dir.parent / path
            if path.exists():
                return True
        if str(item.get("asr_status") or "").lower() == "done" and date:
            return (data_dir / "transcripts" / f"{date}.md").exists()
    return False


def latest_missing_asr_video(data_dir: Path, *, include_errors: bool = False) -> dict[str, Any] | None:
    youtube_path = data_dir / "source" / "youtube_recent.json"
    if not youtube_path.exists():
        return None
    rows = read_json(youtube_path)
    if not isinstance(rows, list):
        return None
    latest = next((row for row in rows if isinstance(row, dict) and row.get("video_id")), None)
    if latest is None or transcript_exists_for_video(data_dir, latest):
        return None
    manifest_by_id = {
        str(item.get("video_id") or ""): item
        for item in read_jsonl(data_dir / "source" / "youtube_audio_manifest.jsonl")
        if item.get("video_id")
    }
    status = str(manifest_by_id.get(str(latest["video_id"]), {}).get("asr_status") or "").lower()
    if status in {"running"}:
        return None
    if status == "error" and not include_errors:
        return None
    return latest


def count_markdown_files(data_dir: Path, folder: str) -> int:
    return sum(1 for path in (data_dir / folder).glob("*.md") if path.is_file())


def run_step(cmd: list[str], *, required: bool = True) -> int:
    print("$ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, check=False)
    if required and result.returncode:
        raise RuntimeError(f"command failed with exit code {result.returncode}: {' '.join(cmd)}")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Yu Ting-Hao public sources once per local day and rebuild derived context when data changes."
    )
    parser.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--state-file", type=Path, default=None)
    parser.add_argument("--force-check", action="store_true", help="ignore today's check marker")
    parser.add_argument("--skip-jokes", action="store_true", help="do not rebuild the jokes inventory")
    parser.add_argument("--skip-market", action="store_true", help="do not refresh broad episode market context")
    parser.add_argument("--skip-asset-market", action="store_true", help="do not refresh mentioned-asset context")
    parser.add_argument(
        "--no-auto-asr",
        dest="auto_asr_latest",
        action="store_false",
        help="skip YouTube audio ASR fallback for the newest missing transcript",
    )
    parser.add_argument("--asr-model", default=DEFAULT_ASR_MODEL)
    parser.add_argument("--keep-audio", action="store_true", help="keep downloaded YouTube audio after ASR")
    parser.add_argument("--force-asr", action="store_true", help="retry the newest missing video even after an ASR error")
    parser.add_argument("--today", default=None, help="override local date for tests, YYYY-MM-DD")
    parser.set_defaults(auto_asr_latest=True)
    args = parser.parse_args()

    skill_dir = args.skill_dir.resolve()
    scripts_dir = skill_dir / "scripts"
    data_dir = skill_dir / "data"
    state_file = args.state_file or data_dir / ".runtime" / "daily_source_check.json"
    today = args.today or local_today()

    state: dict[str, Any] = {}
    if state_file.exists():
        state = read_json(state_file)

    source_missing = missing_source_files(data_dir)
    derived_missing = missing_derived_files(data_dir)
    asr_target_before = latest_missing_asr_video(data_dir, include_errors=args.force_asr) if args.auto_asr_latest else None
    if (
        not args.force_check
        and state.get("checked_date") == today
        and not source_missing
        and not derived_missing
        and not asr_target_before
    ):
        print(f"Yu Ting-Hao public sources already checked for {today}; skipping source crawl.", flush=True)
        return 0

    before = source_signature(data_dir)

    run_step([sys.executable, str(scripts_dir / "crawl_sources.py"), "--out-dir", str(skill_dir)])

    asr_targets: list[dict[str, Any]] = []
    asr_status: dict[str, int] = {}
    asr_target_after_crawl = latest_missing_asr_video(data_dir, include_errors=args.force_asr) if args.auto_asr_latest else None
    if asr_target_after_crawl:
        asr_targets.append(asr_target_after_crawl)
        asr_cmd = [
            sys.executable,
            str(scripts_dir / "transcribe_youtube_audio.py"),
            "--skill-dir",
            str(skill_dir),
            "--video-id",
            str(asr_target_after_crawl["video_id"]),
            "--model",
            args.asr_model,
        ]
        if args.keep_audio:
            asr_cmd.append("--keep-audio")
        if args.force_asr:
            asr_cmd.append("--force")
            asr_cmd.append("--retry-errors")
        asr_status[str(asr_target_after_crawl["video_id"])] = run_step(asr_cmd, required=False)

    after = source_signature(data_dir)
    changes = changed_paths(before, after)
    sources_changed = before != after
    derived_missing = missing_derived_files(data_dir)
    rebuild_needed = sources_changed or bool(derived_missing)

    jokes_status: int | None = None
    market_status: int | None = None
    asset_market_status: int | None = None

    if rebuild_needed and not args.skip_jokes:
        jokes_status = run_step([sys.executable, str(scripts_dir / "extract_note_jokes.py")], required=False)

    if rebuild_needed and not args.skip_market:
        market_cmd = [
            sys.executable,
            str(scripts_dir / "align_market_context.py"),
            "--data-dir",
            str(data_dir),
        ]
        if sources_changed:
            market_cmd.append("--force")
        market_status = run_step(market_cmd, required=False)
        if not args.skip_asset_market:
            asset_cmd = [
                sys.executable,
                str(scripts_dir / "build_episode_asset_context.py"),
                "--data-dir",
                str(data_dir),
            ]
            if sources_changed:
                asset_cmd.append("--force")
            asset_market_status = run_step(asset_cmd, required=False)

    outcome = {
        "checked_date": today,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "sources_changed": sources_changed,
        "source_changes": changes,
        "rebuild_needed": rebuild_needed,
        "missing_source_files_before_crawl": source_missing,
        "missing_derived_files_before_rebuild": derived_missing,
        "auto_asr_latest": args.auto_asr_latest,
        "auto_asr_target_before_crawl": asr_target_before,
        "auto_asr_targets": asr_targets,
        "auto_asr_exit_codes": asr_status,
        "counts": {
            "notes": count_markdown_files(data_dir, "notes"),
            "transcripts": count_markdown_files(data_dir, "transcripts"),
            "official_articles": count_markdown_files(data_dir, "official_articles"),
        },
        "jokes_refresh_exit_code": jokes_status,
        "market_refresh_exit_code": market_status,
        "asset_market_refresh_exit_code": asset_market_status,
    }
    write_json(state_file, outcome)

    if sources_changed:
        print(
            "Updated Yu Ting-Hao source data: "
            f"{len(changes['added'])} added, {len(changes['changed'])} changed, "
            f"{len(changes['removed'])} removed file(s).",
            flush=True,
        )
    else:
        print("No Yu Ting-Hao public source updates found.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - keep the skill failure message actionable.
        print(f"sync_daily_sources.py failed: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
