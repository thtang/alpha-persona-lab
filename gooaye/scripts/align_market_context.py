#!/usr/bin/env python3
"""Build per-episode market snapshots from Yahoo Finance chart data."""

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


DEFAULT_SYMBOLS = [
    "^TWII",
    "^GSPC",
    "^IXIC",
    "^VIX",
    "^TNX",
    "TWD=X",
    "2330.TW",
    "QQQ",
    "SOXX",
    "TSM",
    "NVDA",
    "TSLA",
    "BTC-USD",
]
USER_AGENT = "gooaye-skill-market-aligner/1.0"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def symbol_slug(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", symbol.replace("^", "INDEX_"))


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


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
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Align Gooaye episode dates to daily market context.")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--force", action="store_true", help="redownload price histories")
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    episodes_path = data_dir / "source" / "episodes.json"
    if not episodes_path.exists():
        raise FileNotFoundError(f"missing {episodes_path}; run fetch_transcripts.py first")

    episodes = [ep for ep in read_json(episodes_path) if ep.get("date")]
    episode_days = [parse_day(ep["date"]) for ep in episodes]
    start = min(episode_days) - timedelta(days=100)
    end = max(episode_days) + timedelta(days=5)

    out_dir = data_dir / "market_context"
    prices_dir = out_dir / "prices"
    symbols = [item.strip() for item in args.symbols.split(",") if item.strip()]
    price_series: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []

    for symbol in symbols:
        price_path = prices_dir / f"{symbol_slug(symbol)}.json"
        if price_path.exists() and not args.force:
            series = read_json(price_path)
        else:
            try:
                print(f"Fetching {symbol} {start}..{end}", flush=True)
                series = yahoo_chart(symbol, start, end)
                write_json(price_path, series)
            except Exception as exc:  # noqa: BLE001 - keep partial market context useful.
                errors.append({"symbol": symbol, "error": str(exc)})
                continue
        price_series[symbol] = series

    records: list[dict[str, Any]] = []
    for ep in episodes:
        day = parse_day(ep["date"])
        markets: dict[str, Any] = {}
        for symbol, series in price_series.items():
            snap = snapshot_for_day(series, day)
            if snap:
                markets[symbol] = snap
        records.append(
            {
                "episode": ep["number"],
                "episode_date": ep["date"],
                "title": ep.get("display_title") or ep.get("title"),
                "markets": markets,
            }
        )

    jsonl_path = out_dir / "episode_market_context.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    csv_path = out_dir / "episode_market_context.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "episode",
            "episode_date",
            "symbol",
            "market_date",
            "close",
            "ret_1d_pct",
            "ret_5d_pct",
            "ret_20d_pct",
            "ret_60d_pct",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for record in records:
            for symbol, snap in record["markets"].items():
                writer.writerow({"episode": record["episode"], "episode_date": record["episode_date"], "symbol": symbol, **snap})

    write_json(
        out_dir / "market_context_manifest.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "symbols": symbols,
            "episode_count": len(records),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "source": "Yahoo Finance chart API",
            "notes": "For non-trading podcast dates, snapshots use the nearest prior trading close.",
            "errors": errors,
        },
    )
    print(f"Wrote market context for {len(records)} episodes to {out_dir}", flush=True)
    if errors:
        print(f"Completed with {len(errors)} symbol errors; see market_context_manifest.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
