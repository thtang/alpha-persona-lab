#!/usr/bin/env python3
"""Merge official profile upgrade shards into a single autofill profile file."""

from __future__ import annotations

import argparse
import glob
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from update_theme_graph import read_json, write_json


def load_profiles(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return read_json(path).get("profiles", [])


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge ThemeMiner company profile shards")
    parser.add_argument("--base", default="thememiner/data/company_profiles_autofill.json")
    parser.add_argument("--shards", default="thememiner/data/profile_upgrades/*.json")
    parser.add_argument("--output", default="thememiner/data/company_profiles_official_autofill.json")
    args = parser.parse_args()

    merged = {row["symbol"]: row for row in load_profiles(Path(args.base)) if row.get("symbol")}
    shard_paths = sorted(glob.glob(args.shards))
    shard_counts: dict[str, int] = {}
    for shard_path in shard_paths:
        profiles = load_profiles(Path(shard_path))
        shard_counts[shard_path] = len(profiles)
        for profile in profiles:
            symbol = profile.get("symbol")
            if symbol:
                merged[symbol] = profile

    rows = sorted(merged.values(), key=lambda row: row["symbol"])
    quality_counts = Counter(row.get("profile_quality", "unknown") for row in rows)
    evidence_counts = Counter(row.get("profile_evidence_quality", "unknown") for row in rows)
    payload = {
        "schema_version": "thememiner_company_profiles_official_autofill_v1",
        "updated_at": datetime.now(timezone.utc).date().isoformat(),
        "description": "Merged auto profiles plus official-source profile upgrade shards. Curated seed profiles still override this file in update_theme_graph.py.",
        "base": args.base,
        "shards": shard_counts,
        "profile_count": len(rows),
        "quality_counts": dict(quality_counts),
        "evidence_counts": dict(evidence_counts),
        "profiles": rows,
    }
    write_json(Path(args.output), payload)
    print(f"Wrote {len(rows)} merged profiles to {args.output}")
    print(f"Quality counts: {dict(quality_counts)}")
    print(f"Evidence counts: {dict(evidence_counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
