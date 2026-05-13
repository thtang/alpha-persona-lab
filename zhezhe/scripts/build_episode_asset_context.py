#!/usr/bin/env python3
"""Build market context for assets mentioned in zhezhe sources."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from align_market_context import (
    DATA_DIR,
    ROOT,
    context_target_date,
    display_path,
    load_or_fetch,
    parse_day,
    source_inventory,
    snapshot_for_day,
    strip_frontmatter,
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
        aliases = {str(alias) for alias in item.get("aliases", [])}
        aliases.add(symbol)
        if item.get("name"):
            aliases.add(str(item["name"]))
        patterns[symbol] = [(alias, alias_pattern(alias)) for alias in sorted(aliases, key=len, reverse=True)]
    return by_symbol, patterns


def load_sector_baskets(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    baskets = read_json(path)
    for basket in baskets:
        aliases = {str(alias) for alias in basket.get("aliases", [])}
        aliases.add(str(basket["sector_name"]))
        basket["patterns"] = [(alias, alias_pattern(alias)) for alias in sorted(aliases, key=len, reverse=True)]
    return baskets


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    return rows


def load_baseline(data_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id")): item
        for item in iter_jsonl(data_dir / "market_context" / "episode_market_context.jsonl")
        if item.get("source_id")
    }


def read_source_text(source: dict[str, Any], data_dir: Path) -> str:
    parts: list[str] = []
    for field in ("title", "source_url", "published_at"):
        value = source.get(field)
        if value:
            parts.append(str(value))
    metadata = source.get("metadata")
    if isinstance(metadata, dict):
        parts.append(json.dumps(metadata, ensure_ascii=False, sort_keys=True))

    for path_value in source.get("paths", []):
        path = ROOT / path_value
        if not path.exists():
            path = data_dir / path_value
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        frontmatter, body = strip_frontmatter(raw)
        if frontmatter:
            parts.append(json.dumps(frontmatter, ensure_ascii=False, sort_keys=True))
        parts.append(body)
    return "\n".join(parts)


def scan_direct_mentions(text: str, patterns: dict[str, list[tuple[str, re.Pattern[str]]]]) -> dict[str, dict[str, Any]]:
    mentions: dict[str, dict[str, Any]] = {}
    for symbol, alias_patterns in patterns.items():
        aliases = [alias for alias, pattern in alias_patterns if pattern.search(text)]
        if aliases:
            mentions[symbol] = {
                "matched_aliases": sorted(set(aliases)),
                "sources": {"alias_scan"},
                "mention_kind": "direct",
            }
    return mentions


def scan_sector_proxy_mentions(
    *,
    text: str,
    baskets: list[dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    basket_matches: list[dict[str, Any]] = []
    proxy_mentions: dict[str, dict[str, Any]] = {}
    for basket in baskets:
        matched_aliases = [alias for alias, pattern in basket.get("patterns", []) if pattern.search(text)]
        if not matched_aliases:
            continue
        sector_name = str(basket["sector_name"])
        unique_aliases = sorted(set(matched_aliases))
        symbols = [str(symbol) for symbol in basket.get("symbols", []) if str(symbol) in by_symbol]
        basket_matches.append(
            {
                "sector_name": sector_name,
                "matched_aliases": unique_aliases,
                "proxy_symbols": symbols,
            }
        )
        for symbol in symbols:
            proxy_mentions[symbol] = {
                "matched_aliases": unique_aliases,
                "sources": {f"sector_basket:{sector_name}"},
                "mention_kind": "sector_proxy",
                "sector_name": sector_name,
            }
    return basket_matches, proxy_mentions


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
    if mention.get("sector_name"):
        item["sector_name"] = mention["sector_name"]
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


def write_source_record(out_dir: Path, source_id: str, record: dict[str, Any]) -> None:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source_id).strip("_") or "source"
    write_json(out_dir / f"{safe_name}.json", record)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--asset-map", type=Path, default=ROOT / "references" / "asset-symbol-map.json")
    parser.add_argument("--sector-baskets", type=Path, default=ROOT / "references" / "asset-sector-baskets.json")
    parser.add_argument("--force", action="store_true", help="Redownload price histories.")
    args = parser.parse_args()

    sources = [item for item in source_inventory(args.data_dir) if item.get("published_at")]
    by_symbol, patterns = load_alias_patterns(args.asset_map)
    baskets = load_sector_baskets(args.sector_baskets)
    baseline = load_baseline(args.data_dir)

    direct_mentions_by_source: dict[str, dict[str, dict[str, Any]]] = {}
    proxy_mentions_by_source: dict[str, dict[str, dict[str, Any]]] = {}
    sector_matches_by_source: dict[str, list[dict[str, Any]]] = {}
    needed_pricing_symbols: set[str] = set()
    all_context_days: list[date] = []

    for source in sources:
        source_id = str(source["source_id"])
        text = read_source_text(source, args.data_dir)
        direct_mentions = scan_direct_mentions(text, patterns)
        sector_matches, proxy_mentions = scan_sector_proxy_mentions(text=text, baskets=baskets, by_symbol=by_symbol)
        direct_mentions_by_source[source_id] = direct_mentions
        proxy_mentions_by_source[source_id] = proxy_mentions
        sector_matches_by_source[source_id] = sector_matches

        context_day, _ = context_target_date(source["published_at"])
        all_context_days.append(context_day)
        for symbol in set(direct_mentions) | set(proxy_mentions):
            price_symbol = pricing_symbol(by_symbol[symbol], symbol)
            if price_symbol:
                needed_pricing_symbols.add(price_symbol)

    prices_dir = args.data_dir / "market_context" / "prices"
    price_series: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    if all_context_days and needed_pricing_symbols:
        start = min(all_context_days) - timedelta(days=100)
        end = max(all_context_days) + timedelta(days=5)
        for symbol in sorted(needed_pricing_symbols):
            try:
                print(f"Fetching {symbol} {start}..{end}", flush=True)
                price_series[symbol] = load_or_fetch(symbol, start, end, prices_dir, args.force)
            except Exception as exc:  # noqa: BLE001 - keep partial context usable.
                errors.append({"symbol": symbol, "error": str(exc)})
    else:
        start = end = None

    out_dir = args.data_dir / "market_context" / "episode_asset_context"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale_path in out_dir.glob("*.json"):
        stale_path.unlink()
    aggregate_path = args.data_dir / "market_context" / "episode_asset_context.jsonl"
    records: list[dict[str, Any]] = []
    symbol_source_counts: dict[str, int] = defaultdict(int)

    for source in sources:
        source_id = str(source["source_id"])
        context_day, alignment = context_target_date(source["published_at"])
        direct_assets = []
        sector_proxy_assets = []

        for symbol, mention in sorted(direct_mentions_by_source.get(source_id, {}).items()):
            meta = by_symbol[symbol]
            price_symbol = pricing_symbol(meta, symbol)
            direct_assets.append(
                build_asset_item(
                    symbol=symbol,
                    meta=meta,
                    mention=mention,
                    series=price_series.get(price_symbol or ""),
                    context_day=context_day,
                )
            )
            symbol_source_counts[symbol] += 1

        direct_symbols = set(direct_mentions_by_source.get(source_id, {}))
        for symbol, mention in sorted(proxy_mentions_by_source.get(source_id, {}).items()):
            if symbol in direct_symbols:
                continue
            meta = by_symbol[symbol]
            price_symbol = pricing_symbol(meta, symbol)
            sector_proxy_assets.append(
                build_asset_item(
                    symbol=symbol,
                    meta=meta,
                    mention=mention,
                    series=price_series.get(price_symbol or ""),
                    context_day=context_day,
                )
            )

        record = {
            **source,
            "context_target_date": context_day.isoformat(),
            "session_alignment": alignment,
            "baseline_market_context": baseline.get(source_id, {}).get("markets", {}),
            "direct_mentioned_assets": direct_assets,
            "sector_proxy_assets": sector_proxy_assets,
            "sector_basket_matches": sector_matches_by_source.get(source_id, []),
        }
        write_source_record(out_dir, source_id, record)
        records.append(record)

    aggregate_path.parent.mkdir(parents=True, exist_ok=True)
    with aggregate_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    write_json(
        args.data_dir / "market_context" / "episode_asset_context_manifest.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "source": "Transcript/article/metadata alias scan + Yahoo Finance chart API",
            "asset_map": display_path(args.asset_map),
            "sector_baskets": display_path(args.sector_baskets),
            "source_count": len(records),
            "direct_symbol_count": len(symbol_source_counts),
            "pricing_symbol_count": len(needed_pricing_symbols),
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "outputs": {
                "jsonl": display_path(aggregate_path),
                "per_source_dir": display_path(out_dir),
                "prices_dir": display_path(prices_dir),
            },
            "notes": "Direct alias mentions are kept separate from sector basket proxy assets. Direct mentions take precedence if the same symbol is also in a matched sector basket.",
            "top_direct_mentions": sorted(
                [{"symbol": symbol, "sources": count} for symbol, count in symbol_source_counts.items()],
                key=lambda item: item["sources"],
                reverse=True,
            )[:30],
            "errors": errors,
        },
    )
    print(f"Wrote mentioned-asset context for {len(records)} sources to {out_dir}", flush=True)
    if errors:
        print(f"Completed with {len(errors)} symbol errors; see episode_asset_context_manifest.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
