#!/usr/bin/env python3
"""Collect public source inventory for the Yu Ting-Hao distillation project."""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = "https://digitalgarden-five-azure.vercel.app"
YT_CHANNEL_ID = "UC0lbAQVpenvfA2QqzsRtL_g"
WP_ROOT = "https://yutinghao.finance"
USER_AGENT = "alpha-persona-lab source audit/0.1"


class MainTextParser(HTMLParser):
    """Small HTML-to-text converter tuned for Obsidian Digital Garden pages."""

    BLOCK_TAGS = {"p", "div", "section", "article", "main", "ul", "ol", "li", "br", "hr"}
    HEADING_TAGS = {"h1", "h2", "h3", "h4"}
    SKIP_TAGS = {"script", "style", "svg", "iframe", "nav", "aside"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0
        self.current_heading: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.HEADING_TAGS:
            self.current_heading = tag
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "br":
            self.parts.append("\n")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in self.HEADING_TAGS:
            self.current_heading = None
            self.parts.append("\n")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        cleaned = re.sub(r"\s+", " ", html.unescape(data)).strip()
        if cleaned:
            if self.parts and not self.parts[-1].endswith((" ", "\n", "# ")):
                self.parts.append(" ")
            self.parts.append(cleaned)

    def text(self) -> str:
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        raw = re.sub(r" +", " ", raw)
        return raw.strip()


def fetch_text(url: str, *, retries: int = 3, timeout: int = 30) -> tuple[str, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace"), dict(resp.headers)
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def extract_main_html(document: str) -> str:
    match = re.search(r"<main\b[^>]*>(.*?)</main>", document, flags=re.S | re.I)
    return match.group(1) if match else document


def html_to_text(fragment: str) -> str:
    parser = MainTextParser()
    parser.feed(fragment)
    return parser.text()


def slug_from_permalink(permalink: str) -> str:
    parts = [p for p in permalink.strip("/").split("/") if p]
    return parts[-1] if parts else "index"


def date_from_text(value: str) -> str | None:
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", value)
    return match.group(1) if match else None


def collect_filetree_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, value in node.items():
        if not isinstance(value, dict):
            continue
        if value.get("isNote"):
            out.append(
                {
                    "filename": key,
                    "name": value.get("name", key),
                    "permalink": value.get("permalink"),
                    "hide": value.get("hide", False),
                    "pinned": value.get("pinned", False),
                }
            )
        if value.get("isFolder"):
            out.extend(collect_filetree_nodes(value))
    return out


def crawl_digitalgarden(out_dir: Path, *, max_items: int | None) -> dict[str, Any]:
    tree_text, _ = fetch_text(f"{ROOT}/filetree.json")
    tree = json.loads(tree_text)
    all_nodes = collect_filetree_nodes(tree)

    notes = [
        n
        for n in all_nodes
        if n.get("permalink", "").startswith("/yutinghao-notes/")
        and "游庭皓" in n.get("name", "")
    ]
    transcripts = [
        n
        for n in all_nodes
        if n.get("permalink", "").startswith("/yutinghao-transcripts/")
        and "游庭皓" in n.get("name", "")
    ]
    if max_items:
        notes = notes[:max_items]
        transcripts = transcripts[:max_items]

    def fetch_pages(items: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        target_dir = out_dir / "data" / ("notes" if kind == "note" else "transcripts")
        for item in items:
            permalink = item["permalink"]
            url = urllib.parse.urljoin(ROOT, permalink)
            doc, headers = fetch_text(url)
            main = extract_main_html(doc)
            text = html_to_text(main)
            date = date_from_text(item["name"]) or date_from_text(permalink) or slug_from_permalink(permalink)
            headings = re.findall(r"<h([12])\b[^>]*>(.*?)</h\1>", main, flags=re.S | re.I)
            clean_headings = [re.sub(r"\s+", " ", html_to_text(h)).strip("# ") for _, h in headings]
            youtube_match = re.search(r"https://www\.youtube\.com/watch\?v=[\w-]+", main)
            md_path = target_dir / f"{date}.md"
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(
                f"---\nsource: digitalgarden\nkind: {kind}\ndate: {date}\nurl: {url}\n---\n\n{text}\n",
                encoding="utf-8",
            )
            rows.append(
                {
                    **item,
                    "date": date,
                    "url": url,
                    "kind": kind,
                    "local_path": str(md_path.relative_to(out_dir)),
                    "chars": len(text),
                    "headings": clean_headings[:80],
                    "youtube_url": youtube_match.group(0) if youtube_match else None,
                    "http_last_modified": headers.get("Last-Modified"),
                }
            )
            time.sleep(0.05)
        return rows

    note_rows = fetch_pages(notes, "note")
    transcript_rows = fetch_pages(transcripts, "transcript")
    write_json(out_dir / "data/source/digitalgarden_index.json", {"notes": note_rows, "transcripts": transcript_rows})
    write_jsonl(out_dir / "data/source/digitalgarden_notes.jsonl", note_rows)
    write_jsonl(out_dir / "data/source/digitalgarden_transcripts.jsonl", transcript_rows)
    return {"notes": len(note_rows), "transcripts": len(transcript_rows)}


def crawl_youtube_rss(out_dir: Path) -> dict[str, Any]:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL_ID}"
    feed, _ = fetch_text(url)
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    root = ET.fromstring(feed)
    rows: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        media_group = entry.find("media:group", ns)
        description = ""
        thumbnail = None
        if media_group is not None:
            desc_el = media_group.find("media:description", ns)
            description = desc_el.text or "" if desc_el is not None else ""
            thumb_el = media_group.find("media:thumbnail", ns)
            thumbnail = thumb_el.attrib.get("url") if thumb_el is not None else None
        video_id = entry.findtext("yt:videoId", default="", namespaces=ns)
        rows.append(
            {
                "video_id": video_id,
                "title": entry.findtext("atom:title", default="", namespaces=ns),
                "published": entry.findtext("atom:published", default="", namespaces=ns),
                "updated": entry.findtext("atom:updated", default="", namespaces=ns),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": thumbnail,
                "description_chars": len(description),
                "chapters": re.findall(r"^(\d{1,2}:\d{2})\s+([^\n]+)", description, flags=re.M),
            }
        )
    write_json(out_dir / "data/source/youtube_recent.json", rows)
    return {"recent_videos": len(rows), "latest": rows[0] if rows else None}


def get_wp_json(url: str) -> tuple[Any, dict[str, str]]:
    text, headers = fetch_text(url)
    return json.loads(text), headers


def header_value(headers: dict[str, str], name: str, default: str | None = None) -> str | None:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return default


def crawl_official_wp(out_dir: Path, *, max_pages: int | None) -> dict[str, Any]:
    categories, _ = get_wp_json(f"{WP_ROOT}/wp-json/wp/v2/categories?per_page=100")
    category_map = {cat["id"]: cat for cat in categories}
    write_json(out_dir / "data/source/official_categories.json", categories)

    posts: list[dict[str, Any]] = []
    page = 1
    total_pages = 1
    fields = "id,date,modified,slug,link,title,excerpt,content,categories"
    while page <= total_pages:
        if max_pages and page > max_pages:
            break
        url = f"{WP_ROOT}/wp-json/wp/v2/posts?per_page=100&page={page}&_fields={fields}"
        try:
            page_rows, headers = get_wp_json(url)
        except RuntimeError:
            break
        total_pages = int(header_value(headers, "X-WP-TotalPages", str(total_pages)) or total_pages)
        if not page_rows:
            break
        posts.extend(page_rows)
        page += 1
        time.sleep(0.05)

    out_rows: list[dict[str, Any]] = []
    article_dir = out_dir / "data/official_articles"
    article_dir.mkdir(parents=True, exist_ok=True)
    for post in posts:
        title = html.unescape(re.sub(r"<[^>]+>", "", post.get("title", {}).get("rendered", ""))).strip()
        excerpt = html_to_text(post.get("excerpt", {}).get("rendered", ""))
        content = html_to_text(post.get("content", {}).get("rendered", ""))
        category_names = [category_map.get(cid, {}).get("name", str(cid)) for cid in post.get("categories", [])]
        date = post.get("date", "")[:10]
        md_name = f"{date}_{post.get('slug') or post.get('id')}.md"
        local_path = article_dir / md_name
        if content.strip():
            local_path.write_text(
                f"---\nsource: yutinghao.finance\nid: {post.get('id')}\ndate: {date}\nurl: {post.get('link')}\ncategories: {', '.join(category_names)}\n---\n\n# {title}\n\n{content}\n",
                encoding="utf-8",
            )
        out_rows.append(
            {
                "id": post.get("id"),
                "date": date,
                "modified": post.get("modified"),
                "slug": post.get("slug"),
                "title": title,
                "url": post.get("link"),
                "categories": category_names,
                "excerpt_chars": len(excerpt),
                "content_chars": len(content),
                "local_path": str(local_path.relative_to(out_dir)) if content.strip() else None,
                "access": "full_public" if len(content) > 500 else "metadata_or_excerpt",
            }
        )
    write_jsonl(out_dir / "data/source/official_posts.jsonl", out_rows)
    write_json(out_dir / "data/source/official_posts_index.json", out_rows)
    return {
        "categories": len(categories),
        "posts": len(out_rows),
        "full_public_posts": sum(1 for row in out_rows if row["access"] == "full_public"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="yutinghao")
    parser.add_argument("--max-items", type=int, default=None, help="Limit digital garden notes/transcripts for smoke tests.")
    parser.add_argument("--max-wp-pages", type=int, default=None, help="Limit WordPress pages for smoke tests.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    summary = {
        "digitalgarden": crawl_digitalgarden(out_dir, max_items=args.max_items),
        "youtube_rss": crawl_youtube_rss(out_dir),
        "official_wp": crawl_official_wp(out_dir, max_pages=args.max_wp_pages),
    }
    write_json(out_dir / "data/source/crawl_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
