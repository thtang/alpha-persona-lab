#!/usr/bin/env python3
"""Backtest medium-horizon theme diffusion from leaders to followers.

This is a research backtest, not an execution engine. It asks whether leader
returns over a lookback window contain information about follower returns over
future 5D/10D/20D/40D horizons.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


LEADER_ROLES = {"global_leader", "regional_leader", "high_beta_leader"}
FOLLOWER_ROLES = {"core_follower", "laggard_watch", "concept_only"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_symbol(symbol: str) -> str:
    return (
        symbol.replace("^", "INDEX_")
        .replace("=", "_")
        .replace("/", "_")
        .replace(".", "_")
        .replace("-", "_")
    )


def pct_change(close: float | None, previous: float | None) -> float | None:
    if close is None or previous in (None, 0):
        return None
    value = (close / previous - 1.0) * 100.0
    return value if math.isfinite(value) else None


def mean(values: list[float]) -> float | None:
    values = [value for value in values if value is not None and math.isfinite(value)]
    return sum(values) / len(values) if values else None


def median(values: list[float]) -> float | None:
    values = [value for value in values if value is not None and math.isfinite(value)]
    return statistics.median(values) if values else None


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda idx: values[idx])
    output = [0.0] * len(values)
    idx = 0
    while idx < len(order):
        end = idx + 1
        while end < len(order) and values[order[end]] == values[order[idx]]:
            end += 1
        rank = (idx + end + 1) / 2.0
        for pos in range(idx, end):
            output[order[pos]] = rank
        idx = end
    return output


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 10 or len(xs) != len(ys):
        return None
    corr = float(np.corrcoef(np.array(xs), np.array(ys))[0, 1])
    return corr if math.isfinite(corr) else None


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 10 or len(xs) != len(ys):
        return None
    return pearson(ranks(xs), ranks(ys))


def quantile(values: list[float], q: float) -> float | None:
    values = sorted(value for value in values if value is not None and math.isfinite(value))
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q
    low = int(math.floor(pos))
    high = int(math.ceil(pos))
    if low == high:
        return values[low]
    return values[low] * (high - pos) + values[high] * (pos - low)


def load_history(symbol: str, history_dir: Path) -> list[dict[str, Any]]:
    path = history_dir / f"{safe_symbol(symbol)}.json"
    if not path.exists():
        return []
    data = read_json(path)
    return data.get("rows") or []


def build_return_maps(rows: list[dict[str, Any]], windows: set[int]) -> dict[str, dict[int, dict[str, float]]]:
    rows = [row for row in rows if row.get("adjclose") is not None]
    rows.sort(key=lambda row: row["date"])
    closes = [float(row["adjclose"]) for row in rows]
    dates = [row["date"] for row in rows]
    past: dict[int, dict[str, float]] = {window: {} for window in windows}
    future: dict[int, dict[str, float]] = {window: {} for window in windows}
    for idx, date in enumerate(dates):
        for window in windows:
            if idx - window >= 0:
                value = pct_change(closes[idx], closes[idx - window])
                if value is not None:
                    past[window][date] = value
            if idx + window < len(closes):
                value = pct_change(closes[idx + window], closes[idx])
                if value is not None:
                    future[window][date] = value
    return {"past": past, "future": future}


def basket_value(
    symbols: list[str],
    return_maps: dict[str, dict[str, dict[int, dict[str, float]]]],
    direction: str,
    window: int,
    date: str,
    min_count: int,
) -> tuple[float | None, int, list[dict[str, Any]]]:
    values: list[float] = []
    members: list[dict[str, Any]] = []
    for symbol in symbols:
        value = return_maps.get(symbol, {}).get(direction, {}).get(window, {}).get(date)
        if value is None:
            continue
        values.append(value)
        members.append({"symbol": symbol, "return_pct": round(value, 4)})
    if len(values) < min_count:
        return None, len(values), members
    return mean(values), len(values), members


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def run_backtest(
    seed: dict[str, Any],
    history_dir: Path,
    output_dir: Path,
    lookbacks: list[int],
    horizons: list[int],
    leader_threshold_pct: float,
    gap_threshold_pct: float,
    turn_threshold_pct: float,
    cost_bps: float,
    min_leaders: int,
    min_followers: int,
    include_event_members: bool,
) -> dict[str, Any]:
    windows = set(lookbacks + horizons + [5])
    all_symbols = sorted({node["symbol"] for theme in seed["themes"] for node in theme.get("nodes", [])})
    return_maps: dict[str, dict[str, dict[int, dict[str, float]]]] = {}
    availability: dict[str, dict[str, Any]] = {}
    for symbol in all_symbols:
        rows = load_history(symbol, history_dir)
        if not rows:
            availability[symbol] = {"symbol": symbol, "status": "missing"}
            continue
        return_maps[symbol] = build_return_maps(rows, windows)
        availability[symbol] = {
            "symbol": symbol,
            "status": "ok",
            "row_count": len(rows),
            "first_date": rows[0]["date"],
            "last_date": rows[-1]["date"],
        }

    summary_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    round_trip_cost_pct = 2.0 * cost_bps / 100.0

    for theme in seed["themes"]:
        leaders = [node["symbol"] for node in theme["nodes"] if node.get("role") in LEADER_ROLES]
        followers = [
            node["symbol"]
            for node in theme["nodes"]
            if node.get("role") in FOLLOWER_ROLES or node.get("market") not in {"US"}
        ]
        leaders = [symbol for symbol in leaders if symbol in return_maps]
        followers = [symbol for symbol in followers if symbol in return_maps and symbol not in leaders]
        if not leaders or not followers:
            continue

        dates = sorted(
            set().union(
                *[
                    set(return_maps[symbol]["past"][min(lookbacks)].keys())
                    | set(return_maps[symbol]["future"][min(horizons)].keys())
                    for symbol in leaders + followers
                ]
            )
        )

        for lookback in lookbacks:
            for horizon in horizons:
                observations: list[dict[str, Any]] = []
                for date in dates:
                    leader_signal, leader_count, leader_members = basket_value(
                        leaders, return_maps, "past", lookback, date, min_leaders
                    )
                    if leader_signal is None:
                        continue
                    follower_past, follower_past_count, _ = basket_value(
                        followers, return_maps, "past", lookback, date, min_followers
                    )
                    follower_turn, _, _ = basket_value(followers, return_maps, "past", 5, date, min_followers)
                    follower_future, follower_future_count, follower_members = basket_value(
                        followers, return_maps, "future", horizon, date, min_followers
                    )
                    if follower_future is None or follower_past is None:
                        continue
                    gap = leader_signal - follower_past
                    observations.append(
                        {
                            "date": date,
                            "leader_signal_pct": leader_signal,
                            "follower_past_pct": follower_past,
                            "lag_gap_pct": gap,
                            "follower_turn_5d_pct": follower_turn,
                            "follower_future_pct": follower_future,
                            "leader_count": leader_count,
                            "follower_past_count": follower_past_count,
                            "follower_future_count": follower_future_count,
                            "leaders": leader_members[:8],
                            "followers": follower_members[:12],
                        }
                    )

                if len(observations) < 30:
                    continue

                xs = [row["leader_signal_pct"] for row in observations]
                ys = [row["follower_future_pct"] for row in observations]
                gaps = [row["lag_gap_pct"] for row in observations]
                threshold_q80 = quantile(xs, 0.8)
                top_rows = [row for row in observations if threshold_q80 is not None and row["leader_signal_pct"] >= threshold_q80]
                event_candidates = [
                    row
                    for row in observations
                    if row["leader_signal_pct"] >= leader_threshold_pct
                    and row["lag_gap_pct"] >= gap_threshold_pct
                    and (row.get("follower_turn_5d_pct") is None or row["follower_turn_5d_pct"] >= turn_threshold_pct)
                ]
                event_after_cost = [row["follower_future_pct"] - round_trip_cost_pct for row in event_candidates]
                event_hit_rate = mean([1.0 if value > 0 else 0.0 for value in event_after_cost])
                top_future = [row["follower_future_pct"] for row in top_rows]
                base_avg = mean(ys)
                top_avg = mean(top_future)
                event_avg = mean(event_after_cost)
                row = {
                    "theme_id": theme["theme_id"],
                    "label": theme["label"],
                    "lookback_days": lookback,
                    "horizon_days": horizon,
                    "obs": len(observations),
                    "first_date": observations[0]["date"],
                    "last_date": observations[-1]["date"],
                    "leader_count": len(leaders),
                    "follower_count": len(followers),
                    "pearson_ic": pearson(xs, ys),
                    "spearman_ic": spearman(xs, ys),
                    "base_avg_future_pct": base_avg,
                    "top_quintile_avg_future_pct": top_avg,
                    "top_minus_base_pct": (top_avg - base_avg) if top_avg is not None and base_avg is not None else None,
                    "avg_lag_gap_pct": mean(gaps),
                    "event_count": len(event_candidates),
                    "event_avg_after_cost_pct": event_avg,
                    "event_median_after_cost_pct": median(event_after_cost),
                    "event_hit_rate": event_hit_rate,
                    "event_threshold_leader_pct": leader_threshold_pct,
                    "event_threshold_gap_pct": gap_threshold_pct,
                    "round_trip_cost_pct": round_trip_cost_pct,
                }
                summary_rows.append(row)

                for event in event_candidates:
                    event_row = {
                        "theme_id": theme["theme_id"],
                        "label": theme["label"],
                        "lookback_days": lookback,
                        "horizon_days": horizon,
                        "date": event["date"],
                        "leader_signal_pct": round(event["leader_signal_pct"], 4),
                        "follower_past_pct": round(event["follower_past_pct"], 4),
                        "lag_gap_pct": round(event["lag_gap_pct"], 4),
                        "follower_turn_5d_pct": None
                        if event["follower_turn_5d_pct"] is None
                        else round(event["follower_turn_5d_pct"], 4),
                        "follower_future_pct": round(event["follower_future_pct"], 4),
                        "follower_future_after_cost_pct": round(event["follower_future_pct"] - round_trip_cost_pct, 4),
                        "leader_count": event["leader_count"],
                        "follower_count": event["follower_future_count"],
                    }
                    if include_event_members:
                        event_row["leaders"] = event["leaders"]
                        event_row["followers"] = event["followers"]
                    event_rows.append(event_row)

    summary_rows.sort(
        key=lambda row: (
            row.get("event_avg_after_cost_pct") if row.get("event_avg_after_cost_pct") is not None else -999,
            row.get("top_minus_base_pct") if row.get("top_minus_base_pct") is not None else -999,
        ),
        reverse=True,
    )
    event_rows.sort(key=lambda row: (row["theme_id"], row["date"], row["lookback_days"], row["horizon_days"]))

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "theme_lead_lag_summary.csv"
    fieldnames = [
        "theme_id",
        "label",
        "lookback_days",
        "horizon_days",
        "obs",
        "first_date",
        "last_date",
        "leader_count",
        "follower_count",
        "pearson_ic",
        "spearman_ic",
        "base_avg_future_pct",
        "top_quintile_avg_future_pct",
        "top_minus_base_pct",
        "avg_lag_gap_pct",
        "event_count",
        "event_avg_after_cost_pct",
        "event_median_after_cost_pct",
        "event_hit_rate",
        "event_threshold_leader_pct",
        "event_threshold_gap_pct",
        "round_trip_cost_pct",
    ]
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow({key: fmt(row.get(key), 6) for key in fieldnames})

    write_json(output_dir / "theme_lead_lag_summary.json", summary_rows)
    with (output_dir / "theme_lead_lag_events.jsonl").open("w", encoding="utf-8") as handle:
        for row in event_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_json(
        output_dir / "backtest_manifest.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "history_dir": str(history_dir),
            "lookbacks": lookbacks,
            "horizons": horizons,
            "leader_threshold_pct": leader_threshold_pct,
            "gap_threshold_pct": gap_threshold_pct,
            "turn_threshold_pct": turn_threshold_pct,
            "cost_bps": cost_bps,
            "round_trip_cost_pct": round_trip_cost_pct,
            "include_event_members": include_event_members,
            "summary_count": len(summary_rows),
            "event_count": len(event_rows),
            "availability": availability,
        },
    )
    write_report(output_dir / "backtest_report.md", summary_rows, event_rows)
    return {"summary": summary_rows, "events": event_rows}


def write_report(path: Path, summary_rows: list[dict[str, Any]], event_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Lagradar Backtest Report",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Best Event Returns",
        "",
        "| Rank | Theme | Lookback | Horizon | Obs | Events | Avg After Cost | Hit Rate | IC | Top-Bottom Edge |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    ranked = [row for row in summary_rows if (row.get("event_count") or 0) >= 5]
    ranked.sort(key=lambda row: row.get("event_avg_after_cost_pct") or -999, reverse=True)
    for idx, row in enumerate(ranked[:30], start=1):
        lines.append(
            f"| {idx} | {row['label']} | {row['lookback_days']} | {row['horizon_days']} | {row['obs']} | "
            f"{row['event_count']} | {fmt(row.get('event_avg_after_cost_pct'))}% | "
            f"{fmt((row.get('event_hit_rate') or 0) * 100)}% | {fmt(row.get('spearman_ic'), 4)} | "
            f"{fmt(row.get('top_minus_base_pct'))}% |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This is a raw research backtest using Yahoo adjusted daily prices.",
            "- Event rule: leader lookback return >= threshold, follower lag gap >= threshold, optional follower 5D turn filter.",
            "- Results are not yet neutralized for market, sector, country, FX, rates, commodity, or own momentum controls.",
            "- Treat strong rows as hypotheses for stricter point-in-time and after-cost validation, not as deployable signals.",
            "",
            f"Total events: {len(event_rows)}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest cross-market theme diffusion")
    parser.add_argument("--seed", default="lagradar/data/cross_market_theme_seed.json")
    parser.add_argument("--history-dir", default="lagradar/data/history/yahoo_1d")
    parser.add_argument("--output-dir", default="lagradar/output/backtests")
    parser.add_argument("--lookbacks", default="5,10,20,40")
    parser.add_argument("--horizons", default="5,10,20,40")
    parser.add_argument("--leader-threshold-pct", type=float, default=5.0)
    parser.add_argument("--gap-threshold-pct", type=float, default=5.0)
    parser.add_argument("--turn-threshold-pct", type=float, default=-100.0)
    parser.add_argument("--cost-bps", type=float, default=15.0)
    parser.add_argument("--min-leaders", type=int, default=1)
    parser.add_argument("--min-followers", type=int, default=2)
    parser.add_argument("--include-event-members", action="store_true")
    args = parser.parse_args()

    seed = read_json(Path(args.seed))
    result = run_backtest(
        seed,
        Path(args.history_dir),
        Path(args.output_dir),
        parse_ints(args.lookbacks),
        parse_ints(args.horizons),
        args.leader_threshold_pct,
        args.gap_threshold_pct,
        args.turn_threshold_pct,
        args.cost_bps,
        args.min_leaders,
        args.min_followers,
        args.include_event_members,
    )
    print(
        f"Wrote {len(result['summary'])} summary rows and {len(result['events'])} events "
        f"to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
