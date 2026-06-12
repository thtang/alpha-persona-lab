#!/usr/bin/env python3
"""Scan cross-market theme diffusion and improving laggards.

This is intentionally simple and inspectable. It uses the seed graph to define
what can plausibly transmit, then uses price/volume behavior to decide whether a
candidate is an improving laggard, already caught up, or simply weak.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


USER_AGENT = "alpha-persona-lab-lagradar/0.1"
LEADER_ROLES = {"global_leader", "regional_leader", "high_beta_leader"}
FOLLOWER_ROLES = {"global_follower", "regional_follower", "niche_follower", "core_follower", "laggard_watch", "concept_only"}
# Role normalization for old seed files only; not business/concept evidence.
ROLE_ALIASES = {
    "leader": "regional_leader",
    "follower": "regional_follower",
    "supplier": "core_follower",
    "peer": "core_follower",
    "watch": "laggard_watch",
}
# Legacy bridge from historical Lagradar theme IDs to ThemeMiner concepts.
# Company-level fit comes from ThemeMiner profiles/thesis cards.
THEME_TO_CONCEPTS = {
    "ai_compute_capex_custom_silicon": {"ai_capex", "gpu_accelerator", "tpu_cloud", "ai_foundry_capacity", "ip_asic", "foundry", "cowos", "ems"},
    "agentic_cpu_memory_stack": {
        "agentic_ai_infrastructure",
        "agentic_cpu_rack",
        "host_dram",
        "kv_cache_memory",
        "enterprise_ssd",
        "hdd_cold_storage",
        "memory_interface",
        "cpu_socket",
        "high_speed_connector",
        "server_pcb_abf",
        "ai_test_probe_interface",
        "precision_timing",
        "passive_components",
        "semicap_equipment",
        "networking",
    },
    "passive_components": {
        "passive_components",
        "high_voltage_mlcc",
        "aluminum_polymer_cap",
        "snap_in_capacitor",
        "film_capacitor",
        "chip_resistor",
        "inductor_choke",
        "tantalum_capacitor",
        "passive_component_distribution",
    },
    "memory_hbm": {"hbm", "dram_manufacturing", "memory_ic_design", "legacy_memory"},
    "ai_server_power_thermal": {"gb200", "gb300", "vera_rubin", "thermal_components", "power_supply", "ems"},
    "pcb_abf_ccl": {"pcb_manufacturing", "pcb_material_equipment", "abf_substrate"},
    "optical_800g_cpo": {"cpo_optical", "laser_capacity", "inp_photonics", "silicon_photonics", "specialty_glass_fiber", "networking"},
    "ai_photonics_bottleneck_stack": {
        "cpo_optical",
        "laser_capacity",
        "inp_photonics",
        "silicon_photonics",
        "soi_wafer",
        "epitaxy_equipment",
        "specialty_glass_fiber",
        "optical_interposer_packaging",
        "networking",
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_company_profiles(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    data = read_json(path)
    profiles = data.get("profiles", data if isinstance(data, list) else [])
    return {profile["symbol"]: profile for profile in profiles if profile.get("symbol")}


def load_company_thesis_cards(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    data = read_json(path)
    cards = data.get("cards", data if isinstance(data, list) else [])
    return {card["symbol"]: card for card in cards if card.get("symbol")}


def load_thememiner_bundle(output_dir: Path | None) -> dict[str, Any]:
    """Load the latest ThemeMiner output files used as Lagradar's upstream graph."""

    if not output_dir or not output_dir.exists():
        return {}
    paths = {
        "theme_library": output_dir / "theme_library.json",
        "relation_index": output_dir / "relation_index.json",
        "manifest": output_dir / "update_manifest.json",
        "company_profiles": output_dir / "company_profiles.json",
    }
    if not paths["theme_library"].exists() or not paths["relation_index"].exists():
        return {}
    bundle: dict[str, Any] = {
        "output_dir": str(output_dir),
        "theme_library": read_json(paths["theme_library"]),
        "relation_index": read_json(paths["relation_index"]),
        "manifest": read_json(paths["manifest"]) if paths["manifest"].exists() else {},
        "company_profiles": load_company_profiles(paths["company_profiles"]),
    }
    return bundle


def normalize_role(role: str | None, *, market: str | None = None, weight: float = 0.5) -> str:
    role = (role or "").strip()
    if role in LEADER_ROLES or role in FOLLOWER_ROLES:
        return role
    if role in ROLE_ALIASES:
        return ROLE_ALIASES[role]
    if weight >= 0.86:
        return "global_leader" if market == "US" else "regional_leader"
    if weight >= 0.68:
        return "core_follower"
    return "laggard_watch"


def theme_concepts(theme_id: str) -> set[str]:
    return set(THEME_TO_CONCEPTS.get(theme_id, {theme_id}))


def node_sort_key(node: dict[str, Any]) -> tuple[float, float, str]:
    role = normalize_role(node.get("role"), market=node.get("market"), weight=float(node.get("weight") or node.get("exposure") or 0.5))
    role_score = 2.0 if role in LEADER_ROLES else 1.0 if role in {"core_follower", "regional_follower", "global_follower"} else 0.0
    return (role_score, float(node.get("weight") or node.get("exposure") or 0.5), node.get("symbol") or "")


def merge_theme_nodes(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for node in existing:
        symbol = node.get("symbol")
        if not symbol:
            continue
        by_symbol[symbol] = copy.deepcopy(node)
        order.append(symbol)
    for node in incoming:
        symbol = node.get("symbol")
        if not symbol:
            continue
        if symbol not in by_symbol:
            by_symbol[symbol] = copy.deepcopy(node)
            order.append(symbol)
            continue
        merged = by_symbol[symbol]
        for key in ("name", "market", "region"):
            if not merged.get(key) and node.get(key):
                merged[key] = node[key]
        merged["exposure"] = max(float(merged.get("exposure") or 0.0), float(node.get("exposure") or 0.0))
        concepts = set(merged.get("thememiner_concepts") or [])
        concepts.update(node.get("thememiner_concepts") or [])
        if node.get("thememiner_concept_id"):
            concepts.add(node["thememiner_concept_id"])
        if concepts:
            merged["thememiner_concepts"] = sorted(concepts)
        if not merged.get("thememiner_profile_status") and node.get("thememiner_profile_status"):
            merged["thememiner_profile_status"] = node["thememiner_profile_status"]
    return [by_symbol[symbol] for symbol in order]


def sync_seed_with_thememiner(
    seed: dict[str, Any],
    bundle: dict[str, Any],
    *,
    min_score: float = 0.0,
    min_markets: int = 1,
    max_themes: int = 0,
    max_nodes_per_theme: int = 0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge ThemeMiner concepts into the Lagradar seed graph for automatic sync."""

    if not bundle:
        return seed, {"enabled": False, "reason": "thememiner output not found"}

    relation_concepts = bundle.get("relation_index", {}).get("concepts", [])
    library_themes = bundle.get("theme_library", {}).get("themes", [])
    library_by_id = {theme.get("concept_id"): theme for theme in library_themes if theme.get("concept_id")}
    concepts = []
    for concept in relation_concepts:
        concept_id = concept.get("concept_id")
        if not concept_id:
            continue
        library = library_by_id.get(concept_id, {})
        score = float(concept.get("score") or library.get("score") or 0.0)
        markets = concept.get("markets") or library.get("markets") or []
        stocks = concept.get("stocks") or []
        if score < min_score or len(markets) < min_markets or len(stocks) < 2:
            continue
        concepts.append((score, concept_id, concept, library))
    concepts.sort(key=lambda item: item[0], reverse=True)
    if max_themes > 0:
        concepts = concepts[:max_themes]

    synced = copy.deepcopy(seed)
    synced["schema_version"] = seed.get("schema_version", "lagradar_seed_v1")
    synced["updated_at"] = datetime.now(timezone.utc).isoformat()
    synced["sync_source"] = {
        "name": "thememiner",
        "output_dir": bundle.get("output_dir"),
        "thememiner_built_at": bundle.get("manifest", {}).get("built_at"),
        "min_score": min_score,
        "min_markets": min_markets,
        "max_themes": max_themes,
        "max_nodes_per_theme": max_nodes_per_theme,
    }

    theme_map = {theme["theme_id"]: theme for theme in synced.get("themes", []) if theme.get("theme_id")}
    for _, concept_id, concept, library in concepts:
        stocks = sorted(concept.get("stocks") or [], key=node_sort_key, reverse=True)
        if max_nodes_per_theme > 0:
            stocks = stocks[:max_nodes_per_theme]
        nodes: list[dict[str, Any]] = []
        for stock in stocks:
            weight = float(stock.get("weight") or 0.5)
            nodes.append(
                {
                    "symbol": stock.get("symbol"),
                    "name": stock.get("name") or stock.get("symbol"),
                    "market": stock.get("market"),
                    "region": stock.get("region") or stock.get("market"),
                    "role": normalize_role(stock.get("role"), market=stock.get("market"), weight=weight),
                    "exposure": round(weight, 3),
                    "thememiner_concept_id": concept_id,
                    "thememiner_concepts": [concept_id],
                    "thememiner_profile_status": stock.get("profile_status"),
                }
            )
        top_headlines = [item.get("title") for item in (library.get("top_headlines") or [])[:3] if item.get("title")]
        generated_theme = {
            "theme_id": concept_id,
            "label": concept.get("label") or library.get("label") or concept_id,
            "hypothesis": (
                f"ThemeMiner synced concept `{concept_id}`. Use product/supply-layer relation, "
                "cross-market breadth, price confirmation, and company profiles to judge diffusion."
            ),
            "catalysts": [
                f"ThemeMiner score {float(concept.get('score') or library.get('score') or 0.0):.1f}",
                f"stage {concept.get('stage') or library.get('stage') or '-'}",
                f"markets {', '.join(concept.get('markets') or library.get('markets') or [])}",
                *top_headlines,
            ],
            "nodes": nodes,
            "thememiner": {
                "concept_id": concept_id,
                "category_label": concept.get("category_label") or library.get("category_label"),
                "products": concept.get("products", []),
                "supply_layers": concept.get("supply_layers", []),
                "upstream_concepts": concept.get("upstream_concepts", []),
                "downstream_concepts": concept.get("downstream_concepts", []),
                "stock_count": len(concept.get("stocks") or []),
            },
        }
        if concept_id in theme_map:
            existing = theme_map[concept_id]
            existing["nodes"] = merge_theme_nodes(existing.get("nodes", []), nodes)
            existing["catalysts"] = list(dict.fromkeys((existing.get("catalysts") or []) + generated_theme["catalysts"]))
            existing.setdefault("thememiner", generated_theme["thememiner"])
        else:
            synced.setdefault("themes", []).append(generated_theme)
            theme_map[concept_id] = generated_theme

    info = {
        "enabled": True,
        "output_dir": bundle.get("output_dir"),
        "thememiner_built_at": bundle.get("manifest", {}).get("built_at"),
        "source_concept_count": len(relation_concepts),
        "synced_concept_count": len(concepts),
        "theme_count_after_sync": len(synced.get("themes", [])),
        "company_profile_count": len(bundle.get("company_profiles") or {}),
    }
    return synced, info


def profile_theme_paths(node: dict[str, Any], theme_id: str) -> list[str]:
    profile = node.get("profile") or {}
    concept_ids = theme_concepts(theme_id)
    paths: list[str] = []
    for exposure in profile.get("concept_exposures", []):
        if exposure.get("concept_id") in concept_ids and exposure.get("path"):
            paths.append(exposure["path"])
    return paths[:4]


def unique_text(values: list[Any], *, limit: int = 12) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
        if len(output) >= limit:
            break
    return output


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def mean(values: list[float]) -> float | None:
    values = [value for value in values if value is not None and math.isfinite(value)]
    return sum(values) / len(values) if values else None


def median(values: list[float]) -> float | None:
    values = [value for value in values if value is not None and math.isfinite(value)]
    return statistics.median(values) if values else None


def pct_change(close: float | None, previous: float | None) -> float | None:
    if close is None or previous in (None, 0):
        return None
    return (close / previous - 1.0) * 100.0


def url_json(url: str, *, timeout: int = 12) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def yahoo_history(symbol: str, cache_dir: Path, *, refresh: bool = False) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{symbol.replace('.', '_')}.json"
    if cache_path.exists() and not refresh:
        cached = read_json(cache_path)
        rows = cached.get("rows") or []
        if rows:
            return rows
        if cached.get("error"):
            raise RuntimeError(cached["error"])

    encoded = urllib.parse.quote(symbol, safe="")
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{encoded}?range=6mo&interval=1d"
    try:
        data = url_json(url)
    except Exception as exc:
        write_json(
            cache_path,
            {
                "symbol": symbol,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "rows": [],
                "error": str(exc),
            },
        )
        raise
    result = (data.get("chart", {}).get("result") or [None])[0]
    rows: list[dict[str, Any]] = []
    if result:
        timestamps = result.get("timestamp") or []
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        for idx, ts in enumerate(timestamps):
            close = quote.get("close", [None] * len(timestamps))[idx]
            if close is None:
                continue
            rows.append(
                {
                    "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                    "open": quote.get("open", [None] * len(timestamps))[idx],
                    "high": quote.get("high", [None] * len(timestamps))[idx],
                    "low": quote.get("low", [None] * len(timestamps))[idx],
                    "close": close,
                    "volume": quote.get("volume", [None] * len(timestamps))[idx],
                }
            )
    write_json(cache_path, {"symbol": symbol, "fetched_at": datetime.now(timezone.utc).isoformat(), "rows": rows})
    time.sleep(0.08)
    return rows


def return_n(rows: list[dict[str, Any]], n: int) -> float | None:
    if len(rows) <= n:
        return None
    return pct_change(rows[-1].get("close"), rows[-1 - n].get("close"))


def moving_average(rows: list[dict[str, Any]], n: int) -> float | None:
    if len(rows) < n:
        return None
    return mean([float(row["close"]) for row in rows[-n:] if row.get("close") is not None])


def volume_ratio(rows: list[dict[str, Any]], n: int = 20) -> float | None:
    if len(rows) <= n:
        return None
    current = rows[-1].get("volume")
    previous = [float(row["volume"]) for row in rows[-1 - n : -1] if row.get("volume")]
    avg = mean(previous)
    if not current or not avg:
        return None
    return float(current) / avg


def company_metrics(node: dict[str, Any], cache_dir: Path, refresh: bool) -> dict[str, Any]:
    symbol = node["symbol"]
    row: dict[str, Any] = {
        "symbol": symbol,
        "name": node.get("name") or symbol,
        "market": node.get("market"),
        "region": node.get("region"),
        "role": node.get("role"),
        "exposure": float(node.get("exposure", 0.5)),
        "primary_business": node.get("primary_business"),
        "specializations": node.get("specializations", []),
        "platforms": node.get("platforms", []),
        "constraints": node.get("constraints", []),
        "risk_flags": node.get("risk_flags", []),
        "bottleneck_profile": node.get("bottleneck_profile", {}),
        "thesis_label": node.get("thesis_label"),
        "ai_chain_position": node.get("ai_chain_position"),
        "non_ai_chain_position": node.get("non_ai_chain_position"),
        "business_segments": node.get("business_segments", []),
        "catalysts": node.get("catalysts", []),
        "leader_indicators": node.get("leader_indicators", []),
        "peer_symbols": node.get("peer_symbols", []),
        "thesis_risks": node.get("thesis_risks", []),
        "relation_confidence": node.get("relation_confidence"),
        "source_quality": node.get("source_quality"),
        "manual_thesis_override": node.get("manual_thesis_override"),
        "agent_status": node.get("agent_status"),
        "agent_reasoning_summary": node.get("agent_reasoning_summary"),
        "evidence_gaps": node.get("evidence_gaps", []),
    }
    try:
        rows = yahoo_history(symbol, cache_dir, refresh=refresh)
    except Exception as exc:
        row["error"] = str(exc)
        return row

    if len(rows) < 25:
        row["error"] = f"too few rows: {len(rows)}"
        return row

    close = rows[-1]["close"]
    row.update(
        {
            "asof": rows[-1]["date"],
            "close": close,
            "r1": return_n(rows, 1),
            "r3": return_n(rows, 3),
            "r5": return_n(rows, 5),
            "r10": return_n(rows, 10),
            "r20": return_n(rows, 20),
            "r60": return_n(rows, 60),
            "ma5": moving_average(rows, 5),
            "ma10": moving_average(rows, 10),
            "ma20": moving_average(rows, 20),
            "ma60": moving_average(rows, 60),
            "volume_ratio_20d": volume_ratio(rows, 20),
        }
    )
    highs_20 = [float(item["high"]) for item in rows[-20:] if item.get("high")]
    highs_60 = [float(item["high"]) for item in rows[-60:] if item.get("high")]
    if highs_20:
        high_20 = max(highs_20)
        row["drawdown_from_20d_high_pct"] = pct_change(close, high_20)
        row["near_20d_high"] = bool(close >= high_20 * 0.95)
        row["breakout_20d"] = bool(close >= high_20 * 0.995)
    if highs_60:
        row["drawdown_from_60d_high_pct"] = pct_change(close, max(highs_60))
    row["above_ma5"] = bool(row.get("ma5") and close >= row["ma5"])
    row["above_ma10"] = bool(row.get("ma10") and close >= row["ma10"])
    row["above_ma20"] = bool(row.get("ma20") and close >= row["ma20"])
    row["above_ma60"] = bool(row.get("ma60") and close >= row["ma60"])
    if row.get("ma20"):
        row["ma20_distance_pct"] = pct_change(close, row["ma20"])
    return row


def turning_score(metric: dict[str, Any]) -> float:
    score = 0.0
    score += clamp((metric.get("r3") or 0.0) / 8.0, -0.5, 1.0) * 1.0
    score += clamp((metric.get("r5") or 0.0) / 12.0, -0.5, 1.0) * 1.2
    score += clamp((metric.get("r10") or 0.0) / 20.0, -0.5, 1.0) * 0.8
    score += 0.6 if metric.get("above_ma5") else -0.2
    score += 0.5 if metric.get("above_ma10") else -0.1
    score += 0.5 if metric.get("above_ma20") else -0.1
    score += 0.9 if metric.get("near_20d_high") else 0.0
    score += 0.6 if metric.get("breakout_20d") else 0.0
    vr = metric.get("volume_ratio_20d")
    if vr:
        score += clamp((vr - 1.0) / 1.5, -0.2, 1.0) * 0.8
    return round(score, 3)


def overheat_score(metric: dict[str, Any]) -> float:
    """Penalize names that have likely moved from laggard to crowded chase."""

    score = 0.0
    score += clamp(((metric.get("r5") or 0.0) - 8.0) / 20.0, 0.0, 1.0) * 1.2
    score += clamp(((metric.get("r20") or 0.0) - 25.0) / 50.0, 0.0, 1.0) * 1.4
    score += clamp(((metric.get("ma20_distance_pct") or 0.0) - 10.0) / 25.0, 0.0, 1.0) * 1.2
    vr = metric.get("volume_ratio_20d")
    if vr:
        score += clamp((vr - 2.0) / 3.0, 0.0, 1.0) * 0.8
    if metric.get("breakout_20d"):
        score += 0.4
    return round(score, 3)


def diffusion_score(followers: list[dict[str, Any]]) -> dict[str, float]:
    valid = [row for row in followers if not row.get("error")]
    if not valid:
        return {
            "follower_positive_5d_ratio": 0.0,
            "follower_positive_20d_ratio": 0.0,
            "follower_near_high_ratio": 0.0,
            "follower_breakout_ratio": 0.0,
            "follower_volume_expansion_ratio": 0.0,
            "diffusion_score": 0.0,
            "overheat_ratio": 0.0,
        }
    positive_5d = mean([1.0 if (row.get("r5") or 0.0) > 0 else 0.0 for row in valid]) or 0.0
    positive_20d = mean([1.0 if (row.get("r20") or 0.0) > 0 else 0.0 for row in valid]) or 0.0
    near_high = mean([1.0 if row.get("near_20d_high") else 0.0 for row in valid]) or 0.0
    breakout = mean([1.0 if row.get("breakout_20d") else 0.0 for row in valid]) or 0.0
    volume_expansion = mean([1.0 if (row.get("volume_ratio_20d") or 0.0) >= 1.5 else 0.0 for row in valid]) or 0.0
    overheated = mean([1.0 if overheat_score(row) >= 2.0 else 0.0 for row in valid]) or 0.0
    score = (
        positive_5d * 20.0
        + positive_20d * 15.0
        + near_high * 25.0
        + breakout * 25.0
        + volume_expansion * 15.0
        - overheated * 15.0
    )
    return {
        "follower_positive_5d_ratio": round(positive_5d, 3),
        "follower_positive_20d_ratio": round(positive_20d, 3),
        "follower_near_high_ratio": round(near_high, 3),
        "follower_breakout_ratio": round(breakout, 3),
        "follower_volume_expansion_ratio": round(volume_expansion, 3),
        "diffusion_score": round(max(0.0, score), 2),
        "overheat_ratio": round(overheated, 3),
    }


def lifecycle_stage(theme_heat: float, leader_20: float, diffusion: dict[str, float]) -> str:
    spread = diffusion.get("diffusion_score", 0.0)
    overheat = diffusion.get("overheat_ratio", 0.0)
    breakout = diffusion.get("follower_breakout_ratio", 0.0)
    positive_5d = diffusion.get("follower_positive_5d_ratio", 0.0)
    if theme_heat < 30 or leader_20 <= 0:
        return "0_latent_or_cold"
    if theme_heat >= 45 and spread < 25:
        return "1_overseas_validated"
    if spread >= 25 and breakout < 0.25 and positive_5d >= 0.35:
        return "2_local_initial_move"
    if spread >= 45 and overheat < 0.35:
        return "3_diffusion_confirmation"
    if spread >= 55 and overheat >= 0.35:
        return "4_retail_climax_or_overheat"
    if theme_heat < 45 and spread >= 35:
        return "5_late_catchup_or_fade"
    return "2_local_initial_move"


def classify_candidate(metric: dict[str, Any], leader_20: float, gap_20: float, turn: float) -> str:
    r20 = metric.get("r20") or 0.0
    r60 = metric.get("r60") or 0.0
    heat = overheat_score(metric)
    if heat >= 2.8 and r20 > leader_20 * 0.5:
        return "overheated_catchup"
    if gap_20 < 5 and r20 > leader_20 * 0.6:
        return "already_caught_up"
    if turn >= 2.2 and gap_20 >= 8:
        return "improving_laggard"
    if gap_20 >= 15 and turn >= 1.0 and (metric.get("above_ma5") or metric.get("above_ma10")):
        return "early_turn_laggard"
    if gap_20 >= 20 and turn < 0.5 and r60 < 0:
        return "weak_not_laggard"
    if gap_20 >= 12:
        return "sleeping_laggard"
    return "neutral"


def build_scan(
    seed: dict[str, Any],
    output_dir: Path,
    refresh_history: bool,
    company_profiles: dict[str, dict[str, Any]] | None = None,
    thesis_cards: dict[str, dict[str, Any]] | None = None,
    sync_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cache_dir = output_dir / "cache" / "yahoo"
    company_rows: list[dict[str, Any]] = []
    theme_scores: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    metric_cache: dict[str, dict[str, Any]] = {}

    for theme in seed["themes"]:
        theme_nodes: list[dict[str, Any]] = []
        for node in theme["nodes"]:
            profile = (company_profiles or {}).get(node["symbol"], {})
            thesis_card = (thesis_cards or {}).get(node["symbol"], {})
            merged = {**node, "profile": profile}
            for key in ("primary_business", "specializations", "platforms", "constraints", "risk_flags", "bottleneck_profile"):
                if key in profile:
                    merged[key] = profile[key]
            if thesis_card:
                merged["thesis_card"] = thesis_card
                thesis_fields = {
                    "thesis_label": thesis_card.get("thesis_label"),
                    "primary_business": thesis_card.get("primary_business") or merged.get("primary_business"),
                    "business_segments": thesis_card.get("business_segments") or merged.get("specializations", []),
                    "ai_chain_position": thesis_card.get("ai_chain_position"),
                    "non_ai_chain_position": thesis_card.get("non_ai_chain_position"),
                    "catalysts": thesis_card.get("catalysts", []),
                    "leader_indicators": thesis_card.get("leader_indicators", []),
                    "peer_symbols": thesis_card.get("peer_symbols", []),
                    "thesis_risks": thesis_card.get("risks", []),
                    "relation_confidence": thesis_card.get("relation_confidence"),
                    "source_quality": thesis_card.get("source_quality"),
                    "manual_thesis_override": thesis_card.get("manual_override", False),
                    "agent_status": thesis_card.get("agent_status"),
                    "agent_reasoning_summary": thesis_card.get("agent_reasoning_summary"),
                    "evidence_gaps": thesis_card.get("evidence_gaps", []),
                }
                for key, value in thesis_fields.items():
                    if value not in (None, "", []):
                        merged[key] = value
            theme_nodes.append(merged)
        metrics: list[dict[str, Any]] = []
        for node in theme_nodes:
            symbol = node["symbol"]
            if symbol not in metric_cache:
                metric_cache[symbol] = company_metrics(node, cache_dir, refresh_history)
            thesis_paths = (node.get("thesis_card") or {}).get("relation_paths", [])
            metrics.append(
                dict(metric_cache[symbol])
                | {
                    "theme_id": theme["theme_id"],
                    "relation_paths": unique_text(profile_theme_paths(node, theme["theme_id"]) + thesis_paths, limit=8),
                }
            )
        company_rows.extend(metrics)
        valid = [row for row in metrics if not row.get("error")]
        leaders = [row for row in valid if row.get("role") in LEADER_ROLES]
        followers = [row for row in valid if row.get("role") in FOLLOWER_ROLES or row.get("market") == "TW"]
        leader_20_values = [row.get("r20") for row in leaders if row.get("r20") is not None]
        leader_60_values = [row.get("r60") for row in leaders if row.get("r60") is not None]
        leader_20 = median(leader_20_values) or 0.0
        leader_60 = median(leader_60_values) or 0.0
        leader_max_20 = max(leader_20_values) if leader_20_values else 0.0
        leader_breadth = mean([1.0 if (row.get("r20") or 0.0) > 0 else 0.0 for row in leaders]) or 0.0
        near_high_ratio = mean([1.0 if row.get("near_20d_high") else 0.0 for row in leaders]) or 0.0
        theme_heat = (
            clamp(leader_20 / 30.0, -0.5, 1.5) * 35.0
            + clamp(leader_60 / 60.0, -0.5, 1.2) * 25.0
            + leader_breadth * 20.0
            + near_high_ratio * 20.0
        )
        theme_heat = round(theme_heat, 2)
        diffusion = diffusion_score(followers)
        stage = lifecycle_stage(theme_heat, leader_20, diffusion)

        theme_row = {
            "theme_id": theme["theme_id"],
            "label": theme["label"],
            "theme_heat": theme_heat,
            "diffusion_score": diffusion["diffusion_score"],
            "lifecycle_stage": stage,
            "leader_20d_median": round(leader_20, 2),
            "leader_60d_median": round(leader_60, 2),
            "leader_20d_max": round(leader_max_20, 2),
            "leader_breadth": round(leader_breadth, 3),
            "leader_near_high_ratio": round(near_high_ratio, 3),
            **diffusion,
            "leaders": sorted(
                [
                    {
                        "symbol": row["symbol"],
                        "name": row["name"],
                        "market": row.get("market"),
                        "role": row.get("role"),
                        "r20": row.get("r20"),
                        "r60": row.get("r60"),
                        "near_20d_high": row.get("near_20d_high"),
                    }
                    for row in leaders
                ],
                key=lambda item: item.get("r20") or -999,
                reverse=True,
            ),
        }
        theme_scores.append(theme_row)

        for row in followers:
            gap_20 = leader_max_20 - (row.get("r20") or 0.0)
            gap_60 = leader_60 - (row.get("r60") or 0.0)
            turn = turning_score(row)
            heat_penalty = overheat_score(row)
            status = classify_candidate(row, leader_max_20, gap_20, turn)
            exposure = float(row.get("exposure") or 0.5)
            score = (
                theme_heat * 0.25
                + diffusion["diffusion_score"] * 0.12
                + clamp(gap_20, -20.0, 80.0) * 0.45
                + clamp(gap_60, -40.0, 100.0) * 0.12
                + turn * 8.0
                + exposure * 10.0
                - heat_penalty * 5.0
            )
            if status == "weak_not_laggard":
                score -= 18.0
            if status == "already_caught_up":
                score -= 12.0
            if status == "overheated_catchup":
                score -= 24.0
            if status in {"improving_laggard", "early_turn_laggard"}:
                score += 12.0
            if row.get("role") == "concept_only":
                score -= 16.0
            bottleneck = row.get("bottleneck_profile") or {}
            if "bottleneck" in theme["theme_id"] and bottleneck.get("score") is not None:
                score += clamp(float(bottleneck.get("score") or 0.0), 0.0, 5.0) * 3.0
            candidate = {
                "theme_id": theme["theme_id"],
                "theme_label": theme["label"],
                "symbol": row["symbol"],
                "name": row["name"],
                "market": row.get("market"),
                "role": row.get("role"),
                "status": status,
                "candidate_score": round(score, 2),
                "theme_heat": theme_heat,
                "diffusion_score": diffusion["diffusion_score"],
                "lifecycle_stage": stage,
                "exposure": exposure,
                "leader_20d_max": round(leader_max_20, 2),
                "leader_20d_median": round(leader_20, 2),
                "r3": row.get("r3"),
                "r5": row.get("r5"),
                "r10": row.get("r10"),
                "r20": row.get("r20"),
                "r60": row.get("r60"),
                "lag_gap_20d": round(gap_20, 2),
                "lag_gap_60d": round(gap_60, 2),
                "turning_score": turn,
                "overheat_score": heat_penalty,
                "volume_ratio_20d": row.get("volume_ratio_20d"),
                "near_20d_high": row.get("near_20d_high"),
                "breakout_20d": row.get("breakout_20d"),
                "above_ma5": row.get("above_ma5"),
                "above_ma10": row.get("above_ma10"),
                "above_ma20": row.get("above_ma20"),
                "ma20_distance_pct": row.get("ma20_distance_pct"),
                "drawdown_from_20d_high_pct": row.get("drawdown_from_20d_high_pct"),
                "asof": row.get("asof"),
                "close": row.get("close"),
                "primary_business": row.get("primary_business"),
                "specializations": row.get("specializations", []),
                "thesis_label": row.get("thesis_label"),
                "ai_chain_position": row.get("ai_chain_position"),
                "non_ai_chain_position": row.get("non_ai_chain_position"),
                "business_segments": row.get("business_segments", []),
                "catalysts": row.get("catalysts", []),
                "leader_indicators": row.get("leader_indicators", []),
                "peer_symbols": row.get("peer_symbols", []),
                "thesis_risks": row.get("thesis_risks", []),
                "relation_confidence": row.get("relation_confidence"),
                "source_quality": row.get("source_quality"),
                "manual_thesis_override": row.get("manual_thesis_override"),
                "agent_status": row.get("agent_status"),
                "agent_reasoning_summary": row.get("agent_reasoning_summary"),
                "evidence_gaps": row.get("evidence_gaps", []),
                "relation_paths": row.get("relation_paths", []),
                "risk_flags": row.get("risk_flags", []),
                "bottleneck_profile": row.get("bottleneck_profile", {}),
            }
            candidates.append(candidate)

    theme_scores.sort(key=lambda row: row["theme_heat"], reverse=True)
    candidates.sort(key=lambda row: row["candidate_score"], reverse=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "company_metrics.jsonl", company_rows)
    write_json(output_dir / "theme_scores.json", theme_scores)
    write_json(output_dir / "laggard_candidates.json", candidates)
    write_json(output_dir / "synced_theme_seed.json", seed)
    write_json(
        output_dir / "build_manifest.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "seed_schema": seed.get("schema_version"),
            "seed_updated_at": seed.get("updated_at"),
            "seed_sync_source": seed.get("sync_source"),
            "theme_count": len(seed.get("themes", [])),
            "company_profile_count": len(company_profiles or {}),
            "company_thesis_card_count": len(thesis_cards or {}),
            "unique_company_metric_count": len(metric_cache),
            "company_metric_count": len(company_rows),
            "candidate_count": len(candidates),
            "thememiner_sync": sync_info or {"enabled": False},
        },
    )
    write_report(output_dir / "theme_report.md", theme_scores, candidates)
    return {"theme_scores": theme_scores, "candidates": candidates}


def fmt(value: Any, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def write_report(path: Path, themes: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> None:
    lines = [
        "# Lagradar Report",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Theme Heat",
        "",
        "| Rank | Theme | Heat | Leader 20d | Leader 60d | Diffusion | Overheat |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(themes, start=1):
        lines.append(
            f"| {idx} | {row['label']}<br>{row['lifecycle_stage']} | {fmt(row['theme_heat'])} | {fmt(row['leader_20d_median'])}% | "
            f"{fmt(row['leader_60d_median'])}% | {fmt(row['diffusion_score'], 1)} | {fmt(row['overheat_ratio'], 2)} |"
        )
    lines.extend(
        [
            "",
            "## Top Laggard Candidates",
            "",
            "| Rank | Candidate | Theme | Status | Score | 20d Gap | r5 | r20 | Turn | Heat | Volume |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for idx, row in enumerate(candidates[:30], start=1):
        lines.append(
            f"| {idx} | {row['name']} `{row['symbol']}` | {row['theme_label']} | {row['status']} | "
            f"{fmt(row['candidate_score'])} | {fmt(row['lag_gap_20d'])}% | {fmt(row['r5'])}% | "
            f"{fmt(row['r20'])}% | {fmt(row['turning_score'], 2)} | {fmt(row['overheat_score'], 2)} | {fmt(row['volume_ratio_20d'], 2)}x |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan cross-market theme laggards")
    parser.add_argument("--seed", default="lagradar/data/cross_market_theme_seed.json")
    parser.add_argument("--output-dir", default="lagradar/output")
    parser.add_argument("--company-profiles", default="thememiner/output/company_profiles.json")
    parser.add_argument("--company-thesis-cards", default="thememiner/output/company_thesis_cards.json")
    parser.add_argument("--thememiner-output", default="thememiner/output")
    parser.add_argument("--no-sync-thememiner", action="store_true", help="Disable automatic ThemeMiner concept/profile sync")
    parser.add_argument("--thememiner-min-score", type=float, default=0.0)
    parser.add_argument("--thememiner-min-markets", type=int, default=1)
    parser.add_argument("--max-thememiner-themes", type=int, default=0, help="0 means no cap")
    parser.add_argument("--max-thememiner-nodes-per-theme", type=int, default=0, help="0 means no cap")
    parser.add_argument("--refresh-history", action="store_true")
    args = parser.parse_args()

    seed = read_json(Path(args.seed))
    if seed.get("schema_version") != "lagradar_seed_v1":
        raise RuntimeError(f"unexpected seed schema: {seed.get('schema_version')}")
    thememiner_bundle = {} if args.no_sync_thememiner else load_thememiner_bundle(Path(args.thememiner_output))
    seed, sync_info = sync_seed_with_thememiner(
        seed,
        thememiner_bundle,
        min_score=args.thememiner_min_score,
        min_markets=args.thememiner_min_markets,
        max_themes=args.max_thememiner_themes,
        max_nodes_per_theme=args.max_thememiner_nodes_per_theme,
    )
    company_profiles = {**(thememiner_bundle.get("company_profiles") or {}), **load_company_profiles(Path(args.company_profiles))}
    thesis_cards = load_company_thesis_cards(Path(args.company_thesis_cards))
    result = build_scan(seed, Path(args.output_dir), args.refresh_history, company_profiles, thesis_cards, sync_info)
    print(f"Wrote {len(result['theme_scores'])} theme scores and {len(result['candidates'])} candidates to {args.output_dir}")
    if sync_info.get("enabled"):
        print(
            "Synced ThemeMiner "
            f"{sync_info.get('synced_concept_count')} concepts, "
            f"{sync_info.get('company_profile_count')} profiles "
            f"from {sync_info.get('output_dir')}"
        )
    if thesis_cards:
        print(f"Merged {len(thesis_cards)} company thesis cards from {args.company_thesis_cards}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
