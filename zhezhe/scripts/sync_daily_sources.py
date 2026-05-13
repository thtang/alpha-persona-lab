#!/usr/bin/env python3
"""Check Zhezhe public sources once per local day and refresh derived context."""

from __future__ import annotations

import argparse
import hashlib
import json
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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    parser.add_argument("--today", help="override local date for tests, YYYY-MM-DD")
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
    if not args.force_check and state.get("checked_date") == today and not derived_missing and signature_unchanged:
        print(f"Zhezhe public sources already checked for {today}; skipping source crawl.", flush=True)
        return 0

    before = current_signature

    podcast_status: int | None = None
    article_status: int | None = None
    market_status: int | None = None
    asset_market_status: int | None = None
    distill_status: int | None = None

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
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"sync_daily_sources.py failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
