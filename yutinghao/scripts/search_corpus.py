#!/usr/bin/env python3
"""Search the local 財經皓角 corpus newest-first.

This intentionally stays simple: it is a fast retrieval helper for the skill,
not a semantic search engine. Use it to find candidate episodes, then verify
important claims against the source file.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip()
    return text


def plain(text: str) -> str:
    text = strip_frontmatter(text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", lambda m: m.group(0).split("](")[0][1:], text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*]\s*", "", text, flags=re.M)
    return re.sub(r"\s+", " ", text).strip()


def date_from_path(path: Path) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", path.name)
    return match.group(0) if match else path.stem


def snippet(text: str, terms: list[str], width: int = 220) -> str:
    hay = norm(text)
    positions = [hay.find(norm(term)) for term in terms if norm(term) in hay]
    if not positions:
        return text[:width]
    pos = min(p for p in positions if p >= 0)
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    return text[start:end].strip()


def score(text: str, terms: list[str]) -> int:
    hay = norm(text)
    total = 0
    for term in terms:
        needle = norm(term)
        if not needle:
            continue
        total += hay.count(needle) * max(1, len(needle))
    return total


def iter_markdown(kind: str, folder: str) -> list[dict[str, Any]]:
    rows = []
    base = ROOT / "data" / folder
    for path in sorted(base.glob("*.md")):
        text = plain(path.read_text(encoding="utf-8", errors="ignore"))
        rows.append(
            {
                "kind": kind,
                "date": date_from_path(path),
                "path": str(path.relative_to(ROOT)),
                "text": text,
            }
        )
    return rows


def iter_jokes() -> list[dict[str, Any]]:
    path = ROOT / "data" / "source" / "jokes_inventory.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        rows.append(
            {
                "kind": "joke",
                "date": item.get("date") or "",
                "path": "data/source/jokes_inventory.jsonl",
                "timestamp": item.get("timestamp"),
                "confidence": item.get("confidence"),
                "text": item.get("text_preview") or "",
            }
        )
    return rows


def load_rows(kinds: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if "transcript" in kinds:
        rows.extend(iter_markdown("transcript", "transcripts"))
    if "note" in kinds:
        rows.extend(iter_markdown("note", "notes"))
    if "official" in kinds:
        rows.extend(iter_markdown("official", "official_articles"))
    if "joke" in kinds:
        rows.extend(iter_jokes())
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("terms", nargs="+", help="Search terms. Quote phrases with spaces.")
    parser.add_argument(
        "--kind",
        action="append",
        choices=["transcript", "note", "official", "joke"],
        help="Restrict source kind. Repeatable.",
    )
    parser.add_argument("--date", help="Restrict to YYYY-MM-DD.")
    parser.add_argument("--since", help="Keep rows on/after YYYY-MM-DD.")
    parser.add_argument("--until", help="Keep rows on/before YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--oldest-first", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON lines.")
    args = parser.parse_args()

    kinds = set(args.kind or ["transcript", "note", "official", "joke"])
    rows = []
    for row in load_rows(kinds):
        date = str(row.get("date") or "")
        if args.date and date != args.date:
            continue
        if args.since and date < args.since:
            continue
        if args.until and date > args.until:
            continue
        row_score = score(str(row["text"]), args.terms)
        if row_score <= 0:
            continue
        row["score"] = row_score
        row["snippet"] = snippet(str(row["text"]), args.terms)
        row.pop("text", None)
        rows.append(row)

    rows.sort(key=lambda item: (str(item["date"]), int(item["score"])), reverse=not args.oldest_first)
    rows = rows[: args.limit]

    for row in rows:
        if args.json:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
            continue
        ts = f" @{row['timestamp']}" if row.get("timestamp") else ""
        conf = f" confidence={row['confidence']}" if row.get("confidence") else ""
        print(f"[{row['kind']}] {row['date']}{ts} score={row['score']}{conf} {row['path']}")
        print(row["snippet"])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
