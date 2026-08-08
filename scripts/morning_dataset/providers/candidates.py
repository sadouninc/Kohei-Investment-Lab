from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import sqlite3

from .base import ProviderResult


@dataclass
class CandidatesProvider:
    path: Path = Path("data/database/history.db")
    limit: int = 10
    max_age_days: int = 3
    today: date | None = None
    name: str = "candidates"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical candidate history database not found",
                source_reference=str(self.path),
            )
        try:
            conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                if not self._table_exists(conn, "candidates"):
                    return ProviderResult.unavailable(
                        self.name,
                        reason="candidates table not found in canonical history database",
                        source_reference=str(self.path),
                    )
                latest = conn.execute("SELECT MAX(generated_at) AS generated_at FROM candidates").fetchone()
                generated_at = latest["generated_at"] if latest else None
                if not generated_at:
                    return ProviderResult.unavailable(
                        self.name,
                        reason="canonical candidate history contains no candidate snapshots",
                        source_reference=str(self.path),
                    )
                rows = conn.execute(
                    """
                    SELECT id, generated_at, security_code, horizon, universe_state,
                           long_score, today_score, risk_score, personal_fit,
                           capital_feasibility, rotation_score, rank, status,
                           confidence, model_name, model_version
                      FROM candidates
                     WHERE generated_at = ?
                  ORDER BY CASE WHEN rank IS NULL THEN 1 ELSE 0 END, rank ASC, today_score DESC, id ASC
                     LIMIT ?
                    """,
                    (generated_at, self.limit),
                ).fetchall()
                has_factors = self._table_exists(conn, "candidate_factors")
                payload = [self._serialize_candidate(conn, row, has_factors) for row in rows]
            finally:
                conn.close()
        except sqlite3.Error as exc:
            return ProviderResult.unavailable(
                self.name,
                reason=f"failed to read canonical candidate database: {exc}",
                source_reference=str(self.path),
            )

        if not payload:
            return ProviderResult.unavailable(
                self.name,
                reason="latest candidate snapshot contains no candidates",
                source_reference=str(self.path),
            )

        as_of = self._as_of(generated_at)
        if as_of is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                source_reference=str(self.path),
                reason="candidate rows exist but generated_at cannot be interpreted as a date",
                data=payload,
            )

        age = (self.today or date.today()) - datetime.strptime(as_of, "%Y-%m-%d").date()
        if age.days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"candidate snapshot is {age.days} days old (freshness limit {self.max_age_days})",
                data=payload,
            )

        incomplete = any(not row.get("security_code") or not row.get("status") for row in payload)
        if incomplete:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=as_of,
                source_reference=str(self.path),
                reason="candidate snapshot is fresh but one or more rows lack required identity/status fields",
                data=payload,
            )

        return ProviderResult.ok(
            self.name,
            payload,
            as_of=as_of,
            source_reference=str(self.path),
        )

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    @staticmethod
    def _serialize_candidate(conn: sqlite3.Connection, row: sqlite3.Row, has_factors: bool) -> dict:
        reasons: list[dict] = []
        if has_factors:
            factors = conn.execute(
                """
                SELECT factor_type, factor_key, value_numeric, value_text,
                       contribution, polarity, source_reference
                  FROM candidate_factors
                 WHERE candidate_id = ?
              ORDER BY id ASC
                """,
                (row["id"],),
            ).fetchall()
            reasons = [dict(factor) for factor in factors]
        return {
            "security_code": row["security_code"],
            "rank": row["rank"],
            "horizon": row["horizon"],
            "universe_state": row["universe_state"],
            "long_score": row["long_score"],
            "today_score": row["today_score"],
            "risk_score": row["risk_score"],
            "personal_fit": row["personal_fit"],
            "capital_feasibility": row["capital_feasibility"],
            "rotation_score": row["rotation_score"],
            "status": row["status"],
            "confidence": row["confidence"],
            "model_name": row["model_name"],
            "model_version": row["model_version"],
            "reasons": reasons,
        }

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
