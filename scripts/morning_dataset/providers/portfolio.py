from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import json
import re

from .base import ProviderResult

LAST_UPDATED_RE = re.compile(r"最終更新:\s*(20\d{2}-\d{2}-\d{2})")
SECTION_AS_OF_RE = re.compile(r"^>\s*as_of:\s*(20\d{2}-\d{2}-\d{2})\s*$", re.IGNORECASE)
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
            return ProviderResult.unavailable(self.name, reason="canonical portfolio source not found", source_reference=str(self.path))

        if self.path.suffix.lower() == ".json":
            return self._collect_canonical_json()

        text = self.path.read_text(encoding="utf-8")
        lines = self._portfolio_lines(text)
        section_date = next((m.group(1) for line in lines if (m := SECTION_AS_OF_RE.match(line))), None)
        global_match = LAST_UPDATED_RE.search(text)
        as_of = section_date or (global_match.group(1) if global_match else None)
        if not lines:
            return ProviderResult.unavailable(self.name, status="MISSING", as_of=as_of, source_reference=str(self.path), reason="Portfolio section contains no active holdings")

        positions = []
        malformed = 0
        for line in lines:
            if not line.strip() or line.startswith(">"):
                continue
            bullet = BULLET_RE.match(line)
            if not bullet:
                malformed += 1
                continue
            raw = bullet.group(1).strip()
            detail = DETAIL_RE.match(raw)
            positions.append({"name": detail.group("name").strip(), "details": detail.group("details").strip()} if detail else {"name": raw, "details": None})

        if not positions:
            return ProviderResult.unavailable(self.name, status="MISSING", as_of=as_of, source_reference=str(self.path), reason="Portfolio section could not be parsed into holdings")
        payload = {"positions": positions, "exposure": None, "pnl": None}
        if malformed:
            return ProviderResult.unavailable(self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path), reason=f"{malformed} Portfolio line(s) were not parseable", data=payload)
        if as_of is None:
            return ProviderResult.unavailable(self.name, status="PARTIAL", source_reference=str(self.path), reason="portfolio holdings parsed but section has no freshness date", data=payload)
        age = (self.today or date.today()) - datetime.strptime(as_of, "%Y-%m-%d").date()
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(self.name, status="STALE", as_of=as_of, source_reference=str(self.path), reason=f"portfolio snapshot is {age.days} days old (freshness limit {self.max_age_days})", data=payload)
        return ProviderResult.ok(self.name, payload, as_of=as_of, source_reference=str(self.path))

    def _collect_canonical_json(self) -> ProviderResult:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                source_reference=str(self.path),
                reason=f"canonical portfolio JSON is invalid: {exc}",
            )
        positions = payload.get("positions")
        as_of = payload.get("verification_as_of") or payload.get("as_of")
        status = payload.get("verification_status")
        if not isinstance(positions, list) or not positions:
            return ProviderResult.unavailable(
                self.name, status="MISSING", as_of=as_of, source_reference=str(self.path),
                reason="Canonical Portfolio State contains no active positions",
            )
        data = {
            "positions": positions,
            "exposure": None,
            "pnl": None,
            "verification_status": status,
            "base_snapshot": payload.get("base_snapshot"),
            "verification_diff": payload.get("verification_diff") or [],
        }
        if status == "MISMATCH":
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path),
                reason="Canonical Portfolio State does not match the latest verification",
                data=data,
            )
        if status not in {"VERIFIED", "PROVISIONAL"}:
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path),
                reason=f"unknown portfolio verification status: {status!r}", data=data,
            )
        if not isinstance(as_of, str):
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", source_reference=str(self.path),
                reason="canonical portfolio has no as_of date", data=data,
            )
        try:
            parsed_as_of = datetime.strptime(as_of[:10], "%Y-%m-%d").date()
        except ValueError:
            return ProviderResult.unavailable(
                self.name, status="PARTIAL", as_of=as_of, source_reference=str(self.path),
                reason="canonical portfolio as_of is not YYYY-MM-DD", data=data,
            )
        age = (self.today or date.today()) - parsed_as_of
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name, status="STALE", as_of=as_of, source_reference=str(self.path),
                reason=f"portfolio snapshot is {age.days} days old (freshness limit {self.max_age_days})", data=data,
            )
        return ProviderResult.ok(self.name, data, as_of=as_of, source_reference=str(self.path))

    @staticmethod
    def _portfolio_lines(text: str) -> list[str]:
        in_portfolio = False
        found = False
        result = []
        for line in text.splitlines():
            heading = HEADING_RE.match(line)
            if heading:
                if in_portfolio:
                    break
                in_portfolio = heading.group(1).strip().lower() == "portfolio"
                found = found or in_portfolio
                continue
            if in_portfolio:
                result.append(line)
        return result if found else []
