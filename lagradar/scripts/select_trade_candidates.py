#!/usr/bin/env python3
"""Select trade candidates with a mandatory peer challenge.

This is the recommendation gate for Lagradar. It collapses duplicate
theme-candidate rows into one row per symbol, filters for improving laggards,
then prints a challenger table so a final pick must beat same-theme peers
instead of winning because it was the first plausible story found.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_STATUSES = {"improving_laggard", "early_turn_laggard"}
WATCH_STATUSES = {"improving_laggard", "early_turn_laggard", "sleeping_laggard"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fmt(value: Any, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "Y" if value else "N"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def pct(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.1f}%"
    return str(value)


def unique(values: list[Any], *, limit: int | None = None) -> list[Any]:
    seen: set[str] = set()
    output: list[Any] = []
    for value in values:
        if value in (None, "", []):
            continue
        key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, dict) else str(value)
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
        if limit is not None and len(output) >= limit:
            break
    return output


def quality_bonus(row: dict[str, Any]) -> float:
    confidence = str(row.get("relation_confidence") or "")
    source_quality = str(row.get("source_quality") or "")
    bonus = 0.0
    if "high_manual" in confidence:
        bonus += 11.0
    elif "high_profiled" in confidence:
        bonus += 5.0
    elif "medium" in confidence:
        bonus += 0.0
    elif "low" in confidence:
        bonus -= 10.0
    if row.get("manual_thesis_override"):
        bonus += 3.0
    agent_status = str(row.get("agent_status") or "")
    if agent_status == "agent_applied":
        bonus += 4.0
    elif agent_status == "manual_override":
        bonus += 2.0
    elif agent_status.startswith("agent_unavailable") or agent_status == "agent_failed_or_unusable":
        bonus -= 6.0
    elif agent_status == "not_requested":
        bonus -= 4.0
    if "fallback" in source_quality or "unknown" == source_quality:
        bonus -= 3.0
    if not row.get("thesis_label"):
        bonus -= 4.0
    bonus += thesis_specificity_bonus(row)
    if str(row.get("ai_chain_position") or "").startswith("No explicit"):
        bonus -= 3.0
    return bonus


def thesis_specificity_bonus(row: dict[str, Any]) -> float:
    """Reward agent/manual thesis cards and penalize generic auto mappings."""

    label = str(row.get("thesis_label") or "")
    if not label:
        return -6.0
    parts = [part.strip() for part in label.replace("／", "/").split("/") if part.strip()]
    unique_parts = set(parts)
    penalty = 0.0
    if len(unique_parts) < len(parts):
        penalty -= 4.0
    agent_status = str(row.get("agent_status") or "")
    is_semantic = bool(row.get("manual_thesis_override")) or agent_status in {"agent_applied", "manual_override"}
    if not is_semantic and len(parts) <= 2:
        penalty -= 6.0
    risk_text = " ".join(str(item) for item in (row.get("thesis_risks") or row.get("risk_flags") or []))
    if "auto profile" in risk_text or "verify product purity" in risk_text:
        penalty -= 5.0
    if row.get("manual_thesis_override"):
        penalty += 5.0
    if agent_status == "agent_applied":
        penalty += 4.0
    if len(row.get("business_segments") or []) >= 2:
        penalty += 2.0
    if len(label) >= 18 and len(unique_parts) >= 2:
        penalty += 1.0
    return penalty


def selection_score(row: dict[str, Any]) -> float:
    score = float(row.get("candidate_score") or 0.0)
    score += quality_bonus(row)
    if row.get("status") == "improving_laggard":
        score += 4.0
    elif row.get("status") == "early_turn_laggard":
        score += 1.5
    elif row.get("status") == "sleeping_laggard":
        score -= 7.0
    elif row.get("status") == "already_caught_up":
        score -= 15.0
    elif row.get("status") == "overheated_catchup":
        score -= 25.0
    score -= max(float(row.get("overheat_score") or 0.0) - 1.2, 0.0) * 6.0
    if (row.get("ma20_distance_pct") or 0.0) > 18.0:
        score -= 6.0
    if row.get("near_20d_high"):
        score += 1.5
    if row.get("volume_ratio_20d") and row["volume_ratio_20d"] >= 1.2:
        score += 1.0
    return round(score, 2)


def collapse_candidates(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_symbol: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = row.get("symbol")
        if not symbol:
            continue
        row = dict(row)
        row["_selection_score"] = selection_score(row)
        if symbol not in by_symbol:
            by_symbol[symbol] = row
            by_symbol[symbol]["theme_ids"] = [row.get("theme_id")]
            by_symbol[symbol]["theme_labels"] = [row.get("theme_label")]
            by_symbol[symbol]["all_rows"] = [row]
            continue
        existing = by_symbol[symbol]
        existing["all_rows"].append(row)
        existing["theme_ids"] = unique(existing.get("theme_ids", []) + [row.get("theme_id")], limit=24)
        existing["theme_labels"] = unique(existing.get("theme_labels", []) + [row.get("theme_label")], limit=24)
        if row["_selection_score"] > existing.get("_selection_score", -999999):
            carried = {
                "theme_ids": existing["theme_ids"],
                "theme_labels": existing["theme_labels"],
                "all_rows": existing["all_rows"],
            }
            existing.clear()
            existing.update(row)
            existing.update(carried)
    for row in by_symbol.values():
        # Preserve the strongest metrics across duplicate theme rows.
        rows_for_symbol = row.get("all_rows", [])
        row["max_candidate_score"] = max((item.get("candidate_score") or 0.0) for item in rows_for_symbol)
        row["max_selection_score"] = max((item.get("_selection_score") or 0.0) for item in rows_for_symbol)
        row["best_statuses"] = unique([item.get("status") for item in rows_for_symbol], limit=8)
    return by_symbol


def parse_symbols(value: str | None, more: list[str] | None) -> set[str]:
    symbols: set[str] = set()
    for chunk in ([value] if value else []) + (more or []):
        if not chunk:
            continue
        for item in chunk.replace("，", ",").split(","):
            text = item.strip().upper()
            if text:
                symbols.add(text)
    return symbols


def filter_rows(
    rows: list[dict[str, Any]],
    *,
    markets: set[str],
    theme_key: str | None,
    statuses: set[str],
    max_overheat: float,
    min_score: float,
) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        if markets and str(row.get("market") or "").upper() not in markets:
            continue
        if theme_key:
            key = theme_key.lower()
            if key not in str(row.get("theme_id") or "").lower() and key not in str(row.get("theme_label") or "").lower():
                continue
        if statuses and row.get("status") not in statuses:
            continue
        if (row.get("overheat_score") or 0.0) > max_overheat:
            continue
        if (row.get("_selection_score") or 0.0) < min_score:
            continue
        output.append(row)
    return output


def row_themes(row: dict[str, Any]) -> set[str]:
    return {str(item) for item in row.get("theme_ids", []) if item}


def peers_for(target: dict[str, Any], rows: list[dict[str, Any]], symbol_map: dict[str, dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    target_symbol = target.get("symbol")
    target_themes = row_themes(target)
    explicit_peers = {str(item).upper() for item in target.get("peer_symbols", []) if item}
    peers: list[dict[str, Any]] = [target]
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol or symbol == target_symbol:
            continue
        shared_theme = bool(target_themes & row_themes(row))
        explicit = symbol in explicit_peers
        if shared_theme or explicit:
            peer = dict(row)
            peer["_shared_theme_count"] = len(target_themes & row_themes(row))
            peer["_explicit_peer"] = explicit
            peers.append(peer)
    for symbol in explicit_peers:
        if symbol in symbol_map and all(item.get("symbol") != symbol for item in peers):
            peer = dict(symbol_map[symbol])
            peer["_shared_theme_count"] = len(target_themes & row_themes(peer))
            peer["_explicit_peer"] = True
            peers.append(peer)
    peers.sort(
        key=lambda item: (
            item.get("symbol") == target_symbol,
            item.get("_explicit_peer", False),
            item.get("_shared_theme_count", 0),
            item.get("_selection_score", -999999),
        ),
        reverse=True,
    )
    return peers[:limit]


def why_against(target: dict[str, Any], row: dict[str, Any]) -> str:
    if row.get("symbol") == target.get("symbol"):
        return "focus"
    reasons: list[str] = []
    delta = (row.get("_selection_score") or 0.0) - (target.get("_selection_score") or 0.0)
    if delta > 5:
        reasons.append("score stronger")
    elif delta < -5:
        reasons.append("score weaker")
    if (row.get("overheat_score") or 0.0) > (target.get("overheat_score") or 0.0) + 0.8:
        reasons.append("hotter")
    elif (row.get("overheat_score") or 0.0) + 0.8 < (target.get("overheat_score") or 0.0):
        reasons.append("cleaner heat")
    if (row.get("turning_score") or 0.0) > (target.get("turning_score") or 0.0) + 1.0:
        reasons.append("better turn")
    elif (row.get("turning_score") or 0.0) + 1.0 < (target.get("turning_score") or 0.0):
        reasons.append("weaker turn")
    if row.get("relation_confidence") != target.get("relation_confidence"):
        reasons.append(str(row.get("relation_confidence") or "no thesis"))
    if not reasons:
        reasons.append("similar peer")
    return ", ".join(reasons[:4])


def trigger_for(row: dict[str, Any]) -> str:
    close = row.get("close")
    if row.get("breakout_20d"):
        return "hold breakout; add only on tight pullback above 5D/10D MA"
    if row.get("near_20d_high"):
        return "break 20D high or pullback holds 5D/10D MA"
    if row.get("above_ma5") and row.get("above_ma10"):
        return "reclaim/hold 20D MA with volume > 1.2x"
    return "wait for 5D/10D MA reclaim plus volume confirmation"


def invalidation_for(row: dict[str, Any]) -> str:
    if row.get("above_ma20"):
        return "close below 10D/20D MA or leader basket rolls over"
    return "fails to reclaim 20D MA, or breaks recent reaction low"


def render_candidate_block(target: dict[str, Any], peers: list[dict[str, Any]]) -> list[str]:
    lines = [
        f"### {target.get('symbol')} {target.get('name')} - {target.get('thesis_label') or target.get('theme_label')}",
        "",
        f"- Pick score: {fmt(target.get('_selection_score'))}; status: {target.get('status')}; asof: {target.get('asof')}; close: {fmt(target.get('close'))}",
        f"- Themes: {', '.join(str(item) for item in target.get('theme_labels', [])[:6])}",
        f"- Chain: {target.get('ai_chain_position') or '-'}",
        f"- Trigger: {trigger_for(target)}",
        f"- Invalidation: {invalidation_for(target)}",
    ]
    leaders = target.get("leader_indicators") or []
    if leaders:
        lines.append(f"- Leader indicators: {', '.join(str(item) for item in leaders[:8])}")
    risks = target.get("thesis_risks") or target.get("risk_flags") or []
    if risks:
        lines.append(f"- Key risks: {', '.join(str(item) for item in risks[:4])}")
    lines.extend(
        [
            "",
            "| Challenger | Market | Score | Status | r5 | r20 | Gap20 | Turn | Heat | Thesis | Why vs focus |",
            "|---|---|---:|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in peers:
        lines.append(
            "| "
            f"`{row.get('symbol')}` {row.get('name')} | {row.get('market') or '-'} | {fmt(row.get('_selection_score'))} | "
            f"{row.get('status')} | {pct(row.get('r5'))} | {pct(row.get('r20'))} | {pct(row.get('lag_gap_20d'))} | "
            f"{fmt(row.get('turning_score'), 2)} | {fmt(row.get('overheat_score'), 2)} | "
            f"{row.get('thesis_label') or row.get('theme_label') or '-'} | {why_against(target, row)} |"
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Select Lagradar trade candidates with peer challenge")
    parser.add_argument("--output-dir", default="lagradar/output")
    parser.add_argument("--market", action="append", help="Market filter such as TW or US; can repeat")
    parser.add_argument("--theme", help="Theme id or label substring")
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--symbol", action="append", help="Force one or more symbols into the peer challenge")
    parser.add_argument("--symbols", help="Comma-separated symbols to force into the peer challenge")
    parser.add_argument("--include-sleeping", action="store_true")
    parser.add_argument("--all-status", action="store_true")
    parser.add_argument("--max-overheat", type=float, default=2.2)
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--write-md", help="Optional output markdown path")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    raw_candidates = read_json(output_dir / "laggard_candidates.json")
    collapsed = collapse_candidates(raw_candidates)
    all_rows = list(collapsed.values())
    forced_symbols = parse_symbols(args.symbols, args.symbol)
    markets = {item.upper() for item in (args.market or [])}
    statuses: set[str] = set()
    if not args.all_status:
        statuses = set(WATCH_STATUSES if args.include_sleeping else DEFAULT_STATUSES)

    filtered = filter_rows(
        all_rows,
        markets=markets,
        theme_key=args.theme,
        statuses=statuses,
        max_overheat=args.max_overheat,
        min_score=args.min_score,
    )
    filtered.sort(key=lambda row: row.get("_selection_score", -999999), reverse=True)

    selected: list[dict[str, Any]] = []
    for symbol in forced_symbols:
        if symbol in collapsed:
            selected.append(collapsed[symbol])
    for row in filtered:
        if all(row.get("symbol") != item.get("symbol") for item in selected):
            selected.append(row)
        if len(selected) >= args.top:
            break
    selected.sort(key=lambda row: row.get("_selection_score", -999999), reverse=True)

    lines = [
        "# Lagradar Peer-Challenge Selection",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"Universe: {len(all_rows)} collapsed symbols; filtered: {len(filtered)}; statuses: {', '.join(sorted(statuses)) if statuses else 'all'}",
        "",
        "## Shortlist",
        "",
        "| Rank | Symbol | Market | Pick Score | Status | r5 | r20 | Turn | Heat | Thesis | Trigger |",
        "|---:|---|---|---:|---|---:|---:|---:|---:|---|---|",
    ]
    for idx, row in enumerate(selected, start=1):
        lines.append(
            f"| {idx} | `{row.get('symbol')}` {row.get('name')} | {row.get('market') or '-'} | {fmt(row.get('_selection_score'))} | "
            f"{row.get('status')} | {pct(row.get('r5'))} | {pct(row.get('r20'))} | {fmt(row.get('turning_score'), 2)} | "
            f"{fmt(row.get('overheat_score'), 2)} | {row.get('thesis_label') or row.get('theme_label') or '-'} | {trigger_for(row)} |"
        )
    lines.extend(["", "## Peer Challenge", ""])
    for target in selected:
        peers = peers_for(target, all_rows, collapsed, limit=9)
        lines.extend(render_candidate_block(target, peers))
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    if args.write_md:
        write_text(Path(args.write_md), text)
        print(f"Wrote peer-challenge selection to {args.write_md}")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
