#!/usr/bin/env python3
"""Daily data refresh supervisor for Alpha Persona Lab.

The repo stores its "database" as JSON/JSONL/CSV/HTML artifacts under each
skill's data/output folders. This script coordinates daily refreshes, keeps
jobs from overlapping, writes per-run logs, and passes Codex-agent worker
settings into ThemeMiner.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / ".runtime" / "daily_update"
LOG_ROOT = ROOT / "logs" / "daily_update"


@dataclass
class Job:
    name: str
    command: list[str]
    required: bool = True


@dataclass
class JobResult:
    name: str
    command: list[str]
    returncode: int
    duration_seconds: float
    log_path: Path
    required: bool

    @property
    def ok(self) -> bool:
        return self.returncode == 0 or not self.required


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def repo_python() -> str:
    venv_python = ROOT / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else sys.executable


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def shell_quote(command: Sequence[str]) -> str:
    return shlex.join(command)


def base_env() -> dict[str, str]:
    env = os.environ.copy()
    path_parts = [
        str(ROOT / ".venv" / "bin"),
        "/Applications/Codex.app/Contents/Resources",
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    env["PATH"] = os.pathsep.join([part for part in path_parts if part]) + os.pathsep + env.get("PATH", "")
    codex_command = env.get("THEMEMINER_CODEX_COMMAND")
    bundled_codex = Path("/Applications/Codex.app/Contents/Resources/codex")
    if not codex_command and bundled_codex.exists():
        env["THEMEMINER_CODEX_COMMAND"] = str(bundled_codex)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def run_job(job: Job, *, env: dict[str, str], log_dir: Path) -> JobResult:
    started = time.monotonic()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{job.name}.log"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"started_at={utc_now()}\n")
        log.write(f"cwd={ROOT}\n")
        log.write(f"required={job.required}\n")
        log.write("$ " + shell_quote(job.command) + "\n\n")
        log.flush()
        process = subprocess.run(job.command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        log.write(f"\nfinished_at={utc_now()}\n")
        log.write(f"exit_code={process.returncode}\n")
    return JobResult(
        name=job.name,
        command=job.command,
        returncode=process.returncode,
        duration_seconds=round(time.monotonic() - started, 2),
        log_path=log_path,
        required=job.required,
    )


def run_parallel(jobs: list[Job], *, env: dict[str, str], log_dir: Path, workers: int) -> list[JobResult]:
    if not jobs:
        return []
    results: list[JobResult] = []
    max_workers = max(1, min(workers, len(jobs)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(run_job, job, env=env, log_dir=log_dir): job for job in jobs}
        for future in as_completed(future_map):
            result = future.result()
            status = "ok" if result.returncode == 0 else "failed"
            print(f"{status} {result.name} exit={result.returncode} log={result.log_path}", flush=True)
            results.append(result)
    return sorted(results, key=lambda item: item.name)


def run_sequential(jobs: list[Job], *, env: dict[str, str], log_dir: Path) -> list[JobResult]:
    results: list[JobResult] = []
    for job in jobs:
        result = run_job(job, env=env, log_dir=log_dir)
        status = "ok" if result.returncode == 0 else "failed"
        print(f"{status} {result.name} exit={result.returncode} log={result.log_path}", flush=True)
        results.append(result)
        if result.returncode != 0 and job.required:
            break
    return results


def selected_jobs(value: str) -> set[str]:
    if value == "all":
        return {"corpus", "theme"}
    return {item.strip() for item in value.split(",") if item.strip()}


def corpus_jobs(args: argparse.Namespace) -> list[Job]:
    jobs: list[Job] = []
    python = repo_python()
    common_flags: list[str] = []
    if args.force_check:
        common_flags.append("--force-check")
    if not args.auto_asr:
        common_flags.append("--no-auto-asr")

    jobs.append(Job("gooaye_sources", [python, "gooaye/scripts/sync_daily_sources.py", *common_flags]))
    jobs.append(Job("yutinghao_sources", [python, "yutinghao/scripts/sync_daily_sources.py", *common_flags]))
    jobs.append(Job("zhezhe_sources", [python, "zhezhe/scripts/sync_daily_sources.py", *common_flags]))
    return jobs


def theme_jobs(args: argparse.Namespace) -> list[Job]:
    if args.theme_profile == "skip":
        return []

    python = repo_python()
    if args.theme_profile == "light":
        command = [
            "bash",
            "scripts/bootstrap-theme-stack.sh",
            "--fresh",
            "--agent-mode",
            "auto",
            "--agent-workers",
            str(args.workers),
            "--agent-batch-size",
            str(args.agent_batch_size),
        ]
        if args.price_symbol_limit is not None:
            command.extend(["--price-symbol-limit", str(args.price_symbol_limit)])
        return [Job("thememiner_lagradar_light", command)]

    command = [
        python,
        "thememiner/scripts/run_codex_agent_refresh.py",
        "--workers",
        str(args.workers),
        "--markets",
        args.markets,
        "--discovery-batch-size",
        str(args.discovery_batch_size),
        "--thesis-batch-size",
        str(args.thesis_batch_size),
        "--source-limit",
        str(args.source_limit),
        "--max-urls-per-symbol",
        str(args.max_urls_per_symbol),
    ]
    if args.refresh_agent_cache:
        command.append("--refresh-agent-cache")
    if args.refresh_source_pages:
        command.append("--refresh-source-pages")
    if args.skip_source_fetch:
        command.append("--skip-source-fetch")
    if args.skip_profile_upgrade:
        command.append("--skip-profile-upgrade")
    return [Job("thememiner_lagradar_codex", command)]


def result_payload(result: JobResult) -> dict[str, object]:
    return {
        "name": result.name,
        "command": result.command,
        "returncode": result.returncode,
        "required": result.required,
        "ok": result.ok,
        "duration_seconds": result.duration_seconds,
        "log_path": str(result.log_path),
    }


def fail_if_needed(results: list[JobResult]) -> int:
    failed_required = [result for result in results if result.returncode != 0 and result.required]
    return 1 if failed_required else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily Alpha Persona Lab data refresh.")
    parser.add_argument("--jobs", default="all", help="all, corpus, theme, or comma-separated subset")
    parser.add_argument("--workers", type=int, default=3, help="parallel source/Codex workers")
    parser.add_argument("--theme-profile", choices=["codex", "light", "skip"], default="codex")
    parser.add_argument("--markets", default="US,TW,TWO")
    parser.add_argument("--force-check", action="store_true", help="force source checks even if today's marker exists")
    parser.add_argument("--auto-asr", action="store_true", help="allow daily jobs to transcribe newest missing audio")
    parser.add_argument("--source-limit", type=int, default=60, help="ThemeMiner source rows per shard; 0 means all")
    parser.add_argument("--max-urls-per-symbol", type=int, default=2)
    parser.add_argument("--discovery-batch-size", type=int, default=16)
    parser.add_argument("--thesis-batch-size", type=int, default=12)
    parser.add_argument("--agent-batch-size", type=int, default=24, help="batch size used by light bootstrap mode")
    parser.add_argument("--price-symbol-limit", type=int, default=None, help="light mode price refresh cap")
    parser.add_argument("--refresh-agent-cache", action="store_true")
    parser.add_argument("--refresh-source-pages", action="store_true")
    parser.add_argument("--skip-source-fetch", action="store_true")
    parser.add_argument("--skip-profile-upgrade", action="store_true")
    parser.add_argument("--allow-overlap", action="store_true", help="do not take the repo-level daily update lock")
    args = parser.parse_args()

    tag = run_tag()
    log_dir = LOG_ROOT / tag
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = RUNTIME_DIR / "daily_update.lock"
    summary_path = RUNTIME_DIR / "latest_run.json"
    env = base_env()

    lock_handle = lock_path.open("w", encoding="utf-8")
    if not args.allow_overlap:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            payload = {
                "schema_version": "alpha_persona_lab_daily_update_v1",
                "started_at": utc_now(),
                "status": "skipped_overlap",
                "lock_path": str(lock_path),
            }
            write_json(summary_path, payload)
            print(f"daily update already running; lock={lock_path}", flush=True)
            return 0

    wanted = selected_jobs(args.jobs)
    all_results: list[JobResult] = []
    started_at = utc_now()
    status = "ok"
    try:
        if "corpus" in wanted:
            all_results.extend(run_parallel(corpus_jobs(args), env=env, log_dir=log_dir, workers=args.workers))
        if "theme" in wanted:
            all_results.extend(run_sequential(theme_jobs(args), env=env, log_dir=log_dir))
        exit_code = fail_if_needed(all_results)
        status = "failed" if exit_code else "ok"
        return exit_code
    except Exception:
        status = "failed"
        raise
    finally:
        payload = {
            "schema_version": "alpha_persona_lab_daily_update_v1",
            "started_at": started_at,
            "finished_at": utc_now(),
            "status": status,
            "jobs": sorted(wanted),
            "workers": args.workers,
            "theme_profile": args.theme_profile,
            "log_dir": str(log_dir),
            "results": [result_payload(result) for result in all_results],
        }
        write_json(summary_path, payload)
        write_json(log_dir / "summary.json", payload)
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
