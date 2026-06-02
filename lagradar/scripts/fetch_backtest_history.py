#!/usr/bin/env python3
"""Fetch long daily Yahoo history for Lagradar backtests.

The script intentionally writes one JSON file per symbol. That keeps refreshes
incremental and lets the backtest run without repeatedly hitting the network.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


USER_AGENT = "alpha-persona-lab-lagradar-backtest/0.1"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_symbol(symbol: str) -> str:
    return (
        symbol.replace("^", "INDEX_")
        .replace("=", "_")
        .replace("/", "_")
        .replace(".", "_")
        .replace("-", "_")
    )


def url_json(url: str, *, timeout: int = 30) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def rows_from_yahoo(symbol: str, years: int) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range={years}y&interval=1d&events=div%2Csplits"
    data = url_json(url)
    chart = data.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(chart["error"])
    result = (chart.get("result") or [None])[0]
    if not result:
        raise RuntimeError("empty Yahoo chart result")

    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adj = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or []
    rows: list[dict[str, Any]] = []
    for idx, ts in enumerate(timestamps):
        close = (quote.get("close") or [None] * len(timestamps))[idx]
        if close is None:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                "open": (quote.get("open") or [None] * len(timestamps))[idx],
                "high": (quote.get("high") or [None] * len(timestamps))[idx],
                "low": (quote.get("low") or [None] * len(timestamps))[idx],
                "close": close,
                "adjclose": adj[idx] if idx < len(adj) and adj[idx] is not None else close,
                "volume": (quote.get("volume") or [None] * len(timestamps))[idx],
            }
        )
    if not rows:
        raise RuntimeError("no valid close rows")
    return rows


def load_symbols(seed_path: Path, universe_path: Path) -> dict[str, dict[str, Any]]:
    symbols: dict[str, dict[str, Any]] = {}

    seed = read_json(seed_path)
    for theme in seed.get("themes", []):
        for node in theme.get("nodes", []):
            symbol = node["symbol"]
            item = symbols.setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "name": node.get("name", symbol),
                    "market": node.get("market"),
                    "region": node.get("region"),
                    "roles": [],
                    "themes": [],
                    "source": "theme_seed",
                },
            )
            item["themes"].append(theme["theme_id"])
            item["roles"].append(node.get("role"))

    universe = read_json(universe_path)
    for section in ("markets", "sectors", "macro"):
        for node in universe.get(section, []):
            symbol = node["symbol"]
            item = symbols.setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "name": node.get("name", symbol),
                    "market": node.get("market"),
                    "region": node.get("region"),
                    "roles": [],
                    "themes": [],
                    "source": section,
                },
            )
            item.setdefault("kinds", []).append(node.get("kind"))
            if node.get("sector"):
                item.setdefault("sectors", []).append(node["sector"])
    return symbols


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch 20-year Yahoo daily history for Lagradar backtests")
    parser.add_argument("--seed", default="lagradar/data/cross_market_theme_seed.json")
    parser.add_argument("--universe", default="lagradar/data/backtest_market_universe.json")
    parser.add_argument("--output-dir", default="lagradar/data/history/yahoo_1d")
    parser.add_argument("--years", type=int, default=20)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--max-symbols", type=int)
    parser.add_argument("--sleep", type=float, default=0.08)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    symbols = load_symbols(Path(args.seed), Path(args.universe))
    rows = list(symbols.values())
    rows.sort(key=lambda item: item["symbol"])
    if args.max_symbols:
        rows = rows[: args.max_symbols]

    manifest_rows: list[dict[str, Any]] = []
    for idx, meta in enumerate(rows, start=1):
        symbol = meta["symbol"]
        path = output_dir / f"{safe_symbol(symbol)}.json"
        if path.exists() and not args.refresh:
            cached = read_json(path)
            count = len(cached.get("rows") or [])
            status = "cached" if count else "empty_cache"
            manifest_rows.append({**meta, "status": status, "row_count": count, "path": str(path)})
            print(f"[{idx}/{len(rows)}] {symbol} {status} rows={count}")
            continue
        try:
            history = rows_from_yahoo(symbol, args.years)
            write_json(
                path,
                {
                    **meta,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "years": args.years,
                    "row_count": len(history),
                    "first_date": history[0]["date"],
                    "last_date": history[-1]["date"],
                    "rows": history,
                },
            )
            manifest_rows.append(
                {
                    **meta,
                    "status": "ok",
                    "row_count": len(history),
                    "first_date": history[0]["date"],
                    "last_date": history[-1]["date"],
                    "path": str(path),
                }
            )
            print(f"[{idx}/{len(rows)}] {symbol} ok rows={len(history)} {history[0]['date']}..{history[-1]['date']}")
        except Exception as exc:
            manifest_rows.append({**meta, "status": "error", "error": str(exc), "path": str(path)})
            print(f"[{idx}/{len(rows)}] {symbol} error: {exc}")
        time.sleep(args.sleep)

    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "years": args.years,
        "symbol_count": len(rows),
        "ok_count": sum(1 for row in manifest_rows if row["status"] in {"ok", "cached"}),
        "error_count": sum(1 for row in manifest_rows if row["status"] == "error"),
        "rows": manifest_rows,
    }
    write_json(output_dir.parent / "history_manifest.json", manifest)
    print(
        f"Wrote history manifest: ok={manifest['ok_count']} errors={manifest['error_count']} "
        f"to {output_dir.parent / 'history_manifest.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
