#!/usr/bin/env python3
"""Fetch and structure the Moore/SoundOn podcast feed for the Zhezhe skill."""

from __future__ import annotations

import argparse
import email.utils
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_FEED_URLS = [
    "https://feeds.soundon.fm/podcasts/7c9b0925-29e2-472c-8120-15b13e70b377.xml",
    "https://feeds.soundon.fm/podcasts/35eb55b5-8669-418b-9a08-dc13c482809a.xml",
]
DEFAULT_FILTER_TERMS = ("郭哲榮", "哲哲", "zhezhe")
LOCAL_TZ = ZoneInfo("Asia/Taipei")
USER_AGENT = "alpha-persona-lab zhezhe-podcast-feed/0.1"

NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "soundon": "http://soundon.fm/spec/podcast-1.0",
}


class TextExtractor(HTMLParser):
    """Minimal HTML-to-text converter for SoundOn descriptions."""

    BLOCK_TAGS = {"br", "p", "div", "li", "ul", "ol", "section"}
    SKIP_TAGS = {"script", "style"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = html.unescape(data)
        if text.strip():
            self.parts.append(text)

    def text(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def fetch_bytes(url: str, *, retries: int = 3, timeout: int = 60) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(attempt * 1.5, 6))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


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


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return html.unescape(value).strip()


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    parser = TextExtractor()
    parser.feed(value)
    return parser.text()


def child_text(node: ET.Element, path: str) -> str:
    return clean_text(node.findtext(path, default="", namespaces=NS))


def parse_pub_date(value: str) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None, None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(LOCAL_TZ)
    return parsed.astimezone(timezone.utc).isoformat(), local.date().isoformat()


def parse_duration(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    parts = value.split(":")
    if not all(part.isdigit() for part in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def split_keywords(value: str) -> list[str]:
    if not value:
        return []
    raw_parts = re.split(r"[,，\n\t]+", value)
    keywords: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        cleaned = part.strip().strip("#")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            keywords.append(cleaned)
    return keywords


def extract_hashtags(text: str) -> list[str]:
    tags = re.findall(r"#([^\s#，,、]+)", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        tag = tag.strip()
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


def stable_episode_id(local_date: str | None, guid: str) -> str:
    date_part = local_date or "unknown-date"
    guid_part = re.sub(r"[^0-9A-Za-z]", "", guid)[:8]
    if not guid_part:
        guid_part = hashlib.sha1(guid.encode("utf-8")).hexdigest()[:8]
    return f"zhezhe-{date_part}-{guid_part}"


def feed_slug(feed_url: str) -> str:
    match = re.search(r"/podcasts/([0-9A-Za-z-]+)\.xml", feed_url)
    if match:
        return match.group(1)
    return hashlib.sha1(feed_url.encode("utf-8")).hexdigest()[:12]


def guid_prefix(guid: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z]", "", guid)[:8]
    return prefix or hashlib.sha1(guid.encode("utf-8")).hexdigest()[:8]


def existing_relative_path(path: Path, skill_dir: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return str(path.relative_to(skill_dir))
    except ValueError:
        return str(path)


def parse_episode(item: ET.Element, skill_dir: Path, channel_meta: dict[str, str]) -> dict[str, Any]:
    title = child_text(item, "title")
    raw_description = child_text(item, "description")
    content_html = child_text(item, "content:encoded")
    description_text = html_to_text(content_html or raw_description)
    summary_text = html_to_text(child_text(item, "itunes:summary")) or description_text
    guid = child_text(item, "guid") or child_text(item, "soundon:id") or child_text(item, "link")
    pub_date = child_text(item, "pubDate")
    pub_date_utc, local_date = parse_pub_date(pub_date)
    episode_id = stable_episode_id(local_date, guid or title)

    enclosure = item.find("enclosure")
    audio_url = enclosure.attrib.get("url") if enclosure is not None else None
    enclosure_length = enclosure.attrib.get("length") if enclosure is not None else None
    enclosure_type = enclosure.attrib.get("type") if enclosure is not None else None
    keyword_text = child_text(item, "itunes:keywords")
    keywords = split_keywords(keyword_text)
    for tag in extract_hashtags(f"{title}\n{description_text}"):
        if tag not in keywords:
            keywords.append(tag)

    transcript_candidates = [
        skill_dir / "data" / "transcripts" / f"{local_date}_{guid_prefix(guid)}.md",
        skill_dir / "data" / "transcripts" / f"{local_date}_{episode_id}.md",
        skill_dir / "data" / "transcripts" / f"{episode_id}.md",
    ]
    transcript_path = None
    for candidate in transcript_candidates:
        transcript_path = existing_relative_path(candidate, skill_dir)
        if transcript_path:
            break

    audio_path = existing_relative_path(skill_dir / "data" / "audio" / f"{episode_id}.mp3", skill_dir)
    asr_status = "transcribed" if transcript_path else "pending"

    return {
        "episode_id": episode_id,
        "podcast_id": channel_meta.get("podcast_id"),
        "feed_url": channel_meta.get("feed_url"),
        "channel_title": channel_meta.get("channel_title"),
        "channel_author": channel_meta.get("channel_author"),
        "title": title,
        "pub_date": pub_date,
        "pub_date_utc": pub_date_utc,
        "local_date": local_date,
        "guid": guid,
        "player_url": child_text(item, "link") or None,
        "audio_url": audio_url,
        "duration_seconds": parse_duration(child_text(item, "itunes:duration")),
        "description_text": summary_text,
        "keywords": keywords,
        "transcript_path": transcript_path,
        "audio_path": audio_path,
        "asr_status": asr_status,
        "creator": child_text(item, "dc:creator") or None,
        "soundon_id": child_text(item, "soundon:id") or None,
        "soundon_created_at": child_text(item, "soundon:createdAt") or None,
        "soundon_updated_at": child_text(item, "soundon:updatedAt") or None,
        "enclosure_length": int(enclosure_length) if enclosure_length and enclosure_length.isdigit() else None,
        "enclosure_type": enclosure_type,
        "raw_description_html": raw_description,
    }


def match_zhezhe_episode(row: dict[str, Any], filter_terms: list[str]) -> tuple[bool, dict[str, Any]]:
    haystacks = {
        "channel_author": row.get("channel_author") or "",
        "channel_title": row.get("channel_title") or "",
        "title": row.get("title") or "",
        "description_text": row.get("description_text") or "",
        "keywords": " ".join(row.get("keywords") or []),
    }
    matches: dict[str, list[str]] = {}
    score = 0
    for term in filter_terms:
        term = term.strip()
        if not term:
            continue
        term_hits: list[str] = []
        for field, value in haystacks.items():
            if term.lower() in value.lower():
                term_hits.append(field)
                score += 3 if field == "title" else 2 if field == "description_text" else 1
        if term_hits:
            matches[term] = term_hits

    dedicated_zhezhe_feed = "郭哲榮" in str(row.get("channel_author") or "")
    # Keywords are noisy in the Moore umbrella feed; the dedicated 榮耀華爾街 feed is first-party Zhezhe material.
    included = dedicated_zhezhe_feed or score >= 2
    return included, {"filter_score": score, "matched_terms": matches}


def build_manifest_row(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "episode_id",
        "podcast_id",
        "feed_url",
        "channel_title",
        "channel_author",
        "title",
        "pub_date",
        "local_date",
        "guid",
        "player_url",
        "audio_url",
        "duration_seconds",
        "description_text",
        "keywords",
        "transcript_path",
        "audio_path",
        "asr_status",
    ]
    return {key: row.get(key) for key in keys}


def merge_manifest_rows(manifest_path: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = {str(row.get("episode_id")): row for row in read_jsonl(manifest_path) if row.get("episode_id")}
    preserve_keys = [
        "asr_status",
        "asr_model",
        "asr_at",
        "audio_sha256",
        "transcript_path",
        "asr_error",
    ]
    merged: list[dict[str, Any]] = []
    for row in rows:
        item = build_manifest_row(row)
        old = existing.get(str(item.get("episode_id")))
        if old:
            for key in preserve_keys:
                if old.get(key) not in (None, ""):
                    item[key] = old[key]
            old_audio_path = old.get("audio_path")
            if old_audio_path:
                candidate = Path(str(old_audio_path))
                candidate = candidate if candidate.is_absolute() else manifest_path.parents[1] / candidate
                if candidate.exists():
                    item["audio_path"] = old_audio_path
        merged.append(item)
    return merged


def concise_episode(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "episode_id": row.get("episode_id"),
        "podcast_id": row.get("podcast_id"),
        "channel_title": row.get("channel_title"),
        "title": row.get("title"),
        "local_date": row.get("local_date"),
        "guid": row.get("guid"),
        "player_url": row.get("player_url"),
        "filter_score": row.get("filter_score"),
        "matched_terms": row.get("matched_terms"),
    }


def load_feed(feed_url: str, snapshot_path: Path, *, force: bool) -> tuple[bytes, str]:
    try:
        feed_bytes = fetch_bytes(feed_url)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(feed_bytes)
        return feed_bytes, "fetched"
    except Exception:
        if snapshot_path.exists() and not force:
            return snapshot_path.read_bytes(), "cached_after_fetch_error"
        raise


def parse_feed(
    *,
    feed_url: str,
    snapshot_path: Path,
    skill_dir: Path,
    limit: int,
    force: bool,
    filter_terms: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    feed_bytes, feed_status = load_feed(feed_url, snapshot_path, force=force)
    root = ET.fromstring(feed_bytes)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError(f"RSS channel not found for {feed_url}")

    items = channel.findall("item")
    selected_items = items[:limit] if limit else items
    channel_meta = {
        "feed_url": feed_url,
        "podcast_id": child_text(channel, "soundon:id") or feed_slug(feed_url),
        "channel_title": child_text(channel, "title"),
        "channel_author": child_text(channel, "itunes:author") or child_text(channel, "dc:creator"),
    }

    episodes: list[dict[str, Any]] = []
    zhezhe_episodes: list[dict[str, Any]] = []
    for item in selected_items:
        row = parse_episode(item, skill_dir, channel_meta)
        included, match_info = match_zhezhe_episode(row, filter_terms)
        row.update(match_info)
        row["is_zhezhe_episode"] = included
        episodes.append(row)
        if included:
            zhezhe_episodes.append(row)

    feed_summary = {
        **channel_meta,
        "feed_status": feed_status,
        "channel_last_build_date": child_text(channel, "lastBuildDate"),
        "snapshot_path": str(snapshot_path.relative_to(skill_dir)),
        "episode_count_total_in_feed": len(items),
        "episode_count_parsed": len(episodes),
        "zhezhe_episode_count": len(zhezhe_episodes),
        "latest_episode": concise_episode(episodes[0] if episodes else None),
        "latest_zhezhe_episode": concise_episode(zhezhe_episodes[0] if zhezhe_episodes else None),
    }
    return episodes, zhezhe_episodes, feed_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch SoundOn RSS metadata for the Zhezhe skill.")
    parser.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--feed-url",
        action="append",
        default=[],
        help="SoundOn RSS URL to fetch. Repeatable. Defaults to all known Zhezhe feeds.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Parse only the first N feed items, for smoke tests.")
    parser.add_argument("--force", action="store_true", help="Fail instead of falling back to an existing snapshot.")
    parser.add_argument("--filter-term", action="append", default=[], help="Append an episode filter term.")
    args = parser.parse_args()

    skill_dir = args.skill_dir.resolve()
    source_dir = skill_dir / "data" / "source"
    episodes_path = source_dir / "podcast_episodes.jsonl"
    zhezhe_path = source_dir / "zhezhe_episodes.jsonl"
    manifest_path = skill_dir / "data" / "audio_manifest.jsonl"
    summary_path = source_dir / "podcast_fetch_summary.json"

    filter_terms = list(DEFAULT_FILTER_TERMS) + [term for term in args.filter_term if term]
    feed_urls = args.feed_url or DEFAULT_FEED_URLS

    episodes: list[dict[str, Any]] = []
    zhezhe_episodes: list[dict[str, Any]] = []
    feed_summaries: list[dict[str, Any]] = []
    for feed_url in feed_urls:
        snapshot_path = source_dir / f"podcast_feed_snapshot_{feed_slug(feed_url)}.xml"
        feed_episodes, feed_zhezhe_episodes, feed_summary = parse_feed(
            feed_url=feed_url,
            snapshot_path=snapshot_path,
            skill_dir=skill_dir,
            limit=args.limit,
            force=args.force,
            filter_terms=filter_terms,
        )
        episodes.extend(feed_episodes)
        zhezhe_episodes.extend(feed_zhezhe_episodes)
        feed_summaries.append(feed_summary)

    episodes.sort(key=lambda row: row.get("pub_date_utc") or "", reverse=True)
    zhezhe_episodes.sort(key=lambda row: row.get("pub_date_utc") or "", reverse=True)

    manifest = merge_manifest_rows(manifest_path, zhezhe_episodes)
    write_jsonl(episodes_path, episodes)
    write_jsonl(zhezhe_path, zhezhe_episodes)
    write_jsonl(manifest_path, manifest)

    summary = {
        "feed_urls": feed_urls,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "feed_count": len(feed_summaries),
        "feeds": feed_summaries,
        "episode_count_total_in_feed": sum(feed["episode_count_total_in_feed"] for feed in feed_summaries),
        "episode_count_parsed": len(episodes),
        "zhezhe_episode_count": len(zhezhe_episodes),
        "manifest_count": len(manifest),
        "limit": args.limit or None,
        "filter_terms": filter_terms,
        "outputs": {
            "episodes": str(episodes_path.relative_to(skill_dir)),
            "zhezhe_episodes": str(zhezhe_path.relative_to(skill_dir)),
            "audio_manifest": str(manifest_path.relative_to(skill_dir)),
            "summary": str(summary_path.relative_to(skill_dir)),
        },
        "latest_episode": concise_episode(episodes[0] if episodes else None),
        "latest_zhezhe_episode": concise_episode(zhezhe_episodes[0] if zhezhe_episodes else None),
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI should print a concise batch failure.
        print(f"fetch_podcast_feed.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
