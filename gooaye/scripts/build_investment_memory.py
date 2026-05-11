#!/usr/bin/env python3
"""Build corpus-wide Gooaye investment memory files from transcripts and market context."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THEMES: dict[str, dict[str, Any]] = {
    "valuation": {
        "label": "估值與本益比",
        "keywords": ["本益比", "估值", "評價", "EPS", "便宜", "貴", "目標價", "成長股", "價值投資"],
    },
    "trend_timing": {
        "label": "趨勢、追高與抄底",
        "keywords": ["趨勢", "順勢", "抄底", "追高", "打底", "反彈", "均線", "空頭", "多頭", "突破", "跌破"],
    },
    "position_risk": {
        "label": "部位、停損與資金控管",
        "keywords": ["停損", "停利", "減碼", "加碼", "分批", "部位", "資金", "倉位", "現金", "滿倉"],
    },
    "leverage_derivatives": {
        "label": "槓桿、融資與衍生性商品",
        "keywords": ["槓桿", "融資", "借錢", "期貨", "選擇權", "正2", "反1", "反向", "VIX", "爆倉"],
    },
    "etf_allocation": {
        "label": "ETF、核心配置與長期投資",
        "keywords": ["ETF", "0050", "台灣50", "指數", "被動", "定期定額", "配置", "配息", "複利"],
    },
    "macro_liquidity": {
        "label": "宏觀、利率、匯率與流動性",
        "keywords": ["利率", "升息", "降息", "通膨", "美債", "美元", "匯率", "外資", "資金", "流動性", "聯準會"],
    },
    "semis_tsmc_ai": {
        "label": "台積電、半導體與 AI",
        "keywords": ["台積電", "半導體", "晶圓", "先進製程", "AI", "伺服器", "輝達", "NVDA", "TSMC", "TSM"],
    },
    "crypto_high_beta": {
        "label": "比特幣與高波動題材",
        "keywords": ["比特幣", "加密", "特斯拉", "迷因", "投機", "泡沫", "高波動"],
    },
    "life_money": {
        "label": "理財、職涯與生活決策",
        "keywords": ["工作", "薪水", "轉職", "創業", "買房", "租房", "家庭", "小孩", "人生", "焦慮"],
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_snippet(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def find_snippets(text: str, keywords: list[str], *, limit: int = 3, context: int = 80) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), text, flags=re.IGNORECASE):
            start = max(0, match.start() - context)
            end = min(len(text), match.end() + context)
            key = (start, keyword)
            if key in seen:
                continue
            seen.add(key)
            snippets.append(
                {
                    "keyword": keyword,
                    "offset": match.start(),
                    "snippet": normalize_snippet(text[start:end]),
                }
            )
            if len(snippets) >= limit:
                return snippets
    return snippets


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def market_regime(markets: dict[str, Any]) -> str:
    twii = markets.get("^TWII") or markets.get("2330.TW")
    soxx = markets.get("SOXX")
    qqq = markets.get("QQQ") or markets.get("^IXIC")
    candidates = [snap for snap in [twii, soxx, qqq] if snap]
    if not candidates:
        return "unknown"
    rets20 = [snap.get("ret_20d_pct") for snap in candidates if snap.get("ret_20d_pct") is not None]
    rets60 = [snap.get("ret_60d_pct") for snap in candidates if snap.get("ret_60d_pct") is not None]
    if any(value <= -15 for value in rets20) or any(value <= -25 for value in rets60):
        return "risk-off / drawdown"
    if any(value >= 15 for value in rets20) or any(value >= 25 for value in rets60):
        return "risk-on / momentum"
    if any(value <= -7 for value in rets20):
        return "weak / corrective"
    if any(value >= 7 for value in rets20):
        return "constructive / rising"
    return "mixed / range"


def load_market_records(data_dir: Path) -> dict[int, dict[str, Any]]:
    path = data_dir / "market_context" / "episode_market_context.jsonl"
    if not path.exists():
        return {}
    records: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            records[int(item["episode"])] = item
    return records


def latest_price_snapshot(data_dir: Path) -> dict[str, Any]:
    price_dir = data_dir / "market_context" / "prices"
    if not price_dir.exists():
        return {}
    output: dict[str, Any] = {}
    for path in sorted(price_dir.glob("*.json")):
        series = read_json(path)
        if not series:
            continue
        last = series[-1]
        def ret(days: int) -> float | None:
            if len(series) <= days:
                return None
            base = series[-1 - days]["close"]
            return round((last["close"] / base - 1.0) * 100.0, 2) if base else None
        output[path.stem.replace("INDEX_", "^")] = {
            "date": last["date"],
            "close": round(last["close"], 4),
            "ret_1d_pct": ret(1),
            "ret_5d_pct": ret(5),
            "ret_20d_pct": ret(20),
            "ret_60d_pct": ret(60),
        }
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Gooaye corpus-wide investment memory files.")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--top-episodes", type=int, default=30)
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    out_dir: Path = args.out_dir or data_dir / "distilled"
    episodes = read_json(data_dir / "source" / "episodes.json")
    market_records = load_market_records(data_dir)

    theme_memory: dict[str, Any] = {
        key: {
            "label": theme["label"],
            "keywords": theme["keywords"],
            "episode_count": 0,
            "hit_count": 0,
            "keyword_counts": Counter(),
            "top_episodes": [],
        }
        for key, theme in THEMES.items()
    }
    episode_records: list[dict[str, Any]] = []
    theme_episode_scores: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)

    for ep in episodes:
        number = int(ep["number"])
        path = data_dir / "transcripts" / f"EP{number:03d}.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        market_record = market_records.get(number, {})
        theme_hits: dict[str, Any] = {}

        for key, theme in THEMES.items():
            keyword_counts = Counter({kw: text.count(kw) for kw in theme["keywords"]})
            keyword_counts = Counter({kw: count for kw, count in keyword_counts.items() if count})
            hit_count = sum(keyword_counts.values())
            if not hit_count:
                continue
            snippets = find_snippets(text, list(keyword_counts.keys()), limit=3)
            for snippet in snippets:
                snippet["line"] = line_for_offset(text, int(snippet["offset"]))
                snippet["file"] = str(path.relative_to(data_dir.parents[0]))
            theme_hits[key] = {
                "label": theme["label"],
                "hit_count": hit_count,
                "keyword_counts": dict(keyword_counts),
                "snippets": snippets,
            }
            memory = theme_memory[key]
            memory["episode_count"] += 1
            memory["hit_count"] += hit_count
            memory["keyword_counts"].update(keyword_counts)
            theme_episode_scores[key].append(
                (
                    hit_count,
                    {
                        "episode": number,
                        "date": ep.get("date"),
                        "title": ep.get("display_title") or ep.get("title"),
                        "hit_count": hit_count,
                        "market_regime": market_regime(market_record.get("markets", {})),
                    },
                )
            )

        if theme_hits:
            episode_records.append(
                {
                    "episode": number,
                    "date": ep.get("date"),
                    "title": ep.get("display_title") or ep.get("title"),
                    "market_regime": market_regime(market_record.get("markets", {})),
                    "markets": market_record.get("markets", {}),
                    "themes": theme_hits,
                }
            )

    for key, scored in theme_episode_scores.items():
        top = [item for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[: args.top_episodes]]
        theme_memory[key]["top_episodes"] = top
        theme_memory[key]["keyword_counts"] = dict(theme_memory[key]["keyword_counts"].most_common())

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "episode_investment_memory.jsonl").open("w", encoding="utf-8") as handle:
        for record in episode_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_json(
        out_dir / "theme_memory.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "episode_count": len(episode_records),
            "themes": theme_memory,
        },
    )
    write_json(
        out_dir / "latest_market_snapshot.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "prices": latest_price_snapshot(data_dir),
        },
    )
    print(f"Wrote {len(episode_records)} episode records and {len(theme_memory)} themes to {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
