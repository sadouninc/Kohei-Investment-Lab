from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any

from .schema import EMPTY_DATASET, SCHEMA_VERSION
from .validator import validate_dataset


def load_json_source(path: Path | None) -> dict[str, Any] | list[Any] | None:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _source_record(name: str, value: Any, *, source: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "source": source,
        "as_of": as_of,
        "status": "OK" if value is not None else "MISSING",
    }


def _quality(source_status: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(source_status)
    available = sum(row["status"] == "OK" for row in source_status)
    completeness = 1.0 if total == 0 else available / total
    if completeness == 1.0:
        status = "OK"
    elif completeness == 0.0:
        status = "MISSING"
    else:
        status = "PARTIAL"
    return {
        "status": status,
        "completeness": round(completeness, 4),
        "available_sources": available,
        "total_sources": total,
    }


def build_dataset(
    *,
    generated_at: datetime | None = None,
    as_of: date | None = None,
    market: dict[str, Any] | None = None,
    portfolio: dict[str, Any] | None = None,
    capital: dict[str, Any] | None = None,
    candidates: list[dict[str, Any]] | dict[str, Any] | None = None,
    investor_dna: dict[str, Any] | None = None,
    events: dict[str, Any] | None = None,
    watchlist: list[Any] | None = None,
    source_metadata: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the deterministic AI-input contract.

    Missing values remain None. This layer does not infer, rank, recommend, or
    fill absent facts. AI reasoning belongs downstream of this contract.
    """
    now = generated_at or datetime.now().astimezone()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    target_date = as_of or now.date()

    payload = deepcopy(EMPTY_DATASET)
    payload.update(
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": now.isoformat(timespec="seconds"),
            "as_of": target_date.isoformat(),
        }
    )

    supplied = {
        "market": market,
        "portfolio": portfolio,
        "capital": capital,
        "candidates": candidates,
        "investor_dna": investor_dna,
        "events": events,
        "watchlist": watchlist,
    }
    for key, value in supplied.items():
        if value is not None:
            payload[key] = deepcopy(value)

    metadata = source_metadata or {}
    payload["source_status"] = [
        _source_record(
            key,
            value,
            source=metadata.get(key, {}).get("source"),
            as_of=metadata.get(key, {}).get("as_of"),
        )
        for key, value in supplied.items()
    ]
    payload["data_quality"] = _quality(payload["source_status"])
    payload["warnings"] = [
        f"{row['name']} source is missing"
        for row in payload["source_status"]
        if row["status"] == "MISSING"
    ]
    return validate_dataset(payload)


def write_dataset(payload: dict[str, Any], output: Path) -> Path:
    validate_dataset(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
