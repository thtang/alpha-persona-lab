#!/usr/bin/env python3
"""Build market context for assets mentioned in 財經皓角 notes/transcripts."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, timedelta, timezone, datetime
from pathlib import Path
from typing import Any

from align_market_context import (
    DATA_DIR,
    ROOT,
    episode_inventory,
    load_or_fetch,
    parse_day,
    snapshot_for_day,
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_ascii_alias(alias: str) -> bool:
    return all(ord(ch) < 128 for ch in alias)


def alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if is_ascii_alias(alias):
        return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def load_alias_patterns(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, list[tuple[str, re.Pattern[str]]]]]:
    assets = read_json(path)
    by_symbol: dict[str, dict[str, Any]] = {}
    patterns: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
    for item in assets:
        symbol = str(item["symbol"])
        by_symbol[symbol] = item
        patterns[symbol] = [(str(alias), alias_pattern(str(alias))) for alias in item.get("aliases", [])]
    return by_symbol, patterns


def load_sector_baskets(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    baskets = read_json(path)
    for basket in baskets:
        basket["patterns"] = [(str(alias), alias_pattern(str(alias))) for alias in basket.get("aliases", [])]
    return baskets


def read_text(path_value: str | None) -> str:
    if not path_value:
        return ""
    path = ROOT / path_value
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def scan_direct_mentions(text: str, patterns: dict[str, list[tuple[str, re.Pattern[str]]]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for symbol, alias_patterns in patterns.items():
        aliases = [alias for alias, pattern in alias_patterns if pattern.search(text)]
        if aliases:
            found[symbol] = {
                "matched_aliases": sorted(set(aliases)),
                "sources": {"transcript_or_note"},
                "mention_kind": "direct",
            }
    return found


def add_sector_proxy_mentions(
    *,
    text: str,
    mentions: dict[str, dict[str, Any]],
    baskets: list[dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    matched_baskets: list[dict[str, Any]] = []
    for basket in baskets:
        matched_aliases = [alias for alias, pattern in basket.get("patterns", []) if pattern.search(text)]
        if not matched_aliases:
            continue
        sector_name = str(basket["sector_name"])
        matched_baskets.append({"sector_name": sector_name, "matched_aliases": sorted(set(matched_aliases))})
        for symbol in basket.get("symbols", []):
            if symbol not in by_symbol:
                continue
            mention = mentions.setdefault(
                symbol,
                {"matched_aliases": [], "sources": set(), "mention_kind": "sector_proxy"},
            )
            mention["matched_aliases"] = sorted(set(mention.get("matched_aliases", [])) | set(matched_aliases))
            mention["sources"].add(f"sector_basket:{sector_name}")
            if mention.get("mention_kind") != "direct":
                mention["mention_kind"] = "sector_proxy"
    return matched_baskets


def pricing_symbol(meta: dict[str, Any], symbol: str) -> str | None:
    if "pricing_symbol" in meta:
        value = meta.get("pricing_symbol")
        return str(value) if value else None
    return symbol


def build_asset_item(
    *,
    symbol: str,
    meta: dict[str, Any],
    mention: dict[str, Any],
    series: list[dict[str, Any]] | None,
    context_day: date,
) -> dict[str, Any]:
    price_symbol = pricing_symbol(meta, symbol)
    item: dict[str, Any] = {
        "asset_name": meta.get("name") or symbol,
        "symbol": symbol,
        "pricing_symbol": price_symbol,
        "asset_type": meta.get("asset_type") or "unknown",
        "mention_kind": mention.get("mention_kind") or "direct",
        "matched_aliases": sorted(set(mention.get("matched_aliases", []))),
        "sources": sorted(mention.get("sources", [])),
        "market": None,
        "pricing_status": "ok",
    }
    if not price_symbol:
        item["pricing_status"] = "no_public_symbol"
        return item
    if not series:
        item["pricing_status"] = "missing_price_series"
        return item
    snap = snapshot_for_day(series, context_day)
    if not snap:
        item["pricing_status"] = "no_prior_price"
        return item
    item["market"] = snap
    return item


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_baseline(data_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("episode_id")): item
        for item in iter_jsonl(data_dir / "market_context" / "episode_market_context.jsonl")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--asset-map", type=Path, default=ROOT / "references" / "asset-symbol-map.json")
    parser.add_argument("--sector-baskets", type=Path, default=ROOT / "references" / "asset-sector-baskets.json")
    parser.add_argument("--force", action="store_true", help="Redownload price histories.")
    args = parser.parse_args()

    episodes = episode_inventory(args.data_dir)
    if not episodes:
        raise FileNotFoundError(f"no dated transcript/note files found under {args.data_dir}")

    by_symbol, patterns = load_alias_patterns(args.asset_map)
    baskets = load_sector_baskets(args.sector_baskets)
    baseline = load_baseline(args.data_dir)

    raw_mentions: dict[str, dict[str, dict[str, Any]]] = {}
    sector_matches: dict[str, list[dict[str, Any]]] = {}
    all_pricing_symbols: set[str] = set()
    for episode in episodes:
        text = "\n".join([read_text(episode.get("transcript_path")), read_text(episode.get("note_path"))])
        mentions = scan_direct_mentions(text, patterns)
        sector_matches[episode["episode_id"]] = add_sector_proxy_mentions(
            text=text,
            mentions=mentions,
            baskets=baskets,
            by_symbol=by_symbol,
        )
        raw_mentions[episode["episode_id"]] = mentions
        for symbol in mentions:
            price_symbol = pricing_symbol(by_symbol[symbol], symbol)
            if price_symbol:
                all_pricing_symbols.add(price_symbol)

    episode_days = [parse_day(item["episode_date"]) for item in episodes]
    start = min(episode_days) - timedelta(days=100)
    end = max(episode_days) + timedelta(days=5)
    prices_dir = args.data_dir / "market_context" / "prices"

    price_series: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    for symbol in sorted(all_pricing_symbols):
        try:
            print(f"Fetching {symbol} {start}..{end}", flush=True)
            price_series[symbol] = load_or_fetch(symbol, start, end, prices_dir, args.force)
        except Exception as exc:  # noqa: BLE001 - keep partial context useful.
            errors.append({"symbol": symbol, "error": str(exc)})

    out_dir = args.data_dir / "market_context" / "episode_asset_context"
    out_dir.mkdir(parents=True, exist_ok=True)
    aggregate_path = args.data_dir / "market_context" / "episode_asset_context.jsonl"
    records: list[dict[str, Any]] = []
    symbol_episode_counts: dict[str, int] = defaultdict(int)

    for episode in episodes:
        episode_id = episode["episode_id"]
        context_day = parse_day(episode["episode_date"]) - timedelta(days=1)
        assets = []
        for symbol, mention in sorted(raw_mentions[episode_id].items()):
            meta = by_symbol[symbol]
            price_symbol = pricing_symbol(meta, symbol)
            item = build_asset_item(
                symbol=symbol,
                meta=meta,
                mention=mention,
                series=price_series.get(price_symbol or ""),
                context_day=context_day,
            )
            assets.append(item)
            symbol_episode_counts[symbol] += 1
        record = {
            **episode,
            "context_target_date": context_day.isoformat(),
            "baseline_market_context": baseline.get(episode_id, {}).get("markets", {}),
            "mentioned_assets": assets,
            "sector_basket_matches": sector_matches.get(episode_id, []),
        }
        write_json(out_dir / f"{episode['episode_date']}.json", record)
        records.append(record)

    with aggregate_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source": "Transcript/note alias scan + Yahoo Finance chart API",
        "episode_count": len(records),
        "asset_map": str(args.asset_map.relative_to(ROOT)),
        "sector_baskets": str(args.sector_baskets.relative_to(ROOT)),
        "unique_asset_ids": len(symbol_episode_counts),
        "unique_pricing_symbols": len(all_pricing_symbols),
        "top_mentions": sorted(
            [{"symbol": symbol, "episodes": count} for symbol, count in symbol_episode_counts.items()],
            key=lambda item: item["episodes"],
            reverse=True,
        )[:30],
        "outputs": {
            "jsonl": str(aggregate_path.relative_to(ROOT)),
            "per_episode_dir": str(out_dir.relative_to(ROOT)),
            "prices_dir": str(prices_dir.relative_to(ROOT)),
        },
        "errors": errors,
    }
    write_json(args.data_dir / "market_context" / "episode_asset_context_manifest.json", manifest)
    print(f"Wrote mentioned-asset context for {len(records)} episodes to {out_dir}", flush=True)
    if errors:
        print(f"Completed with {len(errors)} symbol errors; see episode_asset_context_manifest.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
