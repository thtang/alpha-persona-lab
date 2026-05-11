#!/usr/bin/env python3
"""Extract and dedupe 財經皓角 jokes/asides from notes and transcripts.

Notes are the high-precision index because the Digital Garden author labels
`皓哥笑話` sections manually. Transcripts are the evidence layer: they add
original surrounding context and catch unlabeled humor candidates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NOTES_DIR = ROOT / "data" / "notes"
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
OUT_PATH = ROOT / "data" / "source" / "jokes_inventory.jsonl"
RAW_PATH = ROOT / "data" / "source" / "jokes_candidates_raw.jsonl"
SUMMARY_PATH = ROOT / "data" / "source" / "jokes_summary.json"


TIMESTAMP_RE = re.compile(r"(\d{1,2}):(\d{2})")
HEADING_TS_RE = re.compile(r"^(#{1,2})[ \t]+(\d{1,2}:\d{2})(?:[ \t]+([^\n]+))?[ \t]*$", re.M)

HUMOR_MARKERS = {
    "explicit": [
        "笑話",
        "開玩笑",
        "好笑",
        "梗",
        "段子",
        "哏",
        "地獄",
        "吐槽",
    ],
    "absurd_turn": [
        "怎麼可能",
        "你以為",
        "結果",
        "反而",
        "忽然",
        "突然",
        "沒有啦",
        "不是啦",
        "你知道嗎",
    ],
    "persona": [
        "馬桶",
        "TOTO",
        "曹操",
        "唐僧",
        "女兒國",
        "取經",
        "加藤鷹",
        "金瓶梅",
        "皮卡丘",
        "女孩子",
        "女生",
        "學妹",
        "學弟",
        "持久",
        "交往",
        "約會",
        "大一",
        "大二",
        "大三",
        "大四",
        "關稅帝君",
        "三觀",
        "關我什麼事",
        "關你什麼事",
        "關他什麼事",
        "今日割五城",
        "明日割十城",
        "諧音",
    ],
    "market_analogy": [
        "投資人",
        "新手",
        "牛市",
        "熊市",
        "槓桿",
        "持股",
        "持有",
        "韭菜",
        "泡沫",
        "追高",
        "殺低",
    ],
    "return_to_topic": [
        "OK",
        "好",
        "回過頭",
        "不管怎麼說",
        "拉回來",
        "講回",
        "所以",
    ],
}

STRONG_HUMOR_MARKERS = {
    "馬桶",
    "TOTO",
    "曹操",
    "唐僧",
    "女兒國",
    "取經",
    "加藤鷹",
    "金瓶梅",
    "皮卡丘",
    "女孩子",
    "女生",
    "學妹",
    "學弟",
    "持久",
    "交往",
    "約會",
    "大一",
    "大二",
    "大三",
    "大四",
    "關稅帝君",
    "三觀",
    "關我什麼事",
    "關你什麼事",
    "關他什麼事",
    "今日割五城",
    "明日割十城",
    "諧音",
}


@dataclass
class TranscriptChunk:
    date: str
    source_file: str
    timestamp: str
    seconds: int
    heading: str
    level: str
    text: str


def time_to_sec(value: str | None) -> int | None:
    if not value:
        return None
    match = TIMESTAMP_RE.search(value)
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def sec_to_time(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def section_between(text: str, start_heading: str) -> str:
    start = re.search(rf"^# {re.escape(start_heading)}\s*$", text, flags=re.M)
    if not start:
        return ""
    rest = text[start.end() :]
    end = re.search(r"^# [^\n]+", rest, flags=re.M)
    return rest[: end.start()] if end else rest


def clean_lines(block: str) -> list[str]:
    lines = []
    for line in block.splitlines():
        line = line.strip()
        if not line or line == "-":
            continue
        line = re.sub(r"^- ", "", line).strip()
        if line:
            lines.append(line)
    return lines


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip()
    return text


def plain_text(text: str) -> str:
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", lambda m: m.group(0).split("](")[0][1:], text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*]\s*", "", text, flags=re.M)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", plain_text(text)).lower()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    return text


def ngrams(value: str, n: int = 3) -> set[str]:
    value = normalize_text(value)
    if len(value) <= n:
        return {value} if value else set()
    return {value[i : i + n] for i in range(len(value) - n + 1)}


def similarity(left: str, right: str) -> float:
    a = ngrams(left)
    b = ngrams(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def stable_hash(value: str, size: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:size]


def marker_hits(text: str, marker_group: str) -> list[str]:
    return [word for word in HUMOR_MARKERS[marker_group] if word in text]


def humor_score(text: str) -> tuple[int, dict[str, list[str]]]:
    hits = {group: marker_hits(text, group) for group in HUMOR_MARKERS}
    strong_hits = [word for word in STRONG_HUMOR_MARKERS if word in text]
    score = 0
    score += min(5, len(hits["explicit"]) * 4)
    score += min(5, len(strong_hits) * 2)
    if hits["explicit"] or strong_hits:
        score += min(2, len(hits["absurd_turn"]))
    if strong_hits and hits["market_analogy"]:
        score += 2
    if hits["explicit"] and hits["return_to_topic"]:
        score += 1
    if 80 <= len(plain_text(text)) <= 1400:
        score += 1
    if strong_hits:
        hits["strong"] = strong_hits
    return score, {key: value for key, value in hits.items() if value}


def has_humor_signal(text: str, hits: dict[str, list[str]]) -> bool:
    if hits.get("explicit"):
        return True
    if hits.get("strong"):
        return True
    if re.search(r"不是.*是|像.*一樣|哪三觀|帝君|割五城|打臉自己|沖康", text):
        return True
    return False


def classify_humor(block: str) -> str:
    if re.search(r"持久|女兒國|女生|學妹|學弟|女孩子|感情|取經|加藤鷹|交往|約會", block):
        return "sexual_pun"
    if re.search(r"曹操|歷史|考古|唐僧", block):
        return "absurd_history"
    if re.search(r"馬桶|TOTO|靜電吸盤|免治", block):
        return "industry_absurdity"
    if re.search(r"川普|政治|國家|戰爭|關稅|MAGA|帝君|割五城", block):
        return "political_irony"
    if re.search(r"投資人|市場|牛市|槓桿|新手|韭菜|泡沫", block):
        return "analogy"
    if re.search(r"諧音|不是.*是|金瓶梅|JP", block):
        return "wordplay"
    return "other"


def investment_relevance(block: str) -> str:
    if re.search(r"所以我建議|我不建議|應該|不要|紀律|槓桿|投資也是如此|持股|部位", block):
        return "direct_rule_wrapper"
    if re.search(r"投資人|市場|牛市|熊市|槓桿|風險|產業|AI|半導體|泡沫|追高", block):
        return "analogy_for_behavior"
    return "weak_style_only"


def sensitive(block: str) -> bool:
    return bool(
        re.search(
            r"女生|女孩子|女兒國|持久|感情|取經|不要跑|學妹|加藤鷹|交往|約會|身體|胸",
            block,
        )
    )


def parse_note_jokes(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    date = path.stem
    section = section_between(text, "皓哥笑話")
    if not section:
        return []
    parts = re.split(r"^## ", section, flags=re.M)
    rows: list[dict[str, Any]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = clean_lines(part)
        if not lines:
            continue
        heading = lines[0]
        body = "\n".join(lines[1:])
        timestamp_match = TIMESTAMP_RE.search(heading)
        combined = f"{heading}\n{body}"
        rows.append(
            {
                "candidate_source": "note_labeled",
                "date": date,
                "timestamp": timestamp_match.group(0) if timestamp_match else None,
                "seconds": time_to_sec(timestamp_match.group(0)) if timestamp_match else None,
                "source_kinds": ["note"],
                "note": {
                    "source_file": str(path.relative_to(ROOT)),
                    "heading": heading,
                    "timestamp": timestamp_match.group(0) if timestamp_match else None,
                    "text_preview": plain_text(body)[:900],
                },
                "transcript": None,
                "canonical_text": plain_text(combined),
                "confidence": "high",
                "detection": {
                    "method": "explicit_note_section",
                    "signals": ["# 皓哥笑話"],
                },
            }
        )
    return rows


def parse_transcript(path: Path) -> list[TranscriptChunk]:
    text = strip_frontmatter(path.read_text(encoding="utf-8"))
    date = path.stem
    matches = list(HEADING_TS_RE.finditer(text))
    chunks: list[TranscriptChunk] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = plain_text(text[start:end])
        if not body:
            continue
        timestamp = match.group(2)
        title = (match.group(3) or "").strip()
        chunks.append(
            TranscriptChunk(
                date=date,
                source_file=str(path.relative_to(ROOT)),
                timestamp=timestamp,
                seconds=time_to_sec(timestamp) or 0,
                heading=title,
                level=match.group(1),
                text=body,
            )
        )
    return chunks


def load_transcripts() -> dict[str, list[TranscriptChunk]]:
    by_date: dict[str, list[TranscriptChunk]] = {}
    for path in sorted(TRANSCRIPTS_DIR.glob("*.md")):
        by_date[path.stem] = parse_transcript(path)
    return by_date


def chunks_near(
    chunks: list[TranscriptChunk],
    seconds: int | None,
    note_text: str,
    window_before: int = 120,
    window_after: int = 150,
) -> list[tuple[TranscriptChunk, float, int]]:
    if seconds is None:
        return []
    candidates: list[tuple[TranscriptChunk, float, int]] = []
    for chunk in chunks:
        delta = chunk.seconds - seconds
        if -window_before <= delta <= window_after:
            sim = similarity(note_text, f"{chunk.heading} {chunk.text}")
            score, hits = humor_score(f"{chunk.heading} {chunk.text}")
            if sim >= 0.035 or (
                abs(delta) <= 45 and score >= 5 and has_humor_signal(f"{chunk.heading} {chunk.text}", hits)
            ):
                candidates.append((chunk, sim, score))
    if candidates:
        return candidates
    nearest = min(chunks, key=lambda item: abs(item.seconds - seconds), default=None)
    if nearest and abs(nearest.seconds - seconds) <= 180:
        score, hits = humor_score(f"{nearest.heading} {nearest.text}")
        sim = similarity(note_text, f"{nearest.heading} {nearest.text}")
        if sim >= 0.04 or (score >= 6 and has_humor_signal(f"{nearest.heading} {nearest.text}", hits)):
            return [(nearest, sim, score)]
    return []


def transcript_payload(matches: list[tuple[TranscriptChunk, float, int]]) -> dict[str, Any] | None:
    if not matches:
        return None
    chunks = [item[0] for item in sorted(matches, key=lambda item: item[0].seconds)]
    text = "\n".join(f"[{chunk.timestamp}] {chunk.text}" for chunk in chunks)
    scores = [item[2] for item in matches]
    sims = [item[1] for item in matches]
    return {
        "source_file": chunks[0].source_file,
        "start_timestamp": chunks[0].timestamp,
        "end_timestamp": chunks[-1].timestamp,
        "text_preview": plain_text(text)[:1400],
        "matched_chunk_count": len(chunks),
        "match_similarity_max": round(max(sims), 4) if sims else 0.0,
        "humor_score_max": max(scores) if scores else 0,
    }


def attach_transcript_context(
    note_rows: list[dict[str, Any]],
    transcripts_by_date: dict[str, list[TranscriptChunk]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for row in note_rows:
        chunks = transcripts_by_date.get(row["date"], [])
        note_text = f"{row.get('note', {}).get('heading', '')} {row.get('note', {}).get('text_preview', '')}"
        matches = chunks_near(chunks, row.get("seconds"), note_text)
        payload = transcript_payload(matches)
        if payload:
            row["transcript"] = payload
            row["source_kinds"] = ["note", "transcript"]
            row["canonical_text"] = plain_text(
                f"{row.get('note', {}).get('heading', '')}\n{payload.get('text_preview', '')}"
            )
            row["detection"] = {
                "method": "note_anchor_transcript_window",
                "signals": ["# 皓哥笑話", "timestamp_nearby_transcript"],
            }
        merged.append(row)
    return merged


def transcript_only_candidates(
    transcripts_by_date: dict[str, list[TranscriptChunk]],
    anchored_rows: list[dict[str, Any]],
    min_score: int,
) -> list[dict[str, Any]]:
    covered: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in anchored_rows:
        date = str(row["date"])
        seconds = row.get("seconds")
        if isinstance(seconds, int):
            covered[date].append((seconds - 130, seconds + 160))

    rows: list[dict[str, Any]] = []
    for date, chunks in transcripts_by_date.items():
        for chunk in chunks:
            if any(start <= chunk.seconds <= end for start, end in covered.get(date, [])):
                continue
            text = f"{chunk.heading}\n{chunk.text}"
            score, hits = humor_score(text)
            if score < min_score:
                continue
            if not has_humor_signal(text, hits):
                continue
            rows.append(
                {
                    "candidate_source": "transcript_heuristic",
                    "date": date,
                    "timestamp": chunk.timestamp,
                    "seconds": chunk.seconds,
                    "source_kinds": ["transcript"],
                    "note": None,
                    "transcript": {
                        "source_file": chunk.source_file,
                        "start_timestamp": chunk.timestamp,
                        "end_timestamp": chunk.timestamp,
                        "text_preview": plain_text(text)[:1400],
                        "matched_chunk_count": 1,
                        "match_similarity_max": None,
                        "humor_score_max": score,
                    },
                    "canonical_text": plain_text(text),
                    "confidence": "medium" if score >= min_score + 2 else "low",
                    "detection": {
                        "method": "transcript_marker_heuristic",
                        "signals": hits,
                    },
                }
            )
    return rows


def merge_rows(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged["source_kinds"] = sorted(set(base.get("source_kinds", [])) | set(incoming.get("source_kinds", [])))
    if not merged.get("note") and incoming.get("note"):
        merged["note"] = incoming["note"]
    if not merged.get("transcript") and incoming.get("transcript"):
        merged["transcript"] = incoming["transcript"]
    elif merged.get("transcript") and incoming.get("transcript"):
        left = merged["transcript"]
        right = incoming["transcript"]
        if len(str(right.get("text_preview", ""))) > len(str(left.get("text_preview", ""))):
            merged["transcript"] = right
    merged["canonical_text"] = plain_text(
        "\n".join(
            str(part)
            for part in [
                merged.get("canonical_text", ""),
                incoming.get("canonical_text", ""),
            ]
            if part
        )
    )[:2400]
    confidence_order = {"low": 0, "medium": 1, "high": 2}
    if confidence_order.get(str(incoming.get("confidence")), 0) > confidence_order.get(str(merged.get("confidence")), 0):
        merged["confidence"] = incoming.get("confidence")
    merged["cluster_size"] = int(base.get("cluster_size", 1)) + int(incoming.get("cluster_size", 1))
    return merged


def is_duplicate(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["date"] != right["date"]:
        return False
    left_heading = str((left.get("note") or {}).get("heading") or "")
    right_heading = str((right.get("note") or {}).get("heading") or "")
    if left_heading and right_heading and left_heading != right_heading and similarity(left_heading, right_heading) < 0.35:
        return False
    left_sec = left.get("seconds")
    right_sec = right.get("seconds")
    time_close = isinstance(left_sec, int) and isinstance(right_sec, int) and abs(left_sec - right_sec) <= 130
    sim = similarity(str(left.get("canonical_text", "")), str(right.get("canonical_text", "")))
    if time_close and sim >= 0.035:
        return True
    if time_close and set(left.get("source_kinds", [])) != set(right.get("source_kinds", [])):
        return True
    return sim >= 0.55


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (str(item["date"]), int(item.get("seconds") or 999999))):
        merged = False
        for index, existing in enumerate(output):
            if is_duplicate(existing, row):
                output[index] = merge_rows(existing, row)
                merged = True
                break
        if not merged:
            row["cluster_size"] = 1
            output.append(row)
    return output


def finalize(row: dict[str, Any]) -> dict[str, Any]:
    text = str(row.get("canonical_text") or "")
    seconds = row.get("seconds")
    timestamp = sec_to_time(seconds) if isinstance(seconds, int) else row.get("timestamp")
    fingerprint_basis = f"{row['date']}:{timestamp}:{normalize_text(text)[:160]}"
    return {
        "joke_id": f"yutinghao-{row['date']}-{timestamp or 'na'}-{stable_hash(fingerprint_basis, 8)}",
        "date": row["date"],
        "timestamp": timestamp,
        "source_kinds": row.get("source_kinds", []),
        "note": row.get("note"),
        "transcript": row.get("transcript"),
        "humor_type_guess": classify_humor(text),
        "investment_relevance_guess": investment_relevance(text),
        "is_sensitive_guess": sensitive(text),
        "confidence": row.get("confidence", "low"),
        "text_chars": len(text),
        "text_preview": text[:900],
        "detection": row.get("detection", {}),
        "dedupe": {
            "cluster_size": row.get("cluster_size", 1),
            "normalized_fingerprint": stable_hash(normalize_text(text)[:260], 16),
        },
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-transcript-score", type=int, default=5)
    args = parser.parse_args()

    note_rows: list[dict[str, Any]] = []
    for path in sorted(NOTES_DIR.glob("*.md")):
        note_rows.extend(parse_note_jokes(path))

    transcripts_by_date = load_transcripts()
    anchored_rows = attach_transcript_context(note_rows, transcripts_by_date)
    transcript_rows = transcript_only_candidates(transcripts_by_date, anchored_rows, args.min_transcript_score)
    raw_rows = anchored_rows + transcript_rows
    final_rows = [finalize(row) for row in dedupe(raw_rows)]

    write_jsonl(RAW_PATH, raw_rows)
    write_jsonl(OUT_PATH, final_rows)

    summary = {
        "note_labeled_candidates": len(note_rows),
        "transcript_heuristic_candidates": len(transcript_rows),
        "raw_candidates": len(raw_rows),
        "deduped_jokes": len(final_rows),
        "with_transcript_context": sum(1 for row in final_rows if "transcript" in row.get("source_kinds", [])),
        "source_kind_counts": Counter("+".join(row.get("source_kinds", [])) for row in final_rows),
        "humor_type_counts": Counter(row["humor_type_guess"] for row in final_rows),
        "investment_relevance_counts": Counter(row["investment_relevance_guess"] for row in final_rows),
        "sensitive_count": sum(1 for row in final_rows if row["is_sensitive_guess"]),
        "outputs": {
            "inventory": str(OUT_PATH),
            "raw_candidates": str(RAW_PATH),
            "summary": str(SUMMARY_PATH),
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=dict) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
