#!/usr/bin/env python3
"""Build source-date market snapshots for the zhezhe skill.

The alignment rule follows Taiwan cash-market timing:
- sources published at or after 13:35 Asia/Taipei use the same-day close;
- sources published before 13:35 use the prior calendar day;
- weekends and holidays resolve to the nearest prior available close.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TAIPEI = ZoneInfo("Asia/Taipei")
SESSION_CLOSE_CUTOFF = time(13, 35)
USER_AGENT = "alpha-persona-lab-zhezhe-market-aligner/1.0"

DEFAULT_SYMBOLS = [
    "^TWII",
    "^TWOII",
    "2330.TW",
    "2454.TW",
    "SPY",
    "QQQ",
    "SOXX",
    "NVDA",
    "TSM",
    "^VIX",
    "^TNX",
    "DX-Y.NYB",
    "TWD=X",
    "JPY=X",
    "CL=F",
    "GC=F",
    "BTC-USD",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL") from exc
            if isinstance(item, dict):
                rows.append(item)
    return rows


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def symbol_slug(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", symbol.replace("^", "INDEX_"))


def display_path(path: Path, base: Path = ROOT) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def strip_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[3:end].strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("\"'")
    return meta, text[end + 4 :].lstrip()


def first_heading(text: str) -> str | None:
    _, body = strip_frontmatter(text)
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title
    return None


def pick_first(mapping: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def stringify(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def parse_published_at(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        return dt.astimezone(TAIPEI)

    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.combine(parse_day(text), time.min, tzinfo=TAIPEI)

    normalized = text.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=TAIPEI)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TAIPEI)
    return dt.astimezone(TAIPEI)


def source_id_from_metadata(kind: str, meta: dict[str, Any], fallback: str) -> str:
    value = pick_first(meta, ["source_id", "id", "episode_id", "article_id", "video_id", "slug"])
    if value not in (None, ""):
        return str(value)
    number = pick_first(meta, ["number", "episode", "episode_number"])
    if number not in (None, ""):
        number_text = str(number).strip()
        if number_text.isdigit():
            return f"EP{int(number_text):03d}"
        return number_text
    return f"{kind}-{fallback}"


def merge_record(records: dict[str, dict[str, Any]], record: dict[str, Any]) -> None:
    key = str(record["source_id"])
    existing = records.setdefault(key, {"source_id": key})
    for field in ("source_type", "title", "published_at", "source_url"):
        if not existing.get(field) and record.get(field):
            existing[field] = record[field]
    existing.setdefault("metadata", {}).update(record.get("metadata", {}))
    existing.setdefault("paths", [])
    for path_value in record.get("paths", []):
        if path_value and path_value not in existing["paths"]:
            existing["paths"].append(path_value)


def metadata_text(meta: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in meta.values():
        if isinstance(value, (str, int, float)):
            parts.append(str(value))
        elif isinstance(value, list):
            parts.extend(str(item) for item in value if isinstance(item, (str, int, float)))
    return "\n".join(parts)


def source_inventory(data_dir: Path) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    published_keys = [
        "published_at",
        "publish_time",
        "published_time",
        "date",
        "episode_date",
        "published_date",
        "created_at",
        "pub_date_utc",
        "local_date",
        "date_published",
        "date_modified",
        "soundon_created_at",
        "pub_date",
    ]
    source_url_keys = ["url", "source_url", "link", "player_url"]
    source_files = [
        ("episode", data_dir / "source" / "zhezhe_episodes.jsonl"),
        ("article", data_dir / "source" / "zhezhe_articles.jsonl"),
    ]
    for kind, path in source_files:
        for item in iter_jsonl(path):
            source_id = source_id_from_metadata(kind, item, fallback=str(len(records) + 1))
            published_at = parse_published_at(pick_first(item, published_keys))
            merge_record(
                records,
                {
                    "source_id": source_id,
                    "source_type": kind,
                    "title": stringify(pick_first(item, ["title", "display_title", "name"])),
                    "published_at": published_at.isoformat() if published_at else None,
                    "source_url": stringify(pick_first(item, source_url_keys)),
                    "metadata": item,
                    "paths": [],
                },
            )

    markdown_sources = [
        ("episode", data_dir / "transcripts"),
        ("article", data_dir / "articles"),
    ]
    for kind, folder in markdown_sources:
        for path in sorted(folder.glob("*.md")):
            raw = path.read_text(encoding="utf-8", errors="ignore")
            frontmatter, _ = strip_frontmatter(raw)
            source_id = source_id_from_metadata(kind, frontmatter, fallback=path.stem)
            if kind == "article" and source_id not in records:
                continue
            published_at = parse_published_at(pick_first(frontmatter, published_keys) or path.stem)
            merge_record(
                records,
                {
                    "source_id": source_id,
                    "source_type": kind,
                    "title": stringify(pick_first(frontmatter, ["title", "display_title", "name"])) or first_heading(raw),
                    "published_at": published_at.isoformat() if published_at else None,
                    "source_url": stringify(pick_first(frontmatter, source_url_keys)),
                    "metadata": frontmatter,
                    "paths": [display_path(path)],
                },
            )

    inventory = list(records.values())
    inventory.sort(key=lambda item: (item.get("published_at") or "", item["source_id"]))
    return inventory


def context_target_date(published_at: str) -> tuple[date, str]:
    dt = parse_published_at(published_at)
    if dt is None:
        raise ValueError(f"cannot parse published_at={published_at!r}")
    target = dt.date() if dt.time() >= SESSION_CLOSE_CUTOFF else dt.date() - timedelta(days=1)
    alignment = "same_day_close_after_1335_taipei" if dt.time() >= SESSION_CLOSE_CUTOFF else "prior_day_close_before_1335_taipei"
    return target, alignment


def yahoo_chart(symbol: str, start: date, end: date) -> list[dict[str, Any]]:
    period1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period2 = int(datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(symbol, safe='')}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history&includeAdjustedClose=true"
    )
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload.get("chart", {}).get("result") or []
    if not result:
        error = payload.get("chart", {}).get("error")
        raise RuntimeError(f"no data for {symbol}: {error}")
    item = result[0]
    timestamps = item.get("timestamp") or []
    quote_data = (item.get("indicators", {}).get("quote") or [{}])[0]
    adj_data = (item.get("indicators", {}).get("adjclose") or [{}])[0]
    closes = adj_data.get("adjclose") or quote_data.get("close") or []

    series: list[dict[str, Any]] = []
    for ts, close in zip(timestamps, closes):
        if close is None or not math.isfinite(float(close)):
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        series.append({"date": day.isoformat(), "close": float(close)})
    return series


def pct_change(series: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    past_idx = idx - lookback
    if past_idx < 0:
        return None
    current = series[idx]["close"]
    past = series[past_idx]["close"]
    if past == 0:
        return None
    return round((current / past - 1.0) * 100.0, 2)


def max_drawdown(series: list[dict[str, Any]], idx: int, lookback: int = 60) -> float | None:
    start = max(0, idx - lookback + 1)
    window = [item["close"] for item in series[start : idx + 1]]
    if not window:
        return None
    peak = max(window)
    if peak == 0:
        return None
    return round((series[idx]["close"] / peak - 1.0) * 100.0, 2)


def snapshot_for_day(series: list[dict[str, Any]], target: date) -> dict[str, Any] | None:
    days = [parse_day(item["date"]) for item in series]
    idx = bisect.bisect_right(days, target) - 1
    if idx < 0:
        return None
    current = series[idx]
    return {
        "market_date": current["date"],
        "close": round(float(current["close"]), 4),
        "ret_1d_pct": pct_change(series, idx, 1),
        "ret_5d_pct": pct_change(series, idx, 5),
        "ret_20d_pct": pct_change(series, idx, 20),
        "ret_60d_pct": pct_change(series, idx, 60),
        "drawdown_60d_pct": max_drawdown(series, idx, 60),
    }


def load_or_fetch(symbol: str, start: date, end: date, prices_dir: Path, force: bool) -> list[dict[str, Any]]:
    path = prices_dir / f"{symbol_slug(symbol)}.json"
    if path.exists() and not force:
        return read_json(path)
    series = yahoo_chart(symbol, start, end)
    write_json(path, series)
    return series


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--force", action="store_true", help="Redownload price histories.")
    args = parser.parse_args()

    inventory = source_inventory(args.data_dir)
    dated = [item for item in inventory if item.get("published_at")]
    out_dir = args.data_dir / "market_context"
    prices_dir = out_dir / "prices"
    symbols = [item.strip() for item in args.symbols.split(",") if item.strip()]
    errors: list[dict[str, str]] = []
    price_series: dict[str, list[dict[str, Any]]] = {}

    if dated:
        targets = [context_target_date(item["published_at"])[0] for item in dated]
        start = min(targets) - timedelta(days=100)
        end = max(targets) + timedelta(days=5)
        for symbol in symbols:
            try:
                print(f"Fetching {symbol} {start}..{end}", flush=True)
                price_series[symbol] = load_or_fetch(symbol, start, end, prices_dir, args.force)
            except Exception as exc:  # noqa: BLE001 - keep partial market context useful.
                errors.append({"symbol": symbol, "error": str(exc)})
    else:
        start = end = None

    records: list[dict[str, Any]] = []
    for source in dated:
        target_day, alignment = context_target_date(source["published_at"])
        markets = {
            symbol: snap
            for symbol, series in price_series.items()
            if (snap := snapshot_for_day(series, target_day))
        }
        records.append(
            {
                **source,
                "published_date": parse_published_at(source["published_at"]).date().isoformat(),
                "context_target_date": target_day.isoformat(),
                "session_alignment": alignment,
                "markets": markets,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "episode_market_context.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    csv_path = out_dir / "episode_market_context.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "source_id",
            "source_type",
            "published_at",
            "context_target_date",
            "symbol",
            "market_date",
            "close",
            "ret_1d_pct",
            "ret_5d_pct",
            "ret_20d_pct",
            "ret_60d_pct",
            "drawdown_60d_pct",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for record in records:
            for symbol, snap in record["markets"].items():
                writer.writerow(
                    {
                        "source_id": record["source_id"],
                        "source_type": record.get("source_type"),
                        "published_at": record.get("published_at"),
                        "context_target_date": record["context_target_date"],
                        "symbol": symbol,
                        **snap,
                    }
                )

    write_json(
        out_dir / "market_context_manifest.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "source": "Yahoo Finance chart API",
            "source_inventory_count": len(inventory),
            "dated_source_count": len(records),
            "symbols": symbols,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "alignment": "Asia/Taipei >= 13:35 uses same-day close; earlier uses prior day; non-trading days use nearest prior close.",
            "outputs": {
                "jsonl": display_path(jsonl_path),
                "csv": display_path(csv_path),
                "prices_dir": display_path(prices_dir),
            },
            "errors": errors,
        },
    )
    print(f"Wrote market context for {len(records)} sources to {out_dir}", flush=True)
    if errors:
        print(f"Completed with {len(errors)} symbol errors; see market_context_manifest.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
