#!/usr/bin/env python3
"""Query Lagradar outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: Any, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Query Lagradar candidates")
    parser.add_argument("--output-dir", default="lagradar/output")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--theme", help="theme id or label substring")
    parser.add_argument("--market", action="append", help="market filter such as US, JP, TW, CN, HK, KR; can be repeated")
    parser.add_argument(
        "--status",
        action="append",
        help="candidate status filter; can be repeated",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    candidates = read_json(output_dir / "laggard_candidates.json")
    themes = read_json(output_dir / "theme_scores.json")

    theme_rows = themes
    if args.theme:
        key = args.theme.lower()
        theme_rows = [row for row in theme_rows if key in row["theme_id"].lower() or key in row["label"].lower()]

    print("Theme heat:")
    for idx, row in enumerate(theme_rows[:12], start=1):
        print(
            f"{idx}. {row['label']} ({row['theme_id']}) heat={fmt(row['theme_heat'])} "
            f"leader20={fmt(row['leader_20d_median'])}% leader60={fmt(row['leader_60d_median'])}% "
            f"diffusion={fmt(row.get('diffusion_score'))} stage={row.get('lifecycle_stage', '-')}"
        )
    print()

    rows = candidates
    if args.theme:
        key = args.theme.lower()
        rows = [row for row in rows if key in row["theme_id"].lower() or key in row["theme_label"].lower()]
    if args.market:
        allowed_markets = {market.upper() for market in args.market}
        rows = [row for row in rows if str(row.get("market", "")).upper() in allowed_markets]
    pre_status_rows = rows
    explicit_status = bool(args.status)
    allowed_status = set(args.status or ["improving_laggard", "early_turn_laggard", "sleeping_laggard"])
    rows = [row for row in rows if row.get("status") in allowed_status]
    if not rows and not explicit_status and pre_status_rows:
        print("No clean improving/early/sleeping laggards after filters; showing highest-scored names for context.")
        rows = pre_status_rows

    print("Laggard candidates:")
    for idx, row in enumerate(rows[: args.top], start=1):
        print(
            f"{idx}. {row['name']} {row['symbol']} | {row['theme_label']} | {row['status']} | "
            f"score={fmt(row['candidate_score'])} gap20={fmt(row['lag_gap_20d'])}% "
            f"r5={fmt(row['r5'])}% r20={fmt(row['r20'])}% turn={fmt(row['turning_score'], 2)} "
            f"heat={fmt(row.get('overheat_score'), 2)} vol={fmt(row['volume_ratio_20d'], 2)}x "
            f"near20h={bool(row.get('near_20d_high'))} stage={row.get('lifecycle_stage', '-')}"
        )
        if row.get("primary_business") or row.get("specializations"):
            specs = ", ".join((row.get("specializations") or [])[:3]) or "-"
            print(f"   business: {row.get('primary_business') or '-'} | specs: {specs}")
        if row.get("relation_paths"):
            print(f"   path: {' / '.join(row['relation_paths'][:3])}")
        bottleneck = row.get("bottleneck_profile") or {}
        if bottleneck:
            parts = [
                bottleneck.get("layer"),
                f"scarcity={bottleneck.get('scarcity')}" if bottleneck.get("scarcity") else "",
                f"sub={bottleneck.get('substitutability')}" if bottleneck.get("substitutability") else "",
                f"discovery={bottleneck.get('discovery_state')}" if bottleneck.get("discovery_state") else "",
            ]
            print(f"   bottleneck: {' | '.join(part for part in parts if part)}")
        print(
            f"   trigger: watch for continuation above short MAs / 20d high; invalidation: lose MA5/MA10 or leader basket rolls over."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
