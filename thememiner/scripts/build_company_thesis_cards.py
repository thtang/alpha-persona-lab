#!/usr/bin/env python3
"""Build company thesis cards for ThemeMiner/Lagradar.

The raw company profile answers "what data did we collect?". A thesis card
answers "why does this stock belong in this theme, what should lead it, and
what can break the trade?". Lagradar consumes these cards before making a
recommendation so a broad concept match cannot silently become a conviction
trade idea.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_judge import AgentConfig, AgenticJudge, normalize_agent_card, useful_agent_card

QUALITY_ORDER = {
    "manual_curated": 5,
    "profiled": 4,
    "official_tw_exchange_profile": 3,
    "market_metadata_profile": 2,
    "auto_yahoo_search": 1,
    "fallback_from_concepts": 0,
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    return [value]


def uniq(items: list[Any], *, max_items: int | None = None) -> list[Any]:
    seen: set[str] = set()
    output: list[Any] = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else str(item)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
        if max_items is not None and len(output) >= max_items:
            break
    return output


def canonical_symbol(value: Any) -> str:
    return str(value or "").strip().upper().replace(" ", "")


def agent_card_symbol_keys(item: dict[str, Any]) -> list[str]:
    keys = [
        item.get("symbol"),
        item.get("ticker"),
        item.get("input_symbol"),
        item.get("requested_symbol"),
    ]
    output = [canonical_symbol(key) for key in keys if canonical_symbol(key)]
    return uniq(output)


def extract_agent_card_items(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    candidates: list[Any] = []
    if isinstance(raw.get("cards"), list):
        candidates = raw["cards"]
    elif isinstance(raw.get("data"), dict) and isinstance(raw["data"].get("cards"), list):
        candidates = raw["data"]["cards"]
    elif isinstance(raw.get("results"), list):
        candidates = raw["results"]
    elif isinstance(raw.get("card"), dict):
        candidates = [raw["card"]]
    return [item for item in candidates if isinstance(item, dict)]


def load_profiles(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = read_json(path)
    if isinstance(data, dict):
        return data.get("profiles", [])
    if isinstance(data, list):
        return data
    return []


def load_relation_index(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    if not path.exists():
        return {}, {}
    data = read_json(path)
    concepts = data.get("concepts", []) if isinstance(data, dict) else []
    concept_by_id = {item["concept_id"]: item for item in concepts if item.get("concept_id")}
    stock_memberships: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for concept in concepts:
        concept_id = concept.get("concept_id")
        if not concept_id:
            continue
        for stock in concept.get("stocks", []):
            symbol = stock.get("symbol")
            if not symbol:
                continue
            membership = dict(stock)
            membership["concept_id"] = concept_id
            membership["concept_label"] = concept.get("label") or concept_id
            membership["concept_score"] = concept.get("score")
            membership["concept_markets"] = concept.get("markets") or []
            stock_memberships[symbol].append(membership)
    return concept_by_id, stock_memberships


def load_theme_library(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = read_json(path)
    themes = data.get("themes", []) if isinstance(data, dict) else []
    return {item.get("concept_id") or item.get("theme_id"): item for item in themes if item.get("concept_id") or item.get("theme_id")}


def load_overrides(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = read_json(path)
    return data.get("overrides", data if isinstance(data, dict) else {})


def profile_concepts(profile: dict[str, Any], memberships: list[dict[str, Any]], concept_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for exposure in profile.get("concept_exposures", []) or []:
        cid = exposure.get("concept_id")
        if not cid:
            continue
        concept = concept_by_id.get(cid, {})
        rows.append(
            {
                "concept_id": cid,
                "label": concept.get("label") or exposure.get("label") or cid,
                "role": exposure.get("role"),
                "weight": float(exposure.get("weight") or 0.5),
                "source": "profile",
                "path": exposure.get("path"),
                "score": concept.get("score"),
            }
        )
    for membership in memberships:
        cid = membership.get("concept_id")
        if not cid:
            continue
        rows.append(
            {
                "concept_id": cid,
                "label": membership.get("concept_label") or cid,
                "role": membership.get("role"),
                "weight": float(membership.get("weight") or 0.5),
                "source": "relation_index",
                "path": None,
                "score": membership.get("concept_score"),
            }
        )
    rows = uniq(rows)
    rows.sort(key=lambda item: (float(item.get("weight") or 0.0), float(item.get("score") or 0.0)), reverse=True)
    return rows


def infer_thesis_label(profile: dict[str, Any], concepts: list[dict[str, Any]]) -> str:
    labels = [item.get("label") or item.get("concept_id") for item in concepts[:3]]
    specializations = as_list(profile.get("specializations"))[:3]
    if labels:
        return " / ".join(str(item) for item in labels)
    if specializations:
        return " / ".join(str(item) for item in specializations)
    return profile.get("sector") or "company profile requires manual thesis"


def infer_ai_chain_position(profile: dict[str, Any], concepts: list[dict[str, Any]]) -> str:
    labels = uniq([str(item.get("label") or item.get("concept_id")) for item in concepts[:6]], max_items=6)
    if labels:
        return (
            "Fallback semantic summary only: upstream agent was unavailable, so this card lists mapped themes "
            f"({', '.join(labels)}) without asserting an AI supply-chain position. Use agent or manual override before high-conviction trading."
        )
    return "Fallback semantic summary only: no AI-chain position was inferred because no agent judgment or strong profile evidence is available."


def infer_non_ai_position(profile: dict[str, Any], concepts: list[dict[str, Any]]) -> str:
    sector = profile.get("sector") or profile.get("raw_industry") or "unknown sector"
    products = uniq([str(item) for item in as_list(profile.get("products")) + as_list(profile.get("specializations"))], max_items=8)
    if products:
        return f"Non-AI drivers may include {', '.join(products)} within {sector}; verify current revenue mix, inventory cycle, and end-market exposure."
    labels = [str(item.get("label") or item.get("concept_id")) for item in concepts[:5]]
    if labels:
        return f"Non-AI drivers may overlap with {', '.join(labels)}; verify whether this is a pure theme exposure or broad industry beta."
    return "Non-AI drivers are not yet mapped. Mark as lower confidence until the profile is upgraded."


def concept_catalysts(concepts: list[dict[str, Any]], library_by_id: dict[str, dict[str, Any]]) -> list[str]:
    catalysts: list[str] = []
    for concept in concepts[:5]:
        cid = concept.get("concept_id")
        label = concept.get("label") or cid
        score = concept.get("score")
        if label:
            catalysts.append(f"{label} theme score {score:.1f}" if isinstance(score, (int, float)) else f"{label} theme exposure")
        library = library_by_id.get(cid or "", {})
        for headline in library.get("top_headlines", [])[:2]:
            title = headline.get("title") if isinstance(headline, dict) else None
            if title:
                catalysts.append(title)
    return uniq(catalysts, max_items=8)


def leader_indicators(symbol: str, concepts: list[dict[str, Any]], concept_by_id: dict[str, dict[str, Any]]) -> list[str]:
    leaders: list[str] = []
    for concept in concepts[:8]:
        cid = concept.get("concept_id")
        for stock in concept_by_id.get(cid or "", {}).get("stocks", []):
            peer_symbol = stock.get("symbol")
            if not peer_symbol or peer_symbol == symbol:
                continue
            role = str(stock.get("role") or "")
            weight = float(stock.get("weight") or 0.0)
            if "leader" in role or weight >= 0.72:
                label = " ".join(str(part) for part in [peer_symbol, stock.get("name"), stock.get("market")] if part)
                leaders.append(label)
    return uniq(leaders, max_items=12)


def peer_symbols(symbol: str, concepts: list[dict[str, Any]], concept_by_id: dict[str, dict[str, Any]]) -> list[str]:
    peers: list[str] = []
    for concept in concepts[:6]:
        cid = concept.get("concept_id")
        for stock in concept_by_id.get(cid or "", {}).get("stocks", [])[:30]:
            peer_symbol = stock.get("symbol")
            if peer_symbol and peer_symbol != symbol:
                peers.append(peer_symbol)
    return uniq(peers, max_items=20)


def infer_risks(profile: dict[str, Any]) -> list[str]:
    risks = [str(item) for item in as_list(profile.get("risk_flags"))]
    risks.extend(str(item) for item in as_list(profile.get("constraints")))
    if not risks:
        risks.append("profile lacks explicit risk flags; verify revenue mix, liquidity, valuation, and theme purity before trading")
    return uniq(risks, max_items=10)


def relation_confidence(profile: dict[str, Any], concepts: list[dict[str, Any]], override: dict[str, Any] | None) -> str:
    if override:
        return "high_manual_curated"
    quality = profile.get("profile_quality") or profile.get("profile_status") or ""
    score = QUALITY_ORDER.get(str(quality), 1)
    source_refs = profile.get("source_refs") or []
    has_paths = any(item.get("path") for item in concepts)
    if score >= 4 and source_refs and has_paths:
        return "high_profiled"
    if score >= 2 and (source_refs or has_paths):
        return "medium_needs_segment_verification"
    return "low_auto_mapping_backlog"


def merge_card_override(card: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(card)
    list_fields = {
        "business_segments",
        "catalysts",
        "leader_indicators",
        "peer_symbols",
        "risks",
    }
    for key, value in override.items():
        if key in list_fields:
            merged[key] = uniq(as_list(value) + as_list(merged.get(key)), max_items=30)
        elif value not in (None, ""):
            merged[key] = value
    merged["manual_override"] = True
    merged["relation_confidence"] = "high_manual_curated"
    merged["agent_status"] = "manual_override"
    return merged


def agent_evidence_payload(
    profile: dict[str, Any],
    concepts: list[dict[str, Any]],
    memberships: list[dict[str, Any]],
    relation_paths: list[str],
) -> dict[str, Any]:
    keys = [
        "symbol",
        "name",
        "company_name",
        "market",
        "region",
        "sector",
        "raw_industry",
        "primary_business",
        "specializations",
        "products",
        "platforms",
        "constraints",
        "risk_flags",
        "bottleneck_profile",
        "supply_chain_profile",
        "source_refs",
        "profile_quality",
        "profile_evidence_quality",
        "official_metadata",
    ]
    profile_evidence = {key: profile.get(key) for key in keys if profile.get(key) not in (None, "", [], {})}
    return {
        "task": "Create a semantic company thesis card for cross-market theme diffusion. Do not keyword-match; judge business fit.",
        "symbol": profile.get("symbol"),
        "name": profile.get("company_name") or profile.get("name") or profile.get("symbol"),
        "profile": profile_evidence,
        "concept_memberships": concepts[:18],
        "relation_index_memberships": memberships[:18],
        "relation_paths": relation_paths[:10],
        "instructions": [
            "Decide what the company actually does.",
            "Separate AI-chain exposure from non-AI drivers.",
            "If concepts look broad or wrong, correct them and lower confidence.",
            "Name leader indicators and peer symbols only when relation is plausible.",
            "List evidence gaps explicitly.",
        ],
    }


def apply_agent_card(card: dict[str, Any], agent_card: dict[str, Any], config: AgentConfig) -> dict[str, Any]:
    if not useful_agent_card(agent_card):
        card["agent_status"] = config.status if not config.enabled else "agent_failed_or_unusable"
        card["agent_provider"] = config.provider
        card["agent_model"] = config.model
        return card

    merged = dict(card)
    scalar_fields = [
        "thesis_label",
        "primary_business",
        "ai_chain_position",
        "non_ai_chain_position",
        "relation_confidence",
        "agent_reasoning_summary",
    ]
    list_fields = ["business_segments", "catalysts", "leader_indicators", "peer_symbols", "risks", "evidence_gaps"]
    for field in scalar_fields:
        if agent_card.get(field):
            merged[field] = agent_card[field]
    for field in list_fields:
        if agent_card.get(field):
            merged[field] = uniq(agent_card[field] + as_list(merged.get(field)), max_items=30)
    if merged.get("risks"):
        merged["thesis_risks"] = merged["risks"]
    merged["agent_status"] = "agent_applied"
    merged["agent_provider"] = config.provider
    merged["agent_model"] = config.model
    merged["agent_base_url"] = config.base_url if config.provider == "openai" else None
    return merged


def build_card(
    profile: dict[str, Any],
    memberships: list[dict[str, Any]],
    concept_by_id: dict[str, dict[str, Any]],
    library_by_id: dict[str, dict[str, Any]],
    override: dict[str, Any] | None,
    agent: AgenticJudge | None,
) -> dict[str, Any]:
    symbol = profile.get("symbol")
    concepts = profile_concepts(profile, memberships, concept_by_id)
    segments = uniq(
        [str(item) for item in as_list(profile.get("products")) + as_list(profile.get("specializations")) + as_list(profile.get("platforms"))],
        max_items=16,
    )
    source_refs = uniq(as_list(profile.get("source_refs")), max_items=8)
    relation_paths = uniq([item.get("path") for item in concepts if item.get("path")], max_items=8)
    card = {
        "symbol": symbol,
        "name": profile.get("company_name") or profile.get("name") or symbol,
        "market": profile.get("market"),
        "region": profile.get("region"),
        "sector": profile.get("sector") or profile.get("raw_industry"),
        "thesis_label": infer_thesis_label(profile, concepts),
        "primary_business": profile.get("primary_business") or "Primary business not yet profiled; use lower confidence until upgraded.",
        "business_segments": segments,
        "theme_memberships": concepts[:16],
        "relation_paths": relation_paths,
        "ai_chain_position": infer_ai_chain_position(profile, concepts),
        "non_ai_chain_position": infer_non_ai_position(profile, concepts),
        "catalysts": concept_catalysts(concepts, library_by_id),
        "leader_indicators": leader_indicators(symbol, concepts, concept_by_id),
        "peer_symbols": peer_symbols(symbol, concepts, concept_by_id),
        "risks": infer_risks(profile),
        "source_refs": source_refs,
        "profile_quality": profile.get("profile_quality") or profile.get("profile_status"),
        "profile_evidence_quality": profile.get("profile_evidence_quality"),
        "source_quality": profile.get("profile_evidence_quality") or profile.get("profile_quality") or "unknown",
        "relation_confidence": relation_confidence(profile, concepts, override),
        "manual_override": False,
        "agent_status": "not_requested",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if override:
        card = merge_card_override(card, override)
    elif agent:
        agent_payload = agent_evidence_payload(profile, concepts, memberships, relation_paths)
        agent_card = normalize_agent_card(agent.company_thesis(agent_payload))
        card = apply_agent_card(card, agent_card, agent.config)
    return card


def main() -> int:
    parser = argparse.ArgumentParser(description="Build company thesis cards from ThemeMiner profiles and relation graph")
    parser.add_argument("--profiles", default="thememiner/output/company_profiles.json")
    parser.add_argument("--relation-index", default="thememiner/output/relation_index.json")
    parser.add_argument("--theme-library", default="thememiner/output/theme_library.json")
    parser.add_argument("--overrides", default="thememiner/data/company_thesis_overrides.json")
    parser.add_argument("--output", default="thememiner/output/company_thesis_cards.json")
    parser.add_argument(
        "--agent-mode",
        choices=["auto", "on", "off"],
        default="auto",
        help="Use a semantic agent for thesis cards. auto uses OpenAI-compatible API when keyed, otherwise local codex exec when available.",
    )
    parser.add_argument("--agent-provider", choices=["auto", "openai", "codex"], default="auto")
    parser.add_argument("--agent-model", default=None)
    parser.add_argument("--agent-cache-dir", default="thememiner/output/cache/agentic_judge")
    parser.add_argument("--agent-refresh", action="store_true")
    parser.add_argument(
        "--agent-cache-only",
        action="store_true",
        help="Replay successful cached agent judgments without making new agent calls.",
    )
    parser.add_argument("--agent-limit", type=int, default=0, help="debug limit for agent calls; 0 means no cap")
    parser.add_argument("--agent-workers", type=int, default=1, help="parallel semantic agents; use 2-6 for local codex exec")
    parser.add_argument("--agent-batch-size", type=int, default=12, help="companies per semantic agent call; batching is most important for codex exec")
    args = parser.parse_args()

    profiles = load_profiles(Path(args.profiles))
    concept_by_id, stock_memberships = load_relation_index(Path(args.relation_index))
    library_by_id = load_theme_library(Path(args.theme_library))
    overrides = load_overrides(Path(args.overrides))
    requested_agent = args.agent_mode == "on" or args.agent_mode == "auto"
    agent_config = AgentConfig.from_env(
        enabled=requested_agent,
        cache_dir=args.agent_cache_dir,
        refresh=args.agent_refresh,
        model=args.agent_model,
        provider=args.agent_provider,
    )
    if args.agent_mode == "off":
        agent_config.enabled = False
    if args.agent_cache_only:
        agent_config.enabled = False
        agent_config.refresh = False
    if args.agent_mode == "on" and not agent_config.enabled and not args.agent_cache_only:
        raise RuntimeError("agent-mode=on requires an available agent provider: OpenAI-compatible API key or local codex CLI")
    agent = AgenticJudge(agent_config)
    agent_calls = 0

    cards: list[dict[str, Any]] = []
    profile_symbols = set()
    agent_payload_jobs: list[tuple[int, dict[str, Any]]] = []
    for profile in profiles:
        symbol = profile.get("symbol")
        if not symbol:
            continue
        profile_symbols.add(symbol)
        override = overrides.get(symbol)
        use_agent = not override and requested_agent and (
            not agent_config.enabled or args.agent_limit <= 0 or agent_calls < args.agent_limit
        )
        memberships = stock_memberships.get(symbol, [])
        concepts = profile_concepts(profile, memberships, concept_by_id)
        relation_paths = uniq([item.get("path") for item in concepts if item.get("path")], max_items=8)
        card = build_card(
            profile,
            memberships,
            concept_by_id,
            library_by_id,
            override,
            None,
        )
        if use_agent and not agent_config.enabled and not args.agent_cache_only:
            card = apply_agent_card(card, {}, agent_config)
        cards.append(card)
        if use_agent and (agent_config.enabled or args.agent_cache_only):
            agent_payload_jobs.append((len(cards) - 1, agent_evidence_payload(profile, concepts, memberships, relation_paths)))
            agent_calls += 1

    def chunks(values: list[tuple[int, dict[str, Any]]], size: int) -> list[list[tuple[int, dict[str, Any]]]]:
        return [values[index : index + size] for index in range(0, len(values), size)]

    def run_agent_batch(batch: list[tuple[int, dict[str, Any]]]) -> list[tuple[int, dict[str, Any]]]:
        if len(batch) == 1 or args.agent_batch_size <= 1:
            idx, payload = batch[0]
            return [(idx, normalize_agent_card(agent.company_thesis(payload)))]
        raw = agent.company_thesis_batch([payload for _, payload in batch])
        by_symbol: dict[str, dict[str, Any]] = {}
        raw_items = extract_agent_card_items(raw)
        normalized_items = [normalize_agent_card(item) for item in raw_items]
        for item, normalized in zip(raw_items, normalized_items):
            for key in agent_card_symbol_keys(item):
                by_symbol[key] = normalized
        results: list[tuple[int, dict[str, Any]]] = []
        for offset, (idx, payload) in enumerate(batch):
            symbol = canonical_symbol(payload.get("symbol"))
            agent_card = by_symbol.get(symbol, {})
            if not useful_agent_card(agent_card) and offset < len(normalized_items):
                # Codex batch agents normally preserve order even when they omit or alter a symbol.
                # Use the order fallback only after symbol matching fails.
                agent_card = normalized_items[offset]
            results.append((idx, agent_card))
        return results

    agent_batches_attempted = 0
    if agent_payload_jobs:
        batched_jobs = chunks(agent_payload_jobs, max(1, args.agent_batch_size))
        agent_batches_attempted = len(batched_jobs)
        if args.agent_workers > 1:
            with ThreadPoolExecutor(max_workers=max(1, args.agent_workers)) as executor:
                future_map = {executor.submit(run_agent_batch, batch): batch for batch in batched_jobs}
                for future in as_completed(future_map):
                    for idx, agent_card in future.result():
                        cards[idx] = apply_agent_card(cards[idx], agent_card, agent_config)
        else:
            for batch in batched_jobs:
                for idx, agent_card in run_agent_batch(batch):
                    cards[idx] = apply_agent_card(cards[idx], agent_card, agent_config)

    for symbol, override in sorted(overrides.items()):
        if symbol in profile_symbols:
            continue
        cards.append(
            merge_card_override(
                {
                    "symbol": symbol,
                    "name": override.get("name") or symbol,
                    "market": None,
                    "region": None,
                    "sector": None,
                    "thesis_label": override.get("thesis_label") or "manual thesis",
                    "primary_business": override.get("primary_business") or "Manual thesis card without upstream profile.",
                    "business_segments": [],
                    "theme_memberships": [],
                    "relation_paths": [],
                    "ai_chain_position": "Manual card; upstream profile missing.",
                    "non_ai_chain_position": "Manual card; upstream profile missing.",
                    "catalysts": [],
                    "leader_indicators": [],
                    "peer_symbols": [],
                    "risks": [],
                    "source_refs": [],
                    "profile_quality": None,
                    "profile_evidence_quality": None,
                    "source_quality": "manual_only",
                    "relation_confidence": "high_manual_curated",
                    "manual_override": True,
                    "agent_status": "manual_override",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                override,
            )
        )

    cards.sort(key=lambda item: (item.get("market") or "", item.get("symbol") or ""))
    output = {
        "schema_version": "company_thesis_cards_v1",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source_profile_count": len(profiles),
        "manual_override_count": len(overrides),
        "agent": {
            "status": agent_config.status,
            "provider": agent_config.provider,
            "model": agent_config.model,
            "base_url": agent_config.base_url if agent_config.enabled and agent_config.provider == "openai" else None,
            "cache_dir": str(agent_config.cache_dir),
            "calls_attempted": agent_calls,
            "batches_attempted": agent_batches_attempted,
            "batch_size": args.agent_batch_size,
            "limit": args.agent_limit,
            "workers": args.agent_workers,
        },
        "card_count": len(cards),
        "cards": cards,
    }
    write_json(Path(args.output), output)
    print(f"Wrote {len(cards)} company thesis cards to {args.output}")
    print(f"Manual overrides applied: {len([card for card in cards if card.get('manual_override')])}")
    print(f"Agent status: {agent_config.status}; calls attempted: {agent_calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
