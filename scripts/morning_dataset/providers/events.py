from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from .base import ProviderResult


EVENT_KEYS = ("earnings", "economic", "policy", "market_calendar", "company")


@dataclass
class EventsProvider:
    """Load the canonical repository event calendar without inventing events.

    The provider deliberately does not scrape or infer events. Upstream collectors or
    human-reviewed repository updates own event discovery; this provider normalizes
    the canonical calendar into the Morning Dataset and makes freshness explicit.
    """

    path: Path = Path("data/events/calendar.json")
    max_age_days: int = 1
    today: date | None = None
    name: str = "events"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical repository event calendar not found",
                source_reference=str(self.path),
            )

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ProviderResult.unavailable(
                self.name,
                reason=f"failed to read canonical event calendar: {exc}",
                source_reference=str(self.path),
            )

        if not isinstance(raw, dict):
            return ProviderResult.unavailable(
                self.name,
                reason="canonical event calendar must be a JSON object",
                source_reference=str(self.path),
            )

        as_of = self._as_of(raw.get("as_of") or raw.get("generated_at"))
        payload, missing_categories, invalid_items = self._normalize(raw)
        event_count = sum(len(payload[key]) for key in EVENT_KEYS)

        coverage = raw.get("coverage") if isinstance(raw.get("coverage"), dict) else {}
        source = raw.get("source")
        payload["coverage"] = coverage
        if source is not None:
            payload["source"] = source

        if event_count == 0 and not self._explicit_empty_confirmation(raw):
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                as_of=as_of,
                source_reference=str(self.path),
                reason="event calendar contains no events and does not explicitly confirm complete empty coverage",
            )

        if as_of is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                source_reference=str(self.path),
                reason="event data is usable but calendar as_of is missing or invalid",
                data=payload,
            )

        age_days = ((self.today or date.today()) - datetime.strptime(as_of, "%Y-%m-%d").date()).days
        if age_days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"event calendar is {age_days} days old (freshness limit {self.max_age_days})",
                data=payload,
            )

        if missing_categories or invalid_items or not self._coverage_complete(raw):
            details = []
            if missing_categories:
                details.append("missing categories: " + ", ".join(missing_categories))
            if invalid_items:
                details.append(f"ignored {invalid_items} malformed event item(s)")
            if not self._coverage_complete(raw):
                details.append("coverage is not explicitly complete")
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason="; ".join(details),
                data=payload,
            )

        return ProviderResult.ok(
            self.name,
            payload,
            as_of=as_of,
            source_reference=str(self.path),
        )

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str], int]:
        container = raw.get("events") if isinstance(raw.get("events"), dict) else raw
        payload: dict[str, Any] = {}
        missing: list[str] = []
        invalid = 0
        for key in EVENT_KEYS:
            value = container.get(key)
            if value is None:
                missing.append(key)
                payload[key] = []
                continue
            if not isinstance(value, list):
                missing.append(key)
                payload[key] = []
                invalid += 1
                continue
            normalized: list[dict[str, Any]] = []
            for item in value:
                if not isinstance(item, dict):
                    invalid += 1
                    continue
                # A title/name and date/timestamp are the minimum facts needed to
                # distinguish a real scheduled event from unsupported prose.
                title = item.get("title") or item.get("name")
                when = item.get("date") or item.get("scheduled_at") or item.get("timestamp")
                if not isinstance(title, str) or not title.strip() or not isinstance(when, str) or not when.strip():
                    invalid += 1
                    continue
                normalized.append(dict(item))
            payload[key] = normalized
        return payload, missing, invalid

    @staticmethod
    def _coverage_complete(raw: dict[str, Any]) -> bool:
        coverage = raw.get("coverage")
        if not isinstance(coverage, dict):
            return False
        return all(coverage.get(key) is True for key in EVENT_KEYS)

    @classmethod
    def _explicit_empty_confirmation(cls, raw: dict[str, Any]) -> bool:
        return raw.get("empty_confirmed") is True and cls._coverage_complete(raw)

    @staticmethod
    def _as_of(value: object) -> str | None:
        if not isinstance(value, str) or len(value) < 10:
            return None
        candidate = value[:10]
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
        except ValueError:
            return None
        return candidate
