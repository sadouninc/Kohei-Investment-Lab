from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re

from .base import ProviderResult

LAST_UPDATED_RE = re.compile(r"最終更新:\s*(20\d{2}-\d{2}-\d{2})")
SECTION_AS_OF_RE = re.compile(r"^>\s*as_of:\s*(20\d{2}-\d{2}-\d{2})\s*$", re.IGNORECASE)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^[-*]\s+(.+?)\s*$")


@dataclass
class WatchlistProvider:
    path: Path = Path("Current_Status.md")
    max_age_days: int = 3
    today: date | None = None
    name: str = "watchlist"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(self.name, reason="canonical watchlist source not found", source_reference=str(self.path))
        text = self.path.read_text(encoding="utf-8")
        lines = self._section_lines(text, "current focus")
        section_date = next((m.group(1) for line in lines if (m := SECTION_AS_OF_RE.match(line))), None)
        global_match = LAST_UPDATED_RE.search(text)
        as_of = section_date or (global_match.group(1) if global_match else None)
        if not lines:
            return ProviderResult.unavailable(self.name, status="MISSING", as_of=as_of, source_reference=str(self.path), reason="Current Focus section contains no active watch items")

        items = []
        malformed = 0
        for line in lines:
            if not line.strip() or line.startswith(">"):
                continue
            match = BULLET_RE.match(line)
            if not match:
                malformed += 1
                continue
            value = match.group(1).strip()
            if value:
                items.append({"text": value, "security_code": None, "name": None, "theme": None, "reason": value, "priority": None})
        if not items:
            return ProviderResult.unavailable(self.name, status="MISSING", as_of=as_of, source_reference=str(self.path), reason="Current Focus section could not be parsed into watch items")
        payload = {"items": items}
        if malformed:
            return ProviderResult.unavailable(self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path), reason=f"{malformed} Current Focus line(s) were not parseable", data=payload)
        if as_of is None:
            return ProviderResult.unavailable(self.name, status="PARTIAL", source_reference=str(self.path), reason="watchlist parsed but section has no freshness date", data=payload)
        age = (self.today or date.today()) - datetime.strptime(as_of, "%Y-%m-%d").date()
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(self.name, status="STALE", as_of=as_of, source_reference=str(self.path), reason=f"watchlist snapshot is {age.days} days old (freshness limit {self.max_age_days})", data=payload)
        return ProviderResult.ok(self.name, payload, as_of=as_of, source_reference=str(self.path))

    @staticmethod
    def _section_lines(text: str, target: str) -> list[str]:
        in_section = False
        found = False
        result = []
        for line in text.splitlines():
            heading = HEADING_RE.match(line)
            if heading:
                if in_section:
                    break
                in_section = heading.group(1).strip().lower() == target
                found = found or in_section
                continue
            if in_section:
                result.append(line)
        return result if found else []
