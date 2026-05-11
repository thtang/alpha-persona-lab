#!/usr/bin/env python3
"""Build per-episode market context for explicitly mentioned assets."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from align_market_context import parse_day, snapshot_for_day, symbol_slug, yahoo_chart


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def display_path(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def is_ascii_alias(alias: str) -> bool:
    return all(ord(ch) < 128 for ch in alias)


def alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if is_ascii_alias(alias):
        return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def load_aliases(path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[tuple[str, re.Pattern[str]]]]]:
    assets = read_json(path)
    by_symbol: dict[str, dict[str, Any]] = {}
    patterns: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
    for item in assets:
        symbol = str(item["symbol"])
        by_symbol[symbol] = item
        patterns[symbol] = [(alias, alias_pattern(str(alias))) for alias in item.get("aliases", [])]
    return assets, by_symbol, patterns


def load_sector_baskets(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    baskets = read_json(path)
    for basket in baskets:
        basket["patterns"] = [(alias, alias_pattern(str(alias))) for alias in basket.get("aliases", [])]
    return baskets


def load_baseline_context(data_dir: Path) -> dict[int, dict[str, Any]]:
    records: dict[int, dict[str, Any]] = {}
    for item in iter_jsonl(data_dir / "market_context" / "episode_market_context.jsonl"):
        records[int(item["episode"])] = item
    return records


def load_episode_notes(data_dir: Path, episode: int) -> dict[str, Any]:
    path = data_dir / "distilled" / "episode_notes" / f"EP{episode:03d}.json"
    return read_json(path) if path.exists() else {}


def note_symbol_mentions(note: dict[str, Any], by_symbol: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    mentions: dict[str, set[str]] = defaultdict(set)
    for obs in note.get("trade_observations", []) if isinstance(note, dict) else []:
        if not isinstance(obs, dict):
            continue
        symbol = obs.get("asset_symbol")
        if isinstance(symbol, str) and symbol in by_symbol:
            mentions[symbol].add("trade_observations.asset_symbol")
    return mentions


def unresolved_note_mentions(note: dict[str, Any], by_name: dict[str, str], resolved_sector_terms: set[str]) -> list[str]:
    unresolved: set[str] = set()
    for obs in note.get("trade_observations", []) if isinstance(note, dict) else []:
        if not isinstance(obs, dict):
            continue
        asset = str(obs.get("asset_or_sector") or "").strip()
        symbol = obs.get("asset_symbol")
        if isinstance(symbol, str) and symbol and symbol not in by_name.values():
            unresolved.add(f"{asset} ({symbol})" if asset else symbol)
            continue
        if asset and not symbol and asset not in by_name and asset not in resolved_sector_terms:
            unresolved.add(asset)
    return sorted(unresolved)


def scan_transcript(text: str, patterns: dict[str, list[tuple[str, re.Pattern[str]]]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for symbol, alias_patterns in patterns.items():
        aliases: list[str] = []
        for alias, pattern in alias_patterns:
            if pattern.search(text):
                aliases.append(alias)
        if aliases:
            found[symbol] = {"matched_aliases": sorted(set(aliases)), "sources": {"transcript"}}
    return found


def add_sector_basket_mentions(
    *,
    text: str,
    mentions: dict[str, dict[str, Any]],
    baskets: list[dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> tuple[set[str], set[str]]:
    matched_sector_names: set[str] = set()
    matched_sector_terms: set[str] = set()
    for basket in baskets:
        matched_aliases = [alias for alias, pattern in basket.get("patterns", []) if pattern.search(text)]
        if not matched_aliases:
            continue
        sector_name = str(basket["sector_name"])
        matched_sector_names.add(sector_name)
        matched_sector_terms.add(sector_name)
        matched_sector_terms.update(str(alias) for alias in matched_aliases)
        for symbol in basket.get("symbols", []):
            if symbol not in by_symbol:
                continue
            mention = mentions.setdefault(symbol, {"matched_aliases": [], "sources": set()})
            mention["matched_aliases"] = sorted(set(mention.get("matched_aliases", [])) | set(matched_aliases))
            mention["sources"].add(f"sector_basket:{sector_name}")
    return matched_sector_names, matched_sector_terms


def add_sector_basket_mentions_from_note(
    *,
    note: dict[str, Any],
    mentions: dict[str, dict[str, Any]],
    baskets: list[dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> tuple[set[str], set[str]]:
    matched_sector_names: set[str] = set()
    matched_sector_terms: set[str] = set()
    for obs in note.get("trade_observations", []) if isinstance(note, dict) else []:
        if not isinstance(obs, dict):
            continue
        asset = str(obs.get("asset_or_sector") or "").strip()
        if not asset:
            continue
        for basket in baskets:
            sector_name = str(basket["sector_name"])
            matched_aliases = [
                alias for alias, pattern in basket.get("patterns", [])
                if asset == sector_name or pattern.search(asset)
            ]
            if not matched_aliases and asset != sector_name:
                continue
            matched_sector_names.add(sector_name)
            matched_sector_terms.add(sector_name)
            matched_sector_terms.add(asset)
            matched_sector_terms.update(str(alias) for alias in matched_aliases)
            for symbol in basket.get("symbols", []):
                if symbol not in by_symbol:
                    continue
                mention = mentions.setdefault(symbol, {"matched_aliases": [], "sources": set()})
                mention["matched_aliases"] = sorted(set(mention.get("matched_aliases", [])) | set(matched_aliases) | {asset})
                mention["sources"].add(f"sector_basket:{sector_name}")
                mention["sources"].add("trade_observations.asset_or_sector")
    return matched_sector_names, matched_sector_terms


def fetch_price_series(
    *,
    symbols: set[str],
    prices_dir: Path,
    start: date,
    end: date,
    force: bool,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
    price_series: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    for symbol in sorted(symbols):
        price_path = prices_dir / f"{symbol_slug(symbol)}.json"
        if price_path.exists() and not force:
            price_series[symbol] = read_json(price_path)
            continue
        try:
            print(f"Fetching {symbol} {start}..{end}", flush=True)
            series = yahoo_chart(symbol, start, end)
            write_json(price_path, series)
            price_series[symbol] = series
        except Exception as exc:  # noqa: BLE001 - keep partial context usable.
            errors.append({"symbol": symbol, "error": str(exc)})
    return price_series, errors


def build_asset_item(
    *,
    symbol: str,
    asset_meta: dict[str, Any],
    mention_meta: dict[str, Any],
    series: list[dict[str, Any]] | None,
    episode_date: str | None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "asset_name": asset_meta["name"],
        "symbol": symbol,
        "asset_type": asset_meta.get("asset_type") or "stock",
        "matched_aliases": mention_meta.get("matched_aliases", []),
        "sources": sorted(mention_meta.get("sources", [])),
        "market": None,
        "pricing_status": "ok",
    }
    if not episode_date:
        item["pricing_status"] = "missing_episode_date"
        return item
    if not series:
        item["pricing_status"] = "missing_price_series"
        return item
    snap = snapshot_for_day(series, parse_day(episode_date))
    if not snap:
        item["pricing_status"] = "no_prior_price"
        return item
    item["market"] = snap
    return item


def main() -> int:
    skill_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=skill_dir / "data")
    parser.add_argument("--asset-map", type=Path, default=skill_dir / "references" / "asset-symbol-map.json")
    parser.add_argument("--sector-baskets", type=Path, default=skill_dir / "references" / "asset-sector-baskets.json")
    parser.add_argument("--force", action="store_true", help="redownload price histories")
    parser.add_argument("--from-episode", type=int)
    parser.add_argument("--to-episode", type=int)
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    episodes = read_json(data_dir / "source" / "episodes.json")
    dated = [ep for ep in episodes if ep.get("date")]
    start = min(parse_day(ep["date"]) for ep in dated) - timedelta(days=100)
    end = max(parse_day(ep["date"]) for ep in dated) + timedelta(days=5)

    _, by_symbol, patterns = load_aliases(args.asset_map)
    sector_baskets = load_sector_baskets(args.sector_baskets)
    by_name = {str(item.get("name")): symbol for symbol, item in by_symbol.items()}
    baseline = load_baseline_context(data_dir)

    selected = []
    episode_mentions: dict[int, dict[str, dict[str, Any]]] = {}
    episode_sector_matches: dict[int, set[str]] = {}
    episode_sector_terms: dict[int, set[str]] = {}
    needed_symbols: set[str] = set()
    for ep in episodes:
        number = int(ep["number"])
        if args.from_episode is not None and number < args.from_episode:
            continue
        if args.to_episode is not None and number > args.to_episode:
            continue
        transcript_path = data_dir / "transcripts" / f"EP{number:03d}.md"
        text = transcript_path.read_text(encoding="utf-8") if transcript_path.exists() else ""
        note = load_episode_notes(data_dir, number)
        mentions = scan_transcript(text, patterns)
        sector_matches, sector_terms = add_sector_basket_mentions(
            text=text,
            mentions=mentions,
            baskets=sector_baskets,
            by_symbol=by_symbol,
        )
        note_sector_matches, note_sector_terms = add_sector_basket_mentions_from_note(
            note=note,
            mentions=mentions,
            baskets=sector_baskets,
            by_symbol=by_symbol,
        )
        sector_matches.update(note_sector_matches)
        sector_terms.update(note_sector_terms)
        for symbol, sources in note_symbol_mentions(note, by_symbol).items():
            mention = mentions.setdefault(symbol, {"matched_aliases": [], "sources": set()})
            mention["sources"].update(sources)
        for symbol in mentions:
            needed_symbols.add(symbol)
        episode_mentions[number] = mentions
        episode_sector_matches[number] = sector_matches
        episode_sector_terms[number] = sector_terms
        selected.append(ep)

    price_series, errors = fetch_price_series(
        symbols=needed_symbols,
        prices_dir=data_dir / "market_context" / "prices",
        start=start,
        end=end,
        force=args.force,
    )

    out_dir = data_dir / "market_context" / "episode_asset_context"
    jsonl_path = data_dir / "market_context" / "episode_asset_context.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for ep in selected:
        number = int(ep["number"])
        note = load_episode_notes(data_dir, number)
        items = []
        for symbol, mention_meta in sorted(episode_mentions[number].items()):
            items.append(
                build_asset_item(
                    symbol=symbol,
                    asset_meta=by_symbol[symbol],
                    mention_meta=mention_meta,
                    series=price_series.get(symbol),
                    episode_date=ep.get("date"),
                )
            )
        record = {
            "episode": number,
            "episode_date": ep.get("date") or "",
            "title": ep.get("display_title") or ep.get("title") or "",
            "baseline_market_context": baseline.get(number, {}).get("markets", {}),
            "mentioned_assets": items,
            "sector_basket_matches": sorted(episode_sector_matches[number]),
            "unresolved_mentions": unresolved_note_mentions(note, by_name, episode_sector_terms[number]),
        }
        write_json(out_dir / f"EP{number:03d}.json", record)
        records.append(record)

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_json(
        data_dir / "market_context" / "episode_asset_context_manifest.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "source": "Yahoo Finance chart API",
            "asset_map": display_path(args.asset_map, skill_dir),
            "sector_baskets": display_path(args.sector_baskets, skill_dir),
            "episode_count": len(records),
            "symbol_count": len(needed_symbols),
            "symbols": sorted(needed_symbols),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "notes": "Mentioned assets are detected from transcript aliases, distilled-note asset symbols, and clearly labeled sector proxy baskets. Unmapped sectors stay in unresolved_mentions.",
            "errors": errors,
        },
    )
    print(
        f"Wrote asset market context for {len(records)} episodes, {len(needed_symbols)} symbols to {out_dir}",
        flush=True,
    )
    if errors:
        print(f"Completed with {len(errors)} symbol errors; see episode_asset_context_manifest.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
