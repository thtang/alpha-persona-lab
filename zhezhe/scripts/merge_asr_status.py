#!/usr/bin/env python3
"""Merge per-shard ASR status JSONL files back into Zhezhe manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

UPDATE_KEYS = [
    "asr_status",
    "asr_error",
    "asr_model",
    "asr_at",
    "transcript_path",
    "audio_sha256",
    "audio_path",
]


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def load_statuses(status_dir: Path) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for path in sorted(status_dir.glob("*.jsonl")):
        for row in read_jsonl(path):
            eid = row.get("episode_id")
            if not eid:
                continue
            statuses[str(eid)] = row
    return statuses


def resolve_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    return path if path.is_absolute() else ROOT / path


def apply_status(row: dict[str, Any], status: dict[str, Any]) -> bool:
    changed = False
    for key in UPDATE_KEYS:
        if key not in status:
            continue
        value = status.get(key)
        if key == "audio_path":
            path = resolve_path(value)
            if not path or not path.exists():
                value = None
        if value in (None, ""):
            if key in row and row.get(key) not in (None, ""):
                row.pop(key, None)
                changed = True
            continue
        if row.get(key) != value:
            row[key] = value
            changed = True
    if status.get("asr_status") == "done" and row.pop("asr_error", None):
        changed = True
    return changed


def update_file(path: Path, statuses: dict[str, dict[str, Any]]) -> tuple[int, int]:
    rows = read_jsonl(path)
    changed = 0
    matched = 0
    for row in rows:
        eid = row.get("episode_id")
        if not eid:
            continue
        status = statuses.get(str(eid))
        if not status:
            continue
        matched += 1
        if apply_status(row, status):
            changed += 1
    if changed:
        write_jsonl(path, rows)
    return matched, changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--status-dir", type=Path, default=DATA / "asr" / "status")
    parser.add_argument("--manifest", type=Path, default=DATA / "audio_manifest.jsonl")
    parser.add_argument("--episodes", type=Path, default=DATA / "source" / "zhezhe_episodes.jsonl")
    args = parser.parse_args()

    statuses = load_statuses(args.status_dir)
    manifest_matched, manifest_changed = update_file(args.manifest, statuses)
    episode_matched, episode_changed = update_file(args.episodes, statuses)

    done = sum(1 for row in statuses.values() if row.get("asr_status") == "done")
    errors = sum(1 for row in statuses.values() if row.get("asr_status") == "error")
    print(
        json.dumps(
            {
                "status_dir": str(args.status_dir),
                "status_rows": len(statuses),
                "done": done,
                "errors": errors,
                "manifest_matched": manifest_matched,
                "manifest_changed": manifest_changed,
                "episodes_matched": episode_matched,
                "episodes_changed": episode_changed,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
