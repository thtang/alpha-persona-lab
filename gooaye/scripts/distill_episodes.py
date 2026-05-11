#!/usr/bin/env python3
"""Validate canonical Gooaye per-episode distillation notes.

This script is intentionally local-only. Full distillation is performed by Codex
subagents reading transcripts and writing ``data/distilled/episode_notes/EP###.json``;
this script verifies those files against ``references/distillation-schema.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = [
    "schema_version",
    "episode",
    "date",
    "episode_archetype",
    "segment_breakdown",
    "market_regime",
    "topics",
    "host_state",
    "investment_logic",
    "trade_observations",
    "qa_views",
    "catalysts",
    "narrative_threads",
    "view_changes",
    "principles",
    "mantras_or_catchphrases",
    "warnings",
    "references",
    "non_tradeable_insights",
    "open_questions",
]

EPISODE_ARCHETYPES = {
    "market_commentary",
    "qa_heavy",
    "single_stock_deep_dive",
    "industry_supply_chain",
    "philosophy",
    "interview",
    "event_response",
    "milestone_or_retrospective",
    "lifestyle",
    "cautionary_tale",
    "business_or_sponsorship",
}
ACTION_BIASES = {
    "buy",
    "sell",
    "hold",
    "hedge",
    "wait",
    "size-up",
    "size-down",
    "trim",
    "scale-out",
    "scale-in",
    "stop-out",
    "pyramid",
    "rotate",
    "unknown",
}
RISK_CONTROL_TYPES = {"stop-loss", "position-size", "diversify", "liquidity", "time-bound", "none"}
CONFIDENCES = {"high", "medium", "low"}
ASSET_TYPES = {"stock", "sector", "index", "theme", "crypto", "macro", "commodity"}
VIEWS = {"bullish", "bearish", "neutral", "conditional", "unstated"}
HORIZONS = {"intraday", "swing", "medium-term", "long-term", "unclear"}
CONSENSUS_LEVELS = {"consensus", "contrarian", "crowded", "overlooked", "unclear"}
TONES = {"serious", "self_deprecating", "sarcastic", "warning", "joke", "promotional"}
QA_CATEGORIES = {
    "investment_operation",
    "personal_finance",
    "career",
    "family",
    "relationships",
    "lifestyle",
    "ethics",
    "tools_platforms",
    "health_mental",
}
CATALYST_CATEGORIES = {
    "monetary_policy",
    "earnings",
    "macro_data",
    "regulation",
    "product_launch",
    "conference",
    "election",
    "black_swan",
    "IPO_or_listing",
    "merger_acquisition",
    "other",
}
THREAD_ROLES = {"originating", "follow_up", "update", "resolution", "aside"}
PRINCIPLE_CATEGORIES = {
    "position_sizing",
    "exit_discipline",
    "entry_discipline",
    "risk_management",
    "sentiment_reading",
    "contrarian",
    "longterm_outlook",
    "mental_health",
    "lifestyle_balance",
}
WARNING_TYPES = {"instrument_trap", "anti_pattern", "rumor_debunk", "scam_alert"}
REFERENCE_TYPES = {"book", "article", "podcast_or_video", "report", "expert_quote"}
INSIGHT_DOMAINS = {"tech_industry", "macro_trend", "society", "personal_finance", "lifestyle", "management"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def expect_type(errors: list[str], path: str, value: Any, expected: type) -> None:
    if not isinstance(value, expected):
        errors.append(f"{path} must be {expected.__name__}")


def ensure_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def metadata_for_episode(ep: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode": int(ep["number"]),
        "date": ep.get("date"),
        "title": ep.get("display_title") or ep.get("title") or "",
    }


def select_episodes(
    episodes: list[dict[str, Any]],
    *,
    episode_numbers: set[int] | None,
    from_episode: int | None,
    to_episode: int | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for ep in sorted(episodes, key=lambda item: int(item["number"])):
        number = int(ep["number"])
        if episode_numbers and number not in episode_numbers:
            continue
        if from_episode is not None and number < from_episode:
            continue
        if to_episode is not None and number > to_episode:
            continue
        selected.append(ep)
        if limit and len(selected) >= limit:
            break
    return selected


def validate_note(note: dict[str, Any], metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in note:
            errors.append(f"missing {key}")
    if errors:
        return errors

    if note.get("schema_version") != "v2":
        errors.append("schema_version must be v2")
    if note.get("episode") != int(metadata["episode"]):
        errors.append(f"episode mismatch: {note.get('episode')} != {metadata['episode']}")
    expect_type(errors, "date", note.get("date"), str)

    for key in ["episode_archetype", "segment_breakdown", "market_regime", "host_state"]:
        expect_type(errors, key, note.get(key), dict)
    for key in [
        "topics",
        "investment_logic",
        "trade_observations",
        "qa_views",
        "catalysts",
        "narrative_threads",
        "view_changes",
        "principles",
        "mantras_or_catchphrases",
        "warnings",
        "references",
        "non_tradeable_insights",
        "open_questions",
    ]:
        expect_type(errors, key, note.get(key), list)

    topics = note.get("topics") or []
    if isinstance(topics, list) and not (3 <= len(topics) <= 8):
        errors.append("topics must contain 3-8 items")

    archetype = ensure_dict(note.get("episode_archetype"))
    if archetype.get("primary") not in EPISODE_ARCHETYPES:
        errors.append(f"episode_archetype.primary invalid: {archetype.get('primary')}")
    for idx, value in enumerate(ensure_list(archetype.get("secondary"))):
        if value not in EPISODE_ARCHETYPES:
            errors.append(f"episode_archetype.secondary[{idx}] invalid: {value}")

    breakdown = ensure_dict(note.get("segment_breakdown"))
    pct_keys = ["market_pct", "qa_pct", "life_or_aside_pct", "ads_pct", "principles_pct"]
    pct_values = []
    for key in pct_keys:
        value = breakdown.get(key)
        if not isinstance(value, int):
            errors.append(f"segment_breakdown.{key} must be int")
        else:
            pct_values.append(value)
    if len(pct_values) == len(pct_keys):
        total = sum(pct_values)
        if not 95 <= total <= 105:
            errors.append(f"segment_breakdown sum must be near 100, got {total}")

    regime = ensure_dict(note.get("market_regime"))
    for key in ["phase_label", "narrative"]:
        expect_type(errors, f"market_regime.{key}", regime.get(key), str)
    for key in ["geopolitical_factors", "regime_tags"]:
        expect_type(errors, f"market_regime.{key}", regime.get(key), list)

    host = ensure_dict(note.get("host_state"))
    for key in ["disclosed_positions", "self_critique", "personal_arc_markers"]:
        expect_type(errors, f"host_state.{key}", host.get(key), list)
    for idx, item in enumerate(host.get("self_critique") or []):
        if isinstance(item, dict) and item.get("tone") not in TONES:
            errors.append(f"host_state.self_critique[{idx}].tone invalid: {item.get('tone')}")

    for idx, item in enumerate(note.get("investment_logic") or []):
        prefix = f"investment_logic[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be object")
            continue
        for key in [
            "claim",
            "trigger",
            "is_conditional",
            "condition",
            "action_bias",
            "risk_control",
            "risk_control_type",
            "evidence",
            "source_type",
            "confidence",
        ]:
            if key not in item:
                errors.append(f"{prefix} missing {key}")
        if item.get("action_bias") not in ACTION_BIASES:
            errors.append(f"{prefix}.action_bias invalid: {item.get('action_bias')}")
        if item.get("risk_control_type") not in RISK_CONTROL_TYPES:
            errors.append(f"{prefix}.risk_control_type invalid: {item.get('risk_control_type')}")
        if item.get("confidence") not in CONFIDENCES:
            errors.append(f"{prefix}.confidence invalid: {item.get('confidence')}")
        if not isinstance(item.get("is_conditional"), bool):
            errors.append(f"{prefix}.is_conditional must be bool")
        if len(str(item.get("evidence", ""))) > 200:
            errors.append(f"{prefix}.evidence exceeds 200 chars")

    catalyst_ids = {item.get("id") for item in note.get("catalysts") or [] if isinstance(item, dict)}
    for idx, item in enumerate(note.get("catalysts") or []):
        prefix = f"catalysts[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be object")
            continue
        for key in ["id", "event", "expected_date", "category", "expected_impact", "linked_assets"]:
            if key not in item:
                errors.append(f"{prefix} missing {key}")
        if item.get("category") not in CATALYST_CATEGORIES:
            errors.append(f"{prefix}.category invalid: {item.get('category')}")
        expect_type(errors, f"{prefix}.linked_assets", item.get("linked_assets"), list)

    for idx, item in enumerate(note.get("trade_observations") or []):
        prefix = f"trade_observations[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be object")
            continue
        for key in [
            "asset_or_sector",
            "asset_symbol",
            "asset_type",
            "view",
            "primary_horizon",
            "reasoning",
            "industry_nodes",
            "catalyst_anchor",
            "consensus_level",
            "market_alignment",
            "tone",
        ]:
            if key not in item:
                errors.append(f"{prefix} missing {key}")
        if item.get("asset_type") not in ASSET_TYPES:
            errors.append(f"{prefix}.asset_type invalid: {item.get('asset_type')}")
        view = ensure_dict(item.get("view"))
        for key in ["short_term", "medium_term", "long_term"]:
            if view.get(key) not in VIEWS:
                errors.append(f"{prefix}.view.{key} invalid: {view.get(key)}")
        if item.get("primary_horizon") not in HORIZONS:
            errors.append(f"{prefix}.primary_horizon invalid: {item.get('primary_horizon')}")
        if item.get("consensus_level") not in CONSENSUS_LEVELS:
            errors.append(f"{prefix}.consensus_level invalid: {item.get('consensus_level')}")
        if item.get("tone") not in TONES:
            errors.append(f"{prefix}.tone invalid: {item.get('tone')}")
        expect_type(errors, f"{prefix}.industry_nodes", item.get("industry_nodes"), list)
        if item.get("catalyst_anchor") is not None and item.get("catalyst_anchor") not in catalyst_ids:
            errors.append(f"{prefix}.catalyst_anchor missing catalyst: {item.get('catalyst_anchor')}")

    for idx, item in enumerate(note.get("qa_views") or []):
        prefix = f"qa_views[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be object")
            continue
        for key in ["category", "question_theme", "viewpoint", "principle", "tone", "evidence", "asker_persona"]:
            if key not in item:
                errors.append(f"{prefix} missing {key}")
        if item.get("category") not in QA_CATEGORIES:
            errors.append(f"{prefix}.category invalid: {item.get('category')}")
        if len(str(item.get("evidence", ""))) > 200:
            errors.append(f"{prefix}.evidence exceeds 200 chars")

    for idx, item in enumerate(note.get("narrative_threads") or []):
        if isinstance(item, dict) and item.get("this_episode_role") not in THREAD_ROLES:
            errors.append(f"narrative_threads[{idx}].this_episode_role invalid: {item.get('this_episode_role')}")
    for idx, item in enumerate(note.get("principles") or []):
        if isinstance(item, dict) and item.get("category") not in PRINCIPLE_CATEGORIES:
            errors.append(f"principles[{idx}].category invalid: {item.get('category')}")
    for idx, item in enumerate(note.get("warnings") or []):
        if isinstance(item, dict) and item.get("type") not in WARNING_TYPES:
            errors.append(f"warnings[{idx}].type invalid: {item.get('type')}")
    for idx, item in enumerate(note.get("references") or []):
        if isinstance(item, dict) and item.get("type") not in REFERENCE_TYPES:
            errors.append(f"references[{idx}].type invalid: {item.get('type')}")
    for idx, item in enumerate(note.get("non_tradeable_insights") or []):
        if isinstance(item, dict) and item.get("domain") not in INSIGHT_DOMAINS:
            errors.append(f"non_tradeable_insights[{idx}].domain invalid: {item.get('domain')}")

    return errors


def validate(args: argparse.Namespace) -> int:
    episodes = read_json(args.data_dir / "source" / "episodes.json")
    selected = select_episodes(
        episodes,
        episode_numbers=set(args.episode) if args.episode else None,
        from_episode=args.from_episode,
        to_episode=args.to_episode,
        limit=args.limit,
    )
    missing: list[int] = []
    invalid: list[dict[str, Any]] = []
    valid = 0
    for ep in selected:
        number = int(ep["number"])
        metadata = metadata_for_episode(ep)
        path = args.output_dir / f"EP{number:03d}.json"
        if not path.exists():
            missing.append(number)
            continue
        try:
            note = read_json(path)
            if not isinstance(note, dict):
                errors = ["note must be object"]
            else:
                errors = validate_note(note, metadata)
        except Exception as exc:  # noqa: BLE001 - show all invalid local notes.
            errors = [f"{type(exc).__name__}: {exc}"]
        if errors:
            invalid.append({"episode": number, "errors": errors[:20]})
        else:
            valid += 1

    summary = {"target_count": len(selected), "valid": valid, "missing": missing, "invalid": invalid}
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if not missing and not invalid else 1


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    default_data_dir = root / "data"

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate distilled episode note JSON files")
    validate_parser.add_argument("--data-dir", type=Path, default=default_data_dir)
    validate_parser.add_argument("--output-dir", type=Path, default=default_data_dir / "distilled" / "episode_notes")
    validate_parser.add_argument("--episode", type=int, action="append")
    validate_parser.add_argument("--from-episode", type=int)
    validate_parser.add_argument("--to-episode", type=int)
    validate_parser.add_argument("--limit", type=int)
    validate_parser.set_defaults(func=validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
