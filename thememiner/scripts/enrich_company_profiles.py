#!/usr/bin/env python3
"""Generate auto company profiles for ThemeMiner graph coverage.

Curated profiles remain the source of truth. This script fills the long tail
with lightweight profiles based on Yahoo Finance search metadata, exchange
listing metadata, official company URLs when available, and the local
fine-grained concept/supply-chain map, so the graph has no anonymous ticker
nodes.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from update_theme_graph import flatten_taxonomy, load_company_profiles, load_watchlist, read_json, safe_symbol, write_json


USER_AGENT = "alpha-persona-lab-thememiner-profile-enricher/0.1"


def url_json(url: str, *, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def is_cache_fresh(path: Path, max_age_hours: float) -> bool:
    if not path.exists():
        return False
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.now(timezone.utc) - modified <= timedelta(hours=max_age_hours)


def fetch_yahoo_search(symbol: str, cache_dir: Path, *, refresh: bool, delay: float = 0.0) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{safe_symbol(symbol)}.json"
    if cache_path.exists() and not refresh:
        return read_json(cache_path)
    url = "https://query2.finance.yahoo.com/v1/finance/search?" + urllib.parse.urlencode(
        {"q": symbol, "quotesCount": 3, "newsCount": 0}
    )
    try:
        data = url_json(url)
        quotes = data.get("quotes") or []
        exact = next((row for row in quotes if row.get("symbol") == symbol), quotes[0] if quotes else {})
        row = {"symbol": symbol, "fetched_at": datetime.now(timezone.utc).isoformat(), "quote": exact}
    except Exception as exc:
        row = {"symbol": symbol, "fetched_at": datetime.now(timezone.utc).isoformat(), "error": str(exc), "quote": {}}
    write_json(cache_path, row)
    if delay:
        time.sleep(delay)
    return row


def concept_labels(concepts: dict[str, dict[str, Any]], concept_ids: list[str]) -> list[str]:
    labels: list[str] = []
    for concept_id in concept_ids:
        row = concepts.get(concept_id)
        if row:
            labels.append(row["label"])
    return labels


def source_title(symbol: str) -> str:
    return f"Yahoo Finance search metadata for {symbol}"


def unique(values: list[Any]) -> list[Any]:
    return list(dict.fromkeys(value for value in values if value not in (None, "", [], {})))


def merge_supply_chain_profiles(*profiles: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {"layers": [], "products": [], "upstream_concepts": [], "downstream_concepts": [], "matched_rules": []}
    for profile in profiles:
        if not profile:
            continue
        for key in ("layers", "products", "upstream_concepts", "downstream_concepts"):
            merged[key] = unique(merged.get(key, []) + profile.get(key, []))
        merged["matched_rules"] = merged.get("matched_rules", []) + profile.get("matched_rules", [])
    return {key: value for key, value in merged.items() if value}


def quote_value(quote: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = quote.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def exchange_source_ref(node: dict[str, Any], seed_profile: dict[str, Any]) -> dict[str, Any] | None:
    url = node.get("source_url") or quote_value(seed_profile, "source_url")
    if not url:
        return None
    title = node.get("source") or node.get("exchange") or "exchange listing"
    return {"title": f"{title} metadata for {node['symbol']}", "url": url}


def company_website_ref(node: dict[str, Any], seed_profile: dict[str, Any]) -> dict[str, Any] | None:
    website = node.get("website") or seed_profile.get("website")
    if not website:
        return None
    return {"title": f"{node.get('name', node['symbol'])} official website", "url": website}


def source_refs_for(node: dict[str, Any], seed_profile: dict[str, Any]) -> list[dict[str, Any]]:
    refs = [
        {"title": source_title(node["symbol"]), "url": f"https://finance.yahoo.com/quote/{urllib.parse.quote(node['symbol'])}"},
        exchange_source_ref(node, seed_profile),
        company_website_ref(node, seed_profile),
    ]
    refs.extend(seed_profile.get("source_refs", []))
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        if not ref or not ref.get("url"):
            continue
        key = (ref.get("title") or "", ref["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def auto_profile(node: dict[str, Any], concepts: dict[str, dict[str, Any]], quote_row: dict[str, Any]) -> dict[str, Any]:
    quote = quote_row.get("quote") or {}
    seed_profile = node.get("profile") or {}
    labels = concept_labels(concepts, node.get("concepts", []))
    longname = quote_value(quote, "longname", "shortname") or seed_profile.get("name") or node.get("company_name") or node.get("name") or node["symbol"]
    sector = quote_value(quote, "sectorDisp", "sector")
    industry = quote_value(quote, "industryDisp", "industry")
    seed_sector = seed_profile.get("sector")
    sector_text = " / ".join([value for value in [sector, industry] if value]) or seed_sector or " / ".join(labels[:2]) or "Unclassified"
    themes_text = " / ".join(labels[:6]) if labels else "cross-market watchlist"
    supply_chain = merge_supply_chain_profiles(node.get("supply_chain_profile") or {}, seed_profile.get("supply_chain_profile") or {})
    products = unique((seed_profile.get("products") or []) + supply_chain.get("products", []))
    layers = supply_chain.get("layers", [])
    product_text = f" Key product/supply-chain clues: {', '.join(products[:10])}." if products else ""
    layer_text = f" Supply-chain layer: {', '.join(layers[:4])}." if layers else ""
    company_text = ""
    if node.get("company_name") and node.get("company_name") != longname:
        company_text = f" Listed company name: {node['company_name']}."
    summary_quality = "yahoo_search_metadata" if quote else "exchange_rule_metadata"
    return {
        "symbol": node["symbol"],
        "name": longname,
        "market": node.get("market"),
        "region": node.get("region"),
        "exchange": node.get("exchange") or quote.get("exchange") or seed_profile.get("exchange"),
        "raw_industry": node.get("raw_industry") or seed_profile.get("raw_industry"),
        "website": node.get("website") or seed_profile.get("website"),
        "company_name": node.get("company_name") or seed_profile.get("company_name"),
        "sector": sector_text,
        "primary_business": (
            f"{longname} operates in {sector_text}. ThemeMiner maps it to {themes_text} for cross-market theme diffusion work."
            f"{company_text}{product_text}{layer_text} "
            "This profile is synthesized from public ticker/search metadata, exchange listing fields, and local supply-chain rules; "
            "upgrade with filings/product pages before using it as a high-conviction single-name thesis."
        ),
        "specializations": unique(labels[:10] + products[:8]),
        "products": products,
        "platforms": labels[:5],
        "supply_chain_profile": supply_chain,
        "constraints": ["auto profile: verify product purity, customer exposure, and revenue mix before trading"],
        "risk_flags": ["auto profile: concept fit may be broad until upgraded with official sources"],
        "profile_quality": "auto_yahoo_search",
        "profile_evidence_quality": summary_quality,
        "concept_exposures": [
            {
                "concept_id": concept_id,
                "role": node.get("role") or "auto_mapped",
                "weight": 0.5,
                "path": (
                    f"{longname} metadata + exchange/supply-chain mapping -> "
                    f"{concepts.get(concept_id, {}).get('label', concept_id)} exposure candidate"
                ),
            }
            for concept_id in node.get("concepts", [])
            if concept_id in concepts
        ],
        "source_refs": source_refs_for(node, seed_profile),
        "quote_metadata": {
            key: quote.get(key)
            for key in ("exchange", "quoteType", "longname", "shortname", "sector", "sectorDisp", "industry", "industryDisp", "exchDisp")
            if quote.get(key) is not None
        },
        "autofill_inputs": {
            "has_yahoo_search_quote": bool(quote),
            "has_exchange_listing": bool(node.get("source_url") or node.get("exchange")),
            "has_official_website": bool(node.get("website") or seed_profile.get("website")),
            "has_supply_chain_rules": bool(supply_chain),
            "discovery_score": node.get("discovery_score"),
            "discovery_sources": node.get("discovery_sources", []),
            "match_reasons": node.get("match_reasons", []),
        },
    }


def build_profile_for_symbol(symbol: str, node: dict[str, Any], concepts: dict[str, dict[str, Any]], cache_dir: Path, refresh: bool, delay: float) -> dict[str, Any]:
    search = fetch_yahoo_search(symbol, cache_dir, refresh=refresh, delay=delay)
    return auto_profile(node, concepts, search)


def main() -> int:
    parser = argparse.ArgumentParser(description="Autofill ThemeMiner company profiles")
    parser.add_argument("--taxonomy", default="thememiner/data/fine_theme_taxonomy_seed.json")
    parser.add_argument("--watchlist", default="thememiner/data/cross_market_watchlist_seed.json")
    parser.add_argument("--lagradar-seed", default="lagradar/data/cross_market_theme_seed.json")
    parser.add_argument("--curated-profiles", default="thememiner/data/company_profiles_seed.json")
    parser.add_argument("--discovered-universe", default="thememiner/data/discovered_universe.json")
    parser.add_argument("--max-discovered", type=int, default=0, help="0 means include every discovered mapped symbol")
    parser.add_argument("--output", default="thememiner/data/company_profiles_autofill.json")
    parser.add_argument("--cache-dir", default="thememiner/output/cache/profile_search")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--include-curated", action="store_true", help="also generate auto rows for symbols that already have curated profiles")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--delay", type=float, default=0.08, help="small delay after uncached Yahoo search requests in each worker")
    parser.add_argument("--limit", type=int, default=0, help="debug limit; 0 means every eligible symbol")
    parser.add_argument("--symbols", default="", help="comma-separated symbol allowlist for targeted refresh")
    args = parser.parse_args()

    concepts = flatten_taxonomy(read_json(Path(args.taxonomy)))
    curated = load_company_profiles(Path(args.curated_profiles), set(concepts))
    watchlist = load_watchlist(
        Path(args.watchlist),
        Path(args.lagradar_seed),
        set(concepts),
        Path(args.curated_profiles),
        curated,
        Path(args.discovered_universe),
        max_discovered=args.max_discovered,
    )

    profiles: list[dict[str, Any]] = []
    allowlist = {symbol.strip() for symbol in args.symbols.split(",") if symbol.strip()}
    eligible = [
        (symbol, node)
        for symbol, node in sorted(watchlist.items())
        if (not allowlist or symbol in allowlist) and (args.include_curated or symbol not in curated)
    ]
    if args.limit:
        eligible = eligible[: args.limit]

    cache_dir = Path(args.cache_dir)
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(build_profile_for_symbol, symbol, node, concepts, cache_dir, args.refresh, args.delay): symbol
            for symbol, node in eligible
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                profiles.append(future.result())
            except Exception as exc:
                errors.append({"symbol": symbol, "error": str(exc)})
                node = watchlist[symbol]
                profiles.append(auto_profile(node, concepts, {"symbol": symbol, "error": str(exc), "quote": {}}))

    profiles.sort(key=lambda row: row["symbol"])
    quality_counts: dict[str, int] = {}
    input_counts: dict[str, int] = {}
    for profile in profiles:
        quality = profile.get("profile_evidence_quality") or profile.get("profile_quality") or "unknown"
        quality_counts[quality] = quality_counts.get(quality, 0) + 1
        inputs = profile.get("autofill_inputs") or {}
        for key in ("has_yahoo_search_quote", "has_exchange_listing", "has_official_website", "has_supply_chain_rules"):
            if inputs.get(key):
                input_counts[key] = input_counts.get(key, 0) + 1

    payload = {
        "schema_version": "thememiner_company_profiles_autofill_v1",
        "updated_at": datetime.now(timezone.utc).date().isoformat(),
        "description": (
            "Auto-generated profile metadata for long-tail graph coverage. Curated profiles override these rows. "
            "Profiles synthesize Yahoo Finance search metadata, exchange listing metadata, official website URLs, "
            "and local supply-chain rules without copying third-party long-form business descriptions."
        ),
        "profile_count": len(profiles),
        "quality_counts": quality_counts,
        "input_counts": input_counts,
        "errors": errors[:100],
        "profiles": profiles,
    }
    write_json(Path(args.output), payload)
    print(f"Wrote {len(profiles)} auto profiles to {args.output}")
    print(f"Quality counts: {quality_counts}")
    print(f"Input counts: {input_counts}")
    if errors:
        print(f"Errors: {len(errors)} (first {min(len(errors), 100)} stored in output)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
