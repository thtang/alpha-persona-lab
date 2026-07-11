#!/usr/bin/env python3
"""Agentic semantic judges for ThemeMiner.

This module intentionally keeps keyword/rule output as evidence, not as the
final authority. When an OpenAI-compatible agent endpoint is configured, the
agent reads the company profile, concept memberships, relation paths, and
source evidence, then returns a structured thesis card. If no agent is
available, callers can still produce a fallback card, but the fallback is
explicitly labeled as such so it cannot masquerade as high-confidence
reasoning.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_CODEX_MODEL = ""
DEFAULT_CODEX_COMMAND = "codex"
DEFAULT_PROMPT_MAX_CHARS = 80000


def stable_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compact(value: Any, *, max_chars: int = 9000) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[truncated]"


def parse_json_object(text: str) -> dict[str, Any]:
    value = (text or "").strip()
    if value.startswith("```"):
        value = value.strip("`").strip()
        if value.startswith("json"):
            value = value[4:].strip()
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(value[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("agent returned non-object JSON")
    return data


@dataclass
class AgentConfig:
    enabled: bool
    api_key: str
    provider: str = "openai"
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    codex_command: str = DEFAULT_CODEX_COMMAND
    cwd: Path = Path(".")
    cache_dir: Path = Path("thememiner/output/cache/agentic_judge")
    refresh: bool = False
    timeout: int = 90
    prompt_max_chars: int = DEFAULT_PROMPT_MAX_CHARS
    temperature: float = 0.1
    max_retries: int = 2

    @classmethod
    def from_env(
        cls,
        *,
        enabled: bool = False,
        cache_dir: str | Path = "thememiner/output/cache/agentic_judge",
        refresh: bool = False,
        model: str | None = None,
        provider: str | None = None,
    ) -> "AgentConfig":
        api_key = os.getenv("THEMEMINER_AGENT_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        base_url = os.getenv("THEMEMINER_AGENT_BASE_URL") or os.getenv("OPENAI_BASE_URL") or DEFAULT_BASE_URL
        requested_provider = (provider or os.getenv("THEMEMINER_AGENT_PROVIDER") or "auto").strip().lower()
        codex_command = os.getenv("THEMEMINER_CODEX_COMMAND") or DEFAULT_CODEX_COMMAND
        codex_available = shutil.which(codex_command) is not None
        if requested_provider == "auto":
            active_provider = "openai" if api_key else "codex" if codex_available else "none"
        else:
            active_provider = requested_provider
        if active_provider == "openai":
            provider_enabled = enabled and bool(api_key)
            chosen_model = model or os.getenv("THEMEMINER_AGENT_MODEL") or DEFAULT_MODEL
        elif active_provider == "codex":
            provider_enabled = enabled and codex_available
            chosen_model = model or os.getenv("THEMEMINER_CODEX_MODEL") or DEFAULT_CODEX_MODEL or "codex-default"
        else:
            provider_enabled = False
            chosen_model = model or os.getenv("THEMEMINER_AGENT_MODEL") or DEFAULT_MODEL
        try:
            timeout = int(os.getenv("THEMEMINER_AGENT_TIMEOUT", "90"))
        except ValueError:
            timeout = 90
        try:
            prompt_max_chars = int(os.getenv("THEMEMINER_AGENT_PROMPT_MAX_CHARS", str(DEFAULT_PROMPT_MAX_CHARS)))
        except ValueError:
            prompt_max_chars = DEFAULT_PROMPT_MAX_CHARS
        return cls(
            enabled=provider_enabled,
            api_key=api_key,
            provider=active_provider,
            base_url=base_url.rstrip("/"),
            model=chosen_model,
            codex_command=codex_command,
            cwd=Path(os.getenv("THEMEMINER_AGENT_CWD") or "."),
            cache_dir=Path(cache_dir),
            refresh=refresh,
            timeout=timeout,
            prompt_max_chars=prompt_max_chars,
        )

    @property
    def status(self) -> str:
        if self.enabled and self.provider == "openai":
            return "openai_agent_enabled"
        if self.enabled and self.provider == "codex":
            return "codex_agent_enabled"
        if self.provider == "openai":
            return "openai_agent_unavailable_no_api_key" if not self.api_key else "openai_agent_disabled_by_flag"
        if self.provider == "codex":
            return "codex_agent_unavailable_no_cli"
        return "agent_unavailable_no_provider"


class AgenticJudge:
    def __init__(self, config: AgentConfig):
        self.config = config

    def chat_json(self, *, system: str, user: dict[str, Any], cache_namespace: str) -> dict[str, Any] | None:
        payload_for_hash = {
            "provider": self.config.provider,
            "model": self.config.model,
            "prompt_max_chars": self.config.prompt_max_chars,
            "system": system,
            "user": user,
        }
        cache_path = self.config.cache_dir / cache_namespace / f"{stable_hash(payload_for_hash)}.json"
        if cache_path.exists() and not self.config.refresh:
            cached = read_json(cache_path, {})
            if cached.get("ok"):
                return cached.get("data")
        if not self.config.enabled:
            return None
        if self.config.provider == "codex":
            return self.chat_json_codex(system=system, user=user, cache_path=cache_path)
        return self.chat_json_openai(system=system, user=user, cache_path=cache_path)

    def chat_json_openai(self, *, system: str, user: dict[str, Any], cache_path: Path) -> dict[str, Any] | None:
        body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": compact(user, max_chars=self.config.prompt_max_chars)},
            ],
            "temperature": self.config.temperature,
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "alpha-persona-lab-thememiner-agentic-judge/0.1",
            },
            method="POST",
        )
        last_error = ""
        for attempt in range(self.config.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                content = raw["choices"][0]["message"]["content"]
                data = json.loads(content)
                write_json(cache_path, {"ok": True, "fetched_at": time.time(), "data": data})
                return data
            except Exception as exc:
                last_error = str(exc)
                time.sleep(0.6 * (attempt + 1))
        write_json(cache_path, {"ok": False, "fetched_at": time.time(), "error": last_error})
        return None

    def chat_json_codex(self, *, system: str, user: dict[str, Any], cache_path: Path) -> dict[str, Any] | None:
        prompt = (
            "You are a non-interactive JSON judging agent for ThemeMiner.\n"
            "Do not edit files, do not run tools, and do not explain outside JSON.\n\n"
            "System task:\n"
            f"{system}\n\n"
            "Evidence JSON:\n"
            f"{compact(user, max_chars=self.config.prompt_max_chars)}\n\n"
            "Return exactly one valid JSON object that follows the requested fields."
        )
        last_error = ""
        for attempt in range(self.config.max_retries + 1):
            with tempfile.TemporaryDirectory(prefix="thememiner_codex_agent_") as tmp:
                tmp_path = Path(tmp)
                output_path = tmp_path / "last_message.json"
                cmd = [
                    self.config.codex_command,
                    "exec",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "-c",
                    'model_reasoning_effort="low"',
                    "-C",
                    str(self.config.cwd),
                    "-o",
                    str(output_path),
                ]
                if self.config.model and self.config.model != "codex-default":
                    cmd.extend(["-m", self.config.model])
                cmd.append("-")
                try:
                    result = subprocess.run(
                        cmd,
                        input=prompt,
                        text=True,
                        capture_output=True,
                        timeout=self.config.timeout,
                        check=False,
                    )
                    raw = output_path.read_text(encoding="utf-8") if output_path.exists() else result.stdout
                    if result.returncode != 0 and not raw.strip():
                        last_error = (result.stderr or result.stdout or f"codex exited {result.returncode}")[-2000:]
                        raise RuntimeError(last_error)
                    data = parse_json_object(raw)
                    write_json(cache_path, {"ok": True, "fetched_at": time.time(), "provider": "codex", "data": data})
                    return data
                except Exception as exc:
                    last_error = str(exc)
                    time.sleep(0.6 * (attempt + 1))
        write_json(cache_path, {"ok": False, "fetched_at": time.time(), "provider": "codex", "error": last_error})
        return None

    def company_thesis(self, evidence: dict[str, Any]) -> dict[str, Any] | None:
        system = (
            "You are ThemeMiner's supply-chain research agent. Judge semantic exposure without keyword matching. "
            "Use the supplied evidence as clues, but do not assume a concept is true just because a term appears. "
            "Return strict JSON only. If evidence is weak, say so and lower confidence. "
            "Fields: thesis_label string, primary_business string, business_segments array of strings, "
            "ai_chain_position string, non_ai_chain_position string, catalysts array, leader_indicators array, "
            "peer_symbols array, risks array, relation_confidence one of high_agent, medium_agent, low_agent, "
            "agent_reasoning_summary string, evidence_gaps array."
        )
        return self.chat_json(system=system, user=evidence, cache_namespace="company_thesis")

    def company_thesis_batch(self, evidence_items: list[dict[str, Any]]) -> dict[str, Any] | None:
        system = (
            "You are ThemeMiner's supply-chain research agent. Judge semantic exposure without keyword matching. "
            "You will receive a batch of company evidence objects. Return strict JSON only with a top-level `cards` array. "
            "Return exactly one card for every input item, preserve the input order, and copy the input symbol string exactly. "
            "Each card must include symbol and these fields: thesis_label string, primary_business string, "
            "business_segments array of strings, ai_chain_position string, non_ai_chain_position string, catalysts array, "
            "leader_indicators array, peer_symbols array, risks array, relation_confidence one of high_agent, medium_agent, low_agent, "
            "agent_reasoning_summary string, evidence_gaps array. "
            "Do not assume a concept is true just because a term appears. If evidence is weak, say so and lower confidence."
        )
        return self.chat_json(system=system, user={"items": evidence_items}, cache_namespace="company_thesis_batch")

    def concept_match(self, evidence: dict[str, Any]) -> dict[str, Any] | None:
        system = (
            "You are ThemeMiner's semantic concept-mapping agent. You receive exchange/company metadata and candidate concepts. "
            "The candidates may come from brittle keyword or industry-code retrieval; treat them as hypotheses only. "
            "Decide which concepts genuinely fit the business, reject broad/accidental matches, and lower confidence when evidence is thin. "
            "Return strict JSON only. Fields: matched_concepts array of objects with concept_id, confidence number 0-1, role string, reason string; "
            "rejected_concepts array of objects with concept_id and reason; summary string; evidence_gaps array of strings."
        )
        return self.chat_json(system=system, user=evidence, cache_namespace="concept_match")

    def concept_match_batch(self, evidence_items: list[dict[str, Any]]) -> dict[str, Any] | None:
        system = (
            "You are ThemeMiner's semantic concept-mapping agent. You receive a batch of exchange/company metadata objects and candidate concepts. "
            "The candidates may come from brittle keyword or industry-code retrieval; treat them as hypotheses only. "
            "Return strict JSON only with a top-level `results` array. Each result must include symbol, matched_concepts array of objects "
            "with concept_id, confidence number 0-1, role string, reason string; rejected_concepts array of objects with concept_id and reason; "
            "summary string; evidence_gaps array of strings. Reject broad/accidental matches and lower confidence when evidence is thin."
        )
        return self.chat_json(system=system, user={"items": evidence_items}, cache_namespace="concept_match_batch")


def normalize_agent_card(data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}

    def list_field(key: str, limit: int = 24) -> list[str]:
        value = data.get(key)
        if not isinstance(value, list):
            return []
        output: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            output.append(text)
            if len(output) >= limit:
                break
        return output

    confidence = str(data.get("relation_confidence") or "low_agent")
    if confidence not in {"high_agent", "medium_agent", "low_agent"}:
        confidence = "low_agent"
    return {
        "symbol": str(data.get("symbol") or "").strip(),
        "name": str(data.get("name") or data.get("company_name") or "").strip(),
        "thesis_label": str(data.get("thesis_label") or "").strip(),
        "primary_business": str(data.get("primary_business") or "").strip(),
        "business_segments": list_field("business_segments"),
        "ai_chain_position": str(data.get("ai_chain_position") or "").strip(),
        "non_ai_chain_position": str(data.get("non_ai_chain_position") or "").strip(),
        "catalysts": list_field("catalysts"),
        "leader_indicators": list_field("leader_indicators"),
        "peer_symbols": list_field("peer_symbols"),
        "risks": list_field("risks"),
        "relation_confidence": confidence,
        "agent_reasoning_summary": str(data.get("agent_reasoning_summary") or "").strip(),
        "evidence_gaps": list_field("evidence_gaps"),
    }


def useful_agent_card(card: dict[str, Any]) -> bool:
    return bool(
        card
        and card.get("thesis_label")
        and card.get("primary_business")
        and card.get("relation_confidence") in {"high_agent", "medium_agent", "low_agent"}
    )


def normalize_concept_match(data: dict[str, Any] | None, known_concepts: set[str]) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    matched: list[dict[str, Any]] = []
    for item in data.get("matched_concepts", []) if isinstance(data.get("matched_concepts"), list) else []:
        if not isinstance(item, dict):
            continue
        concept_id = str(item.get("concept_id") or "").strip()
        if concept_id not in known_concepts:
            continue
        try:
            confidence = float(item.get("confidence"))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        if confidence < 0.35:
            continue
        matched.append(
            {
                "concept_id": concept_id,
                "confidence": confidence,
                "role": str(item.get("role") or "agent_mapped"),
                "reason": str(item.get("reason") or "").strip(),
            }
        )
    rejected: list[dict[str, str]] = []
    for item in data.get("rejected_concepts", []) if isinstance(data.get("rejected_concepts"), list) else []:
        if not isinstance(item, dict):
            continue
        concept_id = str(item.get("concept_id") or "").strip()
        if concept_id in known_concepts:
            rejected.append({"concept_id": concept_id, "reason": str(item.get("reason") or "").strip()})
    return {
        "matched_concepts": matched,
        "rejected_concepts": rejected[:24],
        "summary": str(data.get("summary") or "").strip(),
        "evidence_gaps": [str(item).strip() for item in data.get("evidence_gaps", []) if str(item).strip()]
        if isinstance(data.get("evidence_gaps"), list)
        else [],
    }
