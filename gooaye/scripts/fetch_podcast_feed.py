#!/usr/bin/env python3
"""Fetch Gooaye SoundOn podcast metadata and track ASR fallback candidates."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


PODCAST_ID = "954689a5-3096-43a4-a80b-7810b219cef3"
DEFAULT_FEED_URL = f"https://feeds.soundon.fm/podcasts/{PODCAST_ID}.xml"
USER_AGENT = "gooaye-skill-soundon-fetcher/1.0"
TAIPEI = ZoneInfo("Asia/Taipei")
NAMESPACES = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)


def fetch_bytes(url: str, retries: int = 3, timeout: int = 60) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2 * attempt, 8))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    parser = TextExtractor()
    parser.feed(value)
    text = html.unescape("".join(parser.parts))
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def child_text(node: ET.Element, name: str) -> str:
    found = node.find(name, NAMESPACES)
    return (found.text or "").strip() if found is not None else ""


def enclosure_url(item: ET.Element) -> str:
    enclosure = item.find("enclosure")
    if enclosure is None:
        return ""
    return (enclosure.attrib.get("url") or "").strip()


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


def parse_pub_date(value: str) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc_dt = dt.astimezone(timezone.utc)
    local_dt = dt.astimezone(TAIPEI)
    return utc_dt.isoformat(), local_dt.date().isoformat()


def episode_number(item: ET.Element, title: str) -> int | None:
    explicit = child_text(item, "itunes:episode")
    if explicit.isdigit():
        return int(explicit)
    match = re.search(r"\bEP\s*(\d{1,4})\b", title, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def compact_summary(text: str, limit: int = 500) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def load_jsonl_by_episode(path: Path) -> dict[int, dict[str, Any]]:
    if not path.exists():
        return {}
    rows: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            number = row.get("number")
            if number is not None:
                rows[int(number)] = row
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_feed(feed_xml: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(feed_xml)
    rows: list[dict[str, Any]] = []
    for item in root.findall("./channel/item"):
        title = child_text(item, "title")
        number = episode_number(item, title)
        if number is None:
            continue
        raw_description = child_text(item, "description") or child_text(item, "content:encoded")
        description_text = html_to_text(raw_description)
        pub_date = child_text(item, "pubDate")
        pub_date_utc, date = parse_pub_date(pub_date)
        guid = child_text(item, "guid")
        rows.append(
            {
                "number": number,
                "episode_id": f"EP{number:03d}",
                "title": title,
                "display_title": title,
                "description": raw_description,
                "description_text": description_text,
                "summary": compact_summary(description_text),
                "pub_date": pub_date,
                "pub_date_utc": pub_date_utc,
                "date": date,
                "guid": guid,
                "player_url": child_text(item, "link"),
                "audio_url": enclosure_url(item),
                "duration_seconds": parse_duration(child_text(item, "itunes:duration")),
                "source": "soundon_rss",
            }
        )
    return sorted(rows, key=lambda row: int(row["number"]))


def mark_asr_status(rows: list[dict[str, Any]], data_dir: Path, existing: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    transcript_dir = data_dir / "transcripts"
    updated: list[dict[str, Any]] = []
    for row in rows:
        number = int(row["number"])
        previous = existing.get(number, {})
        merged = {**previous, **row}
        transcript_path = transcript_dir / f"EP{number:03d}.md"
        if transcript_path.exists():
            merged["local_transcript_path"] = str(transcript_path.relative_to(data_dir))
            merged["asr_status"] = "done"
        elif previous.get("asr_status") in {"error", "running"}:
            merged["asr_status"] = previous["asr_status"]
        else:
            merged["asr_status"] = "pending" if merged.get("audio_url") else "missing_audio"
        updated.append(merged)
    return updated


def source_episode_record(row: dict[str, Any]) -> dict[str, Any]:
    number = int(row["number"])
    date = row.get("date")
    parsed_date = None
    if date:
        try:
            parsed_date = datetime.fromisoformat(str(date))
        except ValueError:
            parsed_date = None
    record: dict[str, Any] = {
        "number": number,
        "title": row.get("display_title") or row.get("title") or f"EP{number:03d}",
        "filename": f"EP{number:03d}_soundon_asr.md",
        "description": row.get("description_text") or row.get("description") or "",
        "display_title": row.get("display_title") or row.get("title") or f"EP{number:03d}",
        "summary": row.get("summary"),
        "date": date,
        "source": "soundon_asr",
        "source_url": row.get("player_url") or row.get("audio_url"),
        "audio_url": row.get("audio_url"),
        "guid": row.get("guid"),
    }
    if parsed_date:
        record.update(
            {
                "year": parsed_date.year,
                "month": parsed_date.month,
                "day": parsed_date.day,
                "month_name": parsed_date.strftime("%B"),
                "date_display": parsed_date.strftime("%b %d, %Y"),
                "date_short": parsed_date.strftime("%b %Y"),
            }
        )
    return record


def reconcile_existing_transcripts(data_dir: Path, rows: list[dict[str, Any]]) -> list[int]:
    """Keep ASR transcript files discoverable after canonical site sync rewrites manifests."""

    manifest_path = data_dir / "transcripts_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
    else:
        manifest = {"source": "mixed", "records": [], "errors": []}
    records = {int(record["number"]): record for record in manifest.get("records", [])}
    added: list[int] = []

    for row in rows:
        number = int(row["number"])
        if number in records:
            continue
        transcript_path = data_dir / "transcripts" / f"EP{number:03d}.md"
        if not transcript_path.exists():
            continue
        text = transcript_path.read_text(encoding="utf-8")
        records[number] = {
            "number": number,
            "date": row.get("date"),
            "title": row.get("title"),
            "display_title": row.get("display_title") or row.get("title"),
            "summary": row.get("summary"),
            "source_filename": f"soundon:{row.get('guid') or number}",
            "source_url": row.get("player_url") or row.get("audio_url"),
            "local_path": f"transcripts/EP{number:03d}.md",
            "bytes": len(text.encode("utf-8")),
            "sha256": sha256_text(text),
            "status": "asr_cached",
            "transcript_source": "soundon_asr",
            "audio_url": row.get("audio_url"),
            "guid": row.get("guid"),
        }
        added.append(number)

    if added:
        ordered = [records[key] for key in sorted(records)]
        manifest["records"] = ordered
        manifest["stored_count"] = len(ordered)
        manifest["episode_count"] = max(int(manifest.get("episode_count") or 0), len(ordered))
        manifest["selected_count"] = max(int(manifest.get("selected_count") or 0), len(ordered))
        manifest["fetched_at"] = datetime.now(timezone.utc).isoformat()
        manifest.setdefault("errors", [])
        write_json(manifest_path, manifest)
        write_jsonl(data_dir / "transcripts_index.jsonl", ordered)

    source_path = data_dir / "source" / "episodes.json"
    source_added: list[int] = []
    if source_path.exists():
        source_episodes = read_json(source_path)
    else:
        source_episodes = []
    source_by_number = {int(item["number"]): item for item in source_episodes if item.get("number") is not None}
    for row in rows:
        number = int(row["number"])
        if number in source_by_number or not (data_dir / "transcripts" / f"EP{number:03d}.md").exists():
            continue
        source_by_number[number] = source_episode_record(row)
        source_added.append(number)
    if source_added:
        write_json(source_path, [source_by_number[key] for key in sorted(source_by_number)])

    return sorted(set(added + source_added))


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Gooaye SoundOn RSS metadata and ASR candidates.")
    parser.add_argument("--feed-url", default=DEFAULT_FEED_URL)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    source_dir = data_dir / "source"
    manifest_path = data_dir / "audio_manifest.jsonl"
    source_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching SoundOn RSS from {args.feed_url}", flush=True)
    feed_xml = fetch_bytes(args.feed_url)
    snapshot_path = source_dir / f"soundon_feed_snapshot_{PODCAST_ID}.xml"
    snapshot_path.write_bytes(feed_xml)

    existing = load_jsonl_by_episode(manifest_path)
    episodes = mark_asr_status(parse_feed(feed_xml), data_dir, existing)
    reconciled = reconcile_existing_transcripts(data_dir, episodes)
    pending = [row for row in episodes if row.get("asr_status") == "pending"]
    latest = max((int(row["number"]) for row in episodes), default=None)

    write_jsonl(source_dir / "soundon_episodes.jsonl", episodes)
    write_jsonl(manifest_path, episodes)
    write_json(
        source_dir / "soundon_fetch_summary.json",
        {
            "source": args.feed_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "episode_count": len(episodes),
            "max_episode": latest,
            "pending_asr": [int(row["number"]) for row in pending],
            "reconciled_existing_transcripts": reconciled,
            "snapshot_path": str(snapshot_path.relative_to(data_dir)),
            "audio_manifest": str(manifest_path.relative_to(data_dir)),
        },
    )

    if pending:
        preview = ", ".join(f"EP{int(row['number']):03d}" for row in sorted(pending, key=lambda item: int(item["number"]), reverse=True)[:5])
        print(f"SoundOn metadata refreshed. Pending ASR: {preview}", flush=True)
    else:
        print("SoundOn metadata refreshed. No pending ASR episodes.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
