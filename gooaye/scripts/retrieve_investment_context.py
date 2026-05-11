#!/usr/bin/env python3
"""Retrieve corpus-wide Gooaye investment context for a question."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def score_theme(query: str, theme: dict[str, Any]) -> int:
    score = 0
    for keyword in theme.get("keywords", []):
        if keyword.lower() in query.lower():
            score += 5
    label = theme.get("label", "")
    for piece in label.replace("、", " ").split():
        if piece and piece in query:
            score += 2
    return score


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieve Gooaye investment memory for a user question.")
    parser.add_argument("query", nargs="+")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--top-themes", type=int, default=4)
    parser.add_argument("--top-episodes", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    query = " ".join(args.query)
    distilled_dir = args.data_dir / "distilled"
    theme_memory = read_json(distilled_dir / "theme_memory.json")["themes"]
    latest = read_json(distilled_dir / "latest_market_snapshot.json") if (distilled_dir / "latest_market_snapshot.json").exists() else {}

    scored = []
    for key, theme in theme_memory.items():
        score = score_theme(query, theme)
        if score:
            scored.append((score, key, theme))
    if not scored:
        scored = [
            (theme.get("hit_count", 0), key, theme)
            for key, theme in theme_memory.items()
            if key in {"valuation", "trend_timing", "position_risk", "macro_liquidity"}
        ]
    scored = sorted(scored, key=lambda row: row[0], reverse=True)[: args.top_themes]

    result = {
        "query": query,
        "themes": [
            {
                "key": key,
                "label": theme["label"],
                "episode_count": theme["episode_count"],
                "hit_count": theme["hit_count"],
                "top_episodes": theme["top_episodes"][: args.top_episodes],
            }
            for _, key, theme in scored
        ],
        "latest_market_snapshot": latest.get("prices", {}),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Query: {query}")
    print("\nRelevant corpus themes:")
    for theme in result["themes"]:
        print(f"- {theme['label']}: {theme['episode_count']} eps, {theme['hit_count']} hits")
        for ep in theme["top_episodes"][: min(5, args.top_episodes)]:
            print(f"  EP{ep['episode']} {ep.get('date') or ''} {ep['title']} [{ep['market_regime']}]")

    if result["latest_market_snapshot"]:
        print("\nLatest market snapshot:")
        for symbol, snap in result["latest_market_snapshot"].items():
            print(
                f"- {symbol} {snap['date']} close={snap['close']} "
                f"1d={snap['ret_1d_pct']}% 5d={snap['ret_5d_pct']}% "
                f"20d={snap['ret_20d_pct']}% 60d={snap['ret_60d_pct']}%"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
