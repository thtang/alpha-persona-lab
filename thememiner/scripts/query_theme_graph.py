#!/usr/bin/env python3
"""Query ThemeMiner output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: Any, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Query ThemeMiner theme library and graph")
    parser.add_argument("--output-dir", default="thememiner/output")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--concept", help="concept id or label substring")
    parser.add_argument("--market", action="append", help="market filter such as US, JP, TW, CN, HK, KR")
    parser.add_argument("--stage", action="append", help="stage filter, e.g. active_cross_market")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    library = read_json(output_dir / "theme_library.json")
    graph = read_json(output_dir / "cross_market_stock_graph.json")
    relation_index_path = output_dir / "relation_index.json"
    relation_index = read_json(relation_index_path) if relation_index_path.exists() else {"concepts": []}
    relation_by_concept = {row["concept_id"]: row for row in relation_index.get("concepts", [])}
    rows = library.get("themes", [])

    if args.concept:
        key = args.concept.lower()
        rows = [row for row in rows if key in row["concept_id"].lower() or key in row["label"].lower()]
    if args.market:
        markets = {item.upper() for item in args.market}
        rows = [row for row in rows if markets.intersection({market.upper() for market in row.get("markets", [])})]
    if args.stage:
        stages = set(args.stage)
        rows = [row for row in rows if row.get("stage") in stages]

    print("ThemeMiner active themes:")
    for idx, row in enumerate(rows[: args.top], start=1):
        print(
            f"{idx}. {row['label']} ({row['concept_id']}) | {row['category_label']} | {row['stage']} | "
            f"score={fmt(row['score'])} markets={','.join(row.get('markets', [])) or '-'} "
            f"stocks={row.get('stock_count', 0)} r5={fmt(row.get('r5_median'))}% "
            f"r20={fmt(row.get('r20_median'))}% news={row.get('news_count', 0)}"
        )
        headlines = row.get("top_headlines") or []
        if headlines:
            clean = [item for item in headlines if not item.get("error")]
            if clean:
                print(f"   news: {clean[0].get('title', '')[:140]}")

    print()
    print(f"Graph: nodes={len(graph.get('nodes', []))} edges={len(graph.get('edges', []))}")
    if rows:
        concept_id = rows[0]["concept_id"]
        relation = relation_by_concept.get(concept_id, {})
        if relation:
            print("Relation index:")
            print(f"   upstream: {', '.join(relation.get('upstream_concepts', [])[:10]) or '-'}")
            print(f"   downstream: {', '.join(relation.get('downstream_concepts', [])[:10]) or '-'}")
            print(f"   products: {', '.join(relation.get('products', [])[:12]) or '-'}")
            print(f"   layers: {', '.join(relation.get('supply_layers', [])[:8]) or '-'}")
            print(
                "   relation edges: "
                f"product_peer={relation.get('same_product_peer_edges', 0)} "
                f"layer_peer={relation.get('same_supply_layer_peer_edges', 0)} "
                f"corr={relation.get('price_correlation_edges', 0)}"
            )
        stock_by_id = {node["id"]: node for node in graph.get("nodes", []) if node.get("type") == "stock"}
        linked_edges = [
            edge
            for edge in graph.get("edges", [])
            if edge.get("source") == f"concept:{concept_id}" and edge.get("type") == "concept_stock"
        ]
        if linked_edges:
            print("Top concept linked stocks:")
            for edge in sorted(linked_edges, key=lambda item: item.get("weight", 0), reverse=True)[:30]:
                stock = stock_by_id.get(edge["target"], {})
                symbol = edge["target"].replace("stock:", "")
                business = stock.get("primary_business") or "-"
                specs = ", ".join((stock.get("specializations") or [])[:2]) or "-"
                bottleneck = stock.get("bottleneck_profile") or {}
                bottleneck_line = " | ".join(
                    item
                    for item in [
                        bottleneck.get("layer"),
                        f"scarcity={bottleneck.get('scarcity')}" if bottleneck.get("scarcity") else "",
                        f"sub={bottleneck.get('substitutability')}" if bottleneck.get("substitutability") else "",
                    ]
                    if item
                )
                supply_chain = stock.get("supply_chain_profile") or {}
                supply_line = " | ".join(
                    item
                    for item in [
                        ", ".join((stock.get("products") or supply_chain.get("products") or [])[:4]),
                        f"up={','.join((supply_chain.get('upstream_concepts') or [])[:4])}" if supply_chain.get("upstream_concepts") else "",
                        f"down={','.join((supply_chain.get('downstream_concepts') or [])[:4])}" if supply_chain.get("downstream_concepts") else "",
                    ]
                    if item
                )
                path = edge.get("relation_path") or "-"
                print(f"   {symbol} {stock.get('name', '')} | weight={fmt(edge.get('weight'), 2)} | {business}")
                print(f"      specs: {specs}")
                if supply_line:
                    print(f"      supply-chain: {supply_line}")
                if bottleneck_line:
                    print(f"      bottleneck: {bottleneck_line}")
                print(f"      path: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
