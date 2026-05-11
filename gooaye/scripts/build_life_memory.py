#!/usr/bin/env python3
"""Build corpus-wide Gooaye life/QA worldview memory files from transcripts."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THEMES: dict[str, dict[str, Any]] = {
    "long_distance_relationship": {
        "label": "遠距、異地與關係收斂",
        "keywords": ["遠距", "遠距離", "異地", "分隔兩地", "分散兩地", "外派", "當兵", "見面"],
    },
    "relationship": {
        "label": "感情、交往與分手判斷",
        "keywords": ["戀愛", "感情", "分手", "交往", "同居", "伴侶", "另一半", "女朋友", "男朋友", "男友", "女友"],
    },
    "marriage_family": {
        "label": "婚姻、家庭與長期承諾",
        "keywords": ["結婚", "婚姻", "求婚", "登記", "老婆", "老公", "太太", "先生", "家庭", "家人"],
    },
    "communication_conflict": {
        "label": "溝通、陪伴與衝突",
        "keywords": ["溝通", "抱怨", "聆聽", "陪伴", "尊重", "控制狂", "吵架", "衝突", "包容", "付出"],
    },
    "children_parenting": {
        "label": "小孩、育兒與家庭責任",
        "keywords": ["小孩", "孩子", "兒子", "女兒", "爸爸", "媽媽", "育兒", "生小孩", "二寶", "安全感", "教育"],
    },
    "work_career": {
        "label": "工作、職涯與自我定位",
        "keywords": ["工作", "職涯", "轉職", "離職", "薪水", "同事", "主管", "創業", "上班", "職場", "工程師"],
    },
    "money_housing": {
        "label": "金錢、買房與生活壓力",
        "keywords": ["買房", "房貸", "租房", "預售屋", "本金", "財務", "存錢", "收入", "支出", "房子", "壓力"],
    },
    "autonomy_values": {
        "label": "自主、價值觀與人生選擇",
        "keywords": ["自由", "選擇", "價值觀", "舒服", "快樂", "成功", "人生", "不要浪費時間", "自己想法", "盲從"],
    },
    "anxiety_health": {
        "label": "焦慮、健康與心理負荷",
        "keywords": ["焦慮", "壓力", "健康", "睡眠", "失眠", "憂鬱", "心理", "醫師", "運動", "減肥"],
    },
    "decision_framework": {
        "label": "決策、取捨與停損",
        "keywords": ["條件", "取捨", "成本", "代價", "機會成本", "期限", "風險", "思考", "準備", "停損"],
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_snippet(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def count_keyword(text: str, keyword: str) -> int:
    return len(re.findall(re.escape(keyword), text, flags=re.IGNORECASE))


def find_snippets(text: str, keywords: list[str], *, limit: int = 4, context: int = 95) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    seen_offsets: set[int] = set()
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), text, flags=re.IGNORECASE):
            if any(abs(match.start() - offset) < context for offset in seen_offsets):
                continue
            seen_offsets.add(match.start())
            start = max(0, match.start() - context)
            end = min(len(text), match.end() + context)
            snippets.append(
                {
                    "keyword": keyword,
                    "offset": match.start(),
                    "line": line_for_offset(text, match.start()),
                    "snippet": normalize_snippet(text[start:end]),
                }
            )
            if len(snippets) >= limit:
                return snippets
    return snippets


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def year_bucket(date_text: str | None) -> str:
    if not date_text:
        return "unknown"
    return date_text[:4]


def episode_sort_key(item: dict[str, Any]) -> tuple[str, int]:
    return (item.get("date") or "", int(item.get("episode") or 0))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Gooaye corpus-wide life/QA memory files.")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--top-episodes", type=int, default=30)
    parser.add_argument("--recent-episodes", type=int, default=16)
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    out_dir: Path = args.out_dir or data_dir / "distilled"
    episodes = read_json(data_dir / "source" / "episodes.json")

    theme_memory: dict[str, Any] = {
        key: {
            "label": theme["label"],
            "keywords": theme["keywords"],
            "episode_count": 0,
            "hit_count": 0,
            "keyword_counts": Counter(),
            "year_counts": Counter(),
            "top_episodes": [],
            "recent_episodes": [],
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
        theme_hits: dict[str, Any] = {}

        for key, theme in THEMES.items():
            keyword_counts = Counter(
                {keyword: count_keyword(text, keyword) for keyword in theme["keywords"]}
            )
            keyword_counts = Counter({kw: count for kw, count in keyword_counts.items() if count})
            hit_count = sum(keyword_counts.values())
            if not hit_count:
                continue

            snippets = find_snippets(text, list(keyword_counts.keys()), limit=4)
            for snippet in snippets:
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
            memory["year_counts"].update([year_bucket(ep.get("date"))])
            theme_episode_scores[key].append(
                (
                    hit_count,
                    {
                        "episode": number,
                        "date": ep.get("date"),
                        "title": ep.get("display_title") or ep.get("title"),
                        "hit_count": hit_count,
                    },
                )
            )

        if theme_hits:
            episode_records.append(
                {
                    "episode": number,
                    "date": ep.get("date"),
                    "title": ep.get("display_title") or ep.get("title"),
                    "themes": theme_hits,
                }
            )

    for key, scored in theme_episode_scores.items():
        top = [item for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[: args.top_episodes]]
        recent_pool = [item for _, item in scored if item.get("date")]
        recent = sorted(recent_pool, key=episode_sort_key, reverse=True)[: args.recent_episodes]
        theme_memory[key]["top_episodes"] = top
        theme_memory[key]["recent_episodes"] = recent
        theme_memory[key]["keyword_counts"] = dict(theme_memory[key]["keyword_counts"].most_common())
        theme_memory[key]["year_counts"] = dict(sorted(theme_memory[key]["year_counts"].items()))

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "episode_life_memory.jsonl").open("w", encoding="utf-8") as handle:
        for record in episode_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_json(
        out_dir / "life_theme_memory.json",
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "episode_count": len(episode_records),
            "themes": theme_memory,
        },
    )
    print(f"Wrote {len(episode_records)} episode life records and {len(theme_memory)} themes to {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
