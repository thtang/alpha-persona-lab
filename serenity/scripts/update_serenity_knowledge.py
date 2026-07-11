#!/usr/bin/env python3
"""Fetch public Serenity-related leads and write a local digest.

This intentionally uses only Python standard library. X access is brittle, so
the script treats social/mirror sources as leads and records failures instead
of pretending the update succeeded.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DATA_DIR = ROOT / "data" / "source"
RAW_DIR = DATA_DIR / "raw"
POSTS_DIR = ROOT / "data" / "posts"
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
GRAPH_INPUTS_DIR = ROOT / "data" / "graph_inputs"
POSTS_PATH = POSTS_DIR / "serenity_posts.jsonl"
TRANSCRIPTS_MANIFEST_PATH = ROOT / "data" / "transcripts_manifest.json"

SERENITY_CONCEPT_HINTS = {
    "data_center_bbu": [
        "BBU",
        "battery backup",
        "rack-level battery",
        "server rack battery",
        "data-center battery",
        "backup power",
    ],
    "high_power_cylindrical_battery": [
        "cylindrical",
        "21700",
        "40V3",
        "tabless",
        "NCA",
        "silicon-carbon",
        "high-current cell",
        "bottle-neck battery",
        "瓶頸",
        "圓柱",
    ],
    "ai_capex": ["AI capex", "AI investment", "AI spending", "hyperscaler capex", "算力"],
    "cloud_ai": ["cloud AI", "AI cloud", "GPU cloud", "TPU cloud", "neocloud"],
    "cpo_optical": ["CPO", "co-packaged optics", "optical I/O"],
    "inp_photonics": ["InP", "indium phosphide", "磷化銦"],
    "silicon_photonics": ["silicon photonics", "SiPh", "矽光子"],
    "soi_wafer": ["SOI", "SOI wafer"],
    "epitaxy_equipment": ["epitaxy", "epitaxial", "MOCVD", "外延"],
    "specialty_glass_fiber": ["specialty glass fiber", "low-loss fiber", "特殊玻纖"],
    "optical_interposer_packaging": ["optical interposer", "photonic interposer"],
    "hvdc_power_semiconductor": ["HVDC", "800V", "power semiconductor", "power MOSFET", "SiC", "GaN"],
    "power_discrete_semiconductor": ["discrete power", "MOSFET", "IGBT", "rectifier", "diode"],
    "passive_components": ["MLCC", "capacitor", "SP-Cap", "snap-in capacitor", "passive component", "被動元件"],
}

KNOWN_COMPANY_ALIASES = {
    "006400.KS": ["Samsung SDI", "三星SDI"],
    "373220.KS": ["LG Energy Solution", "LGES"],
    "6752.T": ["Panasonic", "松下"],
    "6121.TWO": ["Simplo", "新普", "Trend Power"],
    "2308.TW": ["Delta Electronics", "台達電", "台達"],
    "6409.TW": ["Voltronic", "旭隼"],
    "2360.TW": ["Chroma", "致茂"],
    "VRT": ["Vertiv"],
    "ETN": ["Eaton"],
    "ON": ["onsemi", "ON Semiconductor"],
    "STM": ["STMicroelectronics", "STMicro"],
    "TXN": ["Texas Instruments"],
    "VSH": ["Vishay", "Vishay Intertechnology"],
    "IFX.DE": ["Infineon"],
    "6963.T": ["Rohm", "ROHM"],
    "FORM": ["FormFactor"],
    "TER": ["Teradyne"],
    "AAOI": ["Applied Optoelectronics"],
    "AXTI": ["AXT Inc", "AXT"],
    "COHR": ["Coherent"],
    "LITE": ["Lumentum"],
    "NBIS": ["Nebius"],
    "WULF": ["TeraWulf"],
}

DEFAULT_SOURCES = [
    {
        "name": "x_profile_direct",
        "url": "https://x.com/aleabitoreddit",
        "kind": "social_primary",
        "strength": "weak_lead",
    },
    {
        "name": "x_with_replies_jina",
        "url": "https://r.jina.ai/http://x.com/aleabitoreddit/with_replies",
        "kind": "social_mirror",
        "strength": "weak_lead",
    },
    {
        "name": "serenity_method_youminds",
        "url": "https://youmind.com/landing/x-viral-articles/serenity-ai-supply-chain-alpha",
        "kind": "method_reconstruction",
        "strength": "secondary",
    },
    {
        "name": "muxuuu_serenity_skill_raw",
        "url": "https://raw.githubusercontent.com/muxuuu/serenity-skill/main/SKILL.md",
        "kind": "reference_skill",
        "strength": "secondary",
    },
    {
        "name": "thelec_sdi_simplo_bbu",
        "url": "https://www.thelec.net/news/articleView.html?idxno=11952",
        "kind": "trade_media",
        "strength": "medium",
    },
    {
        "name": "thelec_sdi_40v3_bbu",
        "url": "https://www.thelec.net/news/articleView.html?idxno=6792",
        "kind": "trade_media",
        "strength": "medium",
    },
]

KEYWORDS = [
    "aleabitoreddit",
    "Serenity",
    "bottleneck",
    "chokepoint",
    "supply chain",
    "AI data",
    "BBU",
    "battery backup",
    "cylindrical",
    "Simplo",
    "Samsung SDI",
    "Panasonic",
    "InP",
    "silicon photonics",
    "CPO",
    "qualification",
    "capacity",
]


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def slugify(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", value.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:80] or "unknown"


def load_theme_concepts() -> dict[str, dict]:
    taxonomy_path = REPO_ROOT / "thememiner" / "data" / "fine_theme_taxonomy_seed.json"
    taxonomy = read_json(taxonomy_path, {"categories": []})
    concepts = {}
    for category in taxonomy.get("categories", []):
        for concept in category.get("concepts", []):
            concept_id = concept.get("concept_id")
            if not concept_id:
                continue
            concepts[concept_id] = {
                **concept,
                "category_id": category.get("category_id"),
                "category_label": category.get("label"),
            }
    return concepts


def load_company_aliases() -> dict[str, dict]:
    profiles_path = REPO_ROOT / "thememiner" / "output" / "company_profiles.json"
    payload = read_json(profiles_path, {"profiles": []})
    aliases: dict[str, dict] = {}
    for profile in payload.get("profiles", []):
        symbol = profile.get("symbol")
        if not symbol:
            continue
        terms = [
            symbol,
            profile.get("name"),
            profile.get("english_name"),
            profile.get("short_name"),
            *(profile.get("aliases") or []),
        ]
        terms.extend(KNOWN_COMPANY_ALIASES.get(symbol, []))
        aliases[symbol] = {
            "symbol": symbol,
            "name": profile.get("name") or profile.get("english_name") or symbol,
            "market": profile.get("market"),
            "aliases": sorted({str(term).strip() for term in terms if term}),
        }
    for symbol, terms in KNOWN_COMPANY_ALIASES.items():
        aliases.setdefault(
            symbol,
            {
                "symbol": symbol,
                "name": terms[0],
                "market": None,
                "aliases": sorted({symbol, *terms}),
            },
        )
    return aliases


def term_in_text(term: str, text: str, lower_text: str) -> bool:
    if not term:
        return False
    if re.fullmatch(r"[A-Z0-9.$-]{2,10}", term):
        return re.search(rf"(?<![A-Za-z0-9.$-])\$?{re.escape(term)}(?![A-Za-z0-9.$-])", text) is not None
    return term.lower() in lower_text


def match_concepts(text: str, concepts: dict[str, dict]) -> list[dict]:
    lower = text.lower()
    matches = []
    for concept_id, hints in SERENITY_CONCEPT_HINTS.items():
        matched_terms = [term for term in hints if term_in_text(term, text, lower)]
        if not matched_terms:
            continue
        concept = concepts.get(concept_id, {})
        matches.append(
            {
                "concept_id": concept_id,
                "label": concept.get("label") or concept_id,
                "matched_terms": sorted(set(matched_terms)),
                "match_authority": "serenity_recall_hint",
            }
        )
    return matches


def match_companies(text: str, aliases: dict[str, dict]) -> list[dict]:
    lower = text.lower()
    matches = []
    for symbol, row in aliases.items():
        matched_terms = [term for term in row.get("aliases", []) if term_in_text(term, text, lower)]
        if not matched_terms:
            continue
        matches.append(
            {
                "symbol": symbol,
                "name": row.get("name") or symbol,
                "market": row.get("market"),
                "matched_terms": sorted(set(matched_terms)),
                "match_authority": "serenity_recall_hint",
            }
        )
    return matches


def fetch(url: str, timeout: int) -> tuple[bool, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; alpha-persona-lab-serenity/1.0)",
            "Accept": "text/html,text/plain,application/json,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return True, data.decode(charset, errors="replace"), f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:4000]
        return False, body, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - report every fetch failure in digest.
        return False, "", f"{type(exc).__name__}: {exc}"


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    raw = re.sub(r"(?is)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?is)</p>|</div>|</li>|</h[1-6]>", "\n", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n\s*\n+", "\n", raw)
    return raw.strip()


def extract_snippets(text: str, limit: int) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) < 40:
            continue
        lower = line.lower()
        if any(k.lower() in lower for k in KEYWORDS):
            lines.append(line)
    seen = set()
    deduped = []
    for line in lines:
        key = line[:180]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
        if len(deduped) >= limit:
            break
    return deduped


def build_corpus(records: list[dict], now: dt.datetime) -> dict:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_INPUTS_DIR.mkdir(parents=True, exist_ok=True)

    concepts = load_theme_concepts()
    company_aliases = load_company_aliases()
    existing_posts = {row.get("post_id"): row for row in read_jsonl(POSTS_PATH) if row.get("post_id")}
    transcript_manifest = read_json(TRANSCRIPTS_MANIFEST_PATH, {"transcripts": []})
    transcripts_by_hash = {
        row.get("content_hash"): row for row in transcript_manifest.get("transcripts", []) if row.get("content_hash")
    }

    new_posts = 0
    transcript_rows = list(transcript_manifest.get("transcripts", []))

    for record in records:
        raw_rel_path = record.get("raw_path")
        raw_path = ROOT / raw_rel_path if raw_rel_path else None
        text = raw_path.read_text(encoding="utf-8") if raw_path and raw_path.exists() else "\n".join(record.get("snippets", []))
        text = text.strip()
        if not text:
            continue

        content_hash = sha256_text(f"{record.get('url')}|{text}")[:16]
        transcript_id = f"{now.strftime('%Y%m%d')}_{slugify(record.get('name', 'source'))}_{content_hash}"
        concepts_matched = match_concepts(text, concepts)
        companies_matched = match_companies(text, company_aliases)
        if content_hash not in transcripts_by_hash:
            transcript_rel = Path("data") / "transcripts" / f"{transcript_id}.md"
            transcript_path = ROOT / transcript_rel
            transcript_lines = [
                "---",
                f"id: {transcript_id}",
                "author: Serenity / @aleabitoreddit research corpus",
                f"source_name: {record.get('name')}",
                f"source_kind: {record.get('kind')}",
                f"evidence_strength: {record.get('strength')}",
                f"url: {record.get('url')}",
                f"fetched_at: {record.get('fetched_at')}",
                f"content_hash: {content_hash}",
                "match_authority: serenity_recall_hint",
                "---",
                "",
                "# Serenity Source Transcript",
                "",
                "> This is a local, transcript-like extraction of a public source page used for recall. Social/KOL content is a weak lead until confirmed by official, filing, price/volume, or trade-media evidence.",
                "",
                "## Matched Concepts",
                "",
            ]
            if concepts_matched:
                for item in concepts_matched:
                    transcript_lines.append(
                        f"- `{item['concept_id']}` {item['label']} (terms: {', '.join(item['matched_terms'])})"
                    )
            else:
                transcript_lines.append("- None")
            transcript_lines += ["", "## Matched Companies", ""]
            if companies_matched:
                for item in companies_matched:
                    transcript_lines.append(
                        f"- `{item['symbol']}` {item['name']} (terms: {', '.join(item['matched_terms'])})"
                    )
            else:
                transcript_lines.append("- None")
            transcript_lines += ["", "## Extracted Text", "", text[:180000].rstrip(), ""]
            transcript_path.write_text("\n".join(transcript_lines), encoding="utf-8")
            transcript_entry = {
                "id": transcript_id,
                "path": str(transcript_rel),
                "source_name": record.get("name"),
                "source_kind": record.get("kind"),
                "evidence_strength": record.get("strength"),
                "url": record.get("url"),
                "fetched_at": record.get("fetched_at"),
                "content_hash": content_hash,
                "concept_ids": [item["concept_id"] for item in concepts_matched],
                "symbols": [item["symbol"] for item in companies_matched],
                "match_authority": "serenity_recall_hint",
            }
            transcripts_by_hash[content_hash] = transcript_entry
            transcript_rows.append(transcript_entry)

        transcript_entry = transcripts_by_hash[content_hash]
        snippets = record.get("snippets") or [text[:1200]]
        for idx, snippet in enumerate(snippets):
            snippet_hash = sha256_text(f"{record.get('url')}|{idx}|{snippet}")[:16]
            post_id = f"serenity:{snippet_hash}"
            post_concepts = match_concepts(snippet, concepts)
            post_companies = match_companies(snippet, company_aliases)
            post_row = {
                "post_id": post_id,
                "author": "Serenity / @aleabitoreddit research corpus",
                "source_name": record.get("name"),
                "source_kind": record.get("kind"),
                "evidence_strength": record.get("strength"),
                "url": record.get("url"),
                "fetched_at": record.get("fetched_at"),
                "text": snippet,
                "content_hash": content_hash,
                "transcript_id": transcript_entry["id"],
                "transcript_path": transcript_entry["path"],
                "concepts": post_concepts,
                "companies": post_companies,
                "match_authority": "serenity_recall_hint",
                "evidence_policy": "weak lead unless verified by official/trade/market evidence",
            }
            if post_id not in existing_posts:
                new_posts += 1
            existing_posts[post_id] = post_row

    posts = sorted(existing_posts.values(), key=lambda row: (row.get("fetched_at") or "", row.get("post_id") or ""))
    write_jsonl(POSTS_PATH, posts)
    write_json(
        TRANSCRIPTS_MANIFEST_PATH,
        {
            "updated_at": now.isoformat(timespec="seconds"),
            "transcript_count": len(transcript_rows),
            "transcripts": sorted(transcript_rows, key=lambda row: row.get("id", "")),
        },
    )

    theme_rows = []
    company_rows = []
    for post in posts:
        for concept in post.get("concepts", []):
            theme_rows.append(
                {
                    "concept_id": concept["concept_id"],
                    "concept_label": concept["label"],
                    "title": textwrap.shorten(post.get("text", ""), width=220, placeholder=" ..."),
                    "source": f"serenity:{post.get('source_name')}",
                    "url": post.get("url"),
                    "published_at": post.get("fetched_at"),
                    "evidence_tier": post.get("evidence_strength"),
                    "evidence_kind": "kol_or_trade_lead",
                    "post_id": post.get("post_id"),
                    "transcript_id": post.get("transcript_id"),
                    "match_authority": "serenity_recall_hint",
                    "matched_terms": concept.get("matched_terms", []),
                    "evidence_policy": post.get("evidence_policy"),
                }
            )
        for company in post.get("companies", []):
            company_rows.append(
                {
                    "symbol": company["symbol"],
                    "name": company.get("name"),
                    "market": company.get("market"),
                    "source": f"serenity:{post.get('source_name')}",
                    "url": post.get("url"),
                    "published_at": post.get("fetched_at"),
                    "post_id": post.get("post_id"),
                    "transcript_id": post.get("transcript_id"),
                    "text": post.get("text"),
                    "matched_terms": company.get("matched_terms", []),
                    "match_authority": "serenity_recall_hint",
                    "evidence_policy": post.get("evidence_policy"),
                }
            )

    write_jsonl(GRAPH_INPUTS_DIR / "theme_evidence.jsonl", theme_rows)
    write_jsonl(GRAPH_INPUTS_DIR / "company_mentions.jsonl", company_rows)
    write_json(
        GRAPH_INPUTS_DIR / "update_manifest.json",
        {
            "updated_at": now.isoformat(timespec="seconds"),
            "posts_total": len(posts),
            "posts_new": new_posts,
            "transcripts_total": len(transcript_rows),
            "theme_evidence_rows": len(theme_rows),
            "company_mention_rows": len(company_rows),
            "match_authority": "serenity_recall_hint",
            "policy": "Use as recall/lead evidence only; verify with official, trade-media, price/volume, flow, and filing evidence before ranking.",
        },
    )
    return {
        "posts_total": len(posts),
        "posts_new": new_posts,
        "transcripts_total": len(transcript_rows),
        "theme_evidence_rows": len(theme_rows),
        "company_mention_rows": len(company_rows),
    }


def write_outputs(records: list[dict], now: dt.datetime, corpus_stats: dict | None = None) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    jsonl_path = DATA_DIR / "latest_posts.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = {
        "updated_at": now.isoformat(timespec="seconds"),
        "source_count": len(records),
        "ok_count": sum(1 for r in records if r["ok"]),
        "failed_sources": [r["name"] for r in records if not r["ok"]],
        "corpus_stats": corpus_stats or {},
        "note": "Social/X sources are leads only; verify company facts with filings, official sources, or credible trade media.",
    }
    (DATA_DIR / "update_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Serenity Latest Public-Knowledge Digest",
        "",
        f"Updated at: {manifest['updated_at']}",
        "",
        "## Source Status",
        "",
        "| Source | Status | Strength | URL |",
        "|---|---:|---|---|",
    ]
    for r in records:
        status = "ok" if r["ok"] else r["status"]
        lines.append(f"| {r['name']} | {status} | {r['strength']} | {r['url']} |")
    lines += ["", "## Extracted Leads", ""]
    for r in records:
        if not r["snippets"]:
            continue
        lines.append(f"### {r['name']} ({r['strength']})")
        for snippet in r["snippets"]:
            wrapped = textwrap.shorten(snippet, width=360, placeholder=" ...")
            lines.append(f"- {wrapped}")
        lines.append("")
    if not any(r["snippets"] for r in records):
        lines.append("- No snippets extracted. Check `update_manifest.json` for blocked sources.")
    if corpus_stats:
        lines += [
            "",
            "## Local Corpus",
            "",
            f"- Cumulative posts: {corpus_stats.get('posts_total', 0)} ({corpus_stats.get('posts_new', 0)} new)",
            f"- Transcript files: {corpus_stats.get('transcripts_total', 0)}",
            f"- Theme evidence rows for ThemeMiner: {corpus_stats.get('theme_evidence_rows', 0)}",
            f"- Company mention rows: {corpus_stats.get('company_mention_rows', 0)}",
            "- Match authority: `serenity_recall_hint` (recall only; verify before ranking).",
        ]
    (DATA_DIR / "latest_digest.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", default=[], help="Extra URL to fetch")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--max-snippets", type=int, default=12)
    args = parser.parse_args(argv)

    now = dt.datetime.now(dt.timezone.utc)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    sources = list(DEFAULT_SOURCES)
    for idx, url in enumerate(args.source):
        sources.append({"name": f"extra_{idx+1}", "url": url, "kind": "user_extra", "strength": "needs_grading"})

    records = []
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    for source in sources:
        ok, raw, status = fetch(source["url"], args.timeout)
        text = html_to_text(raw)
        digest = hashlib.sha256(source["url"].encode("utf-8")).hexdigest()[:12]
        raw_path = RAW_DIR / f"{stamp}_{source['name']}_{digest}.txt"
        raw_path.write_text(text[:200000], encoding="utf-8")
        records.append(
            {
                **source,
                "ok": ok,
                "status": status,
                "fetched_at": now.isoformat(timespec="seconds"),
                "raw_path": str(raw_path.relative_to(ROOT)),
                "snippets": extract_snippets(text, args.max_snippets),
            }
        )

    corpus_stats = build_corpus(records, now)
    write_outputs(records, now, corpus_stats)
    print(f"Wrote {DATA_DIR / 'latest_digest.md'}")
    print(f"Wrote {POSTS_PATH}")
    print(f"Wrote {GRAPH_INPUTS_DIR / 'theme_evidence.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
