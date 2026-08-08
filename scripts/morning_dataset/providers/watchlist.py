from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re

from .base import ProviderResult

LAST_UPDATED_RE = re.compile(r"最終更新:\s*(20\d{2}-\d{2}-\d{2})")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^[-*]\s+(.+?)\s*$")


@dataclass
class WatchlistProvider:
    """Read the repository's current focus list without inventing security metadata.

    Current_Status.md is the only current repository SSoT that explicitly records
    active focus/watch items.  Until a dedicated WatchList SSoT exists, `Current
    Focus` is treated as the canonical hand-off for Morning Dataset watchlist.
    """

    path: Path = Path("Current_Status.md")
    max_age_days: int = 3
    today: date | None = None
    name: str = "watchlist"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical watchlist source not found",
                source_reference=str(self.path),
            )

        text = self.path.read_text(encoding="utf-8")
        updated = LAST_UPDATED_RE.search(text)
        as_of = updated.group(1) if updated else None
        lines = self._section_lines(text, "current focus")
        if not lines:
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                as_of=as_of,
                source_reference=str(self.path),
                reason="Current Focus section contains no active watch items",
            )

        items = []
        malformed = 0
        for line in lines:
            if not line.strip():
                continue
            match = BULLET_RE.match(line)
            if not match:
                malformed += 1
                continue
            text_value = match.group(1).strip()
            if text_value:
                # Deliberately keep the repository wording intact.  A Current
                # Focus entry may be a security, theme, risk, or action item;
                # security code/theme/priority must not be inferred.
                items.append(
                    {
                        "text": text_value,
                        "security_code": None,
                        "name": None,
                        "theme": None,
                        "reason": text_value,
                        "priority": None,
                    }
                )

        if not items:
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                as_of=as_of,
                source_reference=str(self.path),
                reason="Current Focus section could not be parsed into watch items",
            )

        payload = {"items": items}
        if malformed:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"{malformed} Current Focus line(s) were not parseable",
                data=payload,
            )
        if as_of is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                source_reference=str(self.path),
                reason="watchlist parsed but source has no explicit last-updated date",
                data=payload,
            )

        age = (self.today or date.today()) - datetime.strptime(as_of, "%Y-%m-%d").date()
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"watchlist snapshot is {age.days} days old (freshness limit {self.max_age_days})",
                data=payload,
            )

        return ProviderResult.ok(
            self.name,
            payload,
            as_of=as_of,
            source_reference=str(self.path),
        )

    @staticmethod
    def _section_lines(text: str, target: str) -> list[str]:
        in_section = False
        found = False
        result: list[str] = []
        for line in text.splitlines():
            heading = HEADING_RE.match(line)
            if heading:
                title = heading.group(1).strip().lower()
                if in_section:
                    break
                in_section = title == target
                found = found or in_section
                continue
            if in_section:
                result.append(line)
        return result if found else []
