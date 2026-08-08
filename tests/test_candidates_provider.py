from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.morning_dataset.providers.candidates import CandidatesProvider


SCHEMA = """
CREATE TABLE candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    security_code TEXT,
    horizon TEXT,
    universe_state TEXT,
    long_score REAL,
    today_score REAL,
    risk_score REAL,
    personal_fit REAL,
    capital_feasibility REAL,
    rotation_score REAL,
    rank INTEGER,
    status TEXT,
    confidence REAL,
    model_name TEXT,
    model_version TEXT
);
CREATE TABLE candidate_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    factor_type TEXT,
    factor_key TEXT,
    value_numeric REAL,
    value_text TEXT,
    contribution REAL,
    polarity TEXT,
    source_reference TEXT
);
"""


class CandidatesProviderTest(unittest.TestCase):
    def db(self, root: Path) -> Path:
        path = root / "history.db"
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()
        return path

    def insert(self, path: Path, generated_at: str, code: str | None, rank: int, status: str | None, today_score: float = 80):
        conn = sqlite3.connect(path)
        cur = conn.execute(
            """
            INSERT INTO candidates (
                generated_at, security_code, horizon, universe_state,
                long_score, today_score, risk_score, personal_fit,
                capital_feasibility, rotation_score, rank, status,
                confidence, model_name, model_version
            ) VALUES (?, ?, 'SHORT_SWING', 'ACTIVE', 70, ?, 20, 80, 90, 60, ?, ?, 0.8, 'candidate-v1', '1')
            """,
            (generated_at, code, today_score, rank, status),
        )
        conn.commit()
        conn.close()
        return cur.lastrowid

    def test_reads_latest_snapshot_in_rank_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.db(Path(tmp))
            self.insert(path, "2026-08-07T08:00:00+09:00", "1111", 1, "WATCH")
            self.insert(path, "2026-08-08T08:00:00+09:00", "2222", 2, "WATCH", 85)
            cid = self.insert(path, "2026-08-08T08:00:00+09:00", "3333", 1, "BUY_CANDIDATE", 90)
            conn = sqlite3.connect(path)
            conn.execute(
                "INSERT INTO candidate_factors (candidate_id, factor_type, factor_key, value_text, polarity) VALUES (?, 'positive', 'theme', 'AI strength', 'positive')",
                (cid,),
            )
            conn.commit()
            conn.close()

            result = CandidatesProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual(["3333", "2222"], [row["security_code"] for row in result.data])
            self.assertEqual("AI strength", result.data[0]["reasons"][0]["value_text"])

    def test_stale_snapshot_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.db(Path(tmp))
            self.insert(path, "2026-08-01", "1111", 1, "WATCH")
            result = CandidatesProvider(path, max_age_days=3, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertTrue(result.data)

    def test_missing_database_is_missing(self):
        result = CandidatesProvider(Path("/missing/history.db")).collect()
        self.assertEqual("MISSING", result.status)

    def test_missing_table_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.db"
            sqlite3.connect(path).close()
            result = CandidatesProvider(path).collect()
            self.assertEqual("MISSING", result.status)

    def test_incomplete_identity_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.db(Path(tmp))
            self.insert(path, "2026-08-08", None, 1, "WATCH")
            result = CandidatesProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)

    def test_limit_keeps_compact_top_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.db(Path(tmp))
            for rank in range(1, 13):
                self.insert(path, "2026-08-08", str(1000 + rank), rank, "WATCH", 100-rank)
            result = CandidatesProvider(path, limit=5, today=date(2026, 8, 8)).collect()
            self.assertEqual(5, len(result.data))
            self.assertEqual([1, 2, 3, 4, 5], [row["rank"] for row in result.data])


if __name__ == "__main__":
    unittest.main()
