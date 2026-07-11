#!/usr/bin/env python3
"""
Search local Bonnie Blockchain transcripts.

Usage:
  python3 crypto-mainstream-framework/scripts/search_corpus.py 比特幣 ETF --limit 10
  python3 crypto-mainstream-framework/scripts/search_corpus.py stablecoin --tag stablecoin
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "data" / "transcripts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("terms", nargs="+", help="Search terms. All terms must match.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--tag", help="Require a topic tag from transcript metadata.")
    parser.add_argument("--context", type=int, default=90)
    return parser.parse_args()


def metadata_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def main() -> None:
    args = parse_args()
    terms = [term.lower() for term in args.terms]
    shown = 0

    for path in sorted(TRANSCRIPTS.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower = text.lower()
        if args.tag and args.tag.lower() not in metadata_value(text, "topic_tags").lower():
            continue
        if not all(term in lower for term in terms):
            continue

        title = metadata_value(text, "title").strip('"')
        url = metadata_value(text, "url")
        first_pos = min((lower.find(term) for term in terms if lower.find(term) >= 0), default=0)
        start = max(0, first_pos - args.context)
        end = min(len(text), first_pos + args.context)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()

        print(f"{path.relative_to(ROOT)}")
        print(f"  {title}")
        print(f"  {url}")
        print(f"  ...{snippet}...")
        print()
        shown += 1
        if shown >= args.limit:
            break

    if shown == 0:
        print("No matches.")


if __name__ == "__main__":
    main()
