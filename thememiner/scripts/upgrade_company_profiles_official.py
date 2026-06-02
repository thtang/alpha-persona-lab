#!/usr/bin/env python3
"""Upgrade ThemeMiner auto profiles with official-source metadata.

The output is a profile shard. Use merge_company_profile_shards.py to merge
multiple shards back into a single autofill profile file.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from update_theme_graph import read_json, safe_symbol, write_json


USER_AGENT = "alpha-persona-lab-thememiner-official-profile-upgrader/0.1 thtang@example.com"


def unique(values: list[Any]) -> list[Any]:
    return list(dict.fromkeys(value for value in values if value not in (None, "", [], {})))


def normalize_space(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def truncate(text: Any, limit: int) -> str:
    value = normalize_space(text)
    return value if len(value) <= limit else value[:limit]


def url_json(url: str, cache_path: Path, *, refresh: bool = False, delay: float = 0.0, timeout: int = 30) -> Any:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists() and not refresh:
        return read_json(cache_path)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    write_json(cache_path, data)
    if delay:
        time.sleep(delay)
    return data


def load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {row["symbol"]: row for row in read_json(path).get("profiles", []) if row.get("symbol")}


def load_stock_nodes(path: Path) -> dict[str, dict[str, Any]]:
    graph = read_json(path)
    return {
        node["symbol"]: node
        for node in graph.get("nodes", [])
        if node.get("type") == "stock" and node.get("symbol")
    }


def load_discovered_nodes(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {node["symbol"]: node for node in read_json(path).get("nodes", []) if node.get("symbol")}


def load_source_evidence(path: Path, min_score: float) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    evidence: dict[str, list[dict[str, Any]]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            symbol = row.get("symbol")
            if not symbol or row.get("error") or float(row.get("quality_score") or 0) < min_score:
                continue
            evidence.setdefault(symbol, []).append(row)
    for rows in evidence.values():
        rows.sort(key=lambda row: float(row.get("quality_score") or 0), reverse=True)
    return evidence


def source_refs(*rows: dict[str, Any], extra: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for row in rows:
        refs.extend(row.get("source_refs", []) or [])
        if row.get("source_url"):
            refs.append({"title": f"{row.get('source', 'exchange')} listing for {row['symbol']}", "url": row["source_url"]})
        if row.get("website"):
            refs.append({"title": f"{row.get('name', row.get('symbol', 'company'))} official website", "url": row["website"]})
    refs.extend(extra or [])
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for ref in refs:
        url = ref.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append({"title": ref.get("title") or url, "url": url})
    return deduped


def compact_source_evidence(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for row in rows[:limit]:
        compact.append(
            {
                "source_url": row.get("source_url"),
                "source_title": row.get("source_title"),
                "source_type": row.get("source_type"),
                "title": row.get("title"),
                "description": truncate(row.get("description"), 240),
                "text_preview": truncate(row.get("text_preview"), 500),
                "quality_score": row.get("quality_score"),
                "match_authority": row.get("match_authority"),
                "agent_status": row.get("agent_status"),
                "agent_summary": row.get("agent_summary"),
                "agent_evidence_gaps": row.get("agent_evidence_gaps", [])[:6],
                "matched_concepts": sorted((row.get("matched_concepts") or {}).keys()),
                "matched_terms": row.get("matched_terms", [])[:12],
                "retrieval_matched_concepts": sorted((row.get("retrieval_matched_concepts") or {}).keys())[:24],
                "cache_path": row.get("cache_path"),
                "fetched_at": row.get("fetched_at"),
            }
        )
    return compact


def evidence_business_summary(profile: dict[str, Any], evidence_rows: list[dict[str, Any]]) -> str:
    name = profile.get("name") or profile.get("symbol") or "The company"
    titles = unique(
        [
            truncate(row.get("title") or row.get("source_title"), 90)
            for row in evidence_rows[:4]
            if row.get("title") or row.get("source_title")
        ]
    )
    descriptions = unique(
        [
            truncate(row.get("description"), 120)
            for row in evidence_rows[:3]
            if row.get("description")
        ]
    )
    terms = unique(
        [
            truncate(term.get("term"), 40)
            for row in evidence_rows[:5]
            for term in (row.get("matched_terms") or [])[:6]
            if isinstance(term, dict) and term.get("term")
        ]
    )
    concepts = unique(
        [
            concept
            for row in evidence_rows[:5]
            for concept in (row.get("matched_concepts") or {}).keys()
        ]
    )
    agent_summaries = unique(
        [
            truncate(row.get("agent_summary"), 180)
            for row in evidence_rows[:3]
            if row.get("agent_summary")
        ]
    )
    evidence_bits = titles[:3] or descriptions[:3]
    term_text = f" Matched product/theme terms include {', '.join(terms[:10])}." if terms else ""
    concept_text = f" Agent-approved ThemeMiner concept matches: {', '.join(concepts[:10])}." if concepts else ""
    agent_text = f" Source-agent notes: {'; '.join(agent_summaries[:2])}." if agent_summaries else ""
    if evidence_bits:
        return (
            f"{name} has source-backed evidence from {', '.join(evidence_bits)}."
            f"{term_text}{concept_text}{agent_text} Verify revenue purity and customer exposure from the cited source_evidence/source_refs."
        )
    return f"{name} has Scrapling source evidence attached; verify business details from source_evidence/source_refs."


def needs_business_backfill(profile: dict[str, Any]) -> bool:
    business = normalize_space(profile.get("primary_business"))
    quality = str(profile.get("profile_quality") or profile.get("profile_evidence_quality") or "").lower()
    return len(business) < 140 or quality in {"fallback", "fallback_from_concepts", "market_metadata_profile", "auto_yahoo_search"}


def apply_source_evidence(profile: dict[str, Any], evidence_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not evidence_rows:
        return profile
    extra_refs = [
        {
            "title": f"Scrapling source evidence: {row.get('title') or row.get('source_title') or row.get('source_url')}",
            "url": row["source_url"],
        }
        for row in evidence_rows
        if row.get("source_url")
    ]
    profile["source_refs"] = source_refs(profile, extra=extra_refs)
    profile["source_evidence"] = compact_source_evidence(evidence_rows)
    source_summary = evidence_business_summary(profile, evidence_rows)
    profile["source_business_summary"] = source_summary
    if needs_business_backfill(profile):
        profile["primary_business"] = source_summary
    metadata = dict(profile.get("official_metadata") or {})
    metadata["scrapling_source_evidence"] = compact_source_evidence(evidence_rows, limit=3)
    profile["official_metadata"] = metadata
    current_quality = profile.get("profile_evidence_quality") or ""
    if "scrapling_source_evidence" not in current_quality:
        profile["profile_evidence_quality"] = f"{current_quality}+scrapling_source_evidence" if current_quality else "scrapling_source_evidence"
    return profile


def concept_labels(profile: dict[str, Any], stock: dict[str, Any]) -> list[str]:
    values = []
    values.extend(profile.get("specializations", []) or [])
    values.extend(stock.get("specializations", []) or [])
    return unique([value for value in values if isinstance(value, str)])[:12]


def products_for(profile: dict[str, Any], stock: dict[str, Any]) -> list[str]:
    supply = stock.get("supply_chain_profile") or profile.get("supply_chain_profile") or {}
    return unique((profile.get("products") or []) + (stock.get("products") or []) + (supply.get("products") or []))[:24]


def base_profile(symbol: str, stock: dict[str, Any], auto: dict[str, Any], discovered: dict[str, Any]) -> dict[str, Any]:
    supply = stock.get("supply_chain_profile") or auto.get("supply_chain_profile") or discovered.get("supply_chain_profile") or {}
    return {
        "symbol": symbol,
        "name": auto.get("name") or stock.get("name") or discovered.get("name") or symbol,
        "market": stock.get("market") or auto.get("market") or discovered.get("market"),
        "region": stock.get("region") or auto.get("region") or discovered.get("region"),
        "exchange": stock.get("exchange") or auto.get("exchange") or discovered.get("exchange"),
        "raw_industry": stock.get("raw_industry") or auto.get("raw_industry") or discovered.get("raw_industry"),
        "website": auto.get("website") or discovered.get("website"),
        "company_name": auto.get("company_name") or discovered.get("company_name"),
        "sector": auto.get("sector") or stock.get("sector"),
        "specializations": concept_labels(auto, stock),
        "products": products_for(auto, stock),
        "platforms": unique((auto.get("platforms") or []) + (stock.get("platforms") or []))[:12],
        "constraints": unique((auto.get("constraints") or []) + ["verify official filings/product pages for revenue mix"])[:8],
        "risk_flags": unique((auto.get("risk_flags") or []) + ["auto-upgraded profile: product purity can still be broad"])[:8],
        "bottleneck_profile": stock.get("bottleneck_profile") or auto.get("bottleneck_profile") or {},
        "supply_chain_profile": supply,
        "concept_exposures": auto.get("concept_exposures", []),
        "source_refs": source_refs(auto, stock, discovered),
    }


def sec_company_index(cache_dir: Path, refresh: bool, delay: float) -> dict[str, dict[str, Any]]:
    data = url_json(
        "https://www.sec.gov/files/company_tickers_exchange.json",
        cache_dir / "company_tickers_exchange.json",
        refresh=refresh,
        delay=delay,
    )
    fields = data.get("fields", [])
    index: dict[str, dict[str, Any]] = {}
    for row in data.get("data", []):
        item = dict(zip(fields, row))
        ticker = str(item.get("ticker", "")).upper()
        if ticker:
            index[ticker] = item
    return index


def latest_annual_filing(submissions: dict[str, Any]) -> dict[str, str] | None:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    dates = recent.get("filingDate", [])
    for form, accession, doc, date in zip(forms, accessions, docs, dates):
        if form in {"10-K", "20-F", "40-F"}:
            return {"form": form, "accession": accession, "document": doc, "filing_date": date}
    return None


def upgrade_us(symbol: str, profile: dict[str, Any], stock: dict[str, Any], sec_index: dict[str, dict[str, Any]], cache_dir: Path, refresh: bool, delay: float) -> dict[str, Any]:
    row = sec_index.get(symbol.upper())
    if not row:
        profile["profile_quality"] = "market_metadata_profile"
        profile["profile_evidence_quality"] = "yahoo_search_plus_graph"
        return profile

    cik = int(row["cik"])
    submissions = url_json(
        f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
        cache_dir / "submissions" / f"CIK{cik:010d}.json",
        refresh=refresh,
        delay=delay,
    )
    annual = latest_annual_filing(submissions)
    sic = submissions.get("sic")
    sic_description = submissions.get("sicDescription")
    sec_name = submissions.get("name") or row.get("name")
    products = profile.get("products", [])
    themes = profile.get("specializations", [])
    product_text = f" Product/supply-chain clues in ThemeMiner: {', '.join(products[:10])}." if products else ""
    theme_text = f" ThemeMiner links it to {', '.join(themes[:8])}." if themes else ""
    profile["name"] = sec_name or profile["name"]
    profile["sector"] = f"SEC SIC {sic} - {sic_description}" if sic and sic_description else profile.get("sector")
    profile["primary_business"] = (
        f"{profile['name']} is matched to official SEC company metadata"
        f"{f' classified as {sic_description}' if sic_description else ''}."
        f"{theme_text}{product_text} Use the cited SEC filings and company materials to verify segment and revenue purity."
    )
    profile["profile_quality"] = "official_sec_profile"
    profile["profile_evidence_quality"] = "sec_company_submissions"
    extra_refs = [
        {"title": f"SEC company submissions for {profile['name']}", "url": f"https://data.sec.gov/submissions/CIK{cik:010d}.json"},
        {"title": f"SEC EDGAR browse for {profile['name']}", "url": f"https://www.sec.gov/edgar/browse/?CIK={cik}&owner=exclude"},
    ]
    if annual:
        accession_nodash = annual["accession"].replace("-", "")
        extra_refs.append(
            {
                "title": f"Latest annual filing {annual['form']} {annual['filing_date']}",
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{annual['document']}",
            }
        )
    profile["source_refs"] = source_refs(profile, extra=extra_refs)
    profile["official_metadata"] = {
        "source": "SEC",
        "cik": cik,
        "sic": sic,
        "sic_description": sic_description,
        "entity_type": submissions.get("entityType"),
        "category": submissions.get("category"),
        "tickers": submissions.get("tickers", []),
        "exchanges": submissions.get("exchanges", []),
        "latest_annual_filing": annual,
    }
    return profile


def upgrade_tw(symbol: str, profile: dict[str, Any], discovered: dict[str, Any]) -> dict[str, Any]:
    company_name = discovered.get("company_name") or profile.get("company_name") or profile.get("name")
    products = profile.get("products", [])
    themes = profile.get("specializations", [])
    product_text = f" Product/supply-chain clues in ThemeMiner: {', '.join(products[:10])}." if products else ""
    theme_text = f" ThemeMiner links it to {', '.join(themes[:8])}." if themes else ""
    profile["name"] = profile.get("name") or discovered.get("name") or symbol
    profile["company_name"] = company_name
    profile["website"] = discovered.get("website") or profile.get("website")
    profile["primary_business"] = (
        f"{profile['name']} is matched to official Taiwan exchange listing metadata"
        f"{f' for {company_name}' if company_name else ''}."
        f"{theme_text}{product_text} Use the cited exchange listing and company website to verify product mix and customer exposure."
    )
    profile["profile_quality"] = "official_tw_exchange_profile"
    profile["profile_evidence_quality"] = "twse_tpex_listing_plus_graph"
    profile["source_refs"] = source_refs(profile, discovered)
    profile["official_metadata"] = {
        "source": discovered.get("source"),
        "source_url": discovered.get("source_url"),
        "raw_industry": discovered.get("raw_industry"),
        "company_name": company_name,
        "website": profile.get("website"),
        "discovery_score": discovered.get("discovery_score"),
        "discovery_sources": discovered.get("discovery_sources", []),
        "match_reasons": discovered.get("match_reasons", []),
    }
    return profile


def upgrade_market_metadata(profile: dict[str, Any]) -> dict[str, Any]:
    products = profile.get("products", [])
    themes = profile.get("specializations", [])
    product_text = f" Product/supply-chain clues in ThemeMiner: {', '.join(products[:10])}." if products else ""
    theme_text = f" ThemeMiner links it to {', '.join(themes[:8])}." if themes else ""
    profile["primary_business"] = (
        f"{profile['name']} is upgraded from ticker/search metadata and ThemeMiner supply-chain mapping."
        f"{theme_text}{product_text} Official filing/profile extraction is still pending for this market."
    )
    profile["profile_quality"] = "market_metadata_profile"
    profile["profile_evidence_quality"] = "yahoo_search_plus_graph"
    profile["source_refs"] = source_refs(profile)
    profile["official_metadata"] = {"source": "pending_official_market_parser"}
    return profile


def select_symbols(
    stocks: dict[str, dict[str, Any]],
    curated: dict[str, dict[str, Any]],
    markets: set[str],
    symbols: set[str],
    shard: str,
    limit: int,
    *,
    include_curated: bool = False,
) -> list[str]:
    selected = [
        symbol
        for symbol, stock in sorted(stocks.items())
        if (include_curated or symbol not in curated)
        and (not markets or stock.get("market") in markets)
        and (not symbols or symbol in symbols)
    ]
    if shard:
        index, total = [int(value) for value in shard.split("/", 1)]
        selected = [symbol for idx, symbol in enumerate(selected) if idx % total == index]
    if limit:
        selected = selected[:limit]
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Build official-source profile upgrade shard")
    parser.add_argument("--graph", default="thememiner/output/cross_market_stock_graph.json")
    parser.add_argument("--autofill", default="thememiner/data/company_profiles_autofill.json")
    parser.add_argument("--curated", default="thememiner/data/company_profiles_seed.json")
    parser.add_argument("--discovered", default="thememiner/data/discovered_universe.json")
    parser.add_argument("--source-evidence", default="thememiner/output/company_source_evidence.jsonl")
    parser.add_argument("--source-evidence-min-score", type=float, default=35)
    parser.add_argument("--output", required=True)
    parser.add_argument("--markets", default="", help="comma-separated market filter, e.g. US,TW")
    parser.add_argument("--symbols", default="", help="comma-separated symbol allowlist")
    parser.add_argument("--include-curated", action="store_true", help="also build upgrade rows for curated seed profiles")
    parser.add_argument("--shard", default="", help="shard as index/total after market filtering, e.g. 0/4")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--cache-dir", default="thememiner/output/cache/official_profiles")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--delay", type=float, default=0.12)
    args = parser.parse_args()

    stocks = load_stock_nodes(Path(args.graph))
    autofill = load_profiles(Path(args.autofill))
    curated = load_profiles(Path(args.curated))
    discovered = load_discovered_nodes(Path(args.discovered))
    source_evidence = load_source_evidence(Path(args.source_evidence), args.source_evidence_min_score)
    markets = {item.strip().upper() for item in args.markets.split(",") if item.strip()}
    symbols = {item.strip() for item in args.symbols.split(",") if item.strip()}
    selected = select_symbols(stocks, curated, markets, symbols, args.shard, args.limit, include_curated=args.include_curated)
    cache_dir = Path(args.cache_dir)

    sec_index: dict[str, dict[str, Any]] = {}
    if any(stocks[symbol].get("market") == "US" for symbol in selected):
        sec_index = sec_company_index(cache_dir / "sec", args.refresh, args.delay)

    profiles: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for count, symbol in enumerate(selected, start=1):
        stock = stocks[symbol]
        auto = autofill.get(symbol, {})
        found = discovered.get(symbol, {})
        profile = base_profile(symbol, stock, auto, found)
        try:
            market = profile.get("market")
            if market == "US":
                profile = upgrade_us(symbol, profile, stock, sec_index, cache_dir / "sec", args.refresh, args.delay)
            elif market == "TW":
                profile = upgrade_tw(symbol, profile, found)
            else:
                profile = upgrade_market_metadata(profile)
        except Exception as exc:
            errors.append({"symbol": symbol, "error": str(exc)})
            profile = upgrade_market_metadata(profile)
            profile["profile_evidence_quality"] = "upgrade_error_fallback"
            profile["official_metadata"] = {"error": str(exc)}
        profile = apply_source_evidence(profile, source_evidence.get(symbol, []))
        profile["updated_at"] = datetime.now(timezone.utc).date().isoformat()
        profile["upgrade_batch"] = {
            "markets": sorted(markets),
            "shard": args.shard,
            "output": args.output,
        }
        profiles.append(profile)
        if count % 100 == 0:
            print(f"processed {count}/{len(selected)}")

    payload = {
        "schema_version": "thememiner_company_profiles_official_shard_v1",
        "updated_at": datetime.now(timezone.utc).date().isoformat(),
        "markets": sorted(markets),
        "shard": args.shard,
        "profile_count": len(profiles),
        "errors": errors[:100],
        "profiles": sorted(profiles, key=lambda row: row["symbol"]),
    }
    write_json(Path(args.output), payload)
    print(f"Wrote {len(profiles)} upgraded profiles to {args.output}; errors={len(errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
