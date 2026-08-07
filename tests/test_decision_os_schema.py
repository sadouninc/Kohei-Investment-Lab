from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from init_decision_os_db import apply_migrations  # noqa: E402


EXPECTED_TABLES = {
    "schema_migrations",
    "decision_securities",
    "decision_themes",
    "decision_security_themes",
    "universe_membership",
    "market_observations",
    "security_observations",
    "model_versions",
    "routine_versions",
    "signals",
    "market_states",
    "portfolio_snapshots",
    "position_snapshots",
    "capital_snapshots",
    "capital_policies",
    "candidates",
    "candidate_factors",
    "decisions",
    "decision_checks",
    "decision_trade_links",
    "outcomes",
    "missed_opportunities",
    "daily_reviews",
}


class DecisionOSSchemaTest(unittest.TestCase):
    def test_migration_creates_expected_tables_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "investment.db"
            first = apply_migrations(db_path)
            second = apply_migrations(db_path)

            self.assertIn("001_decision_os_schema.sql", first)
            self.assertEqual([], second)

            with sqlite3.connect(db_path) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                self.assertTrue(EXPECTED_TABLES.issubset(tables))
                migration_count = connection.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE version = '001'"
                ).fetchone()[0]
                self.assertEqual(1, migration_count)

    def test_fact_and_decision_layers_remain_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "investment.db"
            apply_migrations(db_path)

            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    "INSERT INTO decision_securities(security_code, name) VALUES (?, ?)",
                    ("6702", "富士通"),
                )
                connection.execute(
                    """
                    INSERT INTO security_observations(
                        security_code, observed_at, timeframe, close, source
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    ("6702", "2026-08-07T10:00:00+09:00", "1m", 3674.0, "test"),
                )
                connection.execute(
                    """
                    INSERT INTO candidates(
                        generated_at, security_code, horizon, today_score, status,
                        model_name, model_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "2026-08-07T10:00:00+09:00",
                        "6702",
                        "ULTRA_SHORT",
                        92.0,
                        "BUY_CANDIDATE",
                        "candidate-engine",
                        "v0.1",
                    ),
                )
                candidate_id = connection.execute(
                    "SELECT id FROM candidates WHERE security_code = '6702'"
                ).fetchone()[0]
                connection.execute(
                    """
                    INSERT INTO decisions(
                        candidate_id, security_code, decision_at,
                        ai_suggestion, human_decision, reason
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate_id,
                        "6702",
                        "2026-08-07T10:01:00+09:00",
                        "BUY_CANDIDATE",
                        "WATCH",
                        "板と歩み値を確認するまで待つ",
                    ),
                )
                connection.commit()

                observation_count = connection.execute(
                    "SELECT COUNT(*) FROM security_observations"
                ).fetchone()[0]
                decision_count = connection.execute(
                    "SELECT COUNT(*) FROM decisions"
                ).fetchone()[0]
                self.assertEqual(1, observation_count)
                self.assertEqual(1, decision_count)


if __name__ == "__main__":
    unittest.main()
