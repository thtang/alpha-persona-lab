#!/usr/bin/env python3
"""Retrieve corpus-wide Gooaye life/QA context for a question."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def score_theme(query: str, theme: dict[str, Any]) -> int:
    score = 0
    lower_query = query.lower()
    for keyword in theme.get("keywords", []):
        if keyword.lower() in lower_query:
            score += 7
    for piece in theme.get("label", "").replace("、", " ").split():
        if piece and piece in query:
            score += 2
    return score


def evidence_score(record: dict[str, Any], selected: set[str], query: str) -> int:
    score = 0
    lower_query = query.lower()
    for key, theme in record.get("themes", {}).items():
        if key not in selected:
            continue
        score += int(theme.get("hit_count", 0))
        for keyword, count in theme.get("keyword_counts", {}).items():
            if keyword.lower() in lower_query:
                score += int(count) * 5
    return score


def compact_snippets(record: dict[str, Any], selected: set[str], *, limit: int = 3) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    for key in selected:
        theme = record.get("themes", {}).get(key)
        if not theme:
            continue
        for snippet in theme.get("snippets", []):
            snippets.append(
                {
                    "theme": key,
                    "keyword": snippet.get("keyword"),
                    "line": snippet.get("line"),
                    "file": snippet.get("file"),
                    "snippet": snippet.get("snippet"),
                }
            )
            if len(snippets) >= limit:
                return snippets
    return snippets


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieve Gooaye life/QA memory for a user question.")
    parser.add_argument("query", nargs="+")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--top-themes", type=int, default=5)
    parser.add_argument("--top-evidence", type=int, default=8)
    parser.add_argument("--recent-evidence", type=int, default=8)
    parser.add_argument("--recent-from", default="2024-01-01", help="minimum episode date for recent evidence")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    query = " ".join(args.query)
    distilled_dir = args.data_dir / "distilled"
    theme_memory = read_json(distilled_dir / "life_theme_memory.json")["themes"]
    episode_records = read_jsonl(distilled_dir / "episode_life_memory.jsonl")

    scored = []
    for key, theme in theme_memory.items():
        score = score_theme(query, theme)
        if score:
            scored.append((score, key, theme))
    if not scored:
        fallback = {"relationship", "communication_conflict", "autonomy_values", "decision_framework"}
        scored = [
            (theme.get("hit_count", 0), key, theme)
            for key, theme in theme_memory.items()
            if key in fallback
        ]
    scored = sorted(scored, key=lambda row: row[0], reverse=True)[: args.top_themes]
    selected = {key for _, key, _ in scored}

    evidence_pool = [
        (evidence_score(record, selected, query), record)
        for record in episode_records
        if evidence_score(record, selected, query) > 0
    ]
    evidence = [
        {
            "episode": record["episode"],
            "date": record.get("date"),
            "title": record.get("title"),
            "score": score,
            "snippets": compact_snippets(record, selected),
        }
        for score, record in sorted(evidence_pool, key=lambda row: row[0], reverse=True)[: args.top_evidence]
    ]
    recent_pool = [
        (score, record)
        for score, record in evidence_pool
        if (record.get("date") or "") >= args.recent_from
    ]
    recent = [
        {
            "episode": record["episode"],
            "date": record.get("date"),
            "title": record.get("title"),
            "score": score,
            "snippets": compact_snippets(record, selected, limit=2),
        }
        for score, record in sorted(
            recent_pool,
            key=lambda row: (row[0], row[1].get("date") or "", int(row[1].get("episode") or 0)),
            reverse=True,
        )[: args.recent_evidence]
    ]

    result = {
        "query": query,
        "themes": [
            {
                "key": key,
                "label": theme["label"],
                "episode_count": theme["episode_count"],
                "hit_count": theme["hit_count"],
                "year_counts": theme["year_counts"],
                "top_episodes": theme["top_episodes"][:5],
                "recent_episodes": theme["recent_episodes"][:5],
            }
            for _, key, theme in scored
        ],
        "evidence": evidence,
        "recent_evidence": recent,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Query: {query}")
    print("\nRelevant corpus life/QA themes:")
    for theme in result["themes"]:
        print(f"- {theme['label']}: {theme['episode_count']} eps, {theme['hit_count']} hits")
        print("  Recent:")
        for ep in theme["recent_episodes"]:
            print(f"  - EP{ep['episode']} {ep.get('date') or ''} {ep['title']} ({ep['hit_count']} hits)")
        print("  High density:")
        for ep in theme["top_episodes"]:
            print(f"  - EP{ep['episode']} {ep.get('date') or ''} {ep['title']} ({ep['hit_count']} hits)")

    print("\nEvidence episodes:")
    for ep in evidence:
        print(f"- EP{ep['episode']} {ep.get('date') or ''} {ep['title']} [score={ep['score']}]")
        for snippet in ep["snippets"]:
            print(f"  {snippet['file']}:{snippet['line']} {snippet['snippet']}")

    print("\nRecent evidence:")
    for ep in recent:
        print(f"- EP{ep['episode']} {ep.get('date') or ''} {ep['title']} [score={ep['score']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
