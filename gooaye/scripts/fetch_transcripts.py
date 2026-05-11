#!/usr/bin/env python3
"""Fetch Gooaye transcript metadata and episode markdown files."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://whatmkreallysaid.com"
USER_AGENT = "gooaye-skill-transcript-fetcher/1.0"


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


def fetch_json(url: str) -> Any:
    return json.loads(fetch_bytes(url).decode("utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def transcript_name(ep: dict[str, Any]) -> str:
    number = int(ep["number"])
    return f"EP{number:03d}.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Gooaye transcripts into the skill data folder.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--limit", type=int, default=0, help="download only the first N episodes, for testing")
    parser.add_argument("--force", action="store_true", help="redownload existing transcript files")
    parser.add_argument("--sleep", type=float, default=0.03, help="seconds to sleep between episode requests")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    out_dir: Path = args.out_dir
    source_dir = out_dir / "source"
    transcript_dir = out_dir / "transcripts"
    source_dir.mkdir(parents=True, exist_ok=True)
    transcript_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching metadata from {base_url}", flush=True)
    episodes = fetch_json(f"{base_url}/episodes.json")
    manifest = fetch_json(f"{base_url}/pack_manifest.json")
    write_json(source_dir / "episodes.json", episodes)
    write_json(source_dir / "pack_manifest.json", manifest)

    selected = episodes[: args.limit] if args.limit else episodes
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, ep in enumerate(selected, 1):
        local_name = transcript_name(ep)
        local_path = transcript_dir / local_name
        filename = ep["filename"]
        url = f"{base_url}/episodes/{quote(filename, safe='')}"

        if local_path.exists() and not args.force:
            text = local_path.read_text(encoding="utf-8")
            status = "cached"
        else:
            try:
                text = fetch_bytes(url).decode("utf-8")
                local_path.write_text(text, encoding="utf-8")
                status = "fetched"
                if args.sleep:
                    time.sleep(args.sleep)
            except Exception as exc:  # noqa: BLE001 - keep batch going and report all failures.
                errors.append({"number": ep.get("number"), "filename": filename, "url": url, "error": str(exc)})
                print(f"[{idx:03d}/{len(selected):03d}] EP{ep.get('number')} failed: {exc}", file=sys.stderr, flush=True)
                continue

        records.append(
            {
                "number": ep["number"],
                "date": ep.get("date"),
                "title": ep.get("title"),
                "display_title": ep.get("display_title"),
                "summary": ep.get("summary"),
                "source_filename": filename,
                "source_url": url,
                "local_path": str(local_path.relative_to(out_dir)),
                "bytes": len(text.encode("utf-8")),
                "sha256": sha256_text(text),
                "status": status,
            }
        )
        if idx % 25 == 0 or idx == len(selected):
            print(f"[{idx:03d}/{len(selected):03d}] downloaded/cached {len(records)} transcripts", flush=True)

    inventory = {
        "source": base_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "episode_count": len(episodes),
        "selected_count": len(selected),
        "stored_count": len(records),
        "error_count": len(errors),
        "pack_manifest": manifest,
        "records": records,
        "errors": errors,
    }
    write_json(out_dir / "transcripts_manifest.json", inventory)

    index_path = out_dir / "transcripts_index.jsonl"
    with index_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Stored {len(records)} transcripts in {transcript_dir}", flush=True)
    if errors:
        print(f"Completed with {len(errors)} errors. See {out_dir / 'transcripts_manifest.json'}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
