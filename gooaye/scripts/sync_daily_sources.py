#!/usr/bin/env python3
"""Update Gooaye transcript sources, SoundOn metadata, and optional ASR fallback."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://whatmkreallysaid.com"
DEFAULT_FEED_URL = "https://feeds.soundon.fm/podcasts/954689a5-3096-43a4-a80b-7810b219cef3.xml"
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def manifest_signature(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    manifest = read_json(path)
    signature: dict[int, str] = {}
    for record in manifest.get("records", []):
        signature[int(record["number"])] = str(record.get("sha256") or "")
    return signature


def missing_memory_files(data_dir: Path) -> list[str]:
    return [relative for relative in MEMORY_FILES if not (data_dir / relative).exists()]


def run_step(cmd: list[str], *, required: bool = True) -> int:
    print("$ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, check=False)
    if required and result.returncode:
        raise RuntimeError(f"command failed with exit code {result.returncode}: {' '.join(cmd)}")
    return result.returncode


def pending_asr(data_dir: Path) -> list[int]:
    rows = read_jsonl(data_dir / "audio_manifest.jsonl")
    return sorted([int(row["number"]) for row in rows if row.get("asr_status") == "pending"], reverse=True)


def latest_missing_asr_episode(data_dir: Path) -> int | None:
    rows = [row for row in read_jsonl(data_dir / "audio_manifest.jsonl") if row.get("number") is not None]
    if not rows:
        return None
    latest = max(rows, key=lambda row: int(row["number"]))
    return int(latest["number"]) if latest.get("asr_status") == "pending" else None


def should_run_asr(args: argparse.Namespace, latest_missing_episode: int | None) -> bool:
    if args.run_asr:
        return True
    return bool(args.auto_asr_latest and latest_missing_episode is not None)


def refresh_derived_data(args: argparse.Namespace, scripts_dir: Path, data_dir: Path) -> dict[str, int | None]:
    market_status: int | None = None
    asset_market_status: int | None = None
    investment_status: int | None = None
    life_status: int | None = None

    if not args.skip_market:
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

    if not args.skip_memory:
        investment_status = run_step(
            [sys.executable, str(scripts_dir / "build_investment_memory.py"), "--data-dir", str(data_dir)]
        )
        life_status = run_step([sys.executable, str(scripts_dir / "build_life_memory.py"), "--data-dir", str(data_dir)])

    return {
        "market_refresh_exit_code": market_status,
        "asset_market_refresh_exit_code": asset_market_status,
        "investment_memory_exit_code": investment_status,
        "life_memory_exit_code": life_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Gooaye canonical transcripts plus SoundOn ASR fallback metadata.")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--feed-url", default=DEFAULT_FEED_URL)
    parser.add_argument("--force-check", action="store_true", help="force the canonical transcript-site check")
    parser.add_argument("--skip-transcript-site", action="store_true", help="skip whatmkreallysaid transcript sync")
    parser.add_argument("--skip-podcast-feed", action="store_true", help="skip SoundOn RSS sync")
    parser.add_argument("--run-asr", action="store_true", help="transcribe newest SoundOn episodes missing local transcripts")
    parser.add_argument(
        "--no-auto-asr",
        dest="auto_asr_latest",
        action="store_false",
        help="do not automatically ASR the newest missing SoundOn episode",
    )
    parser.set_defaults(auto_asr_latest=True)
    parser.add_argument("--asr-limit", type=int, default=1, help="max newest pending SoundOn episodes to transcribe; 0 means all")
    parser.add_argument("--asr-episode", type=int, action="append", help="transcribe a specific episode number")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--keep-audio", action="store_true", help="keep downloaded MP3 files after ASR")
    parser.add_argument("--force-asr", action="store_true", help="overwrite existing ASR transcript files")
    parser.add_argument("--skip-market", action="store_true", help="do not refresh baseline episode market context")
    parser.add_argument("--skip-asset-market", action="store_true", help="do not refresh per-episode mentioned-asset context")
    parser.add_argument("--skip-memory", action="store_true", help="do not rebuild distilled memory")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parents[1]
    scripts_dir = skill_dir / "scripts"
    data_dir: Path = args.data_dir
    manifest_path = data_dir / "transcripts_manifest.json"
    before = manifest_signature(manifest_path)
    derived_status: dict[str, int | None] = {}

    if not args.skip_transcript_site:
        sync_cmd = [
            sys.executable,
            str(scripts_dir / "sync_daily_transcripts.py"),
            "--base-url",
            args.base_url,
            "--data-dir",
            str(data_dir),
        ]
        if args.force_check:
            sync_cmd.append("--force-check")
        if args.skip_market:
            sync_cmd.append("--skip-market")
        if args.skip_asset_market:
            sync_cmd.append("--skip-asset-market")
        run_step(sync_cmd)

    if not args.skip_podcast_feed:
        run_step(
            [
                sys.executable,
                str(scripts_dir / "fetch_podcast_feed.py"),
                "--feed-url",
                args.feed_url,
                "--data-dir",
                str(data_dir),
            ]
        )

    pending_before_asr = pending_asr(data_dir)
    latest_missing_before_asr = latest_missing_asr_episode(data_dir)
    asr_exit_code: int | None = None
    asr_requested = should_run_asr(args, latest_missing_before_asr)
    if asr_requested:
        if args.asr_episode:
            for episode in args.asr_episode:
                cmd = [
                    sys.executable,
                    str(scripts_dir / "transcribe_audio.py"),
                    "--data-dir",
                    str(data_dir),
                    "--episode",
                    str(episode),
                    "--model",
                    args.model,
                ]
                if args.force_asr:
                    cmd.append("--force")
                if args.keep_audio:
                    cmd.append("--keep-audio")
                asr_exit_code = run_step(cmd, required=False)
        elif args.run_asr:
            cmd = [
                sys.executable,
                str(scripts_dir / "transcribe_audio.py"),
                "--data-dir",
                str(data_dir),
                "--limit",
                str(args.asr_limit),
                "--model",
                args.model,
            ]
            if args.force_asr:
                cmd.append("--force")
            if args.keep_audio:
                cmd.append("--keep-audio")
            asr_exit_code = run_step(cmd, required=False)
        elif latest_missing_before_asr is not None:
            cmd = [
                sys.executable,
                str(scripts_dir / "transcribe_audio.py"),
                "--data-dir",
                str(data_dir),
                "--episode",
                str(latest_missing_before_asr),
                "--model",
                args.model,
            ]
            if args.force_asr:
                cmd.append("--force")
            if args.keep_audio:
                cmd.append("--keep-audio")
            asr_exit_code = run_step(cmd, required=False)

    after = manifest_signature(manifest_path)
    new_episodes = sorted(set(after) - set(before))
    changed_episodes = sorted(number for number in set(after) & set(before) if after[number] != before[number])
    transcripts_changed = before != after
    memory_missing = missing_memory_files(data_dir)
    if transcripts_changed or memory_missing:
        derived_status = refresh_derived_data(args, scripts_dir, data_dir)

    pending_after = pending_asr(data_dir)
    state = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "canonical_source": args.base_url,
        "podcast_feed": args.feed_url,
        "transcripts_changed": transcripts_changed,
        "new_episodes": new_episodes,
        "changed_episodes": changed_episodes,
        "pending_asr_before": pending_before_asr,
        "pending_asr_after": pending_after,
        "latest_missing_asr_episode_before": latest_missing_before_asr,
        "run_asr": asr_requested,
        "auto_asr_latest": args.auto_asr_latest,
        "asr_exit_code": asr_exit_code,
        "max_episode": max(after) if after else None,
        "missing_memory_before_rebuild": memory_missing,
        **derived_status,
    }
    write_json(data_dir / ".runtime" / "daily_source_check.json", state)

    if pending_after and not asr_requested:
        preview = ", ".join(f"EP{number:03d}" for number in pending_after[:5])
        print(f"SoundOn has episodes pending ASR: {preview}", flush=True)
    elif pending_after and asr_requested:
        preview = ", ".join(f"EP{number:03d}" for number in pending_after[:5])
        print(f"SoundOn still has episodes pending ASR: {preview}", flush=True)
    if transcripts_changed:
        print(
            f"Updated Gooaye transcript corpus: {len(new_episodes)} new episode(s), "
            f"{len(changed_episodes)} changed episode(s).",
            flush=True,
        )
    elif not pending_after:
        print("Gooaye sources are current; no pending ASR episodes.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - keep skill sync failures actionable.
        print(f"sync_daily_sources.py failed: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
