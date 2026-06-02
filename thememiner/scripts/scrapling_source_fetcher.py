#!/usr/bin/env python3
"""Fetch and score company source pages for ThemeMiner profiles.

This is the bridge between the broad ThemeMiner graph and source-grounded
company profiles. It builds an upgrade queue, fetches selected official/source
pages with Scrapling, stores raw page evidence, and emits compact JSONL rows
that profile upgraders can consume later.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_judge import AgentConfig, AgenticJudge, normalize_concept_match


LOW_QUALITY = {
    "",
    "fallback",
    "fallback_from_concepts",
    "discovered_exchange_rules",
    "auto_yahoo_search",
    "exchange_rule_metadata",
    "market_metadata_profile",
    "yahoo_search_plus_graph",
}
MEDIUM_QUALITY = {"official_sec_profile", "official_tw_exchange_profile"}
SOURCE_TYPE_WEIGHT = {
    "official": 28,
    "filing": 26,
    "exchange": 22,
    "investor": 20,
    "news": 10,
    "market_data": 6,
    "other": 4,
}
SKIP_URL_PREFIXES = ("/", "file:", "mailto:", "tel:", "#")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
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
            if line.strip():
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_symbol(symbol: str) -> str:
    return (
        symbol.replace("^", "INDEX_")
        .replace("=", "_")
        .replace("/", "_")
        .replace(".", "_")
        .replace("-", "_")
    )


def stable_id(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def normalize_space(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit]


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("www."):
        return "https://" + url
    return url


def is_fetchable_url(url: str) -> bool:
    url = normalize_url(url)
    if not url or url.startswith(SKIP_URL_PREFIXES):
        return False
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"}


def classify_url(url: str, title: str = "") -> str:
    text = f"{url} {title}".lower()
    host = urllib.parse.urlparse(url).netloc.lower()
    if "sec.gov" in host or "annual" in text or "10-k" in text or "20-f" in text or "filing" in text:
        return "filing"
    if "twse.com" in host or "tpex.org" in host or "exchange" in text or "listing" in text:
        return "exchange"
    if "investor" in text or "/ir" in text or "ir." in host or "press-release" in text:
        return "investor"
    if "finance.yahoo" in host or "query" in host:
        return "market_data"
    if "news" in text or "google.com/rss" in text:
        return "news"
    if host:
        return "official"
    return "other"


def fallback_source_refs(symbol: str, market: str | None) -> list[dict[str, str]]:
    encoded = urllib.parse.quote(symbol)
    refs: list[dict[str, str]] = []
    if market == "US":
        refs.append(
            {
                "title": f"SEC EDGAR browse fallback for {symbol}",
                "url": f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={encoded}&owner=exclude&action=getcompany",
                "source_type": "filing",
            }
        )
        refs.append(
            {
                "title": f"Yahoo Finance profile fallback for {symbol}",
                "url": f"https://finance.yahoo.com/quote/{encoded}/profile",
                "source_type": "market_data",
            }
        )
    elif market in {"TW", "TWO"}:
        refs.append(
            {
                "title": f"Yahoo Taiwan profile fallback for {symbol}",
                "url": f"https://tw.stock.yahoo.com/quote/{encoded}/profile",
                "source_type": "market_data",
            }
        )
    elif market:
        refs.append(
            {
                "title": f"Yahoo Finance profile fallback for {symbol}",
                "url": f"https://finance.yahoo.com/quote/{encoded}/profile",
                "source_type": "market_data",
            }
        )
    return refs


def flatten_taxonomy(path: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(path, {"categories": []})
    concepts: dict[str, dict[str, Any]] = {}
    for category in payload.get("categories", []):
        for concept in category.get("concepts", []):
            concepts[concept["concept_id"]] = {
                **concept,
                "category_id": category.get("category_id"),
                "category_label": category.get("label"),
                "terms": list(dict.fromkeys([concept["concept_id"], concept.get("label", "")] + concept.get("aliases", []))),
            }
    return concepts


def load_supply_terms(path: Path) -> dict[str, list[str]]:
    payload = read_json(path, {"rules": []})
    terms: dict[str, list[str]] = defaultdict(list)
    for rule in payload.get("rules", []):
        concept_id = rule.get("concept_id")
        if not concept_id:
            continue
        terms[concept_id].extend(rule.get("products", []) or [])
        terms[concept_id].extend(rule.get("keywords_any", []) or [])
    return {key: list(dict.fromkeys(value for value in values if value)) for key, values in terms.items()}


def stock_nodes(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        node["symbol"]: node
        for node in graph.get("nodes", [])
        if node.get("type") == "stock" and node.get("symbol")
    }


def concepts_by_stock(graph: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for edge in graph.get("edges", []):
        if edge.get("type") != "concept_stock":
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source.startswith("concept:") and target.startswith("stock:"):
            result[target.replace("stock:", "")].add(source.replace("concept:", ""))
    return result


def load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(path, {"profiles": []})
    return {row["symbol"]: row for row in payload.get("profiles", []) if row.get("symbol")}


def load_theme_scores(path: Path) -> dict[str, float]:
    payload = read_json(path, {"themes": []})
    return {row["concept_id"]: float(row.get("score") or 0) for row in payload.get("themes", []) if row.get("concept_id")}


def load_laggard_scores(path: Path) -> dict[str, float]:
    payload = read_json(path, [])
    scores: dict[str, float] = {}
    for row in payload if isinstance(payload, list) else []:
        symbol = row.get("symbol")
        if not symbol:
            continue
        scores[symbol] = max(scores.get(symbol, 0), float(row.get("candidate_score") or 0))
    return scores


def profile_value(stock: dict[str, Any], profile: dict[str, Any], key: str, default: Any = None) -> Any:
    value = profile.get(key)
    if value not in (None, "", [], {}):
        return value
    return stock.get(key, default)


def source_refs_for(stock: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    website = profile_value(stock, profile, "website")
    if website:
        refs.append({"title": f"{profile_value(stock, profile, 'name', stock.get('symbol'))} official website", "url": website})
    for row in (profile.get("source_refs") or []) + (stock.get("source_refs") or []):
        if not isinstance(row, dict):
            continue
        refs.append({"title": row.get("title") or row.get("url") or "source", "url": row.get("url") or ""})
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for ref in refs:
        url = normalize_url(ref.get("url", ""))
        if not is_fetchable_url(url) or url in seen:
            continue
        seen.add(url)
        deduped.append({"title": ref.get("title") or url, "url": url, "source_type": classify_url(url, ref.get("title", ""))})
    if not deduped:
        for ref in fallback_source_refs(stock["symbol"], profile_value(stock, profile, "market", stock.get("market"))):
            if ref["url"] not in seen:
                seen.add(ref["url"])
                deduped.append(ref)
    deduped.sort(key=lambda row: SOURCE_TYPE_WEIGHT.get(row["source_type"], 0), reverse=True)
    return deduped


def queue_priority(
    stock: dict[str, Any],
    profile: dict[str, Any],
    stock_concepts: set[str],
    theme_scores: dict[str, float],
    laggard_scores: dict[str, float],
) -> tuple[float, list[str]]:
    symbol = stock["symbol"]
    reasons: list[str] = []
    score = 0.0
    quality = str(profile_value(stock, profile, "profile_quality", profile_value(stock, profile, "profile_status", "")) or "").lower()
    business = profile_value(stock, profile, "primary_business", "")
    refs = source_refs_for(stock, profile)
    if not business or len(str(business)) < 120:
        score += 95
        reasons.append("thin_or_missing_business")
    if not refs:
        score += 85
        reasons.append("no_fetchable_source_ref")
    if quality in LOW_QUALITY:
        score += 70
        reasons.append(f"low_quality:{quality or 'unknown'}")
    elif quality in MEDIUM_QUALITY:
        score += 22
        reasons.append(f"official_metadata_needs_product_text:{quality}")
    else:
        score += 8
    lag_score = laggard_scores.get(symbol, 0)
    if lag_score:
        score += min(55, lag_score / 3)
        reasons.append(f"active_lagradar_candidate:{lag_score:.1f}")
    max_theme_score = max((theme_scores.get(concept, 0) for concept in stock_concepts), default=0)
    if max_theme_score:
        score += min(35, max_theme_score / 4)
        reasons.append(f"hot_theme:{max_theme_score:.1f}")
    r20 = stock.get("r20")
    if isinstance(r20, (int, float)) and abs(r20) >= 20:
        score += min(18, abs(r20) / 6)
        reasons.append(f"large_r20_move:{r20:.1f}")
    return round(score, 2), reasons


def build_queue(
    stocks: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    concept_map: dict[str, set[str]],
    theme_scores: dict[str, float],
    laggard_scores: dict[str, float],
    *,
    markets: set[str],
    symbols: set[str],
    max_urls: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol, stock in stocks.items():
        if symbols and symbol not in symbols:
            continue
        if markets and stock.get("market") not in markets:
            continue
        profile = profiles.get(symbol, {})
        refs = source_refs_for(stock, profile)
        priority, reasons = queue_priority(stock, profile, concept_map.get(symbol, set()), theme_scores, laggard_scores)
        rows.append(
            {
                "symbol": symbol,
                "name": profile_value(stock, profile, "name", symbol),
                "market": profile_value(stock, profile, "market", stock.get("market")),
                "profile_quality": profile_value(stock, profile, "profile_quality", profile_value(stock, profile, "profile_status", "")),
                "priority": priority,
                "priority_reasons": reasons,
                "concepts": sorted(concept_map.get(symbol, set())),
                "source_urls": refs[:max_urls],
                "business_preview": truncate(normalize_space(profile_value(stock, profile, "primary_business", "")), 260),
            }
        )
    rows.sort(key=lambda row: (row["priority"], len(row["source_urls"])), reverse=True)
    return rows


def import_scrapling(fetcher: str):
    try:
        from scrapling.fetchers import DynamicFetcher, Fetcher, StealthyFetcher
    except ImportError as exc:
        raise RuntimeError("Scrapling is not installed. Run `.venv/bin/python -m pip install -r requirements-scraping.txt`.") from exc
    if fetcher == "dynamic":
        return DynamicFetcher
    if fetcher == "stealth":
        return StealthyFetcher
    return Fetcher


def fetch_with_scrapling(url: str, *, fetcher: str, timeout: int) -> Any:
    cls = import_scrapling(fetcher)
    if fetcher == "dynamic":
        return cls.fetch(url, headless=True, network_idle=False, timeout=timeout * 1000, load_dom=True)
    if fetcher == "stealth":
        return cls.fetch(url, headless=True, network_idle=False, timeout=timeout * 1000)
    return cls.get(url, timeout=timeout, stealthy_headers=True)


def response_html(response: Any) -> str:
    html = getattr(response, "html_content", None)
    if html is None:
        html = getattr(response, "body", None)
    if isinstance(html, bytes):
        return html.decode(getattr(response, "encoding", None) or "utf-8", errors="replace")
    return str(html or "")


def response_text(response: Any) -> str:
    try:
        return normalize_space(response.get_all_text(separator=" ", strip=True))
    except Exception:
        return normalize_space(getattr(response, "text", ""))


def extract_meta(response: Any) -> dict[str, str]:
    def first(*selectors: str) -> str:
        for selector in selectors:
            try:
                value = response.css(selector).get()
            except Exception:
                value = None
            if value:
                return normalize_space(value)
        return ""

    return {
        "title": first("title::text", "h1::text"),
        "description": first('meta[name="description"]::attr(content)', 'meta[property="og:description"]::attr(content)'),
        "h1": first("h1::text"),
    }


def term_patterns(concepts: dict[str, dict[str, Any]], supply_terms: dict[str, list[str]]) -> dict[str, list[str]]:
    patterns: dict[str, list[str]] = {}
    for concept_id, row in concepts.items():
        terms = list(row.get("terms", [])) + supply_terms.get(concept_id, [])
        patterns[concept_id] = [term for term in dict.fromkeys(normalize_space(term) for term in terms) if len(term) >= 2]
    return patterns


def extract_matches(text: str, patterns: dict[str, list[str]], allowed_concepts: set[str]) -> dict[str, Any]:
    lowered = text.lower()
    concept_hits: dict[str, list[str]] = {}
    term_counts: Counter[str] = Counter()
    search_concepts = allowed_concepts or set(patterns)
    for concept_id in search_concepts:
        hits: list[str] = []
        for term in patterns.get(concept_id, []):
            term_norm = term.lower()
            if not term_norm:
                continue
            count = lowered.count(term_norm)
            if count:
                hits.append(term)
                term_counts[term] += count
        if hits:
            concept_hits[concept_id] = hits[:12]
    top_terms = [{"term": term, "count": count} for term, count in term_counts.most_common(24)]
    return {"matched_concepts": concept_hits, "matched_terms": top_terms}


def concept_candidates(
    matches: dict[str, Any],
    concepts: dict[str, dict[str, Any]],
    *,
    limit: int = 48,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for concept_id, hits in (matches.get("matched_concepts") or {}).items():
        concept = concepts.get(concept_id, {})
        candidates.append(
            {
                "concept_id": concept_id,
                "label": concept.get("label"),
                "category_label": concept.get("category_label"),
                "retrieval_terms": list(hits or [])[:10],
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def source_agent_match(
    *,
    agent: AgenticJudge | None,
    row: dict[str, Any],
    source: dict[str, str],
    text: str,
    meta: dict[str, str],
    retrieval_matches: dict[str, Any],
    concepts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    candidates = concept_candidates(retrieval_matches, concepts)
    if not agent or not agent.config.enabled:
        return {
            "match_authority": "term_fallback",
            "agent_status": agent.config.status if agent else "not_requested",
            "matched_concepts": retrieval_matches.get("matched_concepts", {}),
            "matched_terms": retrieval_matches.get("matched_terms", []),
            "agent_matched_concepts": [],
            "agent_rejected_concepts": [],
            "agent_summary": "",
            "agent_evidence_gaps": [],
        }
    if not candidates:
        return {
            "match_authority": "agentic_source_judge_no_candidates",
            "agent_status": "agent_no_candidate_concepts",
            "matched_concepts": {},
            "agent_matched_concepts": [],
            "agent_rejected_concepts": [],
            "agent_summary": "No candidate concepts were retrieved from this source page.",
            "agent_evidence_gaps": ["No candidate concept terms were found in the fetched page text."],
        }

    payload = {
        "symbol": row.get("symbol"),
        "name": row.get("name"),
        "market": row.get("market"),
        "existing_graph_concepts": row.get("concepts", []),
        "source": {
            "title": source.get("title"),
            "url": source.get("url"),
            "source_type": source.get("source_type"),
        },
        "page_meta": meta,
        "text_preview": truncate(text, 5000),
        "candidate_concepts": candidates,
        "retrieval_terms": retrieval_matches.get("matched_terms", [])[:24],
    }
    decision = normalize_concept_match(agent.concept_match(payload), set(concepts))
    if decision.get("matched_concepts"):
        matched = {
            item["concept_id"]: [item.get("reason") or item.get("role") or "agent matched"]
            for item in decision["matched_concepts"]
        }
        return {
            "match_authority": "agentic_source_judge",
            "agent_status": "agent_applied",
            "matched_concepts": matched,
            "agent_matched_concepts": decision["matched_concepts"],
            "agent_rejected_concepts": decision.get("rejected_concepts", []),
            "agent_summary": decision.get("summary", ""),
            "agent_evidence_gaps": decision.get("evidence_gaps", []),
        }
    return {
        "match_authority": "agentic_source_judge_rejected",
        "agent_status": "agent_rejected",
        "matched_concepts": {},
        "agent_matched_concepts": [],
        "agent_rejected_concepts": decision.get("rejected_concepts", []),
        "agent_summary": decision.get("summary", "Agent rejected the retrieved concept hypotheses."),
        "agent_evidence_gaps": decision.get("evidence_gaps", []),
    }


def quality_score(source_type: str, text: str, meta: dict[str, str], matches: dict[str, Any]) -> float:
    score = SOURCE_TYPE_WEIGHT.get(source_type, 4)
    score += min(22, len(text) / 2500 * 10)
    if meta.get("title"):
        score += 8
    if meta.get("description"):
        score += 8
    authority = str(matches.get("match_authority") or "term_fallback")
    if authority == "agentic_source_judge":
        score += min(36, len(matches.get("matched_concepts", {})) * 8)
    elif authority.startswith("agentic_source_judge"):
        score -= 6
    else:
        # Term hits are useful recall signals, but they should not make a
        # source look high-confidence without semantic review.
        score += min(8, len(matches.get("matched_concepts", {})) * 1.5)
        score += min(4, len(matches.get("matched_terms", [])) / 4)
    return round(min(100, score), 2)


def fetch_source(
    row: dict[str, Any],
    source: dict[str, str],
    *,
    source_pages_dir: Path,
    fetcher: str,
    refresh: bool,
    timeout: int,
    max_html_chars: int,
    max_text_chars: int,
    patterns: dict[str, list[str]],
    concepts: dict[str, dict[str, Any]],
    agent: AgenticJudge | None = None,
) -> dict[str, Any]:
    symbol = row["symbol"]
    url = source["url"]
    page_id = stable_id(url)
    cache_path = source_pages_dir / safe_symbol(symbol) / f"{page_id}.json"
    if cache_path.exists() and not refresh:
        cached = read_json(cache_path, {})
        evidence = dict(cached.get("evidence", {}))
        evidence["cache_hit"] = True
        return evidence

    fetched_at = utc_now()
    source_type = source.get("source_type") or classify_url(url, source.get("title", ""))
    evidence: dict[str, Any] = {
        "symbol": symbol,
        "name": row.get("name"),
        "market": row.get("market"),
        "source_url": url,
        "source_title": source.get("title") or url,
        "source_type": source_type,
        "fetcher": fetcher,
        "fetched_at": fetched_at,
        "cache_path": str(cache_path),
        "cache_hit": False,
    }
    try:
        response = fetch_with_scrapling(url, fetcher=fetcher, timeout=timeout)
        html = response_html(response)
        text = response_text(response)
        meta = extract_meta(response)
        retrieval_matches = extract_matches(text, patterns, set(row.get("concepts", [])))
        matches = source_agent_match(
            agent=agent,
            row=row,
            source=source,
            text=text,
            meta=meta,
            retrieval_matches=retrieval_matches,
            concepts=concepts,
        )
        evidence.update(
            {
                "status": getattr(response, "status", None),
                "final_url": str(getattr(response, "url", url)),
                "title": meta.get("title"),
                "description": meta.get("description"),
                "h1": meta.get("h1"),
                "text_chars": len(text),
                "html_chars": len(html),
                "text_preview": truncate(text, 1200),
                "matched_concepts": matches.get("matched_concepts", {}),
                "matched_terms": retrieval_matches["matched_terms"],
                "retrieval_matched_concepts": retrieval_matches["matched_concepts"],
                "retrieval_matched_terms": retrieval_matches["matched_terms"],
                "match_authority": matches.get("match_authority"),
                "agent_status": matches.get("agent_status"),
                "agent_matched_concepts": matches.get("agent_matched_concepts", []),
                "agent_rejected_concepts": matches.get("agent_rejected_concepts", []),
                "agent_summary": matches.get("agent_summary", ""),
                "agent_evidence_gaps": matches.get("agent_evidence_gaps", []),
                "quality_score": quality_score(source_type, text, meta, matches),
                "error": "",
            }
        )
        write_json(
            cache_path,
            {
                "schema_version": "thememiner_source_page_v1",
                "evidence": evidence,
                "html": truncate(html, max_html_chars),
                "text": truncate(text, max_text_chars),
            },
        )
    except Exception as exc:
        evidence.update({"status": None, "quality_score": 0, "error": str(exc)})
        write_json(cache_path, {"schema_version": "thememiner_source_page_v1", "evidence": evidence, "html": "", "text": ""})
    return evidence


def write_report(
    path: Path,
    queue: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    *,
    no_fetch: bool,
    agent_info: dict[str, Any] | None = None,
) -> None:
    quality = Counter(row.get("profile_quality") or "unknown" for row in queue)
    markets = Counter(row.get("market") or "OTHER" for row in queue)
    authority = Counter(row.get("match_authority") or "unknown" for row in evidence_rows)
    agent_status = Counter(row.get("agent_status") or "unknown" for row in evidence_rows)
    errors = [row for row in evidence_rows if row.get("error")]
    lines = [
        "# ThemeMiner Scrapling Source Fetch Report",
        "",
        f"Generated at: {utc_now()}",
        f"- Queue rows: {len(queue)}",
        f"- Evidence rows fetched/read: {len(evidence_rows)}",
        f"- No-fetch mode: {no_fetch}",
        f"- Errors: {len(errors)}",
        f"- Markets: {dict(markets)}",
        f"- Profile quality: {dict(quality)}",
        f"- Match authority: {dict(authority)}",
        f"- Agent status: {dict(agent_status)}",
    ]
    if agent_info:
        lines.append(f"- Agent config: {agent_info}")
    lines.extend(
        [
            "",
            "Term matches are recall evidence only. `matched_concepts` is agent-approved when `match_authority=agentic_source_judge`; otherwise it is fallback evidence.",
            "",
            "## Top Queue",
            "",
            "| Symbol | Market | Priority | Quality | Reasons | URLs |",
            "|---|---|---:|---|---|---:|",
        ]
    )
    for row in queue[:40]:
        lines.append(
            f"| {row['symbol']} | {row.get('market', '-')} | {row['priority']:.1f} | "
            f"{row.get('profile_quality') or '-'} | {', '.join(row.get('priority_reasons', [])[:4]) or '-'} | {len(row.get('source_urls', []))} |"
        )
    if evidence_rows:
        lines.extend(["", "## Source Evidence", "", "| Symbol | Type | Score | Authority | Agent | Status | Title | Error |", "|---|---|---:|---|---|---:|---|---|"])
        for row in sorted(evidence_rows, key=lambda item: item.get("quality_score") or 0, reverse=True)[:60]:
            title = normalize_space(row.get("title") or row.get("source_title") or "")[:100].replace("|", "/")
            error = normalize_space(row.get("error") or "")[:100].replace("|", "/")
            lines.append(
                f"| {row.get('symbol')} | {row.get('source_type')} | {row.get('quality_score', 0):.1f} | "
                f"{row.get('match_authority') or '-'} | {row.get('agent_status') or '-'} | {row.get('status') or '-'} | "
                f"{title or '-'} | {error or '-'} |"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_shard(value: str) -> tuple[int, int] | None:
    value = (value or "").strip()
    if not value:
        return None
    if "/" not in value:
        raise argparse.ArgumentTypeError("shard must use index/total format, for example 0/6")
    index_text, total_text = value.split("/", 1)
    try:
        index = int(index_text)
        total = int(total_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("shard index and total must be integers") from exc
    if total <= 0:
        raise argparse.ArgumentTypeError("shard total must be greater than zero")
    if index < 0 or index >= total:
        raise argparse.ArgumentTypeError("shard index must be between 0 and total - 1")
    return index, total


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/fetch ThemeMiner source evidence with Scrapling")
    parser.add_argument("--graph", default="thememiner/output/cross_market_stock_graph.json")
    parser.add_argument("--profiles", default="thememiner/output/company_profiles.json")
    parser.add_argument("--taxonomy", default="thememiner/data/fine_theme_taxonomy_seed.json")
    parser.add_argument("--supply-rules", default="thememiner/data/product_supply_chain_rules.json")
    parser.add_argument("--theme-library", default="thememiner/output/theme_library.json")
    parser.add_argument("--laggard-candidates", default="lagradar/output/laggard_candidates.json")
    parser.add_argument("--source-pages-dir", default="thememiner/output/source_pages")
    parser.add_argument("--queue-output", default="thememiner/output/profile_upgrade_queue.json")
    parser.add_argument("--evidence-output", default="thememiner/output/company_source_evidence.jsonl")
    parser.add_argument("--report-output", default="thememiner/output/source_fetch_report.md")
    parser.add_argument("--markets", default="", help="comma-separated market filter")
    parser.add_argument("--symbols", default="", help="comma-separated symbol allowlist")
    parser.add_argument("--limit", type=int, default=60, help="queue rows to fetch; 0 means all")
    parser.add_argument("--shard", default="", help="queue shard as index/total after sorting, for example 0/6")
    parser.add_argument("--max-urls-per-symbol", type=int, default=2)
    parser.add_argument("--fetcher", choices=["fetcher", "dynamic", "stealth"], default="fetcher")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-fetch", action="store_true", help="only build queue/report, do not fetch pages")
    parser.add_argument("--append-evidence", action="store_true")
    parser.add_argument("--stream-evidence", action="store_true", help="write each evidence row as soon as it is fetched")
    parser.add_argument("--max-html-chars", type=int, default=500_000)
    parser.add_argument("--max-text-chars", type=int, default=120_000)
    parser.add_argument("--agent-mode", choices=["auto", "on", "off"], default="auto")
    parser.add_argument("--agent-provider", choices=["auto", "openai", "codex"], default="auto")
    parser.add_argument("--agent-model", default="")
    parser.add_argument("--agent-cache-dir", default="thememiner/output/cache/agentic_judge")
    parser.add_argument("--agent-refresh", action="store_true")
    parser.add_argument("--agent-limit", type=int, default=0, help="maximum source pages to send to the agent; 0 means unlimited")
    args = parser.parse_args()

    graph = read_json(Path(args.graph), {"nodes": [], "edges": []})
    stocks = stock_nodes(graph)
    profiles = load_profiles(Path(args.profiles))
    concept_map = concepts_by_stock(graph)
    theme_scores = load_theme_scores(Path(args.theme_library))
    laggard_scores = load_laggard_scores(Path(args.laggard_candidates))
    concepts = flatten_taxonomy(Path(args.taxonomy))
    supply_terms = load_supply_terms(Path(args.supply_rules))
    patterns = term_patterns(concepts, supply_terms)
    agent_config = AgentConfig.from_env(
        enabled=args.agent_mode in {"auto", "on"},
        cache_dir=args.agent_cache_dir,
        refresh=args.agent_refresh,
        model=args.agent_model or None,
        provider=args.agent_provider,
    )
    if args.agent_mode == "off":
        agent_config.enabled = False
    if args.agent_mode == "on" and not agent_config.enabled:
        raise RuntimeError("agent-mode=on requires an available agent provider: OpenAI-compatible API key or local codex CLI")
    agent = AgenticJudge(agent_config)
    agent_calls = 0
    markets = {item.strip().upper() for item in args.markets.split(",") if item.strip()}
    symbols = {item.strip() for item in args.symbols.split(",") if item.strip()}

    full_queue = build_queue(
        stocks,
        profiles,
        concept_map,
        theme_scores,
        laggard_scores,
        markets=markets,
        symbols=symbols,
        max_urls=max(1, args.max_urls_per_symbol),
    )
    shard = parse_shard(args.shard)
    if shard:
        shard_index, shard_total = shard
        queue = [row for idx, row in enumerate(full_queue) if idx % shard_total == shard_index]
    else:
        queue = full_queue
    write_json(
        Path(args.queue_output),
        {
            "schema_version": "thememiner_profile_upgrade_queue_v1",
            "built_at": utc_now(),
            "graph": args.graph,
            "profiles": args.profiles,
            "markets": sorted(markets),
            "symbols": sorted(symbols),
            "shard": args.shard,
            "global_queue_count": len(full_queue),
            "queue_count": len(queue),
            "rows": queue,
        },
    )

    selected = queue if args.limit == 0 else queue[: args.limit]
    evidence_rows: list[dict[str, Any]] = []
    if not args.no_fetch:
        evidence_output = Path(args.evidence_output)
        if args.stream_evidence and not args.append_evidence:
            write_jsonl(evidence_output, [])
        for idx, row in enumerate(selected, start=1):
            for source in row.get("source_urls", [])[: max(1, args.max_urls_per_symbol)]:
                active_agent = (
                    agent
                    if agent_config.enabled and (args.agent_limit <= 0 or agent_calls < args.agent_limit)
                    else None
                )
                evidence = fetch_source(
                    row,
                    source,
                    source_pages_dir=Path(args.source_pages_dir),
                    fetcher=args.fetcher,
                    refresh=args.refresh,
                    timeout=args.timeout,
                    max_html_chars=args.max_html_chars,
                    max_text_chars=args.max_text_chars,
                    patterns=patterns,
                    concepts=concepts,
                    agent=active_agent,
                )
                if active_agent is not None:
                    agent_calls += 1
                evidence_rows.append(evidence)
                if args.stream_evidence:
                    append_jsonl(evidence_output, [evidence])
                if args.delay:
                    time.sleep(args.delay)
            if idx % 25 == 0:
                print(f"processed {idx}/{len(selected)} queue rows")
        if not args.stream_evidence:
            if args.append_evidence:
                append_jsonl(evidence_output, evidence_rows)
            else:
                write_jsonl(evidence_output, evidence_rows)
    else:
        if not args.append_evidence:
            write_jsonl(Path(args.evidence_output), [])
        else:
            evidence_rows = read_jsonl(Path(args.evidence_output))

    write_report(
        Path(args.report_output),
        queue,
        evidence_rows,
        no_fetch=args.no_fetch,
        agent_info={
            "status": agent_config.status,
            "provider": agent_config.provider,
            "model": agent_config.model,
            "cache_dir": str(agent_config.cache_dir),
            "calls_attempted": agent_calls,
            "limit": args.agent_limit,
        },
    )
    print(
        f"Wrote queue={args.queue_output} rows={len(queue)}; "
        f"evidence={len(evidence_rows)} to {args.evidence_output}; report={args.report_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
