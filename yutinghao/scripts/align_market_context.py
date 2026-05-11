#!/usr/bin/env python3
"""Build episode-date market context for 財經皓角.

Episodes are usually published around Taiwan morning before the local cash
session. The baseline therefore uses the nearest close on or before the
previous calendar day for Taiwan, US, FX, rates, commodities, and crypto
proxies. This is a broad-regime lens; ticker-specific decisions still need
current data and, ideally, dynamic mentioned-asset context.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
USER_AGENT = "alpha-persona-lab-yutinghao-market-aligner/1.0"

DEFAULT_SYMBOLS = [
    "^TWII",  # TAIEX
    "2330.TW",  # TSMC Taiwan
    "SPY",
    "QQQ",
    "SOXX",
    "DIA",
    "IWM",
    "NVDA",
    "TSM",
    "^VIX",
    "^TNX",  # US 10Y yield proxy
    "^IRX",  # US short-rate proxy
    "DX-Y.NYB",  # DXY
    "TWD=X",  # USD/TWD
    "JPY=X",  # USD/JPY
    "CL=F",  # WTI
    "BZ=F",  # Brent
    "GC=F",  # gold
    "HG=F",  # copper
    "BTC-USD",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def symbol_slug(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", symbol.replace("^", "INDEX_"))


def strip_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    front_text = text[3:end].strip()
    meta: dict[str, str] = {}
    for line in front_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    return meta, text[end + 4 :].lstrip()


def extract_title(text: str, fallback: str) -> str:
    _, body = strip_frontmatter(text)
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("# "):
            continue
        title = line[2:].strip()
        if title and "逐字稿" not in title and "筆記" not in title:
            return title
    return fallback


def episode_inventory(data_dir: Path) -> list[dict[str, Any]]:
    paths_by_date: dict[str, dict[str, Path]] = {}
    for kind, folder in [("transcript", "transcripts"), ("note", "notes")]:
        for path in sorted((data_dir / folder).glob("*.md")):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem):
                paths_by_date.setdefault(path.stem, {})[kind] = path

    rows: list[dict[str, Any]] = []
    for day, paths in sorted(paths_by_date.items()):
        primary = paths.get("transcript") or paths.get("note")
        if not primary:
            continue
        raw = primary.read_text(encoding="utf-8", errors="ignore")
        meta, _ = strip_frontmatter(raw)
        title = extract_title(raw, fallback=day)
        rows.append(
            {
                "episode_id": f"yutinghao-{day}",
                "episode_date": day,
                "title": title,
                "transcript_path": str(paths["transcript"].relative_to(ROOT)) if "transcript" in paths else None,
                "note_path": str(paths["note"].relative_to(ROOT)) if "note" in paths else None,
                "source_url": meta.get("url"),
            }
        )
    return rows


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


def max_drawdown_60d(series: list[dict[str, Any]], idx: int) -> float | None:
    start = max(0, idx - 59)
    window = [item["close"] for item in series[start : idx + 1]]
    if not window:
        return None
    peak = max(window)
    current = series[idx]["close"]
    if peak == 0:
        return None
    return round((current / peak - 1.0) * 100.0, 2)


def snapshot_for_day(series: list[dict[str, Any]], target: date) -> dict[str, Any] | None:
    days = [parse_day(item["date"]) for item in series]
    idx = bisect.bisect_right(days, target) - 1
    if idx < 0:
        return None
    current = series[idx]
    return {
        "market_date": current["date"],
        "close": round(current["close"], 4),
        "ret_1d_pct": pct_change(series, idx, 1),
        "ret_5d_pct": pct_change(series, idx, 5),
        "ret_20d_pct": pct_change(series, idx, 20),
        "ret_60d_pct": pct_change(series, idx, 60),
        "drawdown_60d_pct": max_drawdown_60d(series, idx),
    }


def load_or_fetch(symbol: str, start: date, end: date, prices_dir: Path, force: bool) -> list[dict[str, Any]]:
    path = prices_dir / f"{symbol_slug(symbol)}.json"
    if path.exists() and not force:
        return read_json(path)
    series = yahoo_chart(symbol, start, end)
    write_json(path, series)
    return series


def main() -> int:
    parser = argparse.ArgumentParser(description="Align 財經皓角 episodes to broad market context.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--force", action="store_true", help="Redownload price histories.")
    args = parser.parse_args()

    episodes = episode_inventory(args.data_dir)
    if not episodes:
        raise FileNotFoundError(f"no dated transcript/note files found under {args.data_dir}")

    episode_days = [parse_day(item["episode_date"]) for item in episodes]
    start = min(episode_days) - timedelta(days=100)
    end = max(episode_days) + timedelta(days=5)
    out_dir = args.data_dir / "market_context"
    prices_dir = out_dir / "prices"
    symbols = [item.strip() for item in args.symbols.split(",") if item.strip()]

    price_series: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    for symbol in symbols:
        try:
            print(f"Fetching {symbol} {start}..{end}", flush=True)
            price_series[symbol] = load_or_fetch(symbol, start, end, prices_dir, args.force)
        except Exception as exc:  # noqa: BLE001 - keep partial context useful.
            errors.append({"symbol": symbol, "error": str(exc)})

    records: list[dict[str, Any]] = []
    for episode in episodes:
        episode_day = parse_day(episode["episode_date"])
        context_day = episode_day - timedelta(days=1)
        markets: dict[str, Any] = {}
        for symbol, series in price_series.items():
            snap = snapshot_for_day(series, context_day)
            if snap:
                markets[symbol] = snap
        records.append(
            {
                **episode,
                "context_target_date": context_day.isoformat(),
                "session_alignment": (
                    "Taiwan morning show baseline: use nearest close on or before the previous calendar day "
                    "for broad market context."
                ),
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
            "episode_id",
            "episode_date",
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
                        "episode_id": record["episode_id"],
                        "episode_date": record["episode_date"],
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
            "episode_count": len(records),
            "symbols": symbols,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "alignment": "nearest prior close on episode_date - 1 day",
            "outputs": {
                "jsonl": str(jsonl_path.relative_to(ROOT)),
                "csv": str(csv_path.relative_to(ROOT)),
                "prices_dir": str(prices_dir.relative_to(ROOT)),
            },
            "errors": errors,
        },
    )
    print(f"Wrote market context for {len(records)} episodes to {out_dir}", flush=True)
    if errors:
        print(f"Completed with {len(errors)} symbol errors; see market_context_manifest.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
