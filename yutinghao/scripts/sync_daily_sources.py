#!/usr/bin/env python3
"""Check Yu Ting-Hao public sources once per local day and refresh derived data."""

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
    parser.add_argument("--today", default=None, help="override local date for tests, YYYY-MM-DD")
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
    if (
        not args.force_check
        and state.get("checked_date") == today
        and not source_missing
        and not derived_missing
    ):
        print(f"Yu Ting-Hao public sources already checked for {today}; skipping source crawl.", flush=True)
        return 0

    before = source_signature(data_dir)

    run_step([sys.executable, str(scripts_dir / "crawl_sources.py"), "--out-dir", str(skill_dir)])

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
