#!/usr/bin/env python3
"""Run a full Codex-agent ThemeMiner/Lagradar refresh.

This supervisor uses local `codex exec` as the semantic judge, so it does not
require THEMEMINER_AGENT_API_KEY/OPENAI_API_KEY. It batches company/concept
judgment where supported and shards source fetching for parallelism.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "thememiner/output/logs"


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def py() -> str:
    venv_python = ROOT / ".venv/bin/python"
    return str(venv_python) if venv_python.exists() else sys.executable


def run(cmd: list[str], *, env: dict[str, str], log_name: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / log_name
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(cmd) + "\n\n")
        log.flush()
        subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    print(f"ok {log_path}")


def run_parallel(commands: list[tuple[list[str], str]], *, env: dict[str, str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    processes = []
    for cmd, log_name in commands:
        log_path = LOG_DIR / log_name
        handle = log_path.open("w", encoding="utf-8")
        handle.write("$ " + " ".join(cmd) + "\n\n")
        handle.flush()
        process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT)
        processes.append((process, handle, log_path))
        print(f"started {process.pid} {log_path}")
    failed = []
    for process, handle, log_path in processes:
        code = process.wait()
        handle.close()
        if code:
            failed.append((code, log_path))
        else:
            print(f"ok {log_path}")
    if failed:
        detail = ", ".join(f"{path} exit={code}" for code, path in failed)
        raise RuntimeError(f"parallel step failed: {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Full ThemeMiner/Lagradar refresh using local Codex agents")
    parser.add_argument("--workers", type=int, default=3, help="parallel codex/source workers")
    parser.add_argument("--markets", default="US,TW,TWO")
    parser.add_argument("--discovery-batch-size", type=int, default=16)
    parser.add_argument("--thesis-batch-size", type=int, default=12)
    parser.add_argument("--source-limit", type=int, default=0, help="source queue rows per shard; 0 means all")
    parser.add_argument("--max-urls-per-symbol", type=int, default=2)
    parser.add_argument("--refresh-agent-cache", action="store_true")
    parser.add_argument("--refresh-source-pages", action="store_true")
    parser.add_argument("--skip-source-fetch", action="store_true")
    parser.add_argument("--skip-profile-upgrade", action="store_true")
    args = parser.parse_args()

    tag = now_tag()
    workers = max(1, args.workers)
    env = os.environ.copy()
    env["THEMEMINER_AGENT_PROVIDER"] = "codex"
    env.setdefault("THEMEMINER_AGENT_TIMEOUT", "240")
    env.setdefault("PYTHONPATH", str(ROOT / "thememiner/scripts"))

    agent_refresh = ["--agent-refresh"] if args.refresh_agent_cache else []

    run(
        [
            sys.executable,
            "thememiner/scripts/discover_market_universe.py",
            "--markets",
            args.markets,
            "--agent-mode",
            "on",
            "--agent-provider",
            "codex",
            "--agent-workers",
            str(workers),
            "--agent-batch-size",
            str(args.discovery_batch_size),
            *agent_refresh,
        ],
        env=env,
        log_name=f"codex_refresh_{tag}_01_discovery.log",
    )
    run(
        [sys.executable, "thememiner/scripts/update_theme_graph.py", "--refresh-prices", "--refresh-news"],
        env=env,
        log_name=f"codex_refresh_{tag}_02_graph.log",
    )

    if not args.skip_source_fetch:
        source_cmds = []
        for index in range(workers):
            cmd = [
                py(),
                "thememiner/scripts/scrapling_source_fetcher.py",
                "--limit",
                str(args.source_limit),
                "--shard",
                f"{index}/{workers}",
                "--max-urls-per-symbol",
                str(args.max_urls_per_symbol),
                "--queue-output",
                f"thememiner/output/profile_upgrade_queue.shard{index}.json",
                "--evidence-output",
                f"thememiner/output/company_source_evidence.shard{index}.jsonl",
                "--report-output",
                f"thememiner/output/source_fetch_report.shard{index}.md",
                "--stream-evidence",
                "--agent-mode",
                "on",
                "--agent-provider",
                "codex",
            ]
            if args.refresh_source_pages:
                cmd.append("--refresh")
            if args.refresh_agent_cache:
                cmd.append("--agent-refresh")
            source_cmds.append((cmd, f"codex_refresh_{tag}_03_source_shard{index}.log"))
        run_parallel(source_cmds, env=env)
        run(
            [sys.executable, "thememiner/scripts/merge_source_evidence.py"],
            env=env,
            log_name=f"codex_refresh_{tag}_04_merge_source.log",
        )

    if not args.skip_profile_upgrade:
        upgrade_dir = ROOT / "thememiner/data/profile_upgrades"
        upgrade_dir.mkdir(parents=True, exist_ok=True)
        upgrade_cmds = []
        for index in range(workers):
            upgrade_cmds.append(
                (
                    [
                        sys.executable,
                        "thememiner/scripts/upgrade_company_profiles_official.py",
                        "--shard",
                        f"{index}/{workers}",
                        "--output",
                        f"thememiner/data/profile_upgrades/codex_agent_shard{index}.json",
                    ],
                    f"codex_refresh_{tag}_05_profile_shard{index}.log",
                )
            )
        run_parallel(upgrade_cmds, env=env)
        run(
            [sys.executable, "thememiner/scripts/merge_company_profile_shards.py"],
            env=env,
            log_name=f"codex_refresh_{tag}_06_merge_profiles.log",
        )
        run(
            [sys.executable, "thememiner/scripts/update_theme_graph.py", "--refresh-prices", "--refresh-news"],
            env=env,
            log_name=f"codex_refresh_{tag}_07_graph_after_profiles.log",
        )

    run(
        [
            sys.executable,
            "thememiner/scripts/build_company_thesis_cards.py",
            "--agent-mode",
            "on",
            "--agent-provider",
            "codex",
            "--agent-workers",
            str(workers),
            "--agent-batch-size",
            str(args.thesis_batch_size),
            *agent_refresh,
        ],
        env=env,
        log_name=f"codex_refresh_{tag}_08_thesis_cards.log",
    )
    run(
        [sys.executable, "lagradar/scripts/scan_laggards.py"],
        env=env,
        log_name=f"codex_refresh_{tag}_09_lagradar_scan.log",
    )
    run(
        [sys.executable, "lagradar/scripts/build_lagradar_html.py"],
        env=env,
        log_name=f"codex_refresh_{tag}_10_lagradar_html.log",
    )
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
