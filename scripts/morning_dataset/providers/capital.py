from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import sqlite3

from .base import ProviderResult


@dataclass
class CapitalProvider:
    path: Path = Path("data/database/history.db")
    max_age_days: int = 3
    today: date | None = None
    name: str = "capital"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical capital history database not found",
                source_reference=str(self.path),
            )

        try:
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='capital_snapshots'"
                ).fetchone()
                if table is None:
                    return ProviderResult.unavailable(
                        self.name,
                        reason="capital_snapshots table not found in canonical history database",
                        source_reference=str(self.path),
                    )

                row = connection.execute(
                    """
                    SELECT snapshot_at,
                           cash_buying_power,
                           margin_buying_power,
                           cash_ratio,
                           margin_exposure,
                           margin_ratio,
                           total_exposure,
                           reserve_amount,
                           source,
                           source_version
                      FROM capital_snapshots
                  ORDER BY snapshot_at DESC, id DESC
                     LIMIT 1
                    """
                ).fetchone()
            finally:
                connection.close()
        except sqlite3.Error as exc:
            return ProviderResult.unavailable(
                self.name,
                reason=f"failed to read canonical capital database: {exc}",
                source_reference=str(self.path),
            )

        if row is None:
            return ProviderResult.unavailable(
                self.name,
                reason="canonical capital history contains no snapshots",
                source_reference=str(self.path),
            )

        as_of = self._as_of(row["snapshot_at"])
        payload = {
            # capital_snapshots stores buying power, not a brokerage cash balance.
            # Do not relabel buying power as cash available.
            "cash_available": None,
            "buying_power": {
                "cash": row["cash_buying_power"],
                "margin": row["margin_buying_power"],
            },
            "margin_usage": {
                "exposure": row["margin_exposure"],
                "ratio": row["margin_ratio"],
            },
            "target_reserve": row["reserve_amount"],
            "capital_state": {
                "cash_ratio": row["cash_ratio"],
                "total_exposure": row["total_exposure"],
                "source": row["source"],
                "source_version": row["source_version"],
            },
        }

        facts = (
            row["cash_buying_power"],
            row["margin_buying_power"],
            row["cash_ratio"],
            row["margin_exposure"],
            row["margin_ratio"],
            row["total_exposure"],
            row["reserve_amount"],
        )
        if all(value is None for value in facts):
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                as_of=as_of,
                source_reference=str(self.path),
                reason="latest capital snapshot contains no usable capital facts",
            )

        if as_of is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                source_reference=str(self.path),
                reason="capital facts exist but snapshot_at cannot be interpreted as a date",
                data=payload,
            )

        age = (self.today or date.today()) - datetime.strptime(as_of, "%Y-%m-%d").date()
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"capital snapshot is {age.days} days old (freshness limit {self.max_age_days})",
                data=payload,
            )

        # A fresh snapshot can still be partial when both forms of buying power are
        # unknown. Preserve the remaining facts without inventing brokerage values.
        if row["cash_buying_power"] is None and row["margin_buying_power"] is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason="capital snapshot is fresh but buying-power values are unavailable",
                data=payload,
            )

        return ProviderResult.ok(
            self.name,
            payload,
            as_of=as_of,
            source_reference=str(self.path),
        )

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
