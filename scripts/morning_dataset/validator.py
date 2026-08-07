from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .schema import SCHEMA_VERSION, STATUS_VALUES, TOP_LEVEL_FIELDS


class MorningDatasetValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MorningDatasetValidationError(message)


def validate_dataset(payload: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(payload, dict), "dataset must be an object")
    missing = [key for key in TOP_LEVEL_FIELDS if key not in payload]
    _require(not missing, f"missing top-level fields: {', '.join(missing)}")
    _require(payload["schema_version"] == SCHEMA_VERSION, "unsupported schema_version")

    for key in ("generated_at", "as_of"):
        value = payload[key]
        _require(isinstance(value, str) and value, f"{key} must be a non-empty string")
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise MorningDatasetValidationError(f"{key} must be ISO-8601") from exc

    quality = payload["data_quality"]
    _require(isinstance(quality, dict), "data_quality must be an object")
    _require(quality.get("status") in STATUS_VALUES, "invalid data_quality.status")
    _require(isinstance(quality.get("completeness"), (int, float)), "data_quality.completeness must be numeric")
    _require(0 <= float(quality["completeness"]) <= 1, "data_quality.completeness must be 0..1")

    _require(isinstance(payload["source_status"], list), "source_status must be an array")
    for source in payload["source_status"]:
        _require(isinstance(source, dict), "source_status entries must be objects")
        _require(source.get("status") in STATUS_VALUES, "invalid source status")
        _require(bool(source.get("name")), "source status needs name")

    # Serialization is part of the public contract.
    json.dumps(payload, ensure_ascii=False)
    return payload
