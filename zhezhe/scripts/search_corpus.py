#!/usr/bin/env python3
"""Search the local Zhezhe corpus newest-first."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


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


def date_from_text(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else text[:10]


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def iter_metadata() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source = DATA / "source" / "zhezhe_episodes.jsonl"
    for item in read_jsonl(source):
        title = str(item.get("title") or "")
        description = str(item.get("description_text") or item.get("description") or item.get("summary") or "")
        eid = str(item.get("episode_id") or item.get("id") or item.get("guid") or "")
        date = (
            date_from_text(item.get("date"))
            or date_from_text(item.get("local_date"))
            or date_from_text(item.get("published_date"))
            or date_from_text(item.get("published_at"))
            or date_from_text(item.get("pub_date"))
            or date_from_text(item.get("pubDate"))
            or date_from_text(item.get("pub_date_utc"))
        )
        link = str(item.get("player_url") or item.get("link") or item.get("url") or "")
        keywords = " ".join(str(value) for value in item.get("keywords") or [])
        text = " ".join(part for part in (title, description, keywords, eid, link) if part)
        rows.append(
            {
                "kind": "metadata",
                "date": date,
                "id": eid,
                "title": title,
                "path": rel(source),
                "text": plain(text),
            }
        )
    return rows


def zhezhe_article_paths() -> set[str]:
    paths: set[str] = set()
    for item in read_jsonl(DATA / "source" / "zhezhe_articles.jsonl"):
        path = item.get("local_path")
        if path:
            paths.add(str(path))
    return paths


def iter_markdown(kind: str, folder: str, allowed_paths: set[str] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base = DATA / folder
    for path in sorted(base.glob("*.md")):
        relative = rel(path)
        if allowed_paths is not None and relative not in allowed_paths:
            continue
        text = plain(path.read_text(encoding="utf-8", errors="ignore"))
        rows.append({"kind": kind, "date": date_from_path(path), "path": relative, "text": text})
    return rows


def iter_article_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = DATA / "source" / "zhezhe_articles.jsonl"
    for item in read_jsonl(path):
        title = str(item.get("title") or "")
        summary = str(item.get("summary") or item.get("description") or "")
        article_id = str(item.get("article_id") or item.get("id") or item.get("url") or "")
        date = (
            date_from_text(item.get("date"))
            or date_from_text(item.get("published_at"))
            or date_from_text(item.get("date_published"))
        )
        rows.append(
            {
                "kind": "article",
                "date": date,
                "id": article_id,
                "title": title,
                "path": rel(path),
                "text": plain(" ".join(part for part in (title, summary, article_id) if part)),
            }
        )
    return rows


def load_rows(kinds: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if "metadata" in kinds:
        rows.extend(iter_metadata())
    if "transcript" in kinds:
        rows.extend(iter_markdown("transcript", "transcripts"))
    if "article" in kinds:
        rows.extend(iter_markdown("article", "articles", zhezhe_article_paths()))
        rows.extend(iter_article_inventory())
    return rows


def wanted_kinds(args: argparse.Namespace) -> set[str]:
    if not args.kind or "all" in args.kind:
        return {"metadata", "transcript", "article"}
    return set(args.kind)


def passes_date_filters(row: dict[str, Any], args: argparse.Namespace) -> bool:
    date = str(row.get("date") or "")
    if args.date and date != args.date:
        return False
    if args.since and date < args.since:
        return False
    if args.until and date > args.until:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("terms", nargs="+", help="Search terms. Quote phrases with spaces.")
    parser.add_argument(
        "--kind",
        action="append",
        choices=["metadata", "transcript", "article", "all"],
        help="Restrict source kind. Repeatable.",
    )
    parser.add_argument("--date", help="Restrict to YYYY-MM-DD.")
    parser.add_argument("--since", help="Keep rows on/after YYYY-MM-DD.")
    parser.add_argument("--until", help="Keep rows on/before YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true", help="Emit JSON lines.")
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for row in load_rows(wanted_kinds(args)):
        if not passes_date_filters(row, args):
            continue
        row_score = score(str(row.get("text") or ""), args.terms)
        if row_score <= 0:
            continue
        row["score"] = row_score
        row["snippet"] = snippet(str(row.get("text") or ""), args.terms)
        row.pop("text", None)
        rows.append(row)

    rows.sort(key=lambda item: (str(item.get("date") or ""), int(item.get("score") or 0)), reverse=True)
    rows = rows[: args.limit]

    for row in rows:
        if args.json:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
            continue
        title = f" {row['title']}" if row.get("title") else ""
        ident = f" id={row['id']}" if row.get("id") else ""
        print(f"[{row['kind']}] {row.get('date') or 'unknown-date'} score={row['score']}{ident} {row['path']}{title}")
        print(row["snippet"])
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
