#!/usr/bin/env python3
"""Build deterministic distilled memory for the Zhezhe corpus.

This script turns local ASR transcripts into compact retrieval artifacts. It is
not a replacement for human/LLM semantic distillation; it creates a stable first
pass that the skill can use before opening raw transcripts.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TRANSCRIPTS = DATA / "transcripts"
DISTILLED = DATA / "distilled"
REFERENCES = ROOT / "references"
MARKET_CONTEXT = DATA / "market_context" / "episode_market_context.jsonl"
ASSET_CONTEXT = DATA / "market_context" / "episode_asset_context.jsonl"

THEMES: dict[str, dict[str, Any]] = {
    "index_direction": {
        "label": "台股/台指方向",
        "keywords": ["台股", "大盤", "加權", "台指", "台子期", "多頭", "空頭", "創新高", "崩盤", "回檔", "拉回", "逆價差", "四萬", "兩萬", "萬點"],
    },
    "tsmc_valuation": {
        "label": "台積電估值與權值股拖拉",
        "keywords": ["台積電", "台積", "TSMC", "2330", "營收", "法說", "EPS", "本益比", "權值", "外資"],
    },
    "ai_supply_chain": {
        "label": "AI伺服器與供應鏈",
        "keywords": ["AI", "人工智慧", "伺服器", "GB200", "GB300", "輝達", "NVIDIA", "鴻海", "廣達", "緯創", "緯穎", "英業達"],
    },
    "memory_cycle": {
        "label": "記憶體循環",
        "keywords": ["記憶體", "DRAM", "DDR4", "DDR5", "HBM", "南亞科", "華邦電", "群聯", "美光", "NAND", "旺宏"],
    },
    "passive_components": {
        "label": "被動元件",
        "keywords": ["被動元件", "國巨", "華新科", "信昌電", "MLCC", "電容", "電阻"],
    },
    "pcb_ccl": {
        "label": "PCB/CCL/ABF",
        "keywords": ["PCB", "CCL", "ABF", "載板", "台光電", "金像電", "欣興", "景碩", "銅箔基板"],
    },
    "shipping_cyclicals": {
        "label": "航運與景氣循環股",
        "keywords": ["航運", "海運", "貨櫃", "長榮", "陽明", "萬海", "中鋼", "景氣循環"],
    },
    "rates_fx_bonds": {
        "label": "美債/匯率/資金面",
        "keywords": ["美債", "殖利率", "利率", "降息", "升息", "美元", "台幣", "匯率", "00687B", "資金"],
    },
    "risk_control": {
        "label": "風險控制與進出紀律",
        "keywords": ["風險", "停損", "停利", "回檔", "拉回", "不碰", "不要追", "減碼", "下車", "獲利", "留意", "注意"],
    },
    "performance_authority": {
        "label": "績效/會員/權威敘事",
        "keywords": ["會員", "大賺", "獲利", "賺錢", "選股比賽", "冠軍", "百萬粉絲", "投資長", "績效"],
    },
}

RHETORIC_PATTERNS: dict[str, dict[str, Any]] = {
    "shock_headline": {
        "label": "驚嚇式標題開場",
        "function": "urgency",
        "keywords": ["不得了", "慘了", "血流成河", "崩盤", "暴雷", "狂殺", "大跳水", "嚇死", "危機"],
    },
    "wealth_imagery": {
        "label": "財富畫面與漲幅承諾",
        "function": "social_proof",
        "keywords": ["數錢", "大賺", "再漲", "漲100%", "噴出", "鎖死漲停", "創新高", "飆股"],
    },
    "authority_scoreboard": {
        "label": "績效榜單與會員見證",
        "function": "authority",
        "keywords": ["會員", "選股比賽", "冠軍", "紀錄保持者", "百萬粉絲", "見證", "投資長"],
    },
    "retail_pain": {
        "label": "散戶焦慮與踏空痛點",
        "function": "fear_control",
        "keywords": ["你手上還沒有", "還沒有上車", "追或不追", "怎麼辦", "會不會", "怕", "緊張"],
    },
    "binary_contrast": {
        "label": "二分對照與轉折",
        "function": "contrast",
        "keywords": ["不是", "而是", "但是", "問題是", "重點是", "可是", "換句話說"],
    },
    "data_checkpoint": {
        "label": "數據節點驗證",
        "function": "authority",
        "keywords": ["三大法人", "外資", "台指期", "逆價差", "營收", "法說", "目標價", "EPS", "K線"],
    },
}

RISK_RULES: dict[str, list[str]] = {
    "wait_pullback": ["等回檔", "等拉回", "拉回再", "不要追", "追高"],
    "take_profit": ["停利", "獲利了結", "下車", "減碼", "獲利"],
    "avoid_weak_large_cap": ["不要碰台積", "浪費你的生命", "台積電上不去", "權值股"],
    "watch_derivatives": ["台指期", "台子期", "逆價差", "多空單", "三大法人"],
    "fraud_warning": ["詐騙", "官方帳號", "盾牌標章", "提高警覺"],
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---\n"):
        return {}, text
    _, fm, body = text.split("---", 2)
    meta: dict[str, str] = {}
    for line in fm.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        meta[key.strip()] = value
    return meta, body.strip()


TIMESTAMP_RE = re.compile(r"\[\d{2}:\d{2}:\d{2}\]\s*")
SPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    text = TIMESTAMP_RE.sub(" ", text)
    text = re.sub(r"^# .*$", " ", text, flags=re.MULTILINE)
    text = text.replace("\ufffd", "")
    return SPACE_RE.sub(" ", text).strip()


def count_keywords(text: str, keywords: list[str]) -> dict[str, int]:
    return {kw: text.count(kw) for kw in keywords if text.count(kw)}


def first_snippet(text: str, keywords: list[str], width: int = 90) -> str:
    best = len(text) + 1
    matched = ""
    for kw in keywords:
        idx = text.find(kw)
        if idx >= 0 and idx < best:
            best = idx
            matched = kw
    if not matched:
        return ""
    start = max(0, best - width)
    end = min(len(text), best + len(matched) + width)
    snippet = text[start:end].strip()
    return ("..." if start else "") + snippet + ("..." if end < len(text) else "")


def load_assets() -> list[dict[str, Any]]:
    assets_path = REFERENCES / "asset-symbol-map.json"
    if not assets_path.exists():
        return []
    return json.loads(assets_path.read_text(encoding="utf-8"))


def load_sector_baskets() -> list[dict[str, Any]]:
    sectors_path = REFERENCES / "asset-sector-baskets.json"
    if not sectors_path.exists():
        return []
    return json.loads(sectors_path.read_text(encoding="utf-8"))


def load_market_context() -> dict[str, dict[str, Any]]:
    return {row.get("source_id"): row for row in read_jsonl(MARKET_CONTEXT) if row.get("source_id")}


def load_asset_context() -> dict[str, dict[str, Any]]:
    return {row.get("source_id"): row for row in read_jsonl(ASSET_CONTEXT) if row.get("source_id")}


def classify_market_regime(context: dict[str, Any] | None) -> dict[str, Any]:
    if not context:
        return {"phase_label": "unknown", "narrative": "缺少 episode-date market context。", "regime_tags": []}
    markets = context.get("markets") or context.get("baseline_market_context") or {}
    twii = markets.get("^TWII") or {}
    soxx = markets.get("SOXX") or {}
    vix = markets.get("^VIX") or {}
    ret_20d = twii.get("ret_20d_pct")
    drawdown = twii.get("drawdown_60d_pct")
    tags: list[str] = []
    phase = "mixed / range"
    if isinstance(ret_20d, (int, float)) and isinstance(drawdown, (int, float)):
        if ret_20d >= 5 and drawdown >= -3:
            phase = "risk-on / momentum"
            tags.append("台股20日動能偏強")
        elif ret_20d <= -5 or drawdown <= -8:
            phase = "weak / corrective"
            tags.append("台股修正或回撤壓力")
        elif abs(ret_20d) <= 2:
            phase = "mixed / range"
            tags.append("台股區間震盪")
    if isinstance(soxx.get("ret_20d_pct"), (int, float)) and soxx["ret_20d_pct"] >= 5:
        tags.append("費半強於近20日")
    if isinstance(vix.get("ret_5d_pct"), (int, float)) and vix["ret_5d_pct"] >= 10:
        tags.append("VIX短線升溫")
    narrative_bits = []
    if twii:
        narrative_bits.append(
            f"TAIEX 20d {twii.get('ret_20d_pct')}%, 60d drawdown {twii.get('drawdown_60d_pct')}%"
        )
    if soxx:
        narrative_bits.append(f"SOXX 20d {soxx.get('ret_20d_pct')}%")
    if vix:
        narrative_bits.append(f"VIX 5d {vix.get('ret_5d_pct')}%")
    return {"phase_label": phase, "narrative": "; ".join(narrative_bits), "regime_tags": tags}


def classify_headline(title: str, body: str) -> dict[str, str]:
    source = f"{title} {body[:2500]}"
    bullish = ["漲", "大漲", "噴", "噴出", "創新高", "多頭", "上攻", "反攻", "起漲", "漲停", "回來了"]
    bearish = ["跌", "殺", "崩", "暴雷", "血流成河", "不保", "風險", "慘", "空頭", "大跳水", "拉回"]
    risk = ["風險", "注意", "小心", "不碰", "不要追", "停利", "減碼", "逆價差"]
    b = sum(source.count(x) for x in bullish)
    s = sum(source.count(x) for x in bearish)
    r = sum(source.count(x) for x in risk)
    if r >= 2 and s >= 1:
        direction = "risk_control"
    elif b and s:
        direction = "mixed"
    elif b:
        direction = "bullish"
    elif s:
        direction = "bearish"
    else:
        direction = "unknown"
    horizon = "swing"
    if any(x in source for x in ["明天", "今天", "尾盤", "盤後", "台指期"]):
        horizon = "intraday"
    elif any(x in source for x in ["下週", "五月", "六月", "本月"]):
        horizon = "monthly"
    elif any(x in source for x in ["今年", "明年", "長線"]):
        horizon = "multi_month"
    return {
        "direction": direction,
        "horizon": horizon,
        "claim": title,
        "trigger": "",
        "invalidation": "",
        "confidence": "medium" if direction != "unknown" else "low",
    }


def detect_themes(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for theme_id, spec in THEMES.items():
        counts = count_keywords(text, spec["keywords"])
        hit_count = sum(counts.values())
        if not hit_count:
            continue
        rows.append(
            {
                "theme_id": theme_id,
                "label": spec["label"],
                "hit_count": hit_count,
                "keyword_counts": counts,
                "evidence": first_snippet(text, spec["keywords"]),
            }
        )
    rows.sort(key=lambda row: row["hit_count"], reverse=True)
    return rows


def detect_rhetoric(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pattern_id, spec in RHETORIC_PATTERNS.items():
        counts = count_keywords(text, spec["keywords"])
        hit_count = sum(counts.values())
        if not hit_count:
            continue
        rows.append(
            {
                "pattern_id": pattern_id,
                "pattern": spec["label"],
                "function": spec["function"],
                "hit_count": hit_count,
                "evidence": first_snippet(text, spec["keywords"]),
            }
        )
    rows.sort(key=lambda row: row["hit_count"], reverse=True)
    return rows


def detect_risk_rules(text: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for rule_id, keywords in RISK_RULES.items():
        counts = count_keywords(text, keywords)
        if not counts:
            continue
        rules.append(
            {
                "rule_id": rule_id,
                "matched_terms": counts,
                "condition": "",
                "action": "wait" if rule_id == "wait_pullback" else "hold",
                "evidence": first_snippet(text, keywords),
            }
        )
    return rules


def detect_assets(text: str, assets: list[dict[str, Any]], sectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for asset in assets:
        aliases = asset.get("aliases", [])
        counts = count_keywords(text, aliases)
        if not counts:
            continue
        rows.append(
            {
                "asset_or_sector": asset.get("name"),
                "asset_symbol": asset.get("symbol"),
                "asset_type": asset.get("asset_type", "unknown"),
                "mention_kind": "direct",
                "hit_count": sum(counts.values()),
                "matched_aliases": counts,
                "view": "unknown",
                "horizon": "unstated",
                "evidence": first_snippet(text, aliases),
            }
        )
    for sector in sectors:
        aliases = sector.get("aliases", [])
        counts = count_keywords(text, aliases)
        if not counts:
            continue
        rows.append(
            {
                "asset_or_sector": sector.get("sector_name"),
                "asset_symbol": "",
                "asset_type": "sector",
                "mention_kind": "sector",
                "hit_count": sum(counts.values()),
                "matched_aliases": counts,
                "view": "unknown",
                "horizon": "unstated",
                "evidence": first_snippet(text, aliases),
            }
        )
    rows.sort(key=lambda row: row["hit_count"], reverse=True)
    return rows[:20]


def make_note(
    path: Path,
    market_context: dict[str, dict[str, Any]],
    asset_context: dict[str, dict[str, Any]],
    assets: list[dict[str, Any]],
    sectors: list[dict[str, Any]],
) -> dict[str, Any]:
    meta, body = parse_frontmatter(path)
    title = meta.get("title") or path.stem
    source_id = meta.get("episode_id") or path.stem.split("_", 1)[-1]
    date = meta.get("date") or path.name[:10]
    text = clean_text(f"{title} {body}")
    context = market_context.get(source_id)
    direct_asset_context = asset_context.get(source_id)
    asset_views = detect_assets(text, assets, sectors)
    if direct_asset_context:
        directly_contextualized = {
            item.get("symbol")
            for item in direct_asset_context.get("direct_mentioned_assets", [])
            if item.get("symbol")
        }
        for row in asset_views:
            if row.get("asset_symbol") in directly_contextualized:
                row["context_status"] = "priced_in_episode_asset_context"
    note = {
        "schema_version": "zhezhe_deterministic_v1",
        "source_id": source_id,
        "source_type": "podcast_transcript",
        "date": date,
        "title": title,
        "source_url": meta.get("source_url", ""),
        "transcript_path": str(path.relative_to(ROOT)),
        "market_regime": classify_market_regime(context),
        "headline_call": classify_headline(title, text),
        "themes": detect_themes(text),
        "asset_views": asset_views,
        "risk_control": detect_risk_rules(text),
        "rhetorical_patterns": detect_rhetoric(text),
        "market_followups": [
            {
                "question": "此集的 headline call 是否被後續價格確認或反駁？",
                "data_to_check": "TAIEX、台指期、文中直接提及個股與族群 1d/5d/20d 後續報酬",
                "deadline_or_horizon": "下一集、5個交易日、20個交易日",
            }
        ],
        "source_quality": {
            "has_full_transcript": True,
            "asr_model": meta.get("asr_model", ""),
            "asr_confidence": "medium",
            "article_full_text_available": False,
            "notes": "MLX Whisper ASR；未做 speaker diarization，部分股票名/人名可能有錯字。",
        },
        "open_questions": [],
    }
    return note


def top_records(counter_rows: dict[str, list[dict[str, Any]]], limit: int = 12) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for key, rows in counter_rows.items():
        result[key] = sorted(rows, key=lambda row: (row.get("hit_count", 0), row.get("date", "")), reverse=True)[:limit]
    return result


def build_theme_memory(notes: list[dict[str, Any]], built_at: str) -> dict[str, Any]:
    theme_counts: dict[str, Counter[str]] = defaultdict(Counter)
    theme_hits: Counter[str] = Counter()
    theme_episodes: Counter[str] = Counter()
    theme_top: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for note in notes:
        for theme in note["themes"]:
            tid = theme["theme_id"]
            theme_episodes[tid] += 1
            theme_hits[tid] += theme["hit_count"]
            theme_counts[tid].update(theme["keyword_counts"])
            theme_top[tid].append(
                {
                    "source_id": note["source_id"],
                    "date": note["date"],
                    "title": note["title"],
                    "hit_count": theme["hit_count"],
                    "market_regime": note["market_regime"]["phase_label"],
                    "evidence": theme["evidence"],
                }
            )
    themes = {}
    top_by_theme = top_records(theme_top, limit=16)
    for tid, spec in THEMES.items():
        if not theme_episodes[tid]:
            continue
        themes[tid] = {
            "label": spec["label"],
            "keywords": spec["keywords"],
            "episode_count": theme_episodes[tid],
            "hit_count": theme_hits[tid],
            "keyword_counts": dict(theme_counts[tid].most_common()),
            "top_episodes": top_by_theme.get(tid, []),
        }
    return {"built_at": built_at, "episode_count": len(notes), "themes": themes}


def build_asset_memory(notes: list[dict[str, Any]], built_at: str) -> dict[str, Any]:
    asset_hits: Counter[str] = Counter()
    asset_episodes: Counter[str] = Counter()
    asset_alias_counts: dict[str, Counter[str]] = defaultdict(Counter)
    asset_meta: dict[str, dict[str, Any]] = {}
    asset_top: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for note in notes:
        seen: set[str] = set()
        for asset in note["asset_views"]:
            key = asset.get("asset_symbol") or asset.get("asset_or_sector")
            if not key:
                continue
            asset_meta[key] = {
                "asset_or_sector": asset.get("asset_or_sector"),
                "asset_symbol": asset.get("asset_symbol"),
                "asset_type": asset.get("asset_type"),
                "mention_kind": asset.get("mention_kind"),
            }
            asset_hits[key] += asset["hit_count"]
            asset_alias_counts[key].update(asset.get("matched_aliases") or {})
            if key not in seen:
                asset_episodes[key] += 1
                seen.add(key)
            asset_top[key].append(
                {
                    "source_id": note["source_id"],
                    "date": note["date"],
                    "title": note["title"],
                    "hit_count": asset["hit_count"],
                    "market_regime": note["market_regime"]["phase_label"],
                    "evidence": asset["evidence"],
                }
            )
    records = []
    top_by_asset = top_records(asset_top, limit=12)
    for key, hits in asset_hits.most_common():
        records.append(
            {
                **asset_meta[key],
                "episode_count": asset_episodes[key],
                "hit_count": hits,
                "alias_counts": dict(asset_alias_counts[key].most_common()),
                "top_episodes": top_by_asset.get(key, []),
            }
        )
    return {"built_at": built_at, "episode_count": len(notes), "assets": records}


def build_rhetoric_memory(notes: list[dict[str, Any]], built_at: str) -> dict[str, Any]:
    pattern_hits: Counter[str] = Counter()
    pattern_episodes: Counter[str] = Counter()
    pattern_top: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for note in notes:
        for pattern in note["rhetorical_patterns"]:
            pid = pattern["pattern_id"]
            pattern_episodes[pid] += 1
            pattern_hits[pid] += pattern["hit_count"]
            pattern_top[pid].append(
                {
                    "source_id": note["source_id"],
                    "date": note["date"],
                    "title": note["title"],
                    "hit_count": pattern["hit_count"],
                    "evidence": pattern["evidence"],
                }
            )
    top_by_pattern = top_records(pattern_top, limit=16)
    patterns = {}
    for pid, spec in RHETORIC_PATTERNS.items():
        if not pattern_episodes[pid]:
            continue
        patterns[pid] = {
            "label": spec["label"],
            "function": spec["function"],
            "keywords": spec["keywords"],
            "episode_count": pattern_episodes[pid],
            "hit_count": pattern_hits[pid],
            "top_episodes": top_by_pattern.get(pid, []),
        }
    return {"built_at": built_at, "episode_count": len(notes), "patterns": patterns}


def write_summary(
    notes: list[dict[str, Any]],
    theme_memory: dict[str, Any],
    asset_memory: dict[str, Any],
    rhetoric_memory: dict[str, Any],
    built_at: str,
) -> None:
    dates = sorted(note["date"] for note in notes if note.get("date"))
    phase_counts = Counter(note["market_regime"]["phase_label"] for note in notes)
    top_themes = sorted(
        theme_memory["themes"].values(), key=lambda row: row["hit_count"], reverse=True
    )[:10]
    top_assets = asset_memory["assets"][:18]
    top_patterns = sorted(
        rhetoric_memory["patterns"].values(), key=lambda row: row["hit_count"], reverse=True
    )[:8]
    lines = [
        "# Zhezhe Corpus Summary",
        "",
        f"- built_at: {built_at}",
        f"- transcript_count: {len(notes)}",
        f"- transcript_date_range: {dates[0] if dates else 'unknown'} to {dates[-1] if dates else 'unknown'}",
        f"- market_regime_counts: {dict(phase_counts)}",
        "",
        "## High-Level Read",
        "",
        "這份 deterministic memory 先把 ASR 逐字稿轉成可檢索索引；它適合做問題路由、找 evidence、抓高頻框架。真正回答時仍要回讀 transcript/article 原文，並把當日 market context 對齊後再下結論。",
        "",
        "## Dominant Themes",
        "",
    ]
    for theme in top_themes:
        lines.append(
            f"- {theme['label']}: episodes={theme['episode_count']}, hits={theme['hit_count']}, top_terms={dict(list(theme['keyword_counts'].items())[:6])}"
        )
    lines.extend(["", "## Top Assets And Sectors", ""])
    for asset in top_assets:
        symbol = asset.get("asset_symbol") or ""
        lines.append(
            f"- {asset['asset_or_sector']} {symbol}: episodes={asset['episode_count']}, hits={asset['hit_count']}, aliases={dict(list(asset['alias_counts'].items())[:5])}"
        )
    lines.extend(["", "## Rhetorical DNA", ""])
    for pattern in top_patterns:
        lines.append(
            f"- {pattern['label']} ({pattern['function']}): episodes={pattern['episode_count']}, hits={pattern['hit_count']}"
        )
    lines.extend(
        [
            "",
            "## Retrieval Rules",
            "",
            "- Live trade questions: fetch current market data, then use `theme_memory.json` and `asset_memory.json` to locate analogous episodes; never answer from old transcript alone.",
            "- Single ticker/sector questions: start from `asset_memory.json`, then open top episode transcripts and `episode_asset_context/<source_id>.json`.",
            "- Style/persona questions: start from `rhetoric_memory.json`, then verify with short transcript snippets.",
            "- Historical call review: use `episode_notes.jsonl` for candidate calls, then compare with later price data manually.",
            "- ASR caveat: duplicate SoundOn feeds can create same-date duplicate transcripts; preserve both source ids but avoid double-counting identical claims in final prose.",
        ]
    )
    (DISTILLED / "corpus_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(args: argparse.Namespace) -> None:
    DISTILLED.mkdir(parents=True, exist_ok=True)
    transcripts = sorted(TRANSCRIPTS.glob("*.md"))
    if args.since:
        transcripts = [p for p in transcripts if p.name[:10] >= args.since]
    if args.until:
        transcripts = [p for p in transcripts if p.name[:10] <= args.until]
    if args.limit:
        transcripts = transcripts[-args.limit :]
    market_context = load_market_context()
    asset_context = load_asset_context()
    assets = load_assets()
    sectors = load_sector_baskets()
    notes = [make_note(p, market_context, asset_context, assets, sectors) for p in transcripts]
    notes.sort(key=lambda row: (row["date"], row["source_id"]))
    built_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    theme_memory = build_theme_memory(notes, built_at)
    asset_memory = build_asset_memory(notes, built_at)
    rhetoric_memory = build_rhetoric_memory(notes, built_at)
    manifest = {
        "built_at": built_at,
        "schema_version": "zhezhe_distilled_v1",
        "transcript_count": len(notes),
        "date_range": [notes[0]["date"], notes[-1]["date"]] if notes else [],
        "outputs": [
            "data/distilled/episode_notes.jsonl",
            "data/distilled/theme_memory.json",
            "data/distilled/asset_memory.json",
            "data/distilled/rhetoric_memory.json",
            "data/distilled/corpus_summary.md",
        ],
    }

    write_jsonl(DISTILLED / "episode_notes.jsonl", notes)
    write_json(DISTILLED / "theme_memory.json", theme_memory)
    write_json(DISTILLED / "asset_memory.json", asset_memory)
    write_json(DISTILLED / "rhetoric_memory.json", rhetoric_memory)
    write_json(DISTILLED / "distillation_manifest.json", manifest)
    write_summary(notes, theme_memory, asset_memory, rhetoric_memory, built_at)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", help="Only include transcripts on/after YYYY-MM-DD.")
    parser.add_argument("--until", help="Only include transcripts on/before YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, help="Only include newest N transcripts after date filters.")
    args = parser.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
