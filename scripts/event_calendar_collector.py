#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

EVENT_KEYS = ("earnings", "economic", "policy", "market_calendar", "company")
WHEN_KEYS = ("date", "scheduled_at", "timestamp")


@dataclass(frozen=True)
class SourceSpec:
    category: str
    path: Path
    source: str


def _when(item: dict[str, Any]) -> str | None:
    for key in WHEN_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _title(item: dict[str, Any]) -> str | None:
    value = item.get("title") or item.get("name")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _event_key(category: str, item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        category,
        (_when(item) or "")[:16],
        (_title(item) or "").casefold(),
        str(item.get("security_code") or item.get("company") or "").casefold(),
    )


def _normalize_item(category: str, item: Any, source_name: str) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    title = _title(item)
    when = _when(item)
    if not title or not when:
        return None
    result = dict(item)
    result.setdefault("category", category)
    result.setdefault("source", source_name)
    return result


def load_source(spec: SourceSpec) -> tuple[list[dict[str, Any]], bool, str | None]:
    """Return events, coverage-confirmed flag and error.

    A source is complete only when its file explicitly declares `coverage_confirmed`.
    Missing or malformed source files never become an empty confirmed calendar.
    """
    if not spec.path.is_file():
        return [], False, "source file missing"
    try:
        raw = json.loads(spec.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], False, f"source read failed: {exc}"
    if not isinstance(raw, dict):
        return [], False, "source payload must be an object"
    values = raw.get("events")
    if not isinstance(values, list):
        return [], False, "source events must be an array"
    events = [event for value in values if (event := _normalize_item(spec.category, value, spec.source))]
    malformed = len(values) - len(events)
    error = f"ignored {malformed} malformed event(s)" if malformed else None
    return events, raw.get("coverage_confirmed") is True, error


def collect(specs: list[SourceSpec], *, as_of: str) -> dict[str, Any]:
    events: dict[str, list[dict[str, Any]]] = {key: [] for key in EVENT_KEYS}
    coverage = {key: False for key in EVENT_KEYS}
    diagnostics: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for spec in specs:
        if spec.category not in EVENT_KEYS:
            raise ValueError(f"unknown event category: {spec.category}")
        source_events, complete, error = load_source(spec)
        coverage[spec.category] = coverage[spec.category] or complete
        accepted = 0
        for item in source_events:
            key = _event_key(spec.category, item)
            if key in seen:
                continue
            seen.add(key)
            events[spec.category].append(item)
            accepted += 1
        diagnostics.append({
            "category": spec.category,
            "source": spec.source,
            "path": str(spec.path),
            "coverage_confirmed": complete,
            "accepted": accepted,
            "error": error,
        })

    for key in EVENT_KEYS:
        events[key].sort(key=lambda item: (_when(item) or "", _title(item) or ""))

    total = sum(len(values) for values in events.values())
    all_covered = all(coverage.values())
    payload: dict[str, Any] = {
        "as_of": as_of,
        "source": "deterministic repository event aggregation",
        "coverage": coverage,
        "events": events,
        "collector_diagnostics": diagnostics,
    }
    if total == 0 and all_covered:
        payload["empty_confirmed"] = True
    return payload


def parse_source(value: str) -> SourceSpec:
    # CATEGORY=PATH[|SOURCE_NAME]
    if "=" not in value:
        raise argparse.ArgumentTypeError("source must be CATEGORY=PATH[|SOURCE_NAME]")
    category, rest = value.split("=", 1)
    if "|" in rest:
        path, source = rest.split("|", 1)
    else:
        path, source = rest, Path(rest).stem
    category = category.strip()
    if category not in EVENT_KEYS:
        raise argparse.ArgumentTypeError(f"category must be one of: {', '.join(EVENT_KEYS)}")
    return SourceSpec(category, Path(path.strip()), source.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate reviewed/official event inputs into canonical calendar.json")
    parser.add_argument("--source", action="append", type=parse_source, default=[], help="CATEGORY=PATH[|SOURCE_NAME]")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=Path("data/events/calendar.json"))
    args = parser.parse_args()

    datetime.strptime(args.as_of, "%Y-%m-%d")
    payload = collect(args.source, as_of=args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Event calendar: {args.output}")
    print("Coverage:", payload["coverage"])
    print("Events:", sum(len(v) for v in payload["events"].values()))


if __name__ == "__main__":
    main()
