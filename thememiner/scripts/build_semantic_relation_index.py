#!/usr/bin/env python3
"""Build stock-theme relation judgments for ThemeMiner and Lagradar.

The script turns broad recall edges into ranked relation evidence. It stays
deterministic without model downloads, but can enrich scores with a local
OpenAI-compatible embedding endpoint, such as an MLX Qwen embedding server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+./_-]*|[\u4e00-\u9fff]")

AUTHORITY_RANK = {
    "manual_override": 6,
    "agent_verified": 5,
    "profile_supported": 4,
    "semantic_supported": 3,
    "needs_review": 2,
    "fallback_recall_only": 1,
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_json_compact(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"semantic config must be a JSON object: {path}")
    return data


def flatten_text(value: Any) -> list[str]:
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            output.extend(flatten_text(item))
        return output
    if isinstance(value, dict):
        output = []
        for key in sorted(value):
            output.extend(flatten_text(value[key]))
        return output
    return [str(value)]


def text_blob(*values: Any, max_chars: int = 12000) -> str:
    parts: list[str] = []
    for value in values:
        parts.extend(flatten_text(value))
    text = "\n".join(part.strip() for part in parts if part and part.strip())
    return text[:max_chars]


def token_counter(text: str) -> Counter[str]:
    raw = [match.group(0).lower() for match in TOKEN_RE.finditer(text or "")]
    tokens: list[str] = []
    cjk_buffer: list[str] = []
    for token in raw:
        if len(token) == 1 and "\u4e00" <= token <= "\u9fff":
            cjk_buffer.append(token)
            continue
        if cjk_buffer:
            tokens.extend(cjk_ngrams(cjk_buffer))
            cjk_buffer = []
        tokens.append(token)
    if cjk_buffer:
        tokens.extend(cjk_ngrams(cjk_buffer))
    return Counter(tokens)


def cjk_ngrams(chars: list[str]) -> list[str]:
    grams: list[str] = []
    grams.extend(chars)
    for n in (2, 3, 4):
        grams.extend("".join(chars[idx : idx + n]) for idx in range(0, max(len(chars) - n + 1, 0)))
    return grams


def cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[key] * b.get(key, 0) for key in a)
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def weighted_jaccard(a: Counter[str], b: Counter[str]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    numerator = sum(min(a.get(key, 0), b.get(key, 0)) for key in keys)
    denominator = sum(max(a.get(key, 0), b.get(key, 0)) for key in keys)
    return numerator / denominator if denominator else 0.0


def dense_cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def normalize_dense_cosine(raw: float, floor: float = 0.25, ceiling: float = 0.80) -> float:
    if ceiling <= floor:
        return clamp(raw)
    return clamp((raw - floor) / (ceiling - floor))


def stable_embedding_key(model: str, text: str) -> str:
    payload = f"{model}\n{text}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()


def chunks(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        size = 16
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def lexical_similarity(a_text: str, b_text: str) -> tuple[float, list[str]]:
    a = token_counter(a_text)
    b = token_counter(b_text)
    sim = cosine(a, b) * 0.7 + weighted_jaccard(a, b) * 0.3
    shared = sorted(set(a) & set(b), key=lambda key: (min(a[key], b[key]), len(key)), reverse=True)
    useful = [term for term in shared if len(term) > 1 or term.isascii()]
    return round(clamp(sim), 4), useful[:18]


def cards_by_symbol(path: Path) -> dict[str, dict[str, Any]]:
    data = read_json(path)
    cards = data.get("cards", data if isinstance(data, list) else [])
    return {card["symbol"]: card for card in cards if card.get("symbol")}


def profiles_by_symbol(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = read_json(path)
    profiles = data.get("profiles", data if isinstance(data, list) else [])
    return {profile["symbol"]: profile for profile in profiles if profile.get("symbol")}


def concepts_by_id(path: Path) -> dict[str, dict[str, Any]]:
    data = read_json(path)
    concepts = data.get("concepts", data if isinstance(data, list) else [])
    return {concept["concept_id"]: concept for concept in concepts if concept.get("concept_id")}


def concept_text(concept: dict[str, Any]) -> str:
    stock_names = [stock.get("name") or stock.get("symbol") for stock in (concept.get("stocks") or [])[:24]]
    return text_blob(
        concept.get("concept_id"),
        concept.get("label"),
        concept.get("category_label"),
        concept.get("products"),
        concept.get("supply_layers"),
        concept.get("upstream_concepts"),
        concept.get("downstream_concepts"),
        stock_names,
    )


def company_text(card: dict[str, Any], profile: dict[str, Any]) -> str:
    refs = [item.get("title") for item in (profile.get("source_refs") or [])[:8] if item.get("title")]
    return text_blob(
        card.get("name"),
        card.get("symbol"),
        card.get("market"),
        card.get("sector"),
        card.get("thesis_label"),
        card.get("primary_business"),
        card.get("business_segments"),
        card.get("ai_chain_position"),
        card.get("non_ai_chain_position"),
        card.get("catalysts"),
        card.get("leader_indicators"),
        card.get("peer_symbols"),
        card.get("relation_paths"),
        profile.get("primary_business"),
        profile.get("specializations"),
        profile.get("products"),
        profile.get("platforms"),
        profile.get("supply_chain_profile"),
        refs,
    )


def base_quality(card: dict[str, Any], membership: dict[str, Any], similarity: float, profile: dict[str, Any]) -> tuple[float, str, list[str]]:
    confidence = str(card.get("relation_confidence") or "")
    agent_status = str(card.get("agent_status") or "")
    source_quality = str(card.get("source_quality") or "")
    profile_quality = str(profile.get("profile_quality") or profile.get("profile_status") or "")
    warnings: list[str] = []

    if card.get("manual_override") or confidence == "high_manual_curated":
        score = 0.94
        authority = "manual_override"
    elif agent_status == "agent_applied":
        score = 0.88
        authority = "agent_verified"
    elif confidence == "high_profiled":
        score = 0.78
        authority = "profile_supported"
    elif confidence == "medium_needs_segment_verification":
        score = 0.56
        authority = "needs_review"
    elif confidence == "low_auto_mapping_backlog":
        score = 0.28
        authority = "fallback_recall_only"
    else:
        score = 0.46
        authority = "needs_review"

    if source_quality in {"official_profile", "official_plus_agent", "manual_override"}:
        score += 0.06
    if "fallback" in source_quality or "unknown" == source_quality:
        score -= 0.06
        warnings.append("fallback_or_unknown_source_quality")
    if "fallback" in profile_quality:
        score -= 0.10
        warnings.append("fallback_profile")
    if "market_metadata" in profile_quality:
        score -= 0.06
        warnings.append("market_metadata_profile")
    if agent_status.startswith("agent_unavailable") or "codex_agent_unavailable" in agent_status:
        score -= 0.08
        warnings.append(agent_status)
    if agent_status == "not_requested":
        score -= 0.05
    if not card.get("thesis_label"):
        score -= 0.08
        warnings.append("missing_thesis_label")
    if membership.get("source") == "relation_index" and not membership.get("path"):
        score -= 0.04
        warnings.append("relation_index_membership_without_path")

    score += clamp(similarity, 0.0, 0.5) * 0.18
    if similarity >= 0.18 and authority == "needs_review":
        authority = "semantic_supported"
    return round(clamp(score), 4), authority, warnings


def dedupe_memberships(card: dict[str, Any]) -> list[dict[str, Any]]:
    by_concept: dict[str, dict[str, Any]] = {}
    for membership in card.get("theme_memberships") or []:
        concept_id = membership.get("concept_id")
        if not concept_id:
            continue
        existing = by_concept.get(concept_id)
        if existing is None:
            by_concept[concept_id] = dict(membership)
            continue
        if membership.get("path") and not existing.get("path"):
            existing["path"] = membership["path"]
        existing["source"] = ",".join(sorted(set(str(existing.get("source") or "").split(",")) | {str(membership.get("source") or "")}))
        existing["score"] = max(float(existing.get("score") or 0.0), float(membership.get("score") or 0.0))
    return list(by_concept.values())


class EmbeddingScorer:
    """Optional embedding client with on-disk caching."""

    def __init__(self, backend: dict[str, Any]):
        self.backend = backend
        self.model = str(backend.get("embedding_model") or "")
        self.endpoint = str(backend.get("embedding_endpoint") or "")
        self.timeout_seconds = float(backend.get("timeout_seconds") or 45)
        self.batch_size = int(backend.get("batch_size") or 16)
        self.embedding_weight = float(backend.get("embedding_weight") or 0.72)
        self.lexical_weight = float(backend.get("lexical_weight") or 0.28)
        self.cosine_floor = float(backend.get("cosine_floor") or 0.25)
        self.cosine_ceiling = float(backend.get("cosine_ceiling") or 0.80)
        self.max_tokens = int(backend.get("max_tokens") or 768)
        self.pooling = str(backend.get("pooling") or "last")
        self.progress_every = int(backend.get("progress_every") or 10)
        self.cache_flush_every = int(backend.get("cache_flush_every") or 8)
        self.cache_path = Path(str(backend.get("cache_path") or ""))
        self.cache: dict[str, list[float]] = {}
        self.dirty_cache = False
        self._local_model = None
        self._local_tokenizer = None
        if self.enabled:
            self._load_cache()

    @property
    def enabled(self) -> bool:
        return self.backend.get("effective") in {"mlx_http", "mlx_local"}

    def _embedding_key(self, text: str) -> str:
        namespace = self.backend.get("effective")
        if namespace == "mlx_local":
            namespace = f"{namespace}:{self.pooling}:{self.max_tokens}"
        return stable_embedding_key(f"{namespace}:{self.model}", text)

    def _load_cache(self) -> None:
        if not self.cache_path or not self.cache_path.exists():
            return
        try:
            payload = read_json(self.cache_path)
        except Exception as exc:
            self.backend["status"] = f"embedding_cache_ignored:{exc.__class__.__name__}"
            return
        if payload.get("model") != self.model:
            return
        embeddings = payload.get("embeddings") or {}
        if isinstance(embeddings, dict):
            self.cache = {str(key): value for key, value in embeddings.items() if isinstance(value, list)}

    def _write_cache(self) -> None:
        if not self.enabled or not self.dirty_cache or not self.cache_path:
            return
        write_json_compact(
            self.cache_path,
            {
                "schema_version": "thememiner_embedding_cache_v1",
                "model": self.model,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "embedding_count": len(self.cache),
                "embeddings": self.cache,
            },
        )
        self.dirty_cache = False

    def prepare(self, texts_by_key: dict[str, str]) -> dict[str, list[float]]:
        if not self.enabled:
            return {}
        unique_texts: dict[str, str] = {}
        resolved: dict[str, list[float]] = {}
        cached_count = 0
        for item_key, text in texts_by_key.items():
            embedding_key = self._embedding_key(text)
            if embedding_key in self.cache:
                resolved[item_key] = self.cache[embedding_key]
                cached_count += 1
            else:
                unique_texts[embedding_key] = text

        try:
            pending_keys = list(unique_texts)
            pending_count = len(pending_keys)
            if pending_count:
                print(
                    f"Embedding backend {self.backend.get('effective')} has "
                    f"{pending_count} uncached texts, {cached_count} cached.",
                    file=sys.stderr,
                    flush=True,
                )
            for batch_idx, batch_keys in enumerate(chunks(pending_keys, self.batch_size), start=1):
                batch_texts = [unique_texts[key] for key in batch_keys]
                vectors = self._embed_texts(batch_texts)
                if len(vectors) != len(batch_keys):
                    raise ValueError("embedding_endpoint_returned_wrong_count")
                for key, vector in zip(batch_keys, vectors):
                    self.cache[key] = [float(value) for value in vector]
                    self.dirty_cache = True
                done = min(batch_idx * self.batch_size, pending_count)
                if pending_count and (batch_idx == 1 or batch_idx % self.progress_every == 0 or done == pending_count):
                    print(
                        f"Embedding progress: {done}/{pending_count} uncached texts "
                        f"(cache={len(self.cache)})",
                        file=sys.stderr,
                        flush=True,
                    )
                if self.cache_flush_every > 0 and batch_idx % self.cache_flush_every == 0:
                    self._write_cache()
        except Exception as exc:
            failed_backend = self.backend.get("effective") or "embedding"
            self.backend["effective"] = "lexical"
            self.backend["status"] = f"{failed_backend}_unavailable:{exc.__class__.__name__}"
            return {}

        for item_key, text in texts_by_key.items():
            embedding_key = self._embedding_key(text)
            vector = self.cache.get(embedding_key)
            if vector:
                resolved[item_key] = vector
        self.backend["status"] = f"{self.backend.get('effective')}_embeddings_ready:cache={len(self.cache)}"
        self._write_cache()
        return resolved

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.backend.get("effective") == "mlx_local":
            return self._embed_texts_mlx_local(texts)
        return self._request_http_embeddings(texts)

    def _embed_texts_mlx_local(self, texts: list[str]) -> list[list[float]]:
        try:
            import mlx.core as mx
            from mlx_lm import load
        except Exception as exc:
            raise RuntimeError(f"mlx_local_import_failed:{exc.__class__.__name__}") from exc

        if self._local_model is None or self._local_tokenizer is None:
            self._local_model, self._local_tokenizer = load(self.model)

        vectors: list[list[float]] = []
        eos_id = getattr(self._local_tokenizer, "eos_token_id", None) or 0
        for text in texts:
            tokens = self._local_tokenizer.encode(text, add_special_tokens=True)
            tokens = tokens[: self.max_tokens] or [eos_id]
            token_array = mx.array([tokens])
            model_body = getattr(self._local_model, "model", None)
            if model_body is None:
                raise RuntimeError("mlx_local_model_has_no_hidden_state_body")
            hidden = model_body(token_array)
            if self.pooling == "mean":
                vector = mx.mean(hidden[0], axis=0)
            else:
                vector = hidden[0, -1, :]
            norm = mx.linalg.norm(vector)
            vector = vector / mx.maximum(norm, mx.array(1e-12))
            mx.eval(vector)
            vectors.append([float(value) for value in vector.tolist()])
        return vectors

    def _request_http_embeddings(self, texts: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"embedding_http_error:{exc.code}:{detail}") from exc
        data = json.loads(body)
        rows = data.get("data")
        if not isinstance(rows, list):
            raise ValueError("embedding_response_missing_data")
        rows = sorted(rows, key=lambda item: item.get("index", 0))
        vectors: list[list[float]] = []
        for item in rows:
            vector = item.get("embedding")
            if not isinstance(vector, list):
                raise ValueError("embedding_response_missing_vector")
            vectors.append(vector)
        return vectors

    def similarity(
        self,
        company_key: str,
        concept_key: str,
        company_text_value: str,
        concept_text_value: str,
        embeddings: dict[str, list[float]],
    ) -> dict[str, Any]:
        lexical, terms = lexical_similarity(company_text_value, concept_text_value)
        raw_embedding = None
        embedding = None
        semantic = lexical
        if self.enabled:
            company_vector = embeddings.get(company_key)
            concept_vector = embeddings.get(concept_key)
            if company_vector and concept_vector:
                raw_embedding = round(dense_cosine(company_vector, concept_vector), 4)
                embedding = round(normalize_dense_cosine(raw_embedding, self.cosine_floor, self.cosine_ceiling), 4)
                total_weight = self.embedding_weight + self.lexical_weight
                if total_weight <= 0:
                    total_weight = 1.0
                semantic = (
                    embedding * (self.embedding_weight / total_weight)
                    + lexical * (self.lexical_weight / total_weight)
                )
        return {
            "semantic_similarity": round(clamp(semantic), 4),
            "lexical_similarity": lexical,
            "embedding_similarity": embedding,
            "embedding_similarity_raw": raw_embedding,
            "matched_terms": terms,
        }


def choose_backend(requested: str, config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if requested not in {"auto", "lexical", "mlx", "mlx-http", "mlx-local"}:
        raise ValueError(f"unsupported backend: {requested}")
    if requested == "lexical":
        return {"requested": requested, "effective": "lexical", "status": "lexical_only"}

    embedding_cfg = config.get("embedding_backend") or {}
    model = args.embedding_model or embedding_cfg.get("daily_model") or "mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"
    endpoint_env = str(embedding_cfg.get("endpoint_env") or "THEMEMINER_EMBEDDING_BASE_URL")
    endpoint = args.embedding_endpoint or os.environ.get(endpoint_env) or embedding_cfg.get("default_endpoint")
    cache_dir = Path(args.embedding_cache_dir or embedding_cfg.get("cache_dir") or "thememiner/output/cache/semantic_embeddings")
    cache_path = cache_dir / f"{hashlib.sha1(model.encode('utf-8')).hexdigest()[:16]}.json"

    auto_backend = os.environ.get("THEMEMINER_EMBEDDING_BACKEND", "").strip()
    auto_enabled = bool(os.environ.get(endpoint_env) or os.environ.get("THEMEMINER_USE_LOCAL_EMBEDDINGS") or auto_backend)
    if requested == "auto" and not auto_enabled:
        return {
            "requested": requested,
            "effective": "lexical",
            "status": "auto_local_embeddings_not_requested",
            "embedding_model": model,
        }

    effective = requested.replace("-", "_")
    if requested == "mlx":
        effective = "mlx_local"
    if requested == "auto":
        effective = auto_backend.replace("-", "_") if auto_backend else "mlx_http"
        if effective == "mlx":
            effective = "mlx_local"
    if effective not in {"mlx_http", "mlx_local"}:
        effective = "mlx_http"

    if effective == "mlx_http" and not endpoint:
        return {
            "requested": requested,
            "effective": "lexical",
            "status": "embedding_endpoint_not_configured",
            "embedding_model": model,
        }

    return {
        "requested": requested,
        "effective": effective,
        "status": f"{effective}_configured",
        "embedding_model": model,
        "embedding_endpoint": str(endpoint) if effective == "mlx_http" else "",
        "cache_path": str(cache_path),
        "batch_size": int(args.embedding_batch_size or embedding_cfg.get("batch_size") or 16),
        "timeout_seconds": float(args.embedding_timeout or embedding_cfg.get("timeout_seconds") or 45),
        "embedding_weight": float(embedding_cfg.get("embedding_weight") or 0.72),
        "lexical_weight": float(embedding_cfg.get("lexical_weight") or 0.28),
        "cosine_floor": float(embedding_cfg.get("cosine_floor") or 0.25),
        "cosine_ceiling": float(embedding_cfg.get("cosine_ceiling") or 0.80),
        "max_tokens": int(args.embedding_max_tokens or embedding_cfg.get("max_tokens") or 768),
        "pooling": str(args.embedding_pooling or embedding_cfg.get("pooling") or "last"),
        "progress_every": int(args.embedding_progress_every or embedding_cfg.get("progress_every") or 10),
        "cache_flush_every": int(args.embedding_cache_flush_every or embedding_cfg.get("cache_flush_every") or 8),
    }


def build_relation_judgments(
    *,
    cards: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    concepts: dict[str, dict[str, Any]],
    backend: dict[str, str],
    limit: int = 0,
) -> dict[str, Any]:
    judgments: list[dict[str, Any]] = []
    symbols = sorted(cards)
    if limit > 0:
        symbols = symbols[:limit]
    concept_text_cache = {concept_id: concept_text(concept) for concept_id, concept in concepts.items()}
    company_text_cache = {
        symbol: company_text(cards[symbol], profiles.get(symbol, {}))
        for symbol in symbols
    }
    scorer = EmbeddingScorer(backend)
    embedding_inputs: dict[str, str] = {}
    if scorer.enabled:
        embedding_inputs.update({f"company:{symbol}": text for symbol, text in company_text_cache.items()})
        embedding_inputs.update({f"concept:{concept_id}": text for concept_id, text in concept_text_cache.items()})
    embeddings = scorer.prepare(embedding_inputs)
    for symbol in symbols:
        card = cards[symbol]
        profile = profiles.get(symbol, {})
        ctext = company_text_cache[symbol]
        for membership in dedupe_memberships(card):
            concept_id = membership["concept_id"]
            concept = concepts.get(concept_id, {})
            ttext = concept_text_cache.get(concept_id) or text_blob(concept_id, membership.get("label"))
            semantic = scorer.similarity(
                f"company:{symbol}",
                f"concept:{concept_id}",
                ctext,
                ttext,
                embeddings,
            )
            similarity = semantic["semantic_similarity"]
            quality, authority, warnings = base_quality(card, membership, similarity, profile)
            relation_paths = [membership.get("path"), *(card.get("relation_paths") or [])]
            judgments.append(
                {
                    "symbol": symbol,
                    "name": card.get("name"),
                    "market": card.get("market"),
                    "concept_id": concept_id,
                    "theme_label": membership.get("label") or concept.get("label") or concept_id,
                    "membership_source": membership.get("source"),
                    "membership_weight": membership.get("weight"),
                    "relation_authority": authority,
                    "relation_quality_score": quality,
                    "semantic_similarity": similarity,
                    "lexical_similarity": semantic["lexical_similarity"],
                    "embedding_similarity": semantic["embedding_similarity"],
                    "embedding_similarity_raw": semantic["embedding_similarity_raw"],
                    "semantic_backend": backend["effective"],
                    "backend_status": backend["status"],
                    "matched_terms": semantic["matched_terms"],
                    "evidence_paths": [path for path in dict.fromkeys(relation_paths) if path][:8],
                    "relation_confidence": card.get("relation_confidence"),
                    "agent_status": card.get("agent_status"),
                    "source_quality": card.get("source_quality"),
                    "manual_thesis_override": bool(card.get("manual_override")),
                    "warnings": sorted(set(warnings)),
                }
            )
    judgments.sort(
        key=lambda row: (
            row["symbol"],
            -AUTHORITY_RANK.get(row["relation_authority"], 0),
            -(row.get("relation_quality_score") or 0.0),
            row["concept_id"],
        )
    )
    return {
        "schema_version": "thememiner_relation_judgments_v1",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "backend": backend,
        "source_card_count": len(cards),
        "source_profile_count": len(profiles),
        "source_concept_count": len(concepts),
        "judgment_count": len(judgments),
        "judgments": judgments,
    }


def write_report(path: Path, data: dict[str, Any]) -> None:
    judgments = data.get("judgments", [])
    by_authority = Counter(row.get("relation_authority") for row in judgments)
    by_warning = Counter(warning for row in judgments for warning in row.get("warnings", []))
    low = [row for row in judgments if (row.get("relation_quality_score") or 0.0) < 0.35]
    high = [row for row in judgments if (row.get("relation_quality_score") or 0.0) >= 0.75]
    lines = [
        "# Semantic Relation Index Report",
        "",
        f"Generated at: {data.get('built_at')}",
        f"Backend: {data.get('backend', {}).get('effective')} ({data.get('backend', {}).get('status')})",
        f"Judgments: {len(judgments)}",
        "",
        "## Authority Mix",
        "",
        "| Authority | Count |",
        "|---|---:|",
    ]
    for authority, count in by_authority.most_common():
        lines.append(f"| {authority} | {count} |")
    lines.extend(["", "## Warning Mix", "", "| Warning | Count |", "|---|---:|"])
    for warning, count in by_warning.most_common(20):
        lines.append(f"| {warning} | {count} |")
    lines.extend(["", "## High-Quality Examples", "", "| Symbol | Theme | Authority | Quality | Similarity |", "|---|---|---|---:|---:|"])
    for row in sorted(high, key=lambda item: item["relation_quality_score"], reverse=True)[:20]:
        lines.append(
            f"| `{row['symbol']}` {row.get('name') or ''} | {row.get('theme_label')} | "
            f"{row.get('relation_authority')} | {row.get('relation_quality_score'):.2f} | {row.get('semantic_similarity'):.2f} |"
        )
    lines.extend(["", "## Low-Quality Backlog Examples", "", "| Symbol | Theme | Authority | Quality | Warnings |", "|---|---|---|---:|---|"])
    for row in sorted(low, key=lambda item: item["relation_quality_score"])[:30]:
        lines.append(
            f"| `{row['symbol']}` {row.get('name') or ''} | {row.get('theme_label')} | "
            f"{row.get('relation_authority')} | {row.get('relation_quality_score'):.2f} | {', '.join(row.get('warnings') or [])} |"
        )
    write_text(path, "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build stock-theme relation judgments")
    parser.add_argument("--company-thesis-cards", default="thememiner/output/company_thesis_cards.json")
    parser.add_argument("--company-profiles", default="thememiner/output/company_profiles.json")
    parser.add_argument("--relation-index", default="thememiner/output/relation_index.json")
    parser.add_argument("--semantic-config", default="thememiner/config/semantic_retrieval.json")
    parser.add_argument("--output", default="thememiner/output/relation_judgments.json")
    parser.add_argument("--report-output", default="thememiner/output/semantic_retrieval_report.md")
    parser.add_argument("--backend", choices=["auto", "lexical", "mlx", "mlx-http", "mlx-local"], default="auto")
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--embedding-endpoint", default="")
    parser.add_argument("--embedding-cache-dir", default="")
    parser.add_argument("--embedding-batch-size", type=int, default=0)
    parser.add_argument("--embedding-timeout", type=float, default=0)
    parser.add_argument("--embedding-max-tokens", type=int, default=0)
    parser.add_argument("--embedding-pooling", choices=["last", "mean"], default="")
    parser.add_argument("--embedding-progress-every", type=int, default=0)
    parser.add_argument("--embedding-cache-flush-every", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0, help="Debug cap; 0 means all cards")
    args = parser.parse_args()

    config = load_config(Path(args.semantic_config))
    backend = choose_backend(args.backend, config, args)
    data = build_relation_judgments(
        cards=cards_by_symbol(Path(args.company_thesis_cards)),
        profiles=profiles_by_symbol(Path(args.company_profiles)),
        concepts=concepts_by_id(Path(args.relation_index)),
        backend=backend,
        limit=args.limit,
    )
    write_json(Path(args.output), data)
    write_report(Path(args.report_output), data)
    print(
        f"Wrote {data['judgment_count']} relation judgments to {args.output} "
        f"using {backend['effective']} ({backend['status']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
