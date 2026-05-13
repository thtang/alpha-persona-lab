#!/usr/bin/env python3
"""Run Zhezhe ASR newest-first with a bounded local worker pool."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transcribe_audio import DATA, MANIFEST, ROOT, episode_date, episode_id, is_filtered_zhezhe, read_jsonl, transcript_exists


def utc_stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def pending_rows(rows: list[dict[str, Any]], *, force: bool = False) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        try:
            eid = episode_id(row)
        except ValueError:
            continue
        if not is_filtered_zhezhe(row):
            continue
        if not force and row.get("asr_status") == "done":
            continue
        if not force and transcript_exists(row, eid):
            continue
        item = dict(row)
        item["_manifest_index"] = idx
        item["_episode_id"] = eid
        item["_episode_date"] = episode_date(row)
        pending.append(item)
    pending.sort(key=lambda item: (item["_episode_date"], int(item["_manifest_index"]) * -1), reverse=True)
    return pending


def status_count(status_file: Path) -> tuple[int, int]:
    done = errors = 0
    if not status_file.exists():
        return done, errors
    for line in status_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue
        if row.get("asr_status") == "done":
            done += 1
        elif row.get("asr_status") == "error":
            errors += 1
    return done, errors


def cleanup_audio() -> None:
    audio_dir = DATA / "audio"
    for path in audio_dir.glob("*"):
        if path.is_file():
            path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--limit", type=int, help="Maximum episodes to complete in this supervisor run.")
    parser.add_argument("--batch-size", type=int, help="Episodes to dispatch per batch. Defaults to concurrency.")
    parser.add_argument("--status-dir", type=Path, default=DATA / "asr" / "newest_status")
    parser.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")
    batch_size = args.batch_size or args.concurrency
    if batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")

    completed_total = 0
    batch = 0
    while True:
        rows = read_jsonl(MANIFEST)
        pending = pending_rows(rows, force=args.force)
        if args.limit is not None:
            remaining_limit = args.limit - completed_total
            if remaining_limit <= 0:
                break
            pending = pending[:remaining_limit]
        if not pending:
            print("No pending Zhezhe ASR episodes remain.", flush=True)
            break

        selected = pending[: min(batch_size, args.concurrency, len(pending))]
        batch += 1
        print(
            json.dumps(
                {
                    "batch": batch,
                    "started_at": utc_stamp(),
                    "selected": [
                        {
                            "episode_id": row["_episode_id"],
                            "date": row["_episode_date"],
                            "title": row.get("title"),
                        }
                        for row in selected
                    ],
                    "pending_before_batch": len(pending),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )

        procs: list[tuple[str, Path, subprocess.Popen[str]]] = []
        for row in selected:
            eid = row["_episode_id"]
            status_file = args.status_dir / f"{eid}.jsonl"
            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "transcribe_audio.py"),
                "--episode-id",
                eid,
                "--model",
                args.model,
                "--status-jsonl",
                str(status_file),
                "--no-manifest-update",
            ]
            if args.force:
                cmd.append("--force")
            proc = subprocess.Popen(cmd, cwd=str(ROOT.parent), text=True)
            procs.append((eid, status_file, proc))

        failures = 0
        for eid, status_file, proc in procs:
            code = proc.wait()
            done_count, error_count = status_count(status_file)
            if code != 0 or error_count:
                failures += 1
            if done_count:
                completed_total += done_count
            print(
                json.dumps(
                    {
                        "episode_id": eid,
                        "exit_code": code,
                        "status_done": done_count,
                        "status_errors": error_count,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )

        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "merge_asr_status.py"),
                "--status-dir",
                str(args.status_dir),
            ],
            cwd=str(ROOT.parent),
            check=False,
        )
        cleanup_audio()
        if failures:
            print(f"Batch {batch} completed with {failures} failed episode(s); continuing.", flush=True)
        time.sleep(1)

    cleanup_audio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
