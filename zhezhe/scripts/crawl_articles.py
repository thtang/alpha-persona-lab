#!/usr/bin/env python3
"""Crawl public UDN/Moore articles for the Zhezhe skill corpus.

This script stores local research copies for corpus analysis. Downstream skill
answers should summarize and link to sources instead of quoting long passages.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


AUTHOR_LIST_ROOT = "https://money.udn.com/author/articles/4755/pv"
USER_AGENT = "alpha-persona-lab zhezhe article crawler/0.1"
MATCH_TERMS = ("郭哲榮", "哲榮", "投資長郭哲榮", "摩爾投顧投資長")
SKIP_TEXT_TAGS = {"script", "style", "svg", "iframe", "noscript", "form", "button"}
ARTICLE_ID_RE = re.compile(r"/story/\d+/(\d+)")


class MarkdownHTMLParser(HTMLParser):
    """Small HTML-to-Markdown converter for UDN article body fragments."""

    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "figcaption",
        "figure",
        "footer",
        "header",
        "main",
        "nav",
        "ol",
        "p",
        "section",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0
        self.href_stack: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in SKIP_TEXT_TAGS or self._is_noise(attrs_dict):
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.HEADING_TAGS:
            level = min(int(tag[1]), 4)
            self._append("\n\n" + "#" * level + " ")
        elif tag == "li":
            self._append("\n- ")
        elif tag == "br":
            self._append("\n")
        elif tag == "a":
            self.href_stack.append(attrs_dict.get("href"))
        elif tag in self.BLOCK_TAGS:
            self._append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TEXT_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "a":
            if self.href_stack:
                self.href_stack.pop()
        elif tag in self.HEADING_TAGS or tag in self.BLOCK_TAGS or tag == "li":
            self._append("\n\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = normalize_space(html.unescape(data))
        if not text:
            return
        if self.href_stack and self.href_stack[-1]:
            href = urllib.parse.urljoin("https://money.udn.com", self.href_stack[-1] or "")
            self._append(f"[{text}]({href})")
        else:
            self._append(text)

    def markdown(self) -> str:
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        raw = re.sub(r"\n[ \t]+", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        raw = re.sub(r"(?<!\n)\n(?!\n)", "\n\n", raw)
        raw = re.sub(r" +", " ", raw)
        return raw.strip()

    def _append(self, value: str) -> None:
        if not value:
            return
        if (
            self.parts
            and value[0] not in "\n，。！？；：、）】』」,.!?:;)]"
            and not self.parts[-1].endswith((" ", "\n", "(", "（", "["))
        ):
            self.parts.append(" ")
        self.parts.append(value)

    @staticmethod
    def _is_noise(attrs: dict[str, str | None]) -> bool:
        combined = " ".join(str(attrs.get(key) or "") for key in ("id", "class", "data-slotname"))
        return any(
            marker in combined
            for marker in (
                "edn-ads",
                "article-body__social-bar",
                "social-bar",
                "vote-embedded",
                "stock_more_button",
                "context-box",
                "only_mobile",
                "web-only",
            )
        )


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def fetch_text(url: str, *, retries: int = 3, timeout: int = 30) -> tuple[str, dict[str, str]]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace"), dict(response.headers)
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.7 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def extract_json_ld(document: str) -> list[Any]:
    blocks = re.findall(
        r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        document,
        flags=re.I | re.S,
    )
    parsed: list[Any] = []
    for block in blocks:
        text = html.unescape(block).strip()
        if not text:
            continue
        try:
            parsed.append(json.loads(text))
        except json.JSONDecodeError as exc:
            cleaned = re.sub(r"[\x00-\x1f]+", " ", text)
            try:
                parsed.append(json.loads(cleaned))
            except json.JSONDecodeError:
                print(f"warning: could not parse JSON-LD block: {exc}", file=sys.stderr)
    return parsed


def walk_json(value: Any) -> list[Any]:
    out = [value]
    if isinstance(value, dict):
        for child in value.values():
            out.extend(walk_json(child))
    elif isinstance(value, list):
        for child in value:
            out.extend(walk_json(child))
    return out


def type_names(value: Any) -> set[str]:
    raw = value.get("@type") if isinstance(value, dict) else None
    if isinstance(raw, list):
        return {str(item) for item in raw}
    if raw:
        return {str(raw)}
    return set()


def first_graph_objects(document: str, type_name: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for block in extract_json_ld(document):
        for item in walk_json(block):
            if isinstance(item, dict) and type_name in type_names(item):
                found.append(item)
    return found


def parse_author_page(document: str, page_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item_list in first_graph_objects(document, "ItemList"):
        for element in item_list.get("itemListElement", []) or []:
            if not isinstance(element, dict):
                continue
            article = element.get("item")
            if not isinstance(article, dict) or "NewsArticle" not in type_names(article):
                continue
            row = normalize_article_metadata(article, source_list_url=page_url, position=element.get("position"))
            url = row.get("url")
            if url and url not in seen:
                seen.add(url)
                rows.append(row)
    return rows


def normalize_article_metadata(
    article: dict[str, Any],
    *,
    source_list_url: str | None = None,
    position: Any = None,
) -> dict[str, Any]:
    url = article.get("url") or article.get("@id") or article.get("mainEntityOfPage")
    if isinstance(url, dict):
        url = url.get("@id") or url.get("url")
    url = urllib.parse.urljoin("https://money.udn.com", str(url or ""))
    article_id = article_id_from_url(url)
    author = article.get("author") or article.get("creator")
    image = article.get("image")
    keywords = article.get("keywords")
    if isinstance(keywords, str):
        keywords = [normalize_space(part) for part in keywords.split(",") if normalize_space(part)]
    row = {
        "source": "udn_money_author_4755",
        "source_list_url": source_list_url,
        "list_position": position,
        "article_id": article_id,
        "url": url,
        "title": normalize_space(article.get("headline") or article.get("name")),
        "description": normalize_space(article.get("description")),
        "date_published": article.get("datePublished"),
        "date_modified": article.get("dateModified"),
        "author": author_name(author),
        "article_section": normalize_space(article.get("articleSection")),
        "genre": normalize_space(article.get("genre")),
        "keywords": keywords if isinstance(keywords, list) else [],
        "image_url": image_url(image),
        "is_accessible_for_free": article.get("isAccessibleForFree"),
    }
    return {key: value for key, value in row.items() if value not in ("", None, [])}


def author_name(author: Any) -> str:
    if isinstance(author, list):
        return ", ".join(filter(None, (author_name(item) for item in author)))
    if isinstance(author, dict):
        return normalize_space(author.get("name") or author.get("@id"))
    return normalize_space(author)


def image_url(image: Any) -> str:
    if isinstance(image, list):
        return image_url(image[0]) if image else ""
    if isinstance(image, dict):
        return normalize_space(image.get("url") or image.get("contentUrl"))
    return normalize_space(image)


def article_id_from_url(url: str) -> str:
    match = ARTICLE_ID_RE.search(url)
    if match:
        return match.group(1)
    parts = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
    return parts[-1] if parts else re.sub(r"\W+", "-", url).strip("-")


def date_from_metadata(row: dict[str, Any]) -> str:
    for key in ("date_published", "date_modified"):
        value = normalize_space(row.get(key))
        match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", value)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
    return "undated"


def page_url(page: int) -> str:
    return AUTHOR_LIST_ROOT if page == 1 else f"{AUTHOR_LIST_ROOT}/{page}"


def crawl_inventory(*, max_pages: int, limit: int | None, sleep_seconds: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        url = page_url(page)
        document, _ = fetch_text(url)
        page_rows = parse_author_page(document, url)
        if not page_rows:
            print(f"warning: no articles parsed from {url}", file=sys.stderr)
            break
        for row in page_rows:
            article_url = row.get("url")
            if article_url and article_url not in seen:
                seen.add(article_url)
                rows.append(row)
                if limit and len(rows) >= limit:
                    return rows
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return rows


def relevant_to_zhezhe(row: dict[str, Any], body: str = "") -> bool:
    haystack = "\n".join(
        normalize_space(row.get(key))
        for key in ("title", "description", "author")
    )
    haystack = f"{haystack}\n{body}"
    return any(term in haystack for term in MATCH_TERMS)


def meta_content(document: str, *, name: str | None = None, prop: str | None = None) -> str:
    if name:
        pattern = rf'<meta\b(?=[^>]*\bname\s*=\s*["\']{re.escape(name)}["\'])(?=[^>]*\bcontent\s*=\s*["\'](.*?)["\'])[^>]*>'
    elif prop:
        pattern = rf'<meta\b(?=[^>]*\bproperty\s*=\s*["\']{re.escape(prop)}["\'])(?=[^>]*\bcontent\s*=\s*["\'](.*?)["\'])[^>]*>'
    else:
        return ""
    match = re.search(pattern, document, flags=re.I | re.S)
    return normalize_space(match.group(1)) if match else ""


def extract_article_body_html(document: str) -> str:
    selectors = (
        r'<section\b(?=[^>]*\bid\s*=\s*["\']article_body["\'])(?=[^>]*\bclass\s*=\s*["\'][^"\']*article-body__editor[^"\']*["\'])[^>]*>(.*?)</section>',
        r'<section\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*article-body__editor[^"\']*["\'])[^>]*>(.*?)</section>',
        r'<div\b(?=[^>]*\bid\s*=\s*["\']story_body["\'])[^>]*>(.*?)</div>',
        r'<article\b[^>]*>(.*?)</article>',
    )
    for pattern in selectors:
        match = re.search(pattern, document, flags=re.I | re.S)
        if match:
            return trim_at_content_finish(match.group(1))
    return ""


def trim_at_content_finish(fragment: str) -> str:
    match = re.search(r'<div\b(?=[^>]*\bid\s*=\s*["\']content-finish["\'])[^>]*>', fragment, flags=re.I | re.S)
    return fragment[: match.start()] if match else fragment


def html_to_markdown(fragment: str) -> str:
    parser = MarkdownHTMLParser()
    parser.feed(fragment)
    return parser.markdown()


def extract_article_page(row: dict[str, Any]) -> tuple[dict[str, Any], str, dict[str, Any]]:
    url = row["url"]
    document, headers = fetch_text(url)
    article_nodes = first_graph_objects(document, "NewsArticle")
    page_meta = normalize_article_metadata(article_nodes[0]) if article_nodes else {}
    merged = {**row, **{key: value for key, value in page_meta.items() if value not in ("", None, [])}}
    merged["url"] = row["url"]
    merged["article_id"] = row.get("article_id") or article_id_from_url(row["url"])
    description = meta_content(document, name="description") or meta_content(document, prop="og:description")
    if description and not merged.get("description"):
        merged["description"] = description
    body_html = extract_article_body_html(document)
    body_markdown = html_to_markdown(body_html)
    stats = {
        "http_last_modified": headers.get("Last-Modified"),
        "json_ld_news_articles": len(article_nodes),
        "body_chars": len(body_markdown),
        "body_source": "article_body_html" if body_markdown else "none",
    }
    return merged, body_markdown, stats


def markdown_document(row: dict[str, Any], body_markdown: str) -> str:
    metadata = {
        "source": "udn_money",
        "article_id": row.get("article_id"),
        "title": row.get("title"),
        "url": row.get("url"),
        "author": row.get("author"),
        "date_published": row.get("date_published"),
        "date_modified": row.get("date_modified"),
        "article_section": row.get("article_section"),
        "keywords": row.get("keywords", []),
        "copyright_note": "Local research corpus. Summarize and link in answers; avoid long verbatim quotation.",
    }
    yaml_lines = ["---"]
    for key, value in metadata.items():
        yaml_lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    yaml_lines.append("---")
    return "\n".join(yaml_lines) + "\n\n" + body_markdown.strip() + "\n"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    skill_dir = Path(args.skill_dir).resolve()
    source_dir = skill_dir / "data" / "source"
    article_dir = skill_dir / "data" / "articles"
    inventory_path = source_dir / "udn_articles.jsonl"
    zhezhe_path = source_dir / "zhezhe_articles.jsonl"
    summary_path = source_dir / "article_fetch_summary.json"

    if inventory_path.exists() and not args.force:
        inventory = load_jsonl(inventory_path)
    else:
        inventory = crawl_inventory(max_pages=args.max_pages, limit=args.limit, sleep_seconds=args.sleep)
        write_jsonl(inventory_path, inventory)

    fetched_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for index, row in enumerate(inventory, start=1):
        if args.limit and index > args.limit:
            break
        article_id = row.get("article_id") or article_id_from_url(row.get("url", ""))
        date = date_from_metadata(row)
        md_path = article_dir / f"{date}_{article_id}.md"
        result: dict[str, Any] = {
            "article_id": article_id,
            "url": row.get("url"),
            "local_path": str(md_path.relative_to(skill_dir)),
            "status": "skipped_existing" if md_path.exists() and not args.force else "pending",
        }
        try:
            if md_path.exists() and not args.force:
                body_markdown = md_path.read_text(encoding="utf-8")
                enriched = dict(row)
                stats = {"body_chars": len(body_markdown), "body_source": "existing_markdown"}
            else:
                enriched, body_markdown, stats = extract_article_page(row)
                date = date_from_metadata(enriched)
                md_path = article_dir / f"{date}_{article_id}.md"
                result["local_path"] = str(md_path.relative_to(skill_dir))
                if body_markdown:
                    md_path.parent.mkdir(parents=True, exist_ok=True)
                    md_path.write_text(markdown_document(enriched, body_markdown), encoding="utf-8")
                    result["status"] = "fetched"
                else:
                    result["status"] = "no_body"
            enriched["local_path"] = str(md_path.relative_to(skill_dir))
            enriched["body_chars"] = stats.get("body_chars", 0)
            enriched["matched_zhezhe_terms"] = sorted(
                term
                for term in MATCH_TERMS
                if term in "\n".join(
                    [
                        normalize_space(enriched.get("title")),
                        normalize_space(enriched.get("description")),
                        normalize_space(enriched.get("author")),
                        body_markdown,
                    ]
                )
            )
            if relevant_to_zhezhe(enriched, body_markdown):
                fetched_rows.append(enriched)
            result.update(stats)
        except Exception as exc:  # Keep crawling even if a single article fails.
            result["status"] = "error"
            result["error"] = str(exc)
            print(f"warning: failed article {row.get('url')}: {exc}", file=sys.stderr)
        summary_rows.append(result)
        if args.sleep:
            time.sleep(args.sleep)

    write_jsonl(zhezhe_path, fetched_rows)
    summary = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": AUTHOR_LIST_ROOT,
        "max_pages": args.max_pages,
        "limit": args.limit,
        "inventory_count": len(inventory),
        "zhezhe_article_count": len(fetched_rows),
        "copyright_note": "Local research corpus. Skill answers should summarize with source links and avoid long verbatim excerpts.",
        "articles": summary_rows,
    }
    write_json(summary_path, summary)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", default="zhezhe", help="Path to the zhezhe skill directory.")
    parser.add_argument("--max-pages", type=int, default=10, help="Maximum UDN author-list pages to crawl.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum inventory/articles to process.")
    parser.add_argument("--force", action="store_true", help="Refresh inventory and overwrite existing article markdown.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to sleep between requests.")
    args = parser.parse_args(argv)
    if args.max_pages < 1:
        parser.error("--max-pages must be >= 1")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")
    if args.sleep < 0:
        parser.error("--sleep must be >= 0")
    return args


def main(argv: list[str] | None = None) -> int:
    summary = run(parse_args(argv))
    print(
        "Fetched UDN inventory: {inventory_count}; matched Zhezhe articles: {zhezhe_article_count}".format(
            **summary
        )
    )
    print("Summary: zhezhe/data/source/article_fetch_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
