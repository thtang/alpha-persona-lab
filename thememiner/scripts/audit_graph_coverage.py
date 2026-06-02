#!/usr/bin/env python3
"""Audit ThemeMiner graph coverage and profile quality."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stock_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [node for node in graph.get("nodes", []) if node.get("type") == "stock"]


def concept_edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [edge for edge in graph.get("edges", []) if edge.get("type") == "concept_stock"]


def correlation_edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [edge for edge in graph.get("edges", []) if edge.get("type") == "price_correlation"]


def edges_by_type(graph: dict[str, Any], edge_type: str) -> list[dict[str, Any]]:
    return [edge for edge in graph.get("edges", []) if edge.get("type") == edge_type]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ThemeMiner profile and correlation coverage")
    parser.add_argument("--graph", default="thememiner/output/cross_market_stock_graph.json")
    parser.add_argument("--library", default="thememiner/output/theme_library.json")
    parser.add_argument("--output", default="thememiner/output/coverage_report.md")
    args = parser.parse_args()

    graph = read_json(Path(args.graph))
    library = read_json(Path(args.library))
    themes = {row["concept_id"]: row for row in library.get("themes", [])}
    stocks = stock_nodes(graph)
    concept_links = concept_edges(graph)
    corr_links = correlation_edges(graph)
    node_type_counts = Counter(node.get("type", "unknown") for node in graph.get("nodes", []))
    edge_type_counts = Counter(edge.get("type", "unknown") for edge in graph.get("edges", []))

    linked_by_stock: dict[str, list[str]] = defaultdict(list)
    for edge in concept_links:
        linked_by_stock[edge["target"].replace("stock:", "")].append(edge["source"].replace("concept:", ""))

    corr_by_concept: Counter[str] = Counter(edge.get("concept_id") for edge in corr_links if edge.get("concept_id"))
    product_by_concept: Counter[str] = Counter()
    layer_by_concept: Counter[str] = Counter()
    upstream_by_concept: Counter[str] = Counter()
    downstream_by_concept: Counter[str] = Counter()
    for edge in graph.get("edges", []):
        edge_type = edge.get("type")
        source = edge.get("source", "")
        target = edge.get("target", "")
        if edge_type in {"product_concept", "product_concept_inferred"} and target.startswith("concept:"):
            product_by_concept[target.replace("concept:", "")] += 1
        elif edge_type in {"layer_concept", "layer_concept_inferred"} and target.startswith("concept:"):
            layer_by_concept[target.replace("concept:", "")] += 1
        elif edge_type == "concept_supply_chain" and source.startswith("concept:") and target.startswith("concept:"):
            downstream_by_concept[source.replace("concept:", "")] += 1
            upstream_by_concept[target.replace("concept:", "")] += 1
    status_counts = Counter(node.get("profile_status", "unknown") for node in stocks)
    quality_counts = Counter(node.get("profile_quality", node.get("profile_status", "unknown")) for node in stocks)
    market_counts = Counter(node.get("market", "OTHER") for node in stocks)
    business_profiled = [
        node
        for node in stocks
        if node.get("primary_business") and node.get("source_refs")
    ]

    fallback_rows = [
        node
        for node in stocks
        if not node.get("primary_business") or not node.get("source_refs")
    ]
    fallback_rows.sort(key=lambda node: (node.get("market") or "", node.get("symbol") or ""))

    concept_quality: list[dict[str, Any]] = []
    stocks_by_concept: dict[str, set[str]] = defaultdict(set)
    profiled_by_concept: dict[str, set[str]] = defaultdict(set)
    business_profiled_by_concept: dict[str, set[str]] = defaultdict(set)
    for edge in concept_links:
        concept_id = edge["source"].replace("concept:", "")
        symbol = edge["target"].replace("stock:", "")
        stocks_by_concept[concept_id].add(symbol)
    stock_map = {node["symbol"]: node for node in stocks if node.get("symbol")}
    for concept_id, symbols in stocks_by_concept.items():
        for symbol in symbols:
            stock = stock_map.get(symbol, {})
            if stock.get("profile_status") == "profiled":
                profiled_by_concept[concept_id].add(symbol)
            if stock.get("primary_business") and stock.get("source_refs"):
                business_profiled_by_concept[concept_id].add(symbol)
        total = len(symbols)
        profiled = len(profiled_by_concept[concept_id])
        usable_profiled = len(business_profiled_by_concept[concept_id])
        concept_quality.append(
            {
                "concept_id": concept_id,
                "label": themes.get(concept_id, {}).get("label", concept_id),
                "score": themes.get(concept_id, {}).get("score", 0),
                "stocks": total,
                "profiled": profiled,
                "profile_coverage": profiled / total if total else 0,
                "usable_profiled": usable_profiled,
                "usable_profile_coverage": usable_profiled / total if total else 0,
                "correlation_edges": corr_by_concept.get(concept_id, 0),
                "product_links": product_by_concept.get(concept_id, 0),
                "layer_links": layer_by_concept.get(concept_id, 0),
                "upstream_links": upstream_by_concept.get(concept_id, 0),
                "downstream_links": downstream_by_concept.get(concept_id, 0),
            }
        )
    concept_quality.sort(key=lambda row: (row["score"], row["stocks"]), reverse=True)

    lines = [
        "# ThemeMiner Coverage Audit",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        f"- Stocks: {len(stocks)}",
        f"- Concept-stock edges: {len(concept_links)}",
        f"- Price-correlation edges: {len(corr_links)}",
        f"- Product nodes: {node_type_counts.get('product', 0)}",
        f"- Supply-layer nodes: {node_type_counts.get('supply_layer', 0)}",
        f"- Concept supply-chain edges: {edge_type_counts.get('concept_supply_chain', 0)}",
        f"- Product-stock edges: {edge_type_counts.get('product_stock', 0)}",
        f"- Layer-stock edges: {edge_type_counts.get('layer_stock', 0)}",
        f"- Same-product peer edges: {edge_type_counts.get('same_product_peer', 0)}",
        f"- Same-layer peer edges: {edge_type_counts.get('same_supply_layer_peer', 0)}",
        f"- Profile status: {dict(status_counts)}",
        f"- Profile quality: {dict(quality_counts)}",
        f"- Usable business profiles with source refs: {len(business_profiled)} / {len(stocks)}",
        f"- Markets: {dict(market_counts)}",
        "",
        "## Node Types",
        "",
        ", ".join(f"{key}={value}" for key, value in node_type_counts.most_common()) or "-",
        "",
        "## Edge Types",
        "",
        ", ".join(f"{key}={value}" for key, value in edge_type_counts.most_common()) or "-",
        "",
        "## Top Theme Coverage",
        "",
        "| Theme | Score | Stocks | Curated/Profiled | Usable Business Profiles | Products | Layers | Up | Down | Corr Edges |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in concept_quality[:45]:
        lines.append(
            f"| {row['label']} `{row['concept_id']}` | {row['score']:.1f} | {row['stocks']} | "
            f"{row['profiled']} ({row['profile_coverage']:.0%}) | {row['usable_profiled']} ({row['usable_profile_coverage']:.0%}) | {row['product_links']} | "
            f"{row['layer_links']} | {row['upstream_links']} | {row['downstream_links']} | {row['correlation_edges']} |"
        )

    lines.extend(["", "## Missing Business/Profile Refs", ""])
    if not fallback_rows:
        lines.append("- All stocks have a business profile and at least one source ref.")
    else:
        lines.extend(["| Symbol | Market | Status | Concepts | Business |", "|---|---|---|---|---|"])
        for node in fallback_rows[:120]:
            symbol = node.get("symbol", "")
            concepts = ", ".join(linked_by_stock.get(symbol, [])[:8])
            business = (node.get("primary_business") or "").replace("|", "/")
            lines.append(
                f"| {symbol} | {node.get('market', '-')} | {node.get('profile_status', '-')} | "
                f"{concepts or '-'} | {business[:180]} |"
            )

    write_text(Path(args.output), "\n".join(lines) + "\n")
    print(f"Wrote {args.output}: {len(stocks)} stocks, {len(fallback_rows)} profiles to upgrade, {len(corr_links)} correlation edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
