#!/usr/bin/env python3
"""Audit ThemeMiner's data-source registry.

The registry is not a fetcher. It is a routing map that tells ThemeMiner which
source should be used to prove each signal family before promoting a theme.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "thememiner" / "data" / "data_source_registry_seed.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def status_rank(status: str) -> int:
    order = {
        "integrated": 0,
        "partially_integrated": 1,
        "manual_only": 2,
        "planned": 3,
        "optional_paid": 4,
        "optional_paid_or_broker": 4,
    }
    return order.get(status, 9)


def evidence_rank(tier: str) -> int:
    order = {
        "strong": 0,
        "medium": 1,
        "weak": 2,
    }
    return order.get(tier, 9)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ThemeMiner data-source registry")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--top-gaps", type=int, default=12)
    args = parser.parse_args()

    registry_path = Path(args.registry)
    registry = read_json(registry_path)
    sources = registry.get("sources", [])
    if not sources:
        raise SystemExit(f"No sources found in {registry_path}")

    ids = [source.get("id") for source in sources]
    duplicate_ids = sorted(source_id for source_id, count in Counter(ids).items() if count > 1)
    if duplicate_ids:
        raise SystemExit(f"Duplicate source ids: {', '.join(duplicate_ids)}")

    known_ids = set(ids)
    missing_refs: list[str] = []
    for group in registry.get("priority_groups", []):
        for source_id in group.get("source_ids", []):
            if source_id not in known_ids:
                missing_refs.append(f"priority_group:{group.get('name')}->{source_id}")
    for phase in registry.get("integration_roadmap", []):
        for source_id in phase.get("sources", []):
            if source_id not in known_ids:
                missing_refs.append(f"roadmap:{phase.get('phase')}->{source_id}")
    if missing_refs:
        raise SystemExit("Missing source references:\n" + "\n".join(missing_refs))

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_status = Counter()
    by_tier = Counter()
    for source in sources:
        by_family[source.get("signal_family", "unknown")].append(source)
        by_status[source.get("current_status", "unknown")] += 1
        by_tier[source.get("evidence_tier", "unknown")] += 1

    print(f"Registry: {registry_path}")
    print(f"Sources: {len(sources)}")
    print("Evidence tiers:", ", ".join(f"{key}={value}" for key, value in sorted(by_tier.items())))
    print("Statuses:", ", ".join(f"{key}={value}" for key, value in sorted(by_status.items())))
    print()

    print("Signal-family coverage:")
    for family, rows in sorted(by_family.items()):
        statuses = Counter(row.get("current_status", "unknown") for row in rows)
        print(
            f"- {family}: {len(rows)} sources | "
            + ", ".join(f"{status}={count}" for status, count in sorted(statuses.items()))
        )
    print()

    gaps = sorted(
        (
            source
            for source in sources
            if source.get("current_status") not in {"integrated", "partially_integrated"}
        ),
        key=lambda item: (
            evidence_rank(item.get("evidence_tier", "")),
            status_rank(item.get("current_status", "")),
            item.get("signal_family", ""),
            item.get("id", ""),
        ),
    )

    print(f"Top {min(args.top_gaps, len(gaps))} integration gaps:")
    for source in gaps[: args.top_gaps]:
        print(
            f"- {source.get('id')} | {source.get('signal_family')} | "
            f"{source.get('evidence_tier')} | {source.get('current_status')} | "
            f"{source.get('next_action')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
