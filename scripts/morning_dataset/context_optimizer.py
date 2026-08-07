from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

DEFAULT_MAX_CHARS = 40_000
DEFAULT_LIST_LIMIT = 10
DEFAULT_STRING_LIMIT = 1_500


def _clip_string(value: str, limit: int = DEFAULT_STRING_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _compact(value: Any, *, list_limit: int = DEFAULT_LIST_LIMIT) -> Any:
    if isinstance(value, str):
        return _clip_string(value)
    if isinstance(value, list):
        return [_compact(item, list_limit=list_limit) for item in value[:list_limit]]
    if isinstance(value, dict):
        return {key: _compact(item, list_limit=list_limit) for key, item in value.items()}
    return value


def _pick(source: dict[str, Any] | None, keys: tuple[str, ...]) -> dict[str, Any] | None:
    if not isinstance(source, dict):
        return None
    result = {key: deepcopy(source[key]) for key in keys if key in source}
    return result or None


def optimize_dataset(dataset: dict[str, Any], *, max_chars: int = DEFAULT_MAX_CHARS) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a compact, deterministic AI input from Morning Dataset.

    The optimizer removes bulky raw/history payloads and keeps only current-day
    facts/features useful for morning reasoning. It never invents or summarizes
    missing facts; omitted data is reported in optimizer diagnostics.
    """
    raw_text = json.dumps(dataset, ensure_ascii=False, separators=(",", ":"))

    optimized: dict[str, Any] = {
        "schema_version": dataset.get("schema_version"),
        "generated_at": dataset.get("generated_at"),
        "as_of": dataset.get("as_of"),
        "data_quality": deepcopy(dataset.get("data_quality")),
        "warnings": _compact(dataset.get("warnings") or [], list_limit=10),
        "source_status": _compact(dataset.get("source_status") or [], list_limit=20),
        "market": _pick(
            dataset.get("market"),
            (
                "generated_at",
                "phase",
                "regime",
                "summary",
                "indices",
                "breadth",
                "sentiment",
                "risk_state",
                "leaders",
                "laggards",
                "data_quality",
                "universe",
            ),
        ),
        "portfolio": _pick(dataset.get("portfolio"), ("positions", "exposure", "pnl")),
        "capital": _pick(
            dataset.get("capital"),
            ("cash_available", "buying_power", "margin_usage", "target_reserve", "capital_state"),
        ),
        "candidates": _compact(dataset.get("candidates"), list_limit=10),
        "investor_dna": _pick(
            dataset.get("investor_dna"),
            (
                "native_dna",
                "environment_fit",
                "style_drift",
                "risk_patterns",
                "summary",
                "security_compatibility",
            ),
        ),
        "events": _compact(dataset.get("events"), list_limit=10),
        "watchlist": _compact(dataset.get("watchlist"), list_limit=10),
    }
    optimized = _compact(optimized, list_limit=10)

    optimized_text = json.dumps(optimized, ensure_ascii=False, separators=(",", ":"))
    if len(optimized_text) > max_chars:
        # Second pass for unusually large nested objects. Keep a strict hard cap
        # by progressively clipping serialized section payloads, never by adding
        # model-generated summaries.
        for key in ("market", "investor_dna", "portfolio", "events", "candidates", "watchlist"):
            value = optimized.get(key)
            if value is None:
                continue
            section = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if len(section) > 5_000:
                optimized[key] = {
                    "status": "TRUNCATED_BY_CONTEXT_OPTIMIZER",
                    "preview": _clip_string(section, 5_000),
                }
            optimized_text = json.dumps(optimized, ensure_ascii=False, separators=(",", ":"))
            if len(optimized_text) <= max_chars:
                break

    if len(optimized_text) > max_chars:
        optimized["optimizer_warning"] = "optimized payload exceeded hard cap; low-priority sections removed"
        for key in ("watchlist", "candidates", "events"):
            optimized[key] = None
            optimized_text = json.dumps(optimized, ensure_ascii=False, separators=(",", ":"))
            if len(optimized_text) <= max_chars:
                break

    raw_chars = len(raw_text)
    optimized_chars = len(optimized_text)
    diagnostics = {
        "raw_dataset_chars": raw_chars,
        "optimized_prompt_chars": optimized_chars,
        "reduction_ratio": round(1 - (optimized_chars / raw_chars), 4) if raw_chars else 0.0,
        "estimated_input_tokens": max(1, round(optimized_chars / 4)),
        "hard_cap_chars": max_chars,
        "status": "OK" if optimized_chars <= max_chars else "OVER_LIMIT",
    }
    return optimized, diagnostics
