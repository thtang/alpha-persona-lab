#!/usr/bin/env python3
"""Discover broad-market stocks and map them to ThemeMiner concepts.

This is the front door before the price/news graph refresh. It scans exchange
lists, applies product/supply-chain keyword rules, and writes a reusable
universe file. Curated watchlists and company profiles remain higher-trust
overrides, but they should not define the boundary of the graph.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_judge import AgentConfig, AgenticJudge, normalize_concept_match


USER_AGENT = "alpha-persona-lab-thememiner-universe-discovery/0.1"

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&download=true"
TWSE_COMPANY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_COMPANY_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
KR_MARKET_UNIVERSE_SEED = Path("thememiner/data/kr_market_universe_seed.json")

US_EXCLUDE_NAME_TERMS = (
    " acquisition corp",
    " acquisition corporation",
    " spac ",
    " right",
    " rights",
    " unit",
    " units",
    " warrant",
    " warrants",
    " preferred",
    " notes due",
    " bond ",
    " etf",
    " etn",
    " fund",
    " closed end",
    " closed-end",
    " trust units",
)

TW_INDUSTRY_CONCEPTS = {
    "01": ["cement"],
    "02": ["food"],
    "03": ["plastics"],
    "04": ["textile_fiber"],
    "05": ["electric_machinery", "transformer_ups"],
    "06": ["wire_cable", "copper"],
    "08": ["glass_ceramics"],
    "09": ["paper"],
    "10": ["steel", "metal_parts"],
    "11": ["rubber"],
    "12": ["auto", "auto_parts"],
    "14": ["construction"],
    "15": ["shipping", "logistics"],
    "16": ["tourism", "travel_reopening"],
    "17": ["financial_holding", "banks", "insurance", "securities"],
    "18": ["department_store"],
    "20": [],
    "21": ["chemicals"],
    "22": ["cdmo_cro", "new_drug", "medical_devices", "healthcare_services"],
    "23": ["oil_lng", "green_environment"],
    "24": ["semiconductor_components", "ic_design", "foundry", "ic_packaging_testing", "semicap_equipment", "wafer_materials"],
    "25": ["notebook_pc", "motherboard", "industrial_pc", "pc_peripherals"],
    "26": ["led_opto", "lcd_tft", "lcd_components", "optical_lens"],
    "27": ["communication_equipment", "networking"],
    "28": ["passive_components", "connectors", "pcb_manufacturing", "electronics_distribution"],
    "29": ["ic_distribution", "electronics_distribution", "passive_component_distribution"],
    "30": ["system_integration", "cloud_ai", "cybersecurity"],
    "31": ["ems", "power_supply", "consumer_electronics"],
    "32": ["cultural_creative"],
    "33": ["food"],
    "34": ["ecommerce"],
    "35": ["green_environment", "solar", "water_resources"],
    "36": ["cloud_ai", "system_integration"],
    "37": ["sports_leisure", "sportswear"],
    "38": ["consumer_electronics", "department_store"],
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def url_text(url: str, *, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def url_json(url: str, *, timeout: int = 30) -> Any:
    return json.loads(url_text(url, timeout=timeout))


def nasdaq_json(url: str, *, timeout: int = 30) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 alpha-persona-lab-thememiner-universe-discovery/0.1",
            "Accept": "application/json",
            "Origin": "https://www.nasdaq.com",
            "Referer": "https://www.nasdaq.com/market-activity/stocks/screener",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def flatten_taxonomy(taxonomy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    concepts: dict[str, dict[str, Any]] = {}
    for category in taxonomy.get("categories", []):
        for concept in category.get("concepts", []):
            concepts[concept["concept_id"]] = {
                **concept,
                "category_id": category["category_id"],
                "category_label": category["label"],
            }
    return concepts


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def ascii_keyword_match(text: str, keyword: str) -> bool:
    escaped = re.escape(keyword.lower())
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text.lower()))


def keyword_match(text: str, keyword: str) -> bool:
    keyword = clean_text(keyword)
    if not keyword:
        return False
    if re.search(r"[A-Za-z0-9]", keyword):
        return ascii_keyword_match(text, keyword)
    return keyword in text


def load_rules(path: Path, known_concepts: set[str]) -> list[dict[str, Any]]:
    payload = read_json(path)
    rows: list[dict[str, Any]] = []
    for rule in payload.get("rules", []):
        concept_id = rule.get("concept_id")
        if concept_id not in known_concepts:
            continue
        normalized = dict(rule)
        normalized["upstream_concepts"] = [item for item in rule.get("upstream_concepts", []) if item in known_concepts]
        normalized["downstream_concepts"] = [item for item in rule.get("downstream_concepts", []) if item in known_concepts]
        rows.append(normalized)
    return rows


def parse_pipe_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    for row in reader:
        if not row or any(value == "File Creation Time" for value in row.values()):
            continue
        rows.append({clean_text(key): clean_text(value) for key, value in row.items() if key})
    return rows


def is_us_operating_common(symbol: str, name: str, *, etf: str, test_issue: str) -> bool:
    if not symbol or test_issue.upper() == "Y" or etf.upper() == "Y":
        return False
    lower = f" {name.lower()} "
    if any(term in lower for term in US_EXCLUDE_NAME_TERMS):
        return False
    if symbol.endswith(("R", "U", "W")) and any(term in lower for term in (" right", " unit", " warrant")):
        return False
    return True


def fetch_us_universe() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        data = nasdaq_json(NASDAQ_SCREENER_URL, timeout=45)
        for row in (data.get("data", {}) or {}).get("rows", []):
            symbol = clean_text(row.get("symbol")).replace(".", "-")
            name = clean_text(row.get("name"))
            if not is_us_operating_common(symbol, name, etf="", test_issue=""):
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "market": "US",
                    "region": "US",
                    "exchange": clean_text(row.get("exchange")) or "US",
                    "raw_industry": " / ".join([value for value in [clean_text(row.get("sector")), clean_text(row.get("industry"))] if value]),
                    "market_cap": clean_text(row.get("marketCap")),
                    "country": clean_text(row.get("country")),
                    "source": "nasdaq_screener_stocks",
                }
            )
    except Exception:
        pass
    for row in parse_pipe_rows(url_text(NASDAQ_LISTED_URL)):
        symbol = row.get("Symbol", "")
        name = row.get("Security Name", "")
        if not is_us_operating_common(symbol, name, etf=row.get("ETF", ""), test_issue=row.get("Test Issue", "")):
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "market": "US",
                "region": "US",
                "exchange": "NASDAQ",
                "raw_industry": row.get("Market Category"),
                "source": "nasdaqtrader_nasdaqlisted",
            }
        )
    for row in parse_pipe_rows(url_text(OTHER_LISTED_URL)):
        symbol = row.get("ACT Symbol", "")
        name = row.get("Security Name", "")
        if not is_us_operating_common(symbol, name, etf=row.get("ETF", ""), test_issue=row.get("Test Issue", "")):
            continue
        rows.append(
            {
                "symbol": symbol.replace(".", "-"),
                "name": name,
                "market": "US",
                "region": "US",
                "exchange": row.get("Exchange"),
                "raw_industry": None,
                "source": "nasdaqtrader_otherlisted",
            }
        )
    return dedupe_symbols(rows)


def fetch_twse_universe() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in url_json(TWSE_COMPANY_URL):
        code = clean_text(row.get("公司代號"))
        if not re.fullmatch(r"\d{4}", code):
            continue
        industry_code = clean_text(row.get("產業別"))
        rows.append(
            {
                "symbol": f"{code}.TW",
                "name": clean_text(row.get("公司簡稱") or row.get("公司名稱")),
                "market": "TW",
                "region": "Taiwan",
                "exchange": "TWSE",
                "raw_industry": industry_code,
                "company_name": clean_text(row.get("公司名稱")),
                "website": clean_text(row.get("網址")),
                "source": "twse_t187ap03_L",
            }
        )
    return rows


def fetch_tpex_universe() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in url_json(TPEX_COMPANY_URL):
        code = clean_text(row.get("SecuritiesCompanyCode"))
        if not re.fullmatch(r"\d{4}", code):
            continue
        industry_code = clean_text(row.get("SecuritiesIndustryCode"))
        rows.append(
            {
                "symbol": f"{code}.TWO",
                "name": clean_text(row.get("CompanyAbbreviation") or row.get("CompanyName")),
                "market": "TW",
                "region": "Taiwan OTC",
                "exchange": "TPEx",
                "raw_industry": industry_code,
                "company_name": clean_text(row.get("CompanyName")),
                "website": clean_text(row.get("WebAddress")),
                "source": "tpex_mopsfin_t187ap03_O",
            }
        )
    return rows


def fetch_kr_seed_universe(path: Path = KR_MARKET_UNIVERSE_SEED) -> list[dict[str, Any]]:
    """Load the curated Korea universe used when a stable broad KRX API is unavailable.

    The seed is deliberately explicit about Yahoo-compatible tickers and concept
    hints so Korea can participate in the same price, graph, and lead-lag
    pipelines as US/JP/TW/CN/HK names.
    """

    if not path.exists():
        return []
    payload = read_json(path)
    rows: list[dict[str, Any]] = []
    for row in payload.get("nodes", []):
        symbol = clean_text(row.get("symbol"))
        if not symbol:
            continue
        normalized = dict(row)
        normalized["symbol"] = symbol
        normalized["name"] = clean_text(row.get("name") or symbol)
        normalized["company_name"] = clean_text(row.get("company_name") or row.get("name") or symbol)
        normalized["market"] = clean_text(row.get("market") or "KR")
        normalized["region"] = clean_text(row.get("region") or "Korea")
        normalized["exchange"] = clean_text(row.get("exchange") or ("KOSDAQ" if symbol.endswith(".KQ") else "KOSPI"))
        normalized["raw_industry"] = clean_text(row.get("raw_industry") or row.get("sector") or "")
        normalized["source"] = "kr_market_universe_seed"
        normalized["source_url"] = str(path)
        rows.append(normalized)
    return dedupe_symbols(rows)


def dedupe_symbols(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = row.get("symbol")
        if symbol and symbol not in seen:
            seen[symbol] = row
    return list(seen.values())


def source_rows(markets: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    sources: list[str] = []
    if "US" in markets:
        rows.extend(fetch_us_universe())
        sources.extend([NASDAQ_SCREENER_URL, NASDAQ_LISTED_URL, OTHER_LISTED_URL])
    if "TW" in markets or "TWSE" in markets:
        rows.extend(fetch_twse_universe())
        sources.append(TWSE_COMPANY_URL)
    if "TWO" in markets or "TPEX" in markets:
        rows.extend(fetch_tpex_universe())
        sources.append(TPEX_COMPANY_URL)
    if "KR" in markets or "KOSPI" in markets or "KOSDAQ" in markets:
        rows.extend(fetch_kr_seed_universe())
        sources.append(str(KR_MARKET_UNIVERSE_SEED))
    return dedupe_symbols(rows), sources


def score_match(
    stock: dict[str, Any],
    rules: list[dict[str, Any]],
    known_concepts: set[str],
    concepts: dict[str, dict[str, Any]],
    agent: AgenticJudge | None = None,
) -> dict[str, Any] | None:
    text = " ".join(
        clean_text(value)
        for value in [
            stock.get("symbol"),
            stock.get("name"),
            stock.get("company_name"),
            stock.get("raw_industry"),
            stock.get("exchange"),
        ]
        if value
    )
    concept_hits: dict[str, dict[str, Any]] = {}

    for concept_id in stock.get("concept_hints", []) or []:
        if concept_id not in known_concepts:
            continue
        concept_hits.setdefault(concept_id, {"score": 0, "keywords": [], "sources": [], "rules": []})
        concept_hits[concept_id]["score"] += 28
        concept_hits[concept_id]["sources"].append("curated_market_universe_seed")

    for concept_id in TW_INDUSTRY_CONCEPTS.get(clean_text(stock.get("raw_industry")), []):
        if concept_id not in known_concepts:
            continue
        concept_hits.setdefault(concept_id, {"score": 0, "keywords": [], "sources": [], "rules": []})
        concept_hits[concept_id]["score"] += 5
        concept_hits[concept_id]["sources"].append(f"industry_code:{stock.get('raw_industry')}")

    for rule in rules:
        matched = [keyword for keyword in rule.get("keywords_any", []) if keyword_match(text, keyword)]
        if not matched:
            continue
        concept_id = rule["concept_id"]
        hit = concept_hits.setdefault(concept_id, {"score": 0, "keywords": [], "sources": [], "rules": []})
        hit["score"] += min(22, 8 + len(matched) * 3)
        hit["keywords"].extend(matched)
        hit["sources"].append("product_supply_chain_rules")
        hit["rules"].append(
            {
                "concept_id": concept_id,
                "layer": rule.get("layer"),
                "matched_keywords": matched,
                "products": rule.get("products", []),
                "upstream_concepts": rule.get("upstream_concepts", []),
                "downstream_concepts": rule.get("downstream_concepts", []),
            }
        )

    if not concept_hits:
        return None

    agent_decision: dict[str, Any] = {}
    if agent and agent.config.enabled:
        candidate_concepts = []
        for concept_id, hit in sorted(concept_hits.items(), key=lambda item: item[1]["score"], reverse=True)[:18]:
            concept = concepts.get(concept_id, {})
            rule_items = hit.get("rules", [])
            candidate_concepts.append(
                {
                    "concept_id": concept_id,
                    "label": concept.get("label") or concept_id,
                    "category_label": concept.get("category_label"),
                    "retrieval_score": hit.get("score"),
                    "retrieval_sources": sorted(set(hit.get("sources", []))),
                    "retrieval_keywords": sorted(set(hit.get("keywords", [])))[:12],
                    "products": sorted({product for rule in rule_items for product in rule.get("products", [])})[:12],
                    "upstream_concepts": sorted({item for rule in rule_items for item in rule.get("upstream_concepts", [])})[:12],
                    "downstream_concepts": sorted({item for rule in rule_items for item in rule.get("downstream_concepts", [])})[:12],
                }
            )
        evidence = {
            "task": "Judge which candidate concepts genuinely describe this listed company. Do not keyword-match.",
            "stock": {
                "symbol": stock.get("symbol"),
                "name": stock.get("name"),
                "company_name": stock.get("company_name"),
                "market": stock.get("market"),
                "exchange": stock.get("exchange"),
                "raw_industry": stock.get("raw_industry"),
                "website": stock.get("website"),
            },
            "candidate_concepts": candidate_concepts,
        }
        agent_decision = normalize_concept_match(agent.concept_match(evidence), known_concepts)
        if agent_decision.get("matched_concepts"):
            filtered_hits: dict[str, dict[str, Any]] = {}
            for item in agent_decision["matched_concepts"]:
                concept_id = item["concept_id"]
                hit = concept_hits.get(concept_id, {"score": 0, "keywords": [], "sources": [], "rules": []})
                hit = dict(hit)
                hit["score"] = max(hit.get("score", 0), round(item["confidence"] * 100, 2))
                hit["sources"] = list(dict.fromkeys(hit.get("sources", []) + ["agentic_concept_judge"]))
                hit["agent_confidence"] = item["confidence"]
                hit["agent_reason"] = item.get("reason")
                hit["agent_role"] = item.get("role")
                filtered_hits[concept_id] = hit
            concept_hits = filtered_hits
        else:
            return None

    layers: set[str] = set()
    products: set[str] = set()
    upstream: set[str] = set()
    downstream: set[str] = set()
    matched_rules: list[dict[str, Any]] = []
    concepts = sorted(concept_hits, key=lambda concept_id: concept_hits[concept_id]["score"], reverse=True)

    rule_lookup = {rule["concept_id"]: rule for rule in rules}
    for concept_id in concepts:
        rule = rule_lookup.get(concept_id, {})
        if rule.get("layer"):
            layers.add(rule["layer"])
        products.update(rule.get("products", []))
        upstream.update(rule.get("upstream_concepts", []))
        downstream.update(rule.get("downstream_concepts", []))
        matched_rules.extend(concept_hits[concept_id].get("rules", []))

    total_score = sum(row["score"] for row in concept_hits.values())
    reason_parts: list[str] = []
    for concept_id in concepts[:5]:
        hit = concept_hits[concept_id]
        keywords = ", ".join(sorted(set(hit.get("keywords", [])))[:5])
        source = ", ".join(sorted(set(hit.get("sources", [])))[:3])
        reason_parts.append(f"{concept_id} via {keywords or source}")

    return {
        "concepts": concepts,
        "discovery_score": min(100, total_score),
        "discovery_sources": sorted({source for hit in concept_hits.values() for source in hit.get("sources", [])}),
        "match_reasons": reason_parts,
        "concept_scores": {concept_id: min(100, round(hit["score"], 2)) for concept_id, hit in concept_hits.items()},
        "match_authority": (
            "agentic_concept_judge"
            if agent_decision.get("matched_concepts")
            else "curated_market_universe_seed"
            if any("curated_market_universe_seed" in hit.get("sources", []) for hit in concept_hits.values())
            else "rule_fallback"
        ),
        "agent_summary": agent_decision.get("summary"),
        "agent_rejected_concepts": agent_decision.get("rejected_concepts", []),
        "agent_evidence_gaps": agent_decision.get("evidence_gaps", []),
        "supply_chain_profile": {
            "layers": sorted(layers),
            "products": sorted(products),
            "upstream_concepts": sorted(upstream),
            "downstream_concepts": sorted(downstream),
            "matched_rules": matched_rules,
        },
    }


def discovered_profile(stock: dict[str, Any], match: dict[str, Any], concepts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    labels = [concepts[concept_id]["label"] for concept_id in match["concepts"] if concept_id in concepts]
    layer_text = ", ".join(match["supply_chain_profile"].get("layers", [])[:3])
    product_text = ", ".join(match["supply_chain_profile"].get("products", [])[:5])
    business = (
        f"{stock['name']} is exchange-discovered as a {' / '.join(labels[:5])} node"
        f"{f' with product clues: {product_text}' if product_text else ''}."
    )
    if layer_text:
        business += f" Supply-chain layer: {layer_text}."
    return {
        "symbol": stock["symbol"],
        "name": stock["name"],
        "market": stock.get("market"),
        "region": stock.get("region"),
        "exchange": stock.get("exchange"),
        "raw_industry": stock.get("raw_industry"),
        "sector": " / ".join(sorted({concepts[concept_id]["category_label"] for concept_id in match["concepts"] if concept_id in concepts})[:3]),
        "primary_business": business,
        "specializations": labels[:10],
        "products": match["supply_chain_profile"].get("products", []),
        "supply_chain_profile": match["supply_chain_profile"],
        "profile_quality": "discovered_exchange_rules",
        "source_refs": [
            {
                "title": f"{stock.get('source')} exchange listing for {stock['symbol']}",
                "url": stock.get("source_url"),
            }
        ],
    }


def run_discovery(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    taxonomy = read_json(Path(args.taxonomy))
    concepts = flatten_taxonomy(taxonomy)
    rules = load_rules(Path(args.rules), set(concepts))
    markets = {item.strip().upper() for item in args.markets.split(",") if item.strip()}
    raw_rows, sources = source_rows(markets)
    requested_agent = args.agent_mode in {"auto", "on"}
    agent_config = AgentConfig.from_env(
        enabled=requested_agent,
        cache_dir=args.agent_cache_dir,
        refresh=args.agent_refresh,
        model=args.agent_model,
        provider=args.agent_provider,
    )
    if args.agent_mode == "off":
        agent_config.enabled = False
    if args.agent_mode == "on" and not agent_config.enabled:
        raise RuntimeError("agent-mode=on requires an available agent provider: OpenAI-compatible API key or local codex CLI")
    agent = AgenticJudge(agent_config)
    agent_calls = 0

    source_url_by_name = {
        "nasdaq_screener_stocks": NASDAQ_SCREENER_URL,
        "nasdaqtrader_nasdaqlisted": NASDAQ_LISTED_URL,
        "nasdaqtrader_otherlisted": OTHER_LISTED_URL,
        "twse_t187ap03_L": TWSE_COMPANY_URL,
        "tpex_mopsfin_t187ap03_O": TPEX_COMPANY_URL,
        "kr_market_universe_seed": str(KR_MARKET_UNIVERSE_SEED),
    }
    discovered: list[dict[str, Any]] = []
    unclassified = 0
    agent_jobs: list[tuple[int, dict[str, Any], dict[str, Any]]] = []

    def concept_evidence(stock: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
        matched_rules = match.get("supply_chain_profile", {}).get("matched_rules", [])
        candidates = []
        for concept_id in match.get("concepts", [])[:18]:
            concept = concepts.get(concept_id, {})
            rule_items = [rule for rule in matched_rules if rule.get("concept_id") == concept_id]
            candidates.append(
                {
                    "concept_id": concept_id,
                    "label": concept.get("label") or concept_id,
                    "category_label": concept.get("category_label"),
                    "retrieval_score": match.get("concept_scores", {}).get(concept_id),
                    "retrieval_sources": match.get("discovery_sources", []),
                    "retrieval_keywords": sorted({keyword for rule in rule_items for keyword in rule.get("matched_keywords", [])})[:12],
                    "products": sorted({product for rule in rule_items for product in rule.get("products", [])})[:12],
                    "upstream_concepts": sorted({item for rule in rule_items for item in rule.get("upstream_concepts", [])})[:12],
                    "downstream_concepts": sorted({item for rule in rule_items for item in rule.get("downstream_concepts", [])})[:12],
                }
            )
        return {
            "task": "Judge which candidate concepts genuinely describe this listed company. Do not keyword-match.",
            "symbol": stock.get("symbol"),
            "stock": {
                "symbol": stock.get("symbol"),
                "name": stock.get("name"),
                "company_name": stock.get("company_name"),
                "market": stock.get("market"),
                "exchange": stock.get("exchange"),
                "raw_industry": stock.get("raw_industry"),
                "website": stock.get("website"),
            },
            "candidate_concepts": candidates,
        }

    def apply_agent_decision(match: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any] | None:
        matched = decision.get("matched_concepts") or []
        if not matched:
            return None
        keep = [item["concept_id"] for item in matched]
        confidence_by_concept = {item["concept_id"]: item["confidence"] for item in matched}
        reason_by_concept = {item["concept_id"]: item.get("reason") for item in matched}
        role_by_concept = {item["concept_id"]: item.get("role") for item in matched}
        next_match = dict(match)
        next_match["concepts"] = keep
        next_match["concept_scores"] = {
            concept_id: max(float(match.get("concept_scores", {}).get(concept_id) or 0), round(confidence_by_concept[concept_id] * 100, 2))
            for concept_id in keep
        }
        next_match["discovery_score"] = min(100, sum(next_match["concept_scores"].values()))
        next_match["discovery_sources"] = sorted(set(match.get("discovery_sources", []) + ["agentic_concept_judge"]))
        next_match["match_authority"] = "agentic_concept_judge"
        next_match["agent_summary"] = decision.get("summary")
        next_match["agent_rejected_concepts"] = decision.get("rejected_concepts", [])
        next_match["agent_evidence_gaps"] = decision.get("evidence_gaps", [])
        next_match["match_reasons"] = [
            f"{concept_id} via agent {confidence_by_concept[concept_id]:.2f}: {reason_by_concept.get(concept_id) or role_by_concept.get(concept_id) or 'semantic match'}"
            for concept_id in keep[:5]
        ]
        profile = dict(match.get("supply_chain_profile") or {})
        matched_rules = [rule for rule in profile.get("matched_rules", []) if rule.get("concept_id") in keep]
        profile["matched_rules"] = matched_rules
        next_match["supply_chain_profile"] = profile
        return next_match

    for stock in raw_rows:
        stock["source_url"] = source_url_by_name.get(stock.get("source"))
        match = score_match(stock, rules, set(concepts), concepts, None)
        if not match:
            if not args.include_unmapped:
                unclassified += 1
                continue
            match = {
                "concepts": [],
                "discovery_score": 0,
                "discovery_sources": [],
                "match_reasons": [],
                "concept_scores": {},
                "match_authority": "unmapped",
                "supply_chain_profile": {"layers": [], "products": [], "upstream_concepts": [], "downstream_concepts": [], "matched_rules": []},
            }
        row = {
            **stock,
            **match,
            "profile": discovered_profile(stock, match, concepts) if match["concepts"] else None,
        }
        if agent_config.enabled and row.get("concepts") and (args.agent_limit <= 0 or agent_calls < args.agent_limit):
            agent_jobs.append((len(discovered), stock, concept_evidence(stock, match)))
            agent_calls += 1
        discovered.append(row)

    def chunks(values: list[tuple[int, dict[str, Any], dict[str, Any]]], size: int) -> list[list[tuple[int, dict[str, Any], dict[str, Any]]]]:
        return [values[index : index + size] for index in range(0, len(values), size)]

    def run_concept_batch(batch: list[tuple[int, dict[str, Any], dict[str, Any]]]) -> list[tuple[int, dict[str, Any]]]:
        if len(batch) == 1 or args.agent_batch_size <= 1:
            idx, _stock, evidence = batch[0]
            return [(idx, normalize_concept_match(agent.concept_match(evidence), set(concepts)))]
        raw = agent.concept_match_batch([evidence for _, _stock, evidence in batch])
        by_symbol: dict[str, dict[str, Any]] = {}
        if isinstance(raw, dict) and isinstance(raw.get("results"), list):
            for item in raw["results"]:
                if isinstance(item, dict) and item.get("symbol"):
                    by_symbol[str(item["symbol"])] = normalize_concept_match(item, set(concepts))
        return [(idx, by_symbol.get(str(evidence.get("symbol") or ""), {})) for idx, _stock, evidence in batch]

    agent_batches_attempted = 0
    if agent_jobs:
        batches = chunks(agent_jobs, max(1, args.agent_batch_size))
        agent_batches_attempted = len(batches)
        batch_results: list[tuple[int, dict[str, Any]]] = []
        if args.agent_workers > 1:
            with ThreadPoolExecutor(max_workers=max(1, args.agent_workers)) as executor:
                future_map = {executor.submit(run_concept_batch, batch): batch for batch in batches}
                for future in as_completed(future_map):
                    batch_results.extend(future.result())
        else:
            for batch in batches:
                batch_results.extend(run_concept_batch(batch))
        for idx, decision in batch_results:
            updated = apply_agent_decision(discovered[idx], decision)
            if updated:
                discovered[idx].update(updated)
                discovered[idx]["profile"] = discovered_profile(discovered[idx], updated, concepts)
            elif not args.include_unmapped:
                discovered[idx]["_agent_rejected"] = True
        if not args.include_unmapped:
            rejected = [row for row in discovered if row.get("_agent_rejected")]
            unclassified += len(rejected)
            discovered = [row for row in discovered if not row.get("_agent_rejected")]
        for row in discovered:
            row.pop("_agent_rejected", None)

    discovered.sort(key=lambda row: (row.get("discovery_score", 0), len(row.get("concepts", [])), row.get("market") or "", row.get("symbol") or ""), reverse=True)
    if args.max_symbols:
        discovered = discovered[: args.max_symbols]

    concept_counts: Counter[str] = Counter()
    market_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for row in discovered:
        market_counts[row.get("market", "OTHER")] += 1
        source_counts[row.get("source", "unknown")] += 1
        for concept_id in row.get("concepts", []):
            concept_counts[concept_id] += 1

    payload = {
        "schema_version": "thememiner_discovered_universe_v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "markets": sorted(markets),
        "sources": sources,
        "raw_symbol_count": len(raw_rows),
        "unclassified_symbol_count": unclassified,
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
        "node_count": len(discovered),
        "concept_counts": dict(concept_counts.most_common()),
        "market_counts": dict(market_counts),
        "source_counts": dict(source_counts),
        "nodes": discovered,
    }

    report_lines = [
        "# ThemeMiner Universe Discovery",
        "",
        f"Generated at: {payload['updated_at']}",
        "",
        "## Summary",
        "",
        f"- Raw symbols scanned: {len(raw_rows)}",
        f"- Discovered/mapped symbols: {len(discovered)}",
        f"- Unclassified symbols: {unclassified}",
        f"- Agent status: {agent_config.status}; calls attempted: {agent_calls}",
        f"- Markets: {dict(market_counts)}",
        f"- Sources: {dict(source_counts)}",
        "",
        "## Top Concepts",
        "",
        "| Concept | Stocks |",
        "|---|---:|",
    ]
    for concept_id, count in concept_counts.most_common(40):
        report_lines.append(f"| {concepts.get(concept_id, {}).get('label', concept_id)} `{concept_id}` | {count} |")

    report_lines.extend(["", "## Top Matched Stocks", "", "| Symbol | Market | Name | Score | Concepts | Supply Chain |", "|---|---|---|---:|---|---|"])
    for row in discovered[:80]:
        labels = [concepts.get(concept_id, {}).get("label", concept_id) for concept_id in row.get("concepts", [])[:6]]
        layers = ", ".join(row.get("supply_chain_profile", {}).get("layers", [])[:3])
        report_lines.append(
            f"| {row.get('symbol')} | {row.get('market')} | {str(row.get('name', '')).replace('|', '/')} | "
            f"{row.get('discovery_score', 0):.0f} | {', '.join(labels)} | {layers or '-'} |"
        )
    return payload, "\n".join(report_lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan broad exchange universes and map stocks to ThemeMiner concepts")
    parser.add_argument("--taxonomy", default="thememiner/data/fine_theme_taxonomy_seed.json")
    parser.add_argument("--rules", default="thememiner/data/product_supply_chain_rules.json")
    parser.add_argument("--markets", default="US,TW,TWO,KR", help="Comma-separated markets: US,TW,TWO/TPEX,KR/KOSPI/KOSDAQ")
    parser.add_argument("--output", default="thememiner/data/discovered_universe.json")
    parser.add_argument("--report", default="thememiner/output/universe_scan_report.md")
    parser.add_argument("--max-symbols", type=int, default=0, help="0 means keep every mapped symbol")
    parser.add_argument("--include-unmapped", action="store_true")
    parser.add_argument(
        "--agent-mode",
        choices=["auto", "on", "off"],
        default="auto",
        help="Use a semantic agent to judge concept matches after candidate retrieval.",
    )
    parser.add_argument("--agent-provider", choices=["auto", "openai", "codex"], default="auto")
    parser.add_argument("--agent-model", default=None)
    parser.add_argument("--agent-cache-dir", default="thememiner/output/cache/agentic_judge")
    parser.add_argument("--agent-refresh", action="store_true")
    parser.add_argument("--agent-limit", type=int, default=0, help="debug limit for agent calls; 0 means no cap")
    parser.add_argument("--agent-workers", type=int, default=1, help="parallel semantic agents; use 2-6 for local codex exec")
    parser.add_argument("--agent-batch-size", type=int, default=16, help="stocks per semantic concept-mapping agent call")
    args = parser.parse_args()

    payload, report = run_discovery(args)
    write_json(Path(args.output), payload)
    write_text(Path(args.report), report)
    print(
        f"Wrote {payload['node_count']} mapped stocks from {payload['raw_symbol_count']} scanned symbols "
        f"to {args.output}; report {args.report}"
    )
    time.sleep(0.01)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
