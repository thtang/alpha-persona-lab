#!/usr/bin/env python3
"""Merge sharded ThemeMiner source evidence JSONL files."""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def row_rank(row: dict[str, Any]) -> tuple[int, float, int]:
    has_no_error = 1 if not row.get("error") else 0
    quality = float(row.get("quality_score") or 0)
    text_chars = int(row.get("text_chars") or 0)
    return has_no_error, quality, text_chars


def merge_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("symbol") or ""), str(row.get("source_url") or row.get("final_url") or ""))
        if not key[0] or not key[1]:
            key = (str(row.get("symbol") or ""), str(row.get("cache_path") or id(row)))
        current = best.get(key)
        if current is None or row_rank(row) > row_rank(current):
            best[key] = row
    return sorted(
        best.values(),
        key=lambda row: (
            str(row.get("market") or ""),
            str(row.get("symbol") or ""),
            -(float(row.get("quality_score") or 0)),
            str(row.get("source_url") or ""),
        ),
    )


def write_report(path: Path, *, inputs: list[Path], rows_in: int, rows_out: list[dict[str, Any]]) -> None:
    errors = [row for row in rows_out if row.get("error")]
    by_market = Counter(str(row.get("market") or "OTHER") for row in rows_out)
    by_type = Counter(str(row.get("source_type") or "other") for row in rows_out)
    by_symbol = Counter(str(row.get("symbol") or "") for row in rows_out)
    lines = [
        "# ThemeMiner Source Evidence Merge Report",
        "",
        f"Generated at: {utc_now()}",
        f"- Input files: {len(inputs)}",
        f"- Raw rows: {rows_in}",
        f"- Merged rows: {len(rows_out)}",
        f"- Symbols covered: {len(by_symbol)}",
        f"- Errors retained: {len(errors)}",
        f"- Markets: {dict(by_market)}",
        f"- Source types: {dict(by_type)}",
        "",
        "## Inputs",
        "",
    ]
    lines.extend(f"- {path}" for path in inputs)
    lines.extend(["", "## Top Evidence", "", "| Symbol | Market | Type | Score | Status | Title | Error |", "|---|---|---|---:|---:|---|---|"])
    for row in sorted(rows_out, key=lambda item: float(item.get("quality_score") or 0), reverse=True)[:80]:
        title = str(row.get("title") or row.get("source_title") or "-").replace("|", "/")[:100]
        error = str(row.get("error") or "-").replace("|", "/")[:100]
        lines.append(
            f"| {row.get('symbol')} | {row.get('market')} | {row.get('source_type')} | "
            f"{float(row.get('quality_score') or 0):.1f} | {row.get('status') or '-'} | {title} | {error} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge ThemeMiner Scrapling evidence shards")
    parser.add_argument("--inputs", default="thememiner/output/company_source_evidence.shard*.jsonl")
    parser.add_argument("--output", default="thememiner/output/company_source_evidence.jsonl")
    parser.add_argument("--report-output", default="thememiner/output/source_fetch_merge_report.md")
    args = parser.parse_args()

    inputs = [Path(path) for path in sorted(glob.glob(args.inputs))]
    raw_rows: list[dict[str, Any]] = []
    for path in inputs:
        raw_rows.extend(read_jsonl(path))
    merged = merge_rows(raw_rows)
    write_jsonl(Path(args.output), merged)
    write_report(Path(args.report_output), inputs=inputs, rows_in=len(raw_rows), rows_out=merged)
    print(f"Merged {len(raw_rows)} rows from {len(inputs)} files into {args.output}; deduped={len(merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
