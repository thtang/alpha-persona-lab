#!/usr/bin/env python3
"""Check the Gooaye transcript site once per local day and refresh derived data."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://whatmkreallysaid.com"
MEMORY_FILES = [
    "distilled/theme_memory.json",
    "distilled/episode_investment_memory.jsonl",
    "distilled/latest_market_snapshot.json",
    "distilled/life_theme_memory.json",
    "distilled/episode_life_memory.jsonl",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def local_today() -> str:
    return datetime.now().astimezone().date().isoformat()


def manifest_signature(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    manifest = read_json(path)
    signature: dict[int, str] = {}
    for record in manifest.get("records", []):
        number = int(record["number"])
        signature[number] = str(record.get("sha256") or "")
    return signature


def missing_memory_files(data_dir: Path) -> list[str]:
    return [relative for relative in MEMORY_FILES if not (data_dir / relative).exists()]


def run_step(cmd: list[str], *, required: bool = True) -> int:
    print("$ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, check=False)
    if required and result.returncode:
        raise RuntimeError(f"command failed with exit code {result.returncode}: {' '.join(cmd)}")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Gooaye transcripts once per local day and rebuild derived memory when data changes."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--state-file", type=Path, default=None)
    parser.add_argument("--force-check", action="store_true", help="ignore today's check marker")
    parser.add_argument("--skip-market", action="store_true", help="do not refresh episode market context")
    parser.add_argument("--skip-asset-market", action="store_true", help="do not refresh per-episode mentioned-asset context")
    parser.add_argument("--today", default=None, help="override local date for tests, YYYY-MM-DD")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parents[1]
    scripts_dir = skill_dir / "scripts"
    data_dir: Path = args.data_dir
    state_file = args.state_file or data_dir / ".runtime" / "daily_transcript_check.json"
    manifest_path = data_dir / "transcripts_manifest.json"
    today = args.today or local_today()

    state: dict[str, Any] = {}
    if state_file.exists():
        state = read_json(state_file)

    if (
        not args.force_check
        and state.get("checked_date") == today
        and manifest_path.exists()
        and not missing_memory_files(data_dir)
    ):
        print(f"Gooaye transcripts already checked for {today}; skipping website fetch.", flush=True)
        return 0

    before = manifest_signature(manifest_path)

    fetch_cmd = [
        sys.executable,
        str(scripts_dir / "fetch_transcripts.py"),
        "--base-url",
        args.base_url,
        "--out-dir",
        str(data_dir),
    ]
    run_step(fetch_cmd)

    after = manifest_signature(manifest_path)
    new_episodes = sorted(set(after) - set(before))
    changed_episodes = sorted(number for number in set(after) & set(before) if after[number] != before[number])
    memory_missing = missing_memory_files(data_dir)
    transcripts_changed = before != after

    market_status: int | None = None
    asset_market_status: int | None = None
    if transcripts_changed and not args.skip_market:
        market_status = run_step(
            [sys.executable, str(scripts_dir / "align_market_context.py"), "--data-dir", str(data_dir), "--force"],
            required=False,
        )
        if not args.skip_asset_market:
            asset_market_status = run_step(
                [
                    sys.executable,
                    str(scripts_dir / "build_episode_asset_context.py"),
                    "--data-dir",
                    str(data_dir),
                    "--force",
                ],
                required=False,
            )

    if transcripts_changed or memory_missing:
        run_step([sys.executable, str(scripts_dir / "build_investment_memory.py"), "--data-dir", str(data_dir)])
        run_step([sys.executable, str(scripts_dir / "build_life_memory.py"), "--data-dir", str(data_dir)])

    outcome = {
        "checked_date": today,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source": args.base_url,
        "transcripts_changed": transcripts_changed,
        "new_episodes": new_episodes,
        "changed_episodes": changed_episodes,
        "episode_count": len(after),
        "max_episode": max(after) if after else None,
        "rebuilt_memory": bool(transcripts_changed or memory_missing),
        "missing_memory_before_rebuild": memory_missing,
        "market_refresh_exit_code": market_status,
        "asset_market_refresh_exit_code": asset_market_status,
    }
    write_json(state_file, outcome)

    if transcripts_changed:
        print(
            f"Updated Gooaye data: {len(new_episodes)} new episode(s), "
            f"{len(changed_episodes)} changed transcript(s).",
            flush=True,
        )
    else:
        print("No transcript updates found on the Gooaye source site.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - keep the skill failure message actionable.
        print(f"sync_daily_transcripts.py failed: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
