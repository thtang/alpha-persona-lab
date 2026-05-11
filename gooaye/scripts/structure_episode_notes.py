#!/usr/bin/env python3
"""Prepare and validate per-episode structured Gooaye extraction notes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TARGET_SYMBOLS = ["^TWII", "2330.TW", "TSM", "SOXX", "QQQ", "NVDA"]
ACTION_BIASES = {"buy", "sell", "hold", "hedge", "wait", "size-down", "rotate", "unknown"}
VIEWS = {"bullish", "bearish", "neutral", "conditional"}
TIME_HORIZONS = {"intraday", "swing", "medium-term", "long-term", "unclear"}
CONFIDENCES = {"high", "medium", "low"}
ACTION_BIAS_ALIASES = {
    "accumulate": "buy",
    "add": "buy",
    "buying": "buy",
    "conditional": "wait",
    "de-risk": "size-down",
    "decrease": "size-down",
    "increase": "buy",
    "reduce": "size-down",
    "sell down": "size-down",
    "size_down": "size-down",
    "size down": "size-down",
    "trim": "size-down",
    "watch": "wait",
    "watchlist": "wait",
    "觀望": "wait",
    "等待": "wait",
    "買進": "buy",
    "加碼": "buy",
    "賣出": "sell",
    "減碼": "size-down",
    "避險": "hedge",
    "輪動": "rotate",
}
VIEW_ALIASES = {
    "positive": "bullish",
    "bull": "bullish",
    "buy": "bullish",
    "negative": "bearish",
    "bear": "bearish",
    "sell": "bearish",
    "hold": "neutral",
    "wait": "conditional",
    "mixed": "conditional",
    "unclear": "neutral",
    "unknown": "neutral",
    "看多": "bullish",
    "偏多": "bullish",
    "看空": "bearish",
    "偏空": "bearish",
    "中性": "neutral",
    "觀望": "conditional",
}
TIME_HORIZON_ALIASES = {
    "short-term": "swing",
    "short term": "swing",
    "near-term": "swing",
    "near term": "swing",
    "mid-term": "medium-term",
    "mid term": "medium-term",
    "medium term": "medium-term",
    "long term": "long-term",
    "短線": "swing",
    "中期": "medium-term",
    "長期": "long-term",
}
CONFIDENCE_ALIASES = {
    "strong": "high",
    "certain": "high",
    "moderate": "medium",
    "normal": "medium",
    "weak": "low",
    "uncertain": "low",
    "高": "high",
    "中": "medium",
    "低": "low",
}
REQUIRED_TOP_LEVEL = [
    "episode",
    "date",
    "title",
    "market_regime",
    "topics",
    "investment_logic",
    "trade_observations",
    "qa_views",
    "open_questions",
]


SYSTEM_PROMPT = """You extract structured Gooaye episode notes.
Return JSON only. Do not impersonate the speaker. Use third-person wording.
This is not a summary task: classify reusable decision rules, asset observations, non-investing QA views, and open questions.
Do not invent missing content."""


USER_PROMPT_TEMPLATE = """Convert this one Gooaye episode into a JSON object matching the schema.

Inputs:
EPISODE_METADATA:
{episode_metadata}

MARKET_CONTEXT:
{market_context}

TRANSCRIPT:
{transcript}

Output fields:
- episode: copy EPISODE_METADATA.episode exactly.
- date: copy EPISODE_METADATA.date exactly.
- title: copy EPISODE_METADATA.title exactly.
- market_regime: one sentence using objective market numbers first, then transcript mood only as support.
- topics: 3-8 short retrieval tags.
- investment_logic: decision rules with claim, trigger, action_bias, risk_control, evidence, confidence.
- trade_observations: asset/sector directional views with asset_or_sector, view, time_horizon, reasoning, market_alignment, is_joke_or_aside.
- qa_views: non-investing views with question_theme, viewpoint, principle, tone, evidence.
- open_questions: unresolved issues later episodes can revisit.

Rules:
1. Output JSON only. No Markdown.
2. Do not impersonate Gooaye. Write "他..." or "依本集脈絡，他..." in Chinese fields.
3. The top-level object must include episode, date, title, market_regime, topics, investment_logic, trade_observations, qa_views, and open_questions.
4. action_bias must be exactly one of: buy, sell, hold, hedge, wait, size-down, rotate, unknown.
5. view must be exactly one of: bullish, bearish, neutral, conditional.
6. time_horizon must be exactly one of: intraday, swing, medium-term, long-term, unclear.
7. confidence must be exactly one of: high, medium, low.
8. Never use hold as trade_observations[].view; use neutral for no directional edge, or conditional when the view depends on a trigger.
9. Never use conditional as investment_logic[].action_bias; use wait or unknown when no concrete action bias is available.
10. Evidence must cite episode/date and stay under 200 Chinese characters.
11. Mark jokes, throwaway comments, or sponsor-like asides with is_joke_or_aside: true.
12. If a category has no real content, return an empty array. Do not fill by guessing.
13. Separate market description, his own positioning, listener advice, and jokes."""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def iter_jsonl(path: Path) -> list[Any]:
    records: list[Any] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
    return records


def load_market_records(data_dir: Path) -> dict[int, dict[str, Any]]:
    path = data_dir / "market_context" / "episode_market_context.jsonl"
    if not path.exists():
        return {}
    records: dict[int, dict[str, Any]] = {}
    for item in iter_jsonl(path):
        records[int(item["episode"])] = item
    return records


def compact_market_context(markets: dict[str, Any]) -> dict[str, Any]:
    return {symbol: markets[symbol] for symbol in TARGET_SYMBOLS if symbol in markets}


def select_episodes(
    episodes: list[dict[str, Any]],
    *,
    episode_numbers: set[int] | None,
    from_episode: int | None,
    to_episode: int | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for episode in episodes:
        number = int(episode["number"])
        if episode_numbers is not None and number not in episode_numbers:
            continue
        if from_episode is not None and number < from_episode:
            continue
        if to_episode is not None and number > to_episode:
            continue
        selected.append(episode)
        if limit and len(selected) >= limit:
            break
    return selected


def metadata_for_episode(ep: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode": int(ep["number"]),
        "date": ep.get("date") or "",
        "title": ep.get("display_title") or ep.get("title") or "",
        "official_summary": ep.get("summary") or ep.get("description") or "",
    }


def load_episode_metadata(data_dir: Path) -> dict[str, dict[str, Any]]:
    path = data_dir / "source" / "episodes.json"
    if not path.exists():
        return {}
    metadata_by_id: dict[str, dict[str, Any]] = {}
    for ep in read_json(path):
        metadata = metadata_for_episode(ep)
        metadata_by_id[f"EP{int(metadata['episode']):03d}"] = metadata
    return metadata_by_id


def build_user_prompt(metadata: dict[str, Any], market_context: dict[str, Any], transcript: str) -> str:
    return USER_PROMPT_TEMPLATE.format(
        episode_metadata=json.dumps(metadata, ensure_ascii=False, indent=2),
        market_context=json.dumps(market_context, ensure_ascii=False, indent=2),
        transcript=transcript,
    )


def responses_batch_request(
    *,
    custom_id: str,
    model: str,
    user_prompt: str,
    schema: dict[str, Any],
    max_output_tokens: int,
) -> dict[str, Any]:
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": model,
            "input": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "gooaye_episode_note",
                    "schema": schema,
                    "strict": True,
                }
            },
            "max_output_tokens": max_output_tokens,
        },
    }


def chat_batch_request(
    *,
    custom_id: str,
    model: str,
    user_prompt: str,
    max_output_tokens: int,
) -> dict[str, Any]:
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": max_output_tokens,
        },
    }


def prepare(args: argparse.Namespace) -> int:
    data_dir: Path = args.data_dir
    episodes = read_json(data_dir / "source" / "episodes.json")
    markets = load_market_records(data_dir)
    schema = read_json(args.schema)
    selected = select_episodes(
        episodes,
        episode_numbers=set(args.episode) if args.episode else None,
        from_episode=args.from_episode,
        to_episode=args.to_episode,
        limit=args.limit,
    )

    records: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for ep in selected:
        number = int(ep["number"])
        transcript_path = data_dir / "transcripts" / f"EP{number:03d}.md"
        if not transcript_path.exists():
            skipped.append({"episode": number, "reason": "missing transcript"})
            continue
        metadata = metadata_for_episode(ep)
        market_context = compact_market_context(markets.get(number, {}).get("markets", {}))
        transcript = transcript_path.read_text(encoding="utf-8")
        user_prompt = build_user_prompt(metadata, market_context, transcript)
        custom_id = f"EP{number:03d}"

        if args.format == "responses_batch":
            record = responses_batch_request(
                custom_id=custom_id,
                model=args.model,
                user_prompt=user_prompt,
                schema=schema,
                max_output_tokens=args.max_output_tokens,
            )
        elif args.format == "chat_batch":
            record = chat_batch_request(
                custom_id=custom_id,
                model=args.model,
                user_prompt=user_prompt,
                max_output_tokens=args.max_output_tokens,
            )
        else:
            record = {
                "custom_id": custom_id,
                "episode": number,
                "input": {
                    "episode_metadata": metadata,
                    "market_context": market_context,
                    "transcript_path": str(transcript_path.relative_to(data_dir.parents[0])),
                    "transcript": transcript,
                },
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
            }
        records.append(record)

    write_jsonl(args.out_path, records)
    write_json(
        args.manifest_path,
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "format": args.format,
            "out_path": str(args.out_path),
            "episode_count": len(records),
            "skipped": skipped,
            "target_symbols": TARGET_SYMBOLS,
            "schema": str(args.schema),
        },
    )
    print(f"Wrote {len(records)} structured extraction input records to {args.out_path}", flush=True)
    if skipped:
        print(f"Skipped {len(skipped)} episodes; see {args.manifest_path}", flush=True)
    return 0


def strip_json_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1).strip() if match else stripped


def parse_json_note(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and all(key in value for key in REQUIRED_TOP_LEVEL):
        return value
    if isinstance(value, str):
        parsed = json.loads(strip_json_fence(value))
        if not isinstance(parsed, dict):
            raise ValueError("parsed content is not a JSON object")
        return parsed
    if not isinstance(value, dict):
        raise ValueError("record is neither JSON object nor text content")

    if "content" in value:
        return parse_json_note(value["content"])
    if "note" in value:
        return parse_json_note(value["note"])

    response = value.get("response") or value.get("body")
    if isinstance(response, dict):
        if "output_text" in response:
            return parse_json_note(response["output_text"])
        choices = response.get("choices")
        if choices:
            return parse_json_note(choices[0].get("message", {}).get("content", ""))
        output = response.get("output")
        if isinstance(output, list):
            chunks: list[str] = []
            for item in output:
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"} and "text" in content:
                        chunks.append(str(content["text"]))
            if chunks:
                return parse_json_note("\n".join(chunks))

    raise ValueError("could not locate structured note in record")


def normalize_enum(value: Any, allowed: set[str], aliases: dict[str, str], fallback: str) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        lowered = stripped.lower()
        if stripped in allowed:
            return stripped
        if lowered in allowed:
            return lowered
        if stripped in aliases:
            return aliases[stripped]
        if lowered in aliases:
            return aliases[lowered]
    return fallback


def truncate_evidence(value: Any) -> str:
    text = str(value or "")
    if len(text) <= 200:
        return text
    return text[:197] + "..."


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "是", "對"}
    return bool(value)


def repair_note(note: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    repaired = dict(note)
    metadata = metadata or {}

    if not isinstance(repaired.get("episode"), int) and isinstance(metadata.get("episode"), int):
        repaired["episode"] = metadata["episode"]
    if not isinstance(repaired.get("date"), str):
        repaired["date"] = str(metadata.get("date") or "")
    if not isinstance(repaired.get("title"), str):
        repaired["title"] = str(metadata.get("title") or "")

    if isinstance(repaired.get("investment_logic"), list):
        items: list[dict[str, Any]] = []
        for item in repaired["investment_logic"]:
            if not isinstance(item, dict):
                continue
            fixed = dict(item)
            fixed["action_bias"] = normalize_enum(
                fixed.get("action_bias"),
                ACTION_BIASES,
                ACTION_BIAS_ALIASES,
                "unknown",
            )
            fixed["confidence"] = normalize_enum(
                fixed.get("confidence"),
                CONFIDENCES,
                CONFIDENCE_ALIASES,
                "medium",
            )
            fixed["evidence"] = truncate_evidence(fixed.get("evidence"))
            items.append(fixed)
        repaired["investment_logic"] = items

    if isinstance(repaired.get("trade_observations"), list):
        items = []
        for item in repaired["trade_observations"]:
            if not isinstance(item, dict):
                continue
            fixed = dict(item)
            fixed["view"] = normalize_enum(fixed.get("view"), VIEWS, VIEW_ALIASES, "neutral")
            fixed["time_horizon"] = normalize_enum(
                fixed.get("time_horizon"),
                TIME_HORIZONS,
                TIME_HORIZON_ALIASES,
                "unclear",
            )
            fixed["is_joke_or_aside"] = coerce_bool(fixed.get("is_joke_or_aside"))
            items.append(fixed)
        repaired["trade_observations"] = items

    if isinstance(repaired.get("qa_views"), list):
        items = []
        for item in repaired["qa_views"]:
            if not isinstance(item, dict):
                continue
            fixed = dict(item)
            fixed["evidence"] = truncate_evidence(fixed.get("evidence"))
            items.append(fixed)
        repaired["qa_views"] = items

    return repaired


def require_type(errors: list[str], path: str, value: Any, expected_type: type) -> None:
    if not isinstance(value, expected_type):
        errors.append(f"{path} must be {expected_type.__name__}")


def validate_note(note: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in note:
            errors.append(f"missing {key}")

    if errors:
        return errors

    require_type(errors, "episode", note["episode"], int)
    require_type(errors, "date", note["date"], str)
    require_type(errors, "title", note["title"], str)
    require_type(errors, "market_regime", note["market_regime"], str)
    require_type(errors, "topics", note["topics"], list)
    require_type(errors, "investment_logic", note["investment_logic"], list)
    require_type(errors, "trade_observations", note["trade_observations"], list)
    require_type(errors, "qa_views", note["qa_views"], list)
    require_type(errors, "open_questions", note["open_questions"], list)

    topics = note.get("topics") or []
    if isinstance(topics, list) and not (3 <= len(topics) <= 8):
        errors.append("topics must contain 3-8 items")

    for idx, item in enumerate(note.get("investment_logic") or []):
        prefix = f"investment_logic[{idx}]"
        for key in ["claim", "trigger", "action_bias", "risk_control", "evidence", "confidence"]:
            if key not in item:
                errors.append(f"{prefix} missing {key}")
        if item.get("action_bias") not in ACTION_BIASES:
            errors.append(f"{prefix}.action_bias invalid: {item.get('action_bias')}")
        if item.get("confidence") not in CONFIDENCES:
            errors.append(f"{prefix}.confidence invalid: {item.get('confidence')}")
        if len(str(item.get("evidence", ""))) > 200:
            errors.append(f"{prefix}.evidence exceeds 200 characters")

    for idx, item in enumerate(note.get("trade_observations") or []):
        prefix = f"trade_observations[{idx}]"
        for key in ["asset_or_sector", "view", "time_horizon", "reasoning", "market_alignment", "is_joke_or_aside"]:
            if key not in item:
                errors.append(f"{prefix} missing {key}")
        if item.get("view") not in VIEWS:
            errors.append(f"{prefix}.view invalid: {item.get('view')}")
        if item.get("time_horizon") not in TIME_HORIZONS:
            errors.append(f"{prefix}.time_horizon invalid: {item.get('time_horizon')}")
        if not isinstance(item.get("is_joke_or_aside"), bool):
            errors.append(f"{prefix}.is_joke_or_aside must be boolean")

    for idx, item in enumerate(note.get("qa_views") or []):
        prefix = f"qa_views[{idx}]"
        for key in ["question_theme", "viewpoint", "principle", "tone", "evidence"]:
            if key not in item:
                errors.append(f"{prefix} missing {key}")
        if len(str(item.get("evidence", ""))) > 200:
            errors.append(f"{prefix}.evidence exceeds 200 characters")

    return errors


def normalize_outputs(args: argparse.Namespace) -> int:
    raw_records = iter_jsonl(args.input_path)
    metadata_by_id = load_episode_metadata(args.data_dir)
    valid_by_id: dict[str, dict[str, Any]] = {}
    anonymous_valid: list[dict[str, Any]] = []
    errors_by_id: dict[str, dict[str, Any]] = {}
    anonymous_errors: list[dict[str, Any]] = []

    for index, record in enumerate(raw_records, 1):
        custom_id = record.get("custom_id") if isinstance(record, dict) else None
        custom_id_text = str(custom_id) if custom_id else ""
        try:
            note = parse_json_note(record)
            note = repair_note(note, metadata_by_id.get(custom_id_text))
            note_errors = validate_note(note)
            if note_errors:
                error_item = {"line": index, "custom_id": custom_id, "errors": note_errors}
                if custom_id_text and custom_id_text not in valid_by_id:
                    errors_by_id[custom_id_text] = error_item
                elif not custom_id_text:
                    anonymous_errors.append(error_item)
                continue
            if custom_id_text:
                valid_by_id[custom_id_text] = note
                errors_by_id.pop(custom_id_text, None)
            else:
                anonymous_valid.append(note)
        except Exception as exc:  # noqa: BLE001 - collect all LLM output failures.
            error_item = {"line": index, "custom_id": custom_id, "errors": [str(exc)]}
            if custom_id_text and custom_id_text not in valid_by_id:
                errors_by_id[custom_id_text] = error_item
            elif not custom_id_text:
                anonymous_errors.append(error_item)

    valid_notes = list(valid_by_id.values()) + anonymous_valid
    valid_notes.sort(key=lambda item: int(item["episode"]))
    errors = list(errors_by_id.values()) + anonymous_errors
    write_jsonl(args.out_path, valid_notes)
    write_json(
        args.manifest_path,
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "input_path": str(args.input_path),
            "out_path": str(args.out_path),
            "valid_count": len(valid_notes),
            "error_count": len(errors),
            "errors": errors,
        },
    )
    print(f"Wrote {len(valid_notes)} validated structured episode notes to {args.out_path}", flush=True)
    if errors:
        print(f"Found {len(errors)} invalid records; see {args.manifest_path}", flush=True)
        return 1
    return 0


def validate_existing(args: argparse.Namespace) -> int:
    records = iter_jsonl(args.notes_path)
    errors: list[dict[str, Any]] = []
    for index, note in enumerate(records, 1):
        note_errors = validate_note(note)
        if note_errors:
            errors.append({"line": index, "episode": note.get("episode"), "errors": note_errors})

    print(f"Validated {len(records)} structured episode notes from {args.notes_path}", flush=True)
    if errors:
        for item in errors[:20]:
            print(json.dumps(item, ensure_ascii=False), file=sys.stderr)
        if len(errors) > 20:
            print(f"... {len(errors) - 20} more errors", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    default_data_dir = Path(__file__).resolve().parents[1] / "data"
    default_schema = Path(__file__).resolve().parents[1] / "schemas" / "episode_note.schema.json"

    parser = argparse.ArgumentParser(description="Prepare and validate structured Gooaye episode notes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="write per-episode LLM extraction input JSONL")
    prepare_parser.add_argument("--data-dir", type=Path, default=default_data_dir)
    prepare_parser.add_argument("--schema", type=Path, default=default_schema)
    prepare_parser.add_argument("--out-path", type=Path, default=default_data_dir / "structured" / "episode_note_inputs.jsonl")
    prepare_parser.add_argument(
        "--manifest-path",
        type=Path,
        default=default_data_dir / "structured" / "episode_note_inputs_manifest.json",
    )
    prepare_parser.add_argument("--episode", type=int, action="append", help="episode number to include; repeatable")
    prepare_parser.add_argument("--from-episode", type=int)
    prepare_parser.add_argument("--to-episode", type=int)
    prepare_parser.add_argument("--limit", type=int)
    prepare_parser.add_argument("--format", choices=["plain", "responses_batch", "chat_batch"], default="plain")
    prepare_parser.add_argument("--model", default="gpt-5.4")
    prepare_parser.add_argument("--max-output-tokens", type=int, default=4096)
    prepare_parser.set_defaults(func=prepare)

    output_parser = subparsers.add_parser("from-output", help="normalize LLM or OpenAI Batch output into episode_notes.jsonl")
    output_parser.add_argument("input_path", type=Path)
    output_parser.add_argument("--data-dir", type=Path, default=default_data_dir)
    output_parser.add_argument("--out-path", type=Path, default=default_data_dir / "structured" / "episode_notes.jsonl")
    output_parser.add_argument(
        "--manifest-path",
        type=Path,
        default=default_data_dir / "structured" / "episode_notes_manifest.json",
    )
    output_parser.set_defaults(func=normalize_outputs)

    validate_parser = subparsers.add_parser("validate", help="validate an existing episode_notes.jsonl")
    validate_parser.add_argument("--notes-path", type=Path, default=default_data_dir / "structured" / "episode_notes.jsonl")
    validate_parser.set_defaults(func=validate_existing)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
