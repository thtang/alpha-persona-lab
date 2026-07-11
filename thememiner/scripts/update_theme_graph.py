#!/usr/bin/env python3
"""Refresh fine-grained theme library and cross-market stock graph."""

from __future__ import annotations

import argparse
import email.utils
import json
import math
import re
import statistics
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


USER_AGENT = "alpha-persona-lab-thememiner/0.1"
LEADER_ROLES = {"global_leader", "regional_leader", "high_beta_leader"}
# Legacy seed-theme bridge only. Stock-level business fit is judged by
# company profiles/thesis cards, not by this theme-id map.
THEME_TO_CONCEPTS = {
    "ai_compute_capex_custom_silicon": ["ai_capex", "gpu_accelerator", "tpu_cloud", "ai_foundry_capacity", "ip_asic", "foundry", "cowos", "ems"],
    "agentic_cpu_memory_stack": [
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
    ],
    "passive_components": [
        "passive_components",
        "high_voltage_mlcc",
        "aluminum_polymer_cap",
        "snap_in_capacitor",
        "film_capacitor",
        "chip_resistor",
        "inductor_choke",
        "tantalum_capacitor",
        "passive_component_distribution",
    ],
    "power_grid_transformer": ["smart_grid", "transformer_ups"],
    "memory_hbm": ["hbm", "dram_manufacturing", "memory_ic_design", "legacy_memory"],
    "ai_server_power_thermal": ["gb200", "gb300", "vera_rubin", "thermal_components", "power_supply", "ems"],
    "pcb_abf_ccl": ["pcb_manufacturing", "pcb_material_equipment", "abf_substrate"],
    "optical_800g_cpo": ["cpo_optical", "laser_capacity", "inp_photonics", "silicon_photonics", "specialty_glass_fiber", "networking"],
    "ai_photonics_bottleneck_stack": [
        "cpo_optical",
        "laser_capacity",
        "inp_photonics",
        "silicon_photonics",
        "soi_wafer",
        "epitaxy_equipment",
        "specialty_glass_fiber",
        "optical_interposer_packaging",
        "networking",
    ],
    "copper_industrial_metals": ["copper", "wire_cable", "metal_parts"],
    "energy_oil_lng": ["oil_lng", "chemicals"],
    "shipping_freight": ["shipping", "logistics"],
    "defense_aerospace": ["defense", "drone"],
    "healthcare_glp1_cdmo": ["glp1_obesity", "cdmo_cro", "new_drug"],
    "banks_rates_insurance": ["banks", "insurance", "financial_holding"],
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


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
    value = (close / previous - 1.0) * 100.0
    return value if math.isfinite(value) else None


def is_cache_fresh(path: Path, max_age_hours: float) -> bool:
    if not path.exists():
        return False
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.now(timezone.utc) - modified <= timedelta(hours=max_age_hours)


def safe_symbol(symbol: str) -> str:
    return (
        symbol.replace("^", "INDEX_")
        .replace("=", "_")
        .replace("/", "_")
        .replace(".", "_")
        .replace("-", "_")
    )


def url_text(url: str, *, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def url_json(url: str, *, timeout: int = 25) -> Any:
    return json.loads(url_text(url, timeout=timeout))


def slugify(value: str) -> str:
    normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", str(value).strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized[:90] or "unknown"


def unique(values: list[Any]) -> list[Any]:
    return list(dict.fromkeys(value for value in values if value not in (None, "", [])))


def flatten_taxonomy(taxonomy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    concepts: dict[str, dict[str, Any]] = {}
    for category in taxonomy.get("categories", []):
        for concept in category.get("concepts", []):
            concepts[concept["concept_id"]] = {
                **concept,
                "category_id": category["category_id"],
                "category_label": category["label"],
                "aliases": list(dict.fromkeys([concept["label"], concept["concept_id"]] + concept.get("aliases", []))),
            }
    return concepts


def load_supply_chain_rules(path: Path | None, known_concepts: set[str]) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    payload = read_json(path)
    rows: list[dict[str, Any]] = []
    for rule in payload.get("rules", []):
        concept_id = rule.get("concept_id")
        if concept_id not in known_concepts:
            continue
        rows.append(
            {
                **rule,
                "upstream_concepts": [item for item in rule.get("upstream_concepts", []) if item in known_concepts],
                "downstream_concepts": [item for item in rule.get("downstream_concepts", []) if item in known_concepts],
            }
        )
    return rows


def concept_ids_from_profile(profile: dict[str, Any], known_concepts: set[str]) -> list[str]:
    concepts: list[str] = []
    for concept_id in profile.get("concepts", []):
        if concept_id in known_concepts:
            concepts.append(concept_id)
    for exposure in profile.get("concept_exposures", []):
        concept_id = exposure.get("concept_id")
        if concept_id in known_concepts:
            concepts.append(concept_id)
    return sorted(set(concepts))


def load_company_profiles(profiles_path: Path | None, known_concepts: set[str]) -> dict[str, dict[str, Any]]:
    if not profiles_path or not profiles_path.exists():
        return {}
    data = read_json(profiles_path)
    profiles: dict[str, dict[str, Any]] = {}
    for profile in data.get("profiles", []):
        symbol = profile.get("symbol")
        if not symbol:
            continue
        normalized = dict(profile)
        normalized["concepts_from_profile"] = concept_ids_from_profile(profile, known_concepts)
        profiles[symbol] = normalized
    return profiles


def merge_profile_maps(*maps: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for profile_map in maps:
        for symbol, profile in profile_map.items():
            if symbol not in merged:
                merged[symbol] = profile
                continue
            base = merged[symbol]
            combined = {**base, **profile}
            if base.get("source_evidence") and not profile.get("source_evidence"):
                combined["source_evidence"] = base["source_evidence"]
            if base.get("source_business_summary") and not profile.get("source_business_summary"):
                combined["source_business_summary"] = base["source_business_summary"]
            base_refs = base.get("source_refs") or []
            profile_refs = profile.get("source_refs") or []
            if base_refs or profile_refs:
                seen_refs: set[str] = set()
                combined_refs: list[dict[str, Any]] = []
                for ref in profile_refs + base_refs:
                    if not isinstance(ref, dict):
                        continue
                    url = ref.get("url")
                    if not url or url in seen_refs:
                        continue
                    seen_refs.add(url)
                    combined_refs.append(ref)
                combined["source_refs"] = combined_refs
            if isinstance(base.get("official_metadata"), dict) or isinstance(profile.get("official_metadata"), dict):
                combined["official_metadata"] = {
                    **(base.get("official_metadata") if isinstance(base.get("official_metadata"), dict) else {}),
                    **(profile.get("official_metadata") if isinstance(profile.get("official_metadata"), dict) else {}),
                }
            if base.get("profile_evidence_quality") and not profile.get("profile_evidence_quality"):
                combined["profile_evidence_quality"] = base["profile_evidence_quality"]
            elif base.get("profile_evidence_quality") and profile.get("profile_evidence_quality"):
                base_quality = str(base["profile_evidence_quality"])
                profile_quality = str(profile["profile_evidence_quality"])
                if "scrapling_source_evidence" in base_quality and "scrapling_source_evidence" not in profile_quality:
                    combined["profile_evidence_quality"] = f"{profile_quality}+scrapling_source_evidence"
            merged[symbol] = combined
    return merged


def merge_company_profiles(
    nodes: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    known_concepts: set[str],
) -> dict[str, dict[str, Any]]:
    for symbol, profile in profiles.items():
        item = nodes.setdefault(
            symbol,
            {
                "symbol": symbol,
                "name": profile.get("name", symbol),
                "market": profile.get("market"),
                "region": profile.get("region"),
                "concepts": [],
                "sources": [],
            },
        )
        item["name"] = item.get("name") or profile.get("name", symbol)
        item["market"] = item.get("market") or profile.get("market")
        item["region"] = item.get("region") or profile.get("region")
        item["concepts"].extend([concept for concept in profile.get("concepts_from_profile", []) if concept in known_concepts])
        item["sources"].append("company_profile")
        item["profile"] = profile
    return nodes


def merge_discovered_universe(
    nodes: dict[str, dict[str, Any]],
    discovered_path: Path | None,
    known_concepts: set[str],
    *,
    max_discovered: int = 0,
) -> dict[str, dict[str, Any]]:
    if not discovered_path or not discovered_path.exists():
        return nodes
    data = read_json(discovered_path)
    discovered_rows = [
        node
        for node in data.get("nodes", [])
        if node.get("symbol") and any(concept in known_concepts for concept in node.get("concepts", []))
    ]
    discovered_rows.sort(
        key=lambda node: (
            node.get("discovery_score", 0),
            len(node.get("concepts", [])),
            node.get("market") or "",
            node.get("symbol") or "",
        ),
        reverse=True,
    )
    if max_discovered:
        discovered_rows = discovered_rows[:max_discovered]

    for node in discovered_rows:
        concepts = [concept for concept in node.get("concepts", []) if concept in known_concepts]
        item = nodes.setdefault(
            node["symbol"],
            {
                "symbol": node["symbol"],
                "name": node.get("name", node["symbol"]),
                "market": node.get("market"),
                "region": node.get("region"),
                "concepts": [],
                "sources": [],
            },
        )
        item["name"] = item.get("name") or node.get("name", node["symbol"])
        item["market"] = item.get("market") or node.get("market")
        item["region"] = item.get("region") or node.get("region")
        item["exchange"] = item.get("exchange") or node.get("exchange")
        item["raw_industry"] = item.get("raw_industry") or node.get("raw_industry")
        item["concepts"].extend(concepts)
        item["sources"].append("discovered_universe")
        item["discovery_score"] = max(float(item.get("discovery_score", 0) or 0), float(node.get("discovery_score", 0) or 0))
        item["discovery_sources"] = sorted(set(item.get("discovery_sources", []) + node.get("discovery_sources", [])))
        item["match_reasons"] = list(dict.fromkeys(item.get("match_reasons", []) + node.get("match_reasons", [])))
        item["concept_scores"] = {**node.get("concept_scores", {}), **item.get("concept_scores", {})}
        item["supply_chain_profile"] = merge_supply_chain_profiles(
            item.get("supply_chain_profile") or {},
            node.get("supply_chain_profile") or {},
        )
        if node.get("profile") and not item.get("profile"):
            item["profile"] = node["profile"]
    return nodes


def merge_supply_chain_profiles(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left or {})
    for key in ("layers", "products", "upstream_concepts", "downstream_concepts"):
        merged[key] = sorted(set((left or {}).get(key, []) + (right or {}).get(key, [])))
    merged["matched_rules"] = (left or {}).get("matched_rules", []) + (right or {}).get("matched_rules", [])
    return merged


def load_watchlist(
    watchlist_path: Path,
    lagradar_seed_path: Path | None,
    known_concepts: set[str],
    profiles_path: Path | None = None,
    profiles: dict[str, dict[str, Any]] | None = None,
    discovered_path: Path | None = None,
    max_discovered: int = 0,
) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    profiles = profiles if profiles is not None else load_company_profiles(profiles_path, known_concepts)
    if watchlist_path.exists():
        for node in read_json(watchlist_path).get("nodes", []):
            item = nodes.setdefault(
                node["symbol"],
                {
                    "symbol": node["symbol"],
                    "name": node.get("name", node["symbol"]),
                    "market": node.get("market"),
                    "region": node.get("region"),
                    "concepts": [],
                    "sources": [],
                },
            )
            item["concepts"].extend([concept for concept in node.get("concepts", []) if concept in known_concepts])
            item["sources"].append("watchlist_seed")

    if lagradar_seed_path and lagradar_seed_path.exists():
        lagradar = read_json(lagradar_seed_path)
        for theme in lagradar.get("themes", []):
            mapped = [concept for concept in THEME_TO_CONCEPTS.get(theme["theme_id"], []) if concept in known_concepts]
            for node in theme.get("nodes", []):
                profile_concepts = set((profiles.get(node["symbol"], {}) or {}).get("concepts_from_profile", []))
                existing_concepts = set((nodes.get(node["symbol"], {}) or {}).get("concepts", []))
                if profile_concepts:
                    node_concepts = [concept for concept in mapped if concept in profile_concepts]
                elif existing_concepts:
                    node_concepts = [concept for concept in mapped if concept in existing_concepts]
                else:
                    node_concepts = mapped
                item = nodes.setdefault(
                    node["symbol"],
                    {
                        "symbol": node["symbol"],
                        "name": node.get("name", node["symbol"]),
                        "market": node.get("market"),
                        "region": node.get("region"),
                        "concepts": [],
                        "sources": [],
                    },
                )
                item["concepts"].extend(node_concepts)
                item["role"] = node.get("role")
                item["sources"].append("lagradar_seed")

    merge_discovered_universe(nodes, discovered_path, known_concepts, max_discovered=max_discovered)
    merge_company_profiles(nodes, profiles, known_concepts)

    for item in nodes.values():
        item["concepts"] = sorted(set(item["concepts"]))
        item["sources"] = sorted(set(item["sources"]))
    return {symbol: item for symbol, item in nodes.items() if item["concepts"]}


def profile_exposure_for(node: dict[str, Any], concept_id: str) -> dict[str, Any] | None:
    profile = node.get("profile") or {}
    for exposure in profile.get("concept_exposures", []):
        if exposure.get("concept_id") == concept_id:
            return exposure
    return None


def discovery_exposure_for(node: dict[str, Any], concept_id: str) -> dict[str, Any] | None:
    profile = node.get("supply_chain_profile") or (node.get("profile") or {}).get("supply_chain_profile") or {}
    matched = [rule for rule in profile.get("matched_rules", []) if rule.get("concept_id") == concept_id]
    if not matched and concept_id not in node.get("concepts", []):
        return None
    concept_score = (node.get("concept_scores") or {}).get(concept_id)
    weight = 0.48
    if concept_score is not None:
        weight = min(0.78, 0.42 + float(concept_score) / 100.0 * 0.36)
    if not matched:
        return {
            "weight": weight,
            "role": "discovered_exchange_rules",
            "path": "exchange industry/product rule -> concept candidate",
            "evidence": node.get("match_reasons", [])[:4],
        }

    products = sorted({product for rule in matched for product in rule.get("products", [])})
    layers = sorted({rule.get("layer") for rule in matched if rule.get("layer")})
    keywords = sorted({keyword for rule in matched for keyword in rule.get("matched_keywords", [])})
    return {
        "weight": weight,
        "role": "discovered_supply_chain_match",
        "path": " / ".join([", ".join(layers[:2]), ", ".join(products[:4])]).strip(" /"),
        "evidence": [f"matched keywords: {', '.join(keywords[:8])}" if keywords else "matched product/supply-chain rule"],
    }


def fetch_yahoo_history(symbol: str, cache_dir: Path, *, price_range: str, refresh: bool) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{safe_symbol(symbol)}_{price_range}.json"
    if not refresh and is_cache_fresh(cache_path, 4):
        return read_json(cache_path).get("rows", [])

    encoded = urllib.parse.quote(symbol, safe="")
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{encoded}?range={price_range}&interval=1d"
    data = url_json(url)
    chart = data.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(chart["error"])
    result = (chart.get("result") or [None])[0]
    if not result:
        raise RuntimeError("empty Yahoo chart result")

    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    rows: list[dict[str, Any]] = []
    for idx, ts in enumerate(timestamps):
        close = (quote.get("close") or [None] * len(timestamps))[idx]
        if close is None:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                "open": (quote.get("open") or [None] * len(timestamps))[idx],
                "high": (quote.get("high") or [None] * len(timestamps))[idx],
                "low": (quote.get("low") or [None] * len(timestamps))[idx],
                "close": close,
                "volume": (quote.get("volume") or [None] * len(timestamps))[idx],
            }
        )
    write_json(cache_path, {"symbol": symbol, "fetched_at": datetime.now(timezone.utc).isoformat(), "rows": rows})
    time.sleep(0.03)
    return rows


def stock_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 22:
        return {"error": f"too few rows: {len(rows)}"}
    close = rows[-1]["close"]
    metric = {
        "asof": rows[-1]["date"],
        "close": close,
        "r1": pct_change(close, rows[-2]["close"]) if len(rows) > 1 else None,
        "r3": pct_change(close, rows[-4]["close"]) if len(rows) > 3 else None,
        "r5": pct_change(close, rows[-6]["close"]) if len(rows) > 5 else None,
        "r20": pct_change(close, rows[-21]["close"]) if len(rows) > 20 else None,
    }
    volumes = [float(row["volume"]) for row in rows[-21:-1] if row.get("volume")]
    avg_volume = mean(volumes)
    metric["volume_ratio_20d"] = (float(rows[-1]["volume"]) / avg_volume) if rows[-1].get("volume") and avg_volume else None
    highs = [float(row["high"]) for row in rows[-20:] if row.get("high")]
    if highs:
        high_20 = max(highs)
        metric["near_20d_high"] = bool(close >= high_20 * 0.95)
        metric["breakout_20d"] = bool(close >= high_20 * 0.995)
    return metric


def daily_return_series(rows: list[dict[str, Any]], *, max_points: int = 100) -> list[tuple[str, float]]:
    closes = [(row.get("date"), row.get("close")) for row in rows if row.get("date") and row.get("close") not in (None, 0)]
    if len(closes) < 3:
        return []
    if len(closes) > max_points + 1:
        closes = closes[-max_points - 1 :]
    returns: list[tuple[str, float]] = []
    for idx in range(1, len(closes)):
        date, close = closes[idx]
        _, previous = closes[idx - 1]
        value = pct_change(float(close), float(previous))
        if value is not None and math.isfinite(value):
            returns.append((str(date), value / 100.0))
    return returns


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_var = sum((value - left_mean) ** 2 for value in left)
    right_var = sum((value - right_mean) ** 2 for value in right)
    if left_var <= 0 or right_var <= 0:
        return None
    covariance = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    value = covariance / math.sqrt(left_var * right_var)
    return value if math.isfinite(value) else None


def lead_lag_correlation(
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
    *,
    max_lag_days: int = 5,
    min_samples: int = 28,
) -> dict[str, Any] | None:
    series_a = daily_return_series(rows_a)
    series_b = daily_return_series(rows_b)
    map_a = {date: value for date, value in series_a}
    map_b = {date: value for date, value in series_b}
    dates = sorted(set(map_a) & set(map_b))
    if len(dates) < min_samples:
        return None
    best: dict[str, Any] | None = None
    for lag in range(-max_lag_days, max_lag_days + 1):
        left: list[float] = []
        right: list[float] = []
        if lag >= 0:
            pairs = [(dates[idx], dates[idx + lag]) for idx in range(0, len(dates) - lag)]
            lead = "left" if lag > 0 else "sync"
        else:
            offset = abs(lag)
            pairs = [(dates[idx + offset], dates[idx]) for idx in range(0, len(dates) - offset)]
            lead = "right"
        for date_a, date_b in pairs:
            left.append(map_a[date_a])
            right.append(map_b[date_b])
        if len(left) < min_samples:
            continue
        corr = pearson(left, right)
        if corr is None:
            continue
        row = {"correlation": corr, "lag_days": lag, "lead_side": lead, "sample_size": len(left)}
        if best is None or abs(corr) > abs(best["correlation"]):
            best = row
    if not best:
        return None
    best["correlation"] = round(best["correlation"], 4)
    return best


def correlation_edges(
    active_concepts: dict[str, dict[str, Any]],
    watchlist: dict[str, dict[str, Any]],
    history_rows: dict[str, list[dict[str, Any]]],
    *,
    min_abs_corr: float = 0.45,
    max_edges_per_concept: int = 90,
) -> list[dict[str, Any]]:
    by_concept: dict[str, list[str]] = {}
    for symbol, node in watchlist.items():
        if symbol not in history_rows:
            continue
        for concept_id in node.get("concepts", []):
            if concept_id in active_concepts:
                by_concept.setdefault(concept_id, []).append(symbol)

    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for concept_id, symbols in by_concept.items():
        unique_symbols = sorted(set(symbols))
        concept_edges: list[dict[str, Any]] = []
        for idx, source in enumerate(unique_symbols):
            for target in unique_symbols[idx + 1 :]:
                source_rows = history_rows.get(source) or []
                target_rows = history_rows.get(target) or []
                stats = lead_lag_correlation(source_rows, target_rows)
                if not stats or abs(stats["correlation"]) < min_abs_corr:
                    continue
                key = (concept_id, source, target)
                if key in seen:
                    continue
                seen.add(key)
                lag_days = stats["lag_days"]
                lead_symbol = None
                lag_direction = "sync"
                if lag_days > 0:
                    lead_symbol = source
                    lag_direction = f"{source} leads {target} by {lag_days} common sessions"
                elif lag_days < 0:
                    lead_symbol = target
                    lag_direction = f"{target} leads {source} by {abs(lag_days)} common sessions"
                concept_edges.append(
                    {
                        "source": f"stock:{source}",
                        "target": f"stock:{target}",
                        "type": "price_correlation",
                        "concept_id": concept_id,
                        "markets": [watchlist[source].get("market"), watchlist[target].get("market")],
                        "weight": round(min(1.0, abs(stats["correlation"])), 3),
                        "correlation": stats["correlation"],
                        "lag_days": lag_days,
                        "lag_direction": lag_direction,
                        "lead_symbol": lead_symbol,
                        "sample_size": stats["sample_size"],
                    }
                )
        concept_edges.sort(key=lambda row: abs(row["correlation"]), reverse=True)
        edges.extend(concept_edges[:max_edges_per_concept])
    return edges


def limited_peer_edges(
    groups: dict[str, list[str]],
    watchlist: dict[str, dict[str, Any]],
    *,
    edge_type: str,
    group_field: str,
    max_edges_per_group: int = 80,
    cross_market_only: bool = True,
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for group_id, symbols in groups.items():
        ranked = sorted(
            set(symbols),
            key=lambda symbol: (
                -float(watchlist.get(symbol, {}).get("discovery_score", 0) or 0),
                watchlist.get(symbol, {}).get("market") or "",
                symbol,
            ),
        )
        group_edges: list[dict[str, Any]] = []
        for idx, source in enumerate(ranked):
            for target in ranked[idx + 1 :]:
                source_market = watchlist[source].get("market")
                target_market = watchlist[target].get("market")
                if cross_market_only and source_market == target_market:
                    continue
                key = (edge_type, group_id, source, target)
                if key in seen:
                    continue
                seen.add(key)
                group_edges.append(
                    {
                        "source": f"stock:{source}",
                        "target": f"stock:{target}",
                        "type": edge_type,
                        group_field: group_id,
                        "markets": [source_market, target_market],
                        "weight": 0.36,
                    }
                )
                if len(group_edges) >= max_edges_per_group:
                    break
            if len(group_edges) >= max_edges_per_group:
                break
        edges.extend(group_edges)
    return edges


def fetch_news(concept: dict[str, Any], cache_dir: Path, *, refresh: bool, limit: int) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{concept['concept_id']}.json"
    if not refresh and is_cache_fresh(cache_path, 6):
        return read_json(cache_path).get("rows", [])[:limit]

    query_terms = [concept["label"]] + concept.get("aliases", [])[:4]
    query = " OR ".join(f'"{term}"' if " " in term else term for term in query_terms)
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"({query}) stock OR 股票 OR semiconductor OR market", "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"}
    )
    rows: list[dict[str, Any]] = []
    try:
        xml_text = url_text(url)
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            source = item.findtext("source") or ""
            published_raw = item.findtext("pubDate") or ""
            published_at = None
            if published_raw:
                try:
                    published_at = email.utils.parsedate_to_datetime(published_raw).astimezone(timezone.utc).isoformat()
                except Exception:
                    published_at = published_raw
            rows.append(
                {
                    "concept_id": concept["concept_id"],
                    "concept_label": concept["label"],
                    "title": title,
                    "source": source,
                    "url": link,
                    "published_at": published_at,
                }
            )
    except Exception as exc:
        rows.append(
            {
                "concept_id": concept["concept_id"],
                "concept_label": concept["label"],
                "error": str(exc),
            }
        )
    write_json(cache_path, {"concept_id": concept["concept_id"], "fetched_at": datetime.now(timezone.utc).isoformat(), "rows": rows})
    time.sleep(0.03)
    return rows[:limit]


def load_external_evidence(paths: list[str], concepts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in paths:
        path = Path(value)
        if not path.exists():
            continue
        for row in read_jsonl(path):
            concept_id = row.get("concept_id")
            if concept_id not in concepts:
                continue
            title = row.get("title") or row.get("text") or ""
            rows.append(
                {
                    "concept_id": concept_id,
                    "concept_label": row.get("concept_label") or concepts[concept_id]["label"],
                    "title": title,
                    "source": row.get("source") or f"external:{path.name}",
                    "url": row.get("url") or "",
                    "published_at": row.get("published_at"),
                    "external_evidence_path": str(path),
                    "evidence_tier": row.get("evidence_tier"),
                    "evidence_kind": row.get("evidence_kind", "external"),
                    "post_id": row.get("post_id"),
                    "transcript_id": row.get("transcript_id"),
                    "match_authority": row.get("match_authority"),
                    "matched_terms": row.get("matched_terms", []),
                    "evidence_policy": row.get("evidence_policy"),
                }
            )
    return rows


def compute_concept_scores(
    concepts: dict[str, dict[str, Any]],
    watchlist: dict[str, dict[str, Any]],
    stock_rows: dict[str, dict[str, Any]],
    news_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    news_by_concept: dict[str, list[dict[str, Any]]] = {}
    for row in news_rows:
        news_by_concept.setdefault(row["concept_id"], []).append(row)

    symbols_by_concept: dict[str, list[str]] = {concept_id: [] for concept_id in concepts}
    for symbol, node in watchlist.items():
        for concept_id in node.get("concepts", []):
            symbols_by_concept.setdefault(concept_id, []).append(symbol)

    rows: list[dict[str, Any]] = []
    for concept_id, concept in concepts.items():
        symbols = sorted(set(symbols_by_concept.get(concept_id, [])))
        metrics = [stock_rows[symbol] for symbol in symbols if symbol in stock_rows and not stock_rows[symbol].get("error")]
        markets = sorted({watchlist[symbol].get("market") for symbol in symbols if symbol in watchlist and watchlist[symbol].get("market")})
        news = [row for row in news_by_concept.get(concept_id, []) if not row.get("error")]
        errors = [row for row in news_by_concept.get(concept_id, []) if row.get("error")]
        r5 = median([row.get("r5") for row in metrics if row.get("r5") is not None])
        r20 = median([row.get("r20") for row in metrics if row.get("r20") is not None])
        breakout_ratio = mean([1.0 if row.get("breakout_20d") else 0.0 for row in metrics]) or 0.0
        volume_ratio = median([row.get("volume_ratio_20d") for row in metrics if row.get("volume_ratio_20d") is not None])
        news_score = clamp(len(news) * 10 + len({row.get("source") for row in news if row.get("source")}) * 4, 0, 100)
        price_score = (
            clamp((r5 or 0.0) / 10.0, -0.5, 1.5) * 28
            + clamp((r20 or 0.0) / 25.0, -0.5, 1.5) * 32
            + breakout_ratio * 25
            + clamp(((volume_ratio or 1.0) - 1.0) / 1.5, -0.2, 1.0) * 15
        )
        cross_market_score = min(len(markets), 5) * 12
        score = news_score * 0.3 + price_score * 0.5 + cross_market_score * 0.2
        if len(markets) >= 2 and score >= 45:
            stage = "active_cross_market"
        elif price_score >= 35 and symbols:
            stage = "price_active"
        elif news_score >= 35:
            stage = "news_active"
        else:
            stage = "quiet"
        rows.append(
            {
                "concept_id": concept_id,
                "label": concept["label"],
                "category_id": concept["category_id"],
                "category_label": concept["category_label"],
                "score": round(score, 2),
                "stage": stage,
                "market_count": len(markets),
                "markets": markets,
                "stock_count": len(symbols),
                "symbols": symbols,
                "news_count": len(news),
                "news_error_count": len(errors),
                "r5_median": None if r5 is None else round(r5, 2),
                "r20_median": None if r20 is None else round(r20, 2),
                "breakout_ratio": round(breakout_ratio, 3),
                "volume_ratio_median": None if volume_ratio is None else round(volume_ratio, 2),
                "top_headlines": news[:5],
            }
        )
    rows.sort(key=lambda row: row["score"], reverse=True)
    return rows


def build_graph(
    theme_rows: list[dict[str, Any]],
    watchlist: dict[str, dict[str, Any]],
    stock_rows: dict[str, dict[str, Any]],
    history_rows: dict[str, list[dict[str, Any]]] | None = None,
    supply_chain_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    active_concepts = {row["concept_id"]: row for row in theme_rows if row["score"] >= 20 or row["stock_count"] > 0}
    theme_lookup = {row["concept_id"]: row for row in theme_rows}
    supply_chain_rules = supply_chain_rules or []

    def add_node(node: dict[str, Any]) -> None:
        node_id = node.get("id")
        if not node_id or node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append(node)

    def profile_value(node: dict[str, Any], key: str, fallback: Any = None) -> Any:
        profile = node.get("profile") or {}
        return profile.get(key) or fallback

    def concept_labels(node: dict[str, Any]) -> list[str]:
        labels: list[str] = []
        for concept_id in node.get("concepts", []):
            row = theme_lookup.get(concept_id)
            if row and row.get("label"):
                labels.append(row["label"])
        return labels

    def rule_profile_for_concepts(concept_ids: list[str], products: list[str] | None = None) -> dict[str, Any]:
        layers: list[str] = []
        rule_products: list[str] = list(products or [])
        upstream: list[str] = []
        downstream: list[str] = []
        matched_rules: list[dict[str, Any]] = []
        for concept_id in concept_ids:
            for rule in rule_for_concept(concept_id):
                layers.extend([rule.get("layer")] if rule.get("layer") else [])
                rule_products.extend(rule.get("products", []))
                upstream.extend(rule.get("upstream_concepts", []))
                downstream.extend(rule.get("downstream_concepts", []))
                matched_rules.append(
                    {
                        "concept_id": concept_id,
                        "layer": rule.get("layer"),
                        "products": rule.get("products", []),
                        "upstream_concepts": rule.get("upstream_concepts", []),
                        "downstream_concepts": rule.get("downstream_concepts", []),
                    }
                )
        return {
            "layers": sorted(set(layers)),
            "products": sorted(set(rule_products)),
            "upstream_concepts": sorted(set(upstream)),
            "downstream_concepts": sorted(set(downstream)),
            "matched_rules": matched_rules,
        }

    def supply_chain_profile(node: dict[str, Any]) -> dict[str, Any]:
        profile = node.get("profile") or {}
        profile_quality = profile.get("profile_quality")
        is_curated = bool(profile) and profile_quality not in {"auto_yahoo_search", "discovered_exchange_rules"}
        if is_curated:
            concept_ids = concept_ids_from_profile(profile, set(theme_lookup)) or node.get("concepts", [])
            profile_products = unique((profile.get("products") or []) + (profile.get("specializations") or []))
            derived = rule_profile_for_concepts(concept_ids, profile_products)
            return merge_supply_chain_profiles(derived, profile.get("supply_chain_profile") or {})
        return merge_supply_chain_profiles(node.get("supply_chain_profile") or {}, profile.get("supply_chain_profile") or {})

    def fallback_business(node: dict[str, Any]) -> str:
        labels = concept_labels(node)
        supply_chain = supply_chain_profile(node)
        products = supply_chain.get("products", [])
        layers = supply_chain.get("layers", [])
        if labels:
            product_text = f" Product clues: {', '.join(products[:5])}." if products else ""
            layer_text = f" Supply-chain layer: {', '.join(layers[:3])}." if layers else ""
            return (
                f"{node.get('name', node.get('symbol'))} is tracked as a {' / '.join(labels[:4])} theme node."
                f"{product_text}{layer_text} Full company profile pending."
            )
        return f"{node.get('name', node.get('symbol'))} is tracked in the cross-market watchlist; full company profile pending."

    def fallback_sector(node: dict[str, Any]) -> str | None:
        categories: list[str] = []
        for concept_id in node.get("concepts", []):
            row = theme_lookup.get(concept_id)
            if row and row.get("category_label"):
                categories.append(row["category_label"])
        unique = list(dict.fromkeys(categories))
        return " / ".join(unique[:2]) if unique else None

    def rule_for_concept(concept_id: str) -> list[dict[str, Any]]:
        return [rule for rule in supply_chain_rules if rule.get("concept_id") == concept_id]

    category_seen: set[str] = set()
    for concept_id, row in active_concepts.items():
        category_id = row.get("category_id") or slugify(row.get("category_label") or "uncategorized")
        if category_id not in category_seen:
            category_seen.add(category_id)
            add_node(
                {
                    "id": f"category:{category_id}",
                    "type": "category",
                    "label": row.get("category_label") or category_id,
                    "category_id": category_id,
                }
            )
        add_node({"id": f"concept:{concept_id}", "type": "concept", **{k: row[k] for k in ("label", "category_label", "score", "stage", "markets", "stock_count")}})
        edges.append(
            {
                "source": f"category:{category_id}",
                "target": f"concept:{concept_id}",
                "type": "category_concept",
                "weight": 0.18,
            }
        )

    product_to_symbols: dict[str, list[str]] = {}
    product_labels: dict[str, str] = {}
    layer_to_symbols: dict[str, list[str]] = {}
    product_to_concepts: dict[str, set[str]] = {}
    layer_to_concepts: dict[str, set[str]] = {}

    for rule in supply_chain_rules:
        concept_id = rule.get("concept_id")
        if concept_id not in active_concepts:
            continue
        for upstream_concept in rule.get("upstream_concepts", []):
            if upstream_concept in active_concepts:
                edges.append(
                    {
                        "source": f"concept:{upstream_concept}",
                        "target": f"concept:{concept_id}",
                        "type": "concept_supply_chain",
                        "direction": "upstream_to_concept",
                        "weight": 0.42,
                        "products": rule.get("products", []),
                        "layer": rule.get("layer"),
                    }
                )
        for downstream_concept in rule.get("downstream_concepts", []):
            if downstream_concept in active_concepts:
                edges.append(
                    {
                        "source": f"concept:{concept_id}",
                        "target": f"concept:{downstream_concept}",
                        "type": "concept_supply_chain",
                        "direction": "concept_to_downstream",
                        "weight": 0.42,
                        "products": rule.get("products", []),
                        "layer": rule.get("layer"),
                    }
                )
        layer = rule.get("layer")
        if layer:
            add_node(
                {
                    "id": f"layer:{layer}",
                    "type": "supply_layer",
                    "label": layer.split(".")[-1].replace("_", " "),
                    "layer": layer,
                    "path": layer,
                }
            )
            edges.append(
                {
                    "source": f"layer:{layer}",
                    "target": f"concept:{concept_id}",
                    "type": "layer_concept",
                    "weight": 0.32,
                }
            )
            layer_to_concepts.setdefault(layer, set()).add(concept_id)
        for product in rule.get("products", []):
            product_id = slugify(product)
            product_labels[product_id] = product
            add_node(
                {
                    "id": f"product:{product_id}",
                    "type": "product",
                    "label": product,
                    "product_id": product_id,
                    "source": "product_supply_chain_rules",
                }
            )
            edges.append(
                {
                    "source": f"product:{product_id}",
                    "target": f"concept:{concept_id}",
                    "type": "product_concept",
                    "weight": 0.36,
                }
            )
            product_to_concepts.setdefault(product_id, set()).add(concept_id)

    for symbol, node in watchlist.items():
        metric = stock_rows.get(symbol, {})
        labels = concept_labels(node)
        supply_chain = supply_chain_profile(node)
        add_node(
            {
                "id": f"stock:{symbol}",
                "type": "stock",
                "symbol": symbol,
                "name": node["name"],
                "market": node.get("market"),
                "region": node.get("region"),
                "exchange": node.get("exchange") or profile_value(node, "exchange"),
                "raw_industry": node.get("raw_industry") or profile_value(node, "raw_industry"),
                "sector": profile_value(node, "sector", fallback_sector(node)),
                "primary_business": profile_value(node, "primary_business", fallback_business(node)),
                "profile_status": profile_value(
                    node,
                    "profile_quality",
                    "profiled" if node.get("profile") else ("discovered_exchange_rules" if node.get("supply_chain_profile") else "fallback_from_concepts"),
                ),
                "specializations": profile_value(node, "specializations", labels[:5]),
                "products": profile_value(node, "products", supply_chain.get("products", [])),
                "platforms": profile_value(node, "platforms", []),
                "constraints": profile_value(node, "constraints", []),
                "risk_flags": profile_value(node, "risk_flags", []),
                "bottleneck_profile": profile_value(node, "bottleneck_profile", {}),
                "supply_chain_profile": supply_chain,
                "discovery_score": node.get("discovery_score"),
                "discovery_sources": node.get("discovery_sources", []),
                "match_reasons": node.get("match_reasons", []),
                "source_refs": profile_value(node, "source_refs", []),
                "profile_quality": profile_value(node, "profile_quality", "curated" if node.get("profile") else ("discovered_exchange_rules" if node.get("supply_chain_profile") else "fallback")),
                "r5": metric.get("r5"),
                "r20": metric.get("r20"),
                "near_20d_high": metric.get("near_20d_high"),
                "price_status": "skipped" if metric.get("price_skipped") else ("error" if metric.get("error") else "ok"),
            }
        )
        for layer in supply_chain.get("layers", []):
            add_node(
                {
                    "id": f"layer:{layer}",
                    "type": "supply_layer",
                    "label": layer.split(".")[-1].replace("_", " "),
                    "layer": layer,
                    "path": layer,
                }
            )
            edges.append(
                {
                    "source": f"layer:{layer}",
                    "target": f"stock:{symbol}",
                    "type": "layer_stock",
                    "weight": 0.24,
                    "market": node.get("market"),
                }
            )
            layer_to_symbols.setdefault(layer, []).append(symbol)
        for product in supply_chain.get("products", []):
            product_id = slugify(product)
            product_labels[product_id] = product
            add_node(
                {
                    "id": f"product:{product_id}",
                    "type": "product",
                    "label": product,
                    "product_id": product_id,
                    "source": "company_supply_chain_profile",
                }
            )
            edges.append(
                {
                    "source": f"product:{product_id}",
                    "target": f"stock:{symbol}",
                    "type": "product_stock",
                    "weight": 0.28,
                    "market": node.get("market"),
                }
            )
            product_to_symbols.setdefault(product_id, []).append(symbol)
        for concept_id in node.get("concepts", []):
            if concept_id in active_concepts:
                exposure = profile_exposure_for(node, concept_id)
                discovered_exposure = discovery_exposure_for(node, concept_id)
                relation = exposure or discovered_exposure or {}
                edges.append(
                    {
                        "source": f"concept:{concept_id}",
                        "target": f"stock:{symbol}",
                        "type": "concept_stock",
                        "weight": float(relation.get("weight", 0.55)),
                        "market": node.get("market"),
                        "role": relation.get("role") or node.get("role"),
                        "relation_path": relation.get("path"),
                        "evidence": relation.get("evidence", []),
                    }
                )
        for upstream_concept in supply_chain.get("upstream_concepts", []):
            if upstream_concept in active_concepts:
                edges.append(
                    {
                        "source": f"concept:{upstream_concept}",
                        "target": f"stock:{symbol}",
                        "type": "upstream_concept_stock",
                        "weight": 0.25,
                        "market": node.get("market"),
                        "role": "upstream_supply_chain",
                    }
                )
        for downstream_concept in supply_chain.get("downstream_concepts", []):
            if downstream_concept in active_concepts:
                edges.append(
                    {
                        "source": f"stock:{symbol}",
                        "target": f"concept:{downstream_concept}",
                        "type": "stock_downstream_concept",
                        "weight": 0.25,
                        "market": node.get("market"),
                        "role": "downstream_supply_chain",
                    }
                )

    edges.extend(
        limited_peer_edges(
            {key: values for key, values in product_to_symbols.items() if len(set(values)) >= 2},
            watchlist,
            edge_type="same_product_peer",
            group_field="product_id",
            max_edges_per_group=90,
        )
    )
    edges.extend(
        limited_peer_edges(
            {key: values for key, values in layer_to_symbols.items() if len(set(values)) >= 2},
            watchlist,
            edge_type="same_supply_layer_peer",
            group_field="layer",
            max_edges_per_group=90,
        )
    )

    by_concept: dict[str, list[str]] = {}
    for symbol, node in watchlist.items():
        for concept_id in node.get("concepts", []):
            by_concept.setdefault(concept_id, []).append(symbol)
    for concept_id, symbols in by_concept.items():
        if concept_id not in active_concepts:
            continue
        unique_symbols = sorted(set(symbols))
        for idx, source in enumerate(unique_symbols):
            for target in unique_symbols[idx + 1 :]:
                source_market = watchlist[source].get("market")
                target_market = watchlist[target].get("market")
                if source_market == target_market:
                    continue
                edges.append(
                    {
                        "source": f"stock:{source}",
                        "target": f"stock:{target}",
                        "type": "same_concept_cross_market",
                        "concept_id": concept_id,
                        "markets": [source_market, target_market],
                        "weight": 0.5,
                    }
                )
    price_edges = correlation_edges(active_concepts, watchlist, history_rows or {})
    edges.extend(price_edges)
    edge_counts: dict[str, int] = {}
    node_counts: dict[str, int] = {}
    for edge in edges:
        edge_counts[edge.get("type", "unknown")] = edge_counts.get(edge.get("type", "unknown"), 0) + 1
    for node in nodes:
        node_counts[node.get("type", "unknown")] = node_counts.get(node.get("type", "unknown"), 0) + 1
    return {
        "nodes": nodes,
        "edges": edges,
        "correlation_edge_count": len(price_edges),
        "node_type_counts": node_counts,
        "edge_type_counts": edge_counts,
    }


def extract_discovered_terms(news_rows: list[dict[str, Any]], known_labels: set[str]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    pattern = re.compile(r"\b[A-Z][A-Z0-9+\-]{2,}\b|[\u4e00-\u9fff]{2,8}")
    stop = {"股票", "市場", "台股", "美股", "新聞", "公司", "投資", "今日", "今年", "億元", "表示"}
    for row in news_rows:
        title = row.get("title") or ""
        for term in pattern.findall(title):
            if term in stop or term in known_labels:
                continue
            if len(term) <= 1:
                continue
            counts[term] = counts.get(term, 0) + 1
    rows = [{"term": term, "count": count} for term, count in counts.items() if count >= 2]
    rows.sort(key=lambda row: row["count"], reverse=True)
    return rows[:40]


def write_report(path: Path, theme_rows: list[dict[str, Any]], graph: dict[str, Any], discovered_terms: list[dict[str, Any]]) -> None:
    lines = [
        "# ThemeMiner Report",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Top Active Themes",
        "",
        "| Rank | Theme | Category | Stage | Score | Markets | Stocks | r5 | r20 | News |",
        "|---:|---|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(theme_rows[:30], start=1):
        lines.append(
            f"| {idx} | {row['label']} `{row['concept_id']}` | {row['category_label']} | {row['stage']} | "
            f"{row['score']:.1f} | {','.join(row['markets'])} | {row['stock_count']} | "
            f"{row.get('r5_median') if row.get('r5_median') is not None else '-'} | "
            f"{row.get('r20_median') if row.get('r20_median') is not None else '-'} | {row['news_count']} |"
        )
    lines.extend(
        [
            "",
            "## Graph Stats",
            "",
            f"- Nodes: {len(graph['nodes'])}",
            f"- Edges: {len(graph['edges'])}",
            "",
            "## Discovered Terms",
            "",
        ]
    )
    if discovered_terms:
        lines.append(", ".join([f"{row['term']}({row['count']})" for row in discovered_terms[:30]]))
    else:
        lines.append("-")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_relation_index(graph: dict[str, Any], theme_rows: list[dict[str, Any]]) -> dict[str, Any]:
    node_by_id = {node["id"]: node for node in graph.get("nodes", []) if node.get("id")}
    theme_by_concept = {row["concept_id"]: row for row in theme_rows}
    index: dict[str, dict[str, Any]] = {}

    def concept_row(concept_id: str) -> dict[str, Any]:
        theme = theme_by_concept.get(concept_id, {})
        return index.setdefault(
            concept_id,
            {
                "concept_id": concept_id,
                "label": theme.get("label", concept_id),
                "category_label": theme.get("category_label"),
                "score": theme.get("score"),
                "stage": theme.get("stage"),
                "markets": theme.get("markets", []),
                "upstream_concepts": [],
                "downstream_concepts": [],
                "products": [],
                "supply_layers": [],
                "stocks": [],
                "same_product_peer_edges": 0,
                "same_supply_layer_peer_edges": 0,
                "price_correlation_edges": 0,
            },
        )

    for edge in graph.get("edges", []):
        edge_type = edge.get("type")
        source = edge.get("source", "")
        target = edge.get("target", "")
        if edge_type == "concept_supply_chain":
            if source.startswith("concept:") and target.startswith("concept:"):
                source_concept = source.replace("concept:", "")
                target_concept = target.replace("concept:", "")
                concept_row(source_concept)["downstream_concepts"].append(target_concept)
                concept_row(target_concept)["upstream_concepts"].append(source_concept)
        elif edge_type in {"product_concept", "product_concept_inferred"} and target.startswith("concept:"):
            concept_id = target.replace("concept:", "")
            product = node_by_id.get(source, {}).get("label") or source.replace("product:", "")
            concept_row(concept_id)["products"].append(product)
        elif edge_type in {"layer_concept", "layer_concept_inferred"} and target.startswith("concept:"):
            concept_id = target.replace("concept:", "")
            layer = node_by_id.get(source, {}).get("path") or source.replace("layer:", "")
            concept_row(concept_id)["supply_layers"].append(layer)
        elif edge_type == "concept_stock" and source.startswith("concept:"):
            concept_id = source.replace("concept:", "")
            stock = node_by_id.get(target, {})
            concept_row(concept_id)["stocks"].append(
                {
                    "symbol": stock.get("symbol") or target.replace("stock:", ""),
                    "name": stock.get("name"),
                    "market": stock.get("market"),
                    "profile_status": stock.get("profile_status"),
                    "r20": stock.get("r20"),
                    "weight": edge.get("weight"),
                    "role": edge.get("role"),
                }
            )
        elif edge_type == "price_correlation":
            concept_id = edge.get("concept_id")
            if concept_id:
                concept_row(concept_id)["price_correlation_edges"] += 1

    product_peer_edges = [edge for edge in graph.get("edges", []) if edge.get("type") == "same_product_peer"]
    layer_peer_edges = [edge for edge in graph.get("edges", []) if edge.get("type") == "same_supply_layer_peer"]
    products_by_concept = {concept_id: set(row.get("products", [])) for concept_id, row in index.items()}
    layers_by_concept = {concept_id: set(row.get("supply_layers", [])) for concept_id, row in index.items()}
    product_label_by_id = {
        node["id"].replace("product:", ""): node.get("label")
        for node in graph.get("nodes", [])
        if node.get("type") == "product"
    }
    for edge in product_peer_edges:
        label = product_label_by_id.get(edge.get("product_id"), edge.get("product_id"))
        for concept_id, products in products_by_concept.items():
            if label in products:
                index[concept_id]["same_product_peer_edges"] += 1
    for edge in layer_peer_edges:
        layer = edge.get("layer")
        for concept_id, layers in layers_by_concept.items():
            if layer in layers:
                index[concept_id]["same_supply_layer_peer_edges"] += 1

    for row in index.values():
        row["upstream_concepts"] = sorted(set(row["upstream_concepts"]))
        row["downstream_concepts"] = sorted(set(row["downstream_concepts"]))
        row["products"] = sorted(set(row["products"]))
        row["supply_layers"] = sorted(set(row["supply_layers"]))
        row["stocks"].sort(key=lambda item: (-(item.get("weight") or 0), item.get("market") or "", item.get("symbol") or ""))

    return {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "description": "Concept-centric relation index derived from cross_market_stock_graph.json. Use it for upstream/downstream traversal, product peer expansion, and laggard discovery candidate generation.",
        "concepts": sorted(index.values(), key=lambda row: (-(row.get("score") or 0), row["concept_id"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh fine-grained cross-market theme graph")
    parser.add_argument("--taxonomy", default="thememiner/data/fine_theme_taxonomy_seed.json")
    parser.add_argument("--watchlist", default="thememiner/data/cross_market_watchlist_seed.json")
    parser.add_argument("--lagradar-seed", default="lagradar/data/cross_market_theme_seed.json")
    parser.add_argument("--company-profiles", default="thememiner/data/company_profiles_seed.json")
    parser.add_argument("--auto-profiles", default="thememiner/data/company_profiles_autofill.json")
    parser.add_argument("--discovered-universe", default="thememiner/data/discovered_universe.json")
    parser.add_argument("--supply-chain-rules", default="thememiner/data/product_supply_chain_rules.json")
    parser.add_argument("--max-discovered", type=int, default=0, help="0 means include every discovered mapped symbol")
    parser.add_argument("--output-dir", default="thememiner/output")
    parser.add_argument("--price-range", default="3mo")
    parser.add_argument("--price-symbol-limit", type=int, default=1000, help="0 means fetch prices for every graph symbol")
    parser.add_argument("--refresh-prices", action="store_true")
    parser.add_argument("--refresh-news", action="store_true")
    parser.add_argument("--max-concepts", type=int, default=0, help="0 means all concepts")
    parser.add_argument("--news-per-query", type=int, default=6)
    parser.add_argument(
        "--external-evidence",
        action="append",
        default=[],
        help="Extra JSONL evidence rows to merge into concept news evidence. Repeat for multiple files.",
    )
    args = parser.parse_args()
    if not args.external_evidence:
        args.external_evidence = ["serenity/data/graph_inputs/theme_evidence.jsonl"]

    output_dir = Path(args.output_dir)
    taxonomy = read_json(Path(args.taxonomy))
    concepts = flatten_taxonomy(taxonomy)
    supply_chain_rules = load_supply_chain_rules(Path(args.supply_chain_rules), set(concepts))
    auto_profiles = load_company_profiles(Path(args.auto_profiles), set(concepts))
    curated_profiles = load_company_profiles(Path(args.company_profiles), set(concepts))
    profiles = merge_profile_maps(auto_profiles, curated_profiles)
    watchlist = load_watchlist(
        Path(args.watchlist),
        Path(args.lagradar_seed),
        set(concepts),
        Path(args.company_profiles),
        profiles,
        Path(args.discovered_universe),
        max_discovered=args.max_discovered,
    )

    stock_rows: dict[str, dict[str, Any]] = {}
    history_rows: dict[str, list[dict[str, Any]]] = {}
    def price_priority(item: tuple[str, dict[str, Any]]) -> tuple[int, float, str]:
        symbol, node = item
        sources = set(node.get("sources", []))
        is_seed_or_profile = bool(sources & {"watchlist_seed", "lagradar_seed", "company_profile"})
        return (0 if is_seed_or_profile else 1, -float(node.get("discovery_score", 0) or 0), symbol)

    fetched_price_count = 0
    skipped_price_count = 0
    for symbol, node in sorted(watchlist.items(), key=price_priority):
        if args.price_symbol_limit and fetched_price_count >= args.price_symbol_limit:
            stock_rows[symbol] = {
                "symbol": symbol,
                "name": node["name"],
                "market": node.get("market"),
                "price_skipped": True,
                "error": "price fetch skipped by --price-symbol-limit",
            }
            skipped_price_count += 1
            continue
        try:
            rows = fetch_yahoo_history(symbol, output_dir / "cache" / "yahoo", price_range=args.price_range, refresh=args.refresh_prices)
            history_rows[symbol] = rows
            stock_rows[symbol] = {**stock_metrics(rows), "symbol": symbol, "name": node["name"], "market": node.get("market")}
            fetched_price_count += 1
        except Exception as exc:
            stock_rows[symbol] = {"symbol": symbol, "name": node["name"], "market": node.get("market"), "error": str(exc)}
            fetched_price_count += 1

    concept_items = list(concepts.values())
    if args.max_concepts:
        concept_items = concept_items[: args.max_concepts]
    news_rows: list[dict[str, Any]] = []
    for concept in concept_items:
        news_rows.extend(fetch_news(concept, output_dir / "cache" / "news", refresh=args.refresh_news, limit=args.news_per_query))
    external_news_rows = load_external_evidence(args.external_evidence, concepts)
    news_rows.extend(external_news_rows)

    theme_rows = compute_concept_scores(concepts, watchlist, stock_rows, news_rows)
    graph = build_graph(theme_rows, watchlist, stock_rows, history_rows, supply_chain_rules)
    relation_index = build_relation_index(graph, theme_rows)
    discovered_terms = extract_discovered_terms(news_rows, {concept["label"] for concept in concepts.values()})
    graph_profiles = merge_profile_maps(
        profiles,
        {
            symbol: node["profile"]
            for symbol, node in watchlist.items()
            if node.get("profile") and symbol not in profiles
        },
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "theme_library.json", {"built_at": datetime.now(timezone.utc).isoformat(), "themes": theme_rows})
    write_json(output_dir / "cross_market_stock_graph.json", {"built_at": datetime.now(timezone.utc).isoformat(), **graph})
    write_json(output_dir / "relation_index.json", relation_index)
    write_json(
        output_dir / "theme_correlations.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "method": "Pearson correlation of daily returns over the fetched price range, scanning -5..+5 common-session lags.",
            "edges": [edge for edge in graph["edges"] if edge.get("type") == "price_correlation"],
        },
    )
    write_json(output_dir / "company_profiles.json", {"built_at": datetime.now(timezone.utc).isoformat(), "profiles": list(graph_profiles.values())})
    write_json(output_dir / "theme_candidates.json", theme_rows[:80])
    write_json(output_dir / "discovered_terms.json", discovered_terms)
    write_jsonl(output_dir / "news_evidence.jsonl", news_rows)
    write_report(output_dir / "theme_report.md", theme_rows, graph, discovered_terms)
    write_json(
        output_dir / "update_manifest.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "concept_count": len(concepts),
            "queried_concepts": len(concept_items),
            "watchlist_symbol_count": len(watchlist),
            "discovered_universe_path": args.discovered_universe,
            "max_discovered": args.max_discovered,
            "price_symbol_limit": args.price_symbol_limit,
            "price_fetched_count": fetched_price_count,
            "price_skipped_count": skipped_price_count,
            "company_profile_count": len(graph_profiles),
            "stock_error_count": sum(1 for row in stock_rows.values() if row.get("error") and not row.get("price_skipped")),
            "news_row_count": len(news_rows),
            "news_error_count": sum(1 for row in news_rows if row.get("error")),
            "external_evidence_paths": args.external_evidence,
            "external_evidence_count": len(external_news_rows),
            "graph_node_count": len(graph["nodes"]),
            "graph_edge_count": len(graph["edges"]),
            "correlation_edge_count": graph.get("correlation_edge_count", 0),
            "node_type_counts": graph.get("node_type_counts", {}),
            "edge_type_counts": graph.get("edge_type_counts", {}),
            "supply_chain_rule_count": len(supply_chain_rules),
            "structural_edge_count": sum(
                1
                for edge in graph["edges"]
                if edge.get("type")
                in {
                    "category_concept",
                    "concept_supply_chain",
                    "layer_concept",
                    "layer_concept_inferred",
                    "product_concept",
                    "product_concept_inferred",
                    "product_stock",
                    "layer_stock",
                }
            ),
            "supply_chain_edge_count": sum(
                1
                for edge in graph["edges"]
                if edge.get("type")
                in {
                    "concept_supply_chain",
                    "upstream_concept_stock",
                    "stock_downstream_concept",
                    "layer_concept",
                    "layer_concept_inferred",
                    "product_concept",
                    "product_concept_inferred",
                    "product_stock",
                    "layer_stock",
                    "same_product_peer",
                    "same_supply_layer_peer",
                }
            ),
        },
    )
    print(
        f"Wrote {len(theme_rows)} themes, {len(watchlist)} stocks, "
        f"{len(graph['nodes'])} graph nodes, {len(graph['edges'])} edges "
        f"({graph.get('correlation_edge_count', 0)} correlation) to {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
