#!/usr/bin/env python3
"""Search the local Gooaye transcript corpus."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


def load_records(data_dir: Path) -> list[dict[str, Any]]:
    manifest_path = data_dir / "transcripts_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing {manifest_path}; run fetch_transcripts.py first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return manifest["records"]


def normalize_snippet(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def find_matches(
    text: str,
    pattern: str,
    *,
    regex: bool,
    ignore_case: bool,
    context: int,
) -> Iterable[dict[str, Any]]:
    flags = re.IGNORECASE if ignore_case else 0
    expr = re.compile(pattern if regex else re.escape(pattern), flags)
    for match in expr.finditer(text):
        start = max(0, match.start() - context)
        end = min(len(text), match.end() + context)
        yield {
            "offset": match.start(),
            "match": match.group(0),
            "snippet": normalize_snippet(text[start:end]),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Search local Gooaye transcript markdown files, newest episodes first by default.")
    parser.add_argument("query", nargs="+", help="substring or regex to search for")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--episode", type=int, action="append", help="limit search to one or more episode numbers")
    parser.add_argument("--oldest-first", action="store_true", help="search from EP001 upward instead of newest episodes first")
    parser.add_argument("--regex", action="store_true")
    parser.add_argument("--case-sensitive", action="store_true")
    parser.add_argument("--context", type=int, default=90)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--jsonl", action="store_true", help="emit machine-readable JSONL")
    args = parser.parse_args()

    records = sorted(
        load_records(args.data_dir),
        key=lambda record: int(record["number"]),
        reverse=not args.oldest_first,
    )
    episode_filter = set(args.episode or [])
    queries = args.query
    emitted = 0

    for record in records:
        if episode_filter and int(record["number"]) not in episode_filter:
            continue
        path = args.data_dir / record["local_path"]
        text = path.read_text(encoding="utf-8")
        for query in queries:
            for match in find_matches(
                text,
                query,
                regex=args.regex,
                ignore_case=not args.case_sensitive,
                context=args.context,
            ):
                output = {
                    "episode": record["number"],
                    "date": record.get("date"),
                    "title": record.get("display_title") or record.get("title"),
                    "query": query,
                    **match,
                }
                if args.jsonl:
                    print(json.dumps(output, ensure_ascii=False))
                else:
                    print(
                        f"EP{output['episode']} {output.get('date') or ''} "
                        f"{output['title']}\n  {output['snippet']}\n"
                    )
                emitted += 1
                if emitted >= args.limit:
                    return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
