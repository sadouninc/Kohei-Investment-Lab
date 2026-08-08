from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re

from .base import ProviderResult

LAST_UPDATED_RE = re.compile(r"最終更新:\s*(20\d{2}-\d{2}-\d{2})")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^[-*]\s+(.+?)\s*$")
DETAIL_RE = re.compile(r"^(?P<name>.+?)（(?P<details>.+)）$")


@dataclass
class PortfolioProvider:
    path: Path = Path("Current_Status.md")
    max_age_days: int = 3
    today: date | None = None
    name: str = "portfolio"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical portfolio source not found",
                source_reference=str(self.path),
            )

        text = self.path.read_text(encoding="utf-8")
        match = LAST_UPDATED_RE.search(text)
        as_of = match.group(1) if match else None
        lines = self._portfolio_lines(text)
        if not lines:
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                as_of=as_of,
                source_reference=str(self.path),
                reason="Portfolio section contains no active holdings",
            )

        positions = []
        malformed = 0
        for line in lines:
            bullet = BULLET_RE.match(line)
            if not bullet:
                if line.strip():
                    malformed += 1
                continue
            raw = bullet.group(1).strip()
            detail = DETAIL_RE.match(raw)
            if detail:
                positions.append(
                    {
                        "name": detail.group("name").strip(),
                        "details": detail.group("details").strip(),
                    }
                )
            else:
                positions.append({"name": raw, "details": None})

        if not positions:
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                as_of=as_of,
                source_reference=str(self.path),
                reason="Portfolio section could not be parsed into holdings",
            )

        payload = {
            "positions": positions,
            "exposure": None,
            "pnl": None,
        }

        if malformed:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"{malformed} Portfolio line(s) were not parseable",
                data=payload,
            )

        if as_of is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                source_reference=str(self.path),
                reason="portfolio holdings parsed but source has no explicit last-updated date",
                data=payload,
            )

        age = (self.today or date.today()) - datetime.strptime(as_of, "%Y-%m-%d").date()
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"portfolio snapshot is {age.days} days old (freshness limit {self.max_age_days})",
                data=payload,
            )

        return ProviderResult.ok(
            self.name,
            payload,
            as_of=as_of,
            source_reference=str(self.path),
        )

    @staticmethod
    def _portfolio_lines(text: str) -> list[str]:
        in_portfolio = False
        found = False
        result: list[str] = []
        for line in text.splitlines():
            heading = HEADING_RE.match(line)
            if heading:
                title = heading.group(1).strip().lower()
                if in_portfolio:
                    break
                in_portfolio = title == "portfolio"
                found = found or in_portfolio
                continue
            if in_portfolio:
                result.append(line)
        return result if found else []
