#!/usr/bin/env python3
"""Check Zhezhe public sources once per local day and refresh derived context."""

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
    "source/*.json",
    "source/*.jsonl",
    "source/*.xml",
    "transcripts/*.md",
    "articles/*.md",
]

MARKET_DERIVED_FILES = [
    "market_context/episode_market_context.jsonl",
    "market_context/episode_market_context.csv",
    "market_context/market_context_manifest.json",
    "market_context/episode_asset_context.jsonl",
    "market_context/episode_asset_context_manifest.json",
]

DISTILLED_FILES = [
    "distilled/episode_notes.jsonl",
    "distilled/theme_memory.json",
    "distilled/asset_memory.json",
    "distilled/rhetoric_memory.json",
    "distilled/corpus_summary.md",
    "distilled/distillation_manifest.json",
]

DERIVED_FILES = MARKET_DERIVED_FILES + DISTILLED_FILES
DEFAULT_ASR_MODEL = "mlx-community/whisper-large-v3-turbo"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    for pattern in SOURCE_GLOBS:
        paths.update(path for path in data_dir.glob(pattern) if path.is_file())
    audio_manifest = data_dir / "audio_manifest.jsonl"
    if audio_manifest.exists():
        paths.add(audio_manifest)
    return sorted(paths)


def source_signature(data_dir: Path) -> dict[str, str]:
    signature: dict[str, str] = {}
    for path in source_paths(data_dir):
        signature[str(path.relative_to(data_dir))] = sha256_file(path)
    return signature


def missing_derived_files(data_dir: Path) -> list[str]:
    return [relative for relative in DERIVED_FILES if not (data_dir / relative).exists()]


def missing_market_files(data_dir: Path) -> list[str]:
    return [relative for relative in MARKET_DERIVED_FILES if not (data_dir / relative).exists()]


def missing_distilled_files(data_dir: Path) -> list[str]:
    return [relative for relative in DISTILLED_FILES if not (data_dir / relative).exists()]


def changed_paths(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    before_paths = set(before)
    after_paths = set(after)
    return {
        "added": sorted(after_paths - before_paths),
        "changed": sorted(path for path in before_paths & after_paths if before[path] != after[path]),
        "removed": sorted(before_paths - after_paths),
    }


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())


def count_files(data_dir: Path, folder: str) -> int:
    return sum(1 for path in (data_dir / folder).glob("*.md") if path.is_file())


def run_step(cmd: list[str], *, required: bool = True) -> int:
    print("$ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, check=False)
    if required and result.returncode:
        raise RuntimeError(f"command failed with exit code {result.returncode}: {' '.join(cmd)}")
    return result.returncode


def transcript_exists(data_dir: Path, row: dict[str, Any]) -> bool:
    value = row.get("transcript_path")
    if value:
        path = Path(str(value))
        candidates = [path]
        if not path.is_absolute():
            candidates.append(data_dir.parent / path)
            candidates.append(data_dir / path)
        if any(candidate.exists() for candidate in candidates):
            return True
    episode_id = row.get("episode_id")
    if episode_id:
        return any((data_dir / "transcripts").glob(f"*_{episode_id}.md"))
    return False


def parse_time_key(row: dict[str, Any]) -> float:
    for key in ("pub_date_utc", "published_at", "pub_date", "local_date"):
        value = row.get(key)
        if not value:
            continue
        text = str(value).replace("Z", "+00:00")
        if len(text) == 10:
            text += "T00:00:00+00:00"
        try:
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            continue
    return 0.0


def is_full_audio(row: dict[str, Any], min_duration_seconds: int) -> bool:
    title = str(row.get("title") or "").lower()
    duration = int(row.get("duration_seconds") or 0)
    if "#shorts" in title or "只有60秒" in title:
        return False
    return duration >= min_duration_seconds


def asr_done(data_dir: Path, row: dict[str, Any]) -> bool:
    return str(row.get("asr_status") or "").lower() in {"done", "transcribed"} or transcript_exists(data_dir, row)


def content_key(row: dict[str, Any]) -> tuple[str, str, int]:
    title = str(row.get("title") or "")
    title = re.sub(r"#shorts", "", title, flags=re.IGNORECASE)
    title = title.replace("郭哲榮分析師", "")
    title = title.replace("哲哲只有60秒", "")
    title = re.sub(r"\s+", "", title)
    duration_bucket = int(int(row.get("duration_seconds") or 0) / 30)
    return str(row.get("local_date") or ""), title, duration_bucket


def latest_missing_asr_targets(
    data_dir: Path,
    *,
    limit: int,
    prefer_full_audio: bool,
    min_duration_seconds: int,
) -> list[str]:
    rows = read_jsonl(data_dir / "audio_manifest.jsonl")
    eligible = [
        row
        for row in rows
        if row.get("episode_id")
        and row.get("audio_url")
        and str(row.get("asr_status") or "").lower() not in {"error", "running"}
    ]
    if not eligible:
        return []

    latest_date = max(str(row.get("local_date") or "") for row in eligible)
    same_day = [row for row in eligible if str(row.get("local_date") or "") == latest_date]
    if prefer_full_audio:
        full_rows = [row for row in same_day if is_full_audio(row, min_duration_seconds)]
        if full_rows:
            same_day = full_rows

    same_day.sort(
        key=lambda row: (
            parse_time_key(row),
            1 if "郭哲榮" in str(row.get("channel_author") or "") else 0,
            int(row.get("duration_seconds") or 0),
        ),
        reverse=True,
    )
    if not same_day:
        return []

    target_key = content_key(same_day[0])
    duplicate_rows = [row for row in same_day if content_key(row) == target_key]
    if any(asr_done(data_dir, row) for row in duplicate_rows):
        return []
    selected = [row for row in duplicate_rows if not asr_done(data_dir, row)]
    selected = selected[:limit] if limit else selected
    return [str(row["episode_id"]) for row in selected]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Zhezhe public sources once per local day and rebuild derived market context when data changes."
    )
    parser.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--force-check", action="store_true", help="ignore today's check marker")
    parser.add_argument("--skip-podcast", action="store_true")
    parser.add_argument("--skip-articles", action="store_true")
    parser.add_argument("--skip-market", action="store_true")
    parser.add_argument("--skip-asset-market", action="store_true")
    parser.add_argument("--skip-distill", action="store_true")
    parser.add_argument(
        "--no-auto-asr",
        dest="auto_asr_latest",
        action="store_false",
        help="do not automatically ASR the newest missing filtered episode",
    )
    parser.add_argument("--asr-limit", type=int, default=1, help="max newest missing episodes to auto-ASR; 0 means all")
    parser.add_argument("--asr-model", default=DEFAULT_ASR_MODEL)
    parser.add_argument("--keep-audio", action="store_true", help="keep downloaded MP3 files after auto-ASR")
    parser.add_argument("--force-asr", action="store_true", help="re-transcribe rows even if marked done")
    parser.add_argument(
        "--allow-shorts-first",
        dest="prefer_full_audio",
        action="store_false",
        help="allow 60-second shorts to be auto-ASR'd before full-length episodes",
    )
    parser.add_argument("--min-full-duration-seconds", type=int, default=300)
    parser.add_argument("--today", help="override local date for tests, YYYY-MM-DD")
    parser.set_defaults(auto_asr_latest=True, prefer_full_audio=True)
    args = parser.parse_args()

    skill_dir = args.skill_dir.resolve()
    scripts_dir = skill_dir / "scripts"
    data_dir = skill_dir / "data"
    state_file = args.state_file or data_dir / ".runtime" / "daily_source_check.json"
    today = args.today or local_today()

    state: dict[str, Any] = {}
    if state_file.exists():
        state = read_json(state_file)

    current_signature = source_signature(data_dir)
    derived_missing = missing_derived_files(data_dir)
    signature_unchanged = state.get("source_signature") == current_signature
    auto_asr_targets_before = (
        latest_missing_asr_targets(
            data_dir,
            limit=args.asr_limit,
            prefer_full_audio=args.prefer_full_audio,
            min_duration_seconds=args.min_full_duration_seconds,
        )
        if args.auto_asr_latest
        else []
    )
    if (
        not args.force_check
        and state.get("checked_date") == today
        and not derived_missing
        and signature_unchanged
        and not auto_asr_targets_before
    ):
        print(f"Zhezhe public sources already checked for {today}; skipping source crawl.", flush=True)
        return 0

    before = current_signature

    podcast_status: int | None = None
    article_status: int | None = None
    market_status: int | None = None
    asset_market_status: int | None = None
    distill_status: int | None = None
    asr_statuses: dict[str, int] = {}

    if not args.skip_podcast:
        podcast_status = run_step(
            [sys.executable, str(scripts_dir / "fetch_podcast_feed.py"), "--skill-dir", str(skill_dir)],
            required=False,
        )

    if not args.skip_articles:
        article_status = run_step(
            [sys.executable, str(scripts_dir / "crawl_articles.py"), "--skill-dir", str(skill_dir)],
            required=False,
        )

    auto_asr_targets = (
        latest_missing_asr_targets(
            data_dir,
            limit=args.asr_limit,
            prefer_full_audio=args.prefer_full_audio,
            min_duration_seconds=args.min_full_duration_seconds,
        )
        if args.auto_asr_latest
        else []
    )
    for episode_id in auto_asr_targets:
        cmd = [
            sys.executable,
            str(scripts_dir / "transcribe_audio.py"),
            "--episode-id",
            episode_id,
            "--model",
            args.asr_model,
        ]
        if args.keep_audio:
            cmd.append("--keep-audio")
        if args.force_asr:
            cmd.append("--force")
        asr_statuses[episode_id] = run_step(cmd, required=False)

    after = source_signature(data_dir)
    changes = changed_paths(before, after)
    sources_changed = before != after
    derived_missing = missing_derived_files(data_dir)
    market_missing = missing_market_files(data_dir)
    distilled_missing = missing_distilled_files(data_dir)
    market_rebuild_needed = sources_changed or bool(market_missing)
    distill_rebuild_needed = sources_changed or bool(distilled_missing)

    if market_rebuild_needed and not args.skip_market:
        market_status = run_step(
            [sys.executable, str(scripts_dir / "align_market_context.py"), "--data-dir", str(data_dir)],
            required=False,
        )
        if not args.skip_asset_market:
            asset_market_status = run_step(
                [sys.executable, str(scripts_dir / "build_episode_asset_context.py"), "--data-dir", str(data_dir)],
                required=False,
            )
        distill_rebuild_needed = True

    if distill_rebuild_needed and not args.skip_distill:
        distill_status = run_step(
            [sys.executable, str(scripts_dir / "build_distilled_memory.py")],
            required=False,
        )

    final_signature = source_signature(data_dir)

    outcome = {
        "checked_date": today,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "sources_changed": sources_changed,
        "source_changes": changes,
        "market_rebuild_needed": market_rebuild_needed,
        "distill_rebuild_needed": distill_rebuild_needed,
        "missing_derived_files_before_rebuild": derived_missing,
        "missing_market_files_before_rebuild": market_missing,
        "missing_distilled_files_before_rebuild": distilled_missing,
        "source_signature": final_signature,
        "podcast_fetch_exit_code": podcast_status,
        "article_fetch_exit_code": article_status,
        "auto_asr_latest": args.auto_asr_latest,
        "auto_asr_targets_before_fetch": auto_asr_targets_before,
        "auto_asr_targets": auto_asr_targets,
        "auto_asr_exit_codes": asr_statuses,
        "market_refresh_exit_code": market_status,
        "asset_market_refresh_exit_code": asset_market_status,
        "distill_refresh_exit_code": distill_status,
        "counts": {
            "all_podcast_episodes": count_jsonl(data_dir / "source" / "podcast_episodes.jsonl"),
            "zhezhe_podcast_episodes": count_jsonl(data_dir / "source" / "zhezhe_episodes.jsonl"),
            "udn_articles": count_jsonl(data_dir / "source" / "udn_articles.jsonl"),
            "zhezhe_articles": count_jsonl(data_dir / "source" / "zhezhe_articles.jsonl"),
            "transcripts": count_files(data_dir, "transcripts"),
            "articles": count_files(data_dir, "articles"),
        },
    }
    write_json(state_file, outcome)

    if sources_changed:
        print(
            "Updated Zhezhe source data: "
            f"{len(changes['added'])} added, {len(changes['changed'])} changed, "
            f"{len(changes['removed'])} removed file(s).",
            flush=True,
        )
    else:
        print("No Zhezhe public source updates found.", flush=True)
    if auto_asr_targets:
        print(
            "Auto-ASR attempted for latest missing Zhezhe episode(s): "
            + ", ".join(f"{episode_id}={code}" for episode_id, code in asr_statuses.items()),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"sync_daily_sources.py failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
