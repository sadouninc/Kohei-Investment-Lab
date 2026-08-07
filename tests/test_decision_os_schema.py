from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from init_decision_os_db import TARGETS, migrate_all, migrate_target  # noqa: E402


EXPECTED_MASTER_TABLES = {
    "schema_migrations",
    "decision_securities",
    "decision_themes",
    "decision_security_themes",
    "universe_membership",
    "model_versions",
    "routine_versions",
    "framework_metadata",
}

EXPECTED_HISTORY_TABLES = {
    "schema_migrations",
    "portfolio_snapshots",
    "position_snapshots",
    "capital_snapshots",
    "signals",
    "market_states",
    "capital_policies",
    "candidates",
    "candidate_factors",
    "decisions",
    "decision_checks",
    "decision_trade_links",
    "outcomes",
    "missed_opportunities",
    "daily_reviews",
    "investor_dna_profiles",
    "security_behavior_profiles",
    "compatibility_assessments",
    "compatibility_factors",
    "strategy_experiments",
    "investor_environment_profiles",
    "investor_style_periods",
    "environment_fit_assessments",
    "security_lifetime_contributions",
    "theme_lifetime_contributions",
    "risk_pattern_assessments",
    "daily_dna_fit_assessments",
}

EXPECTED_ANALYSIS_TABLES = {
    "schema_migrations",
    "market_observations",
    "security_observations",
    "order_book_snapshots",
    "intraday_features",
    "analysis_cache",
}


def tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }


class DecisionOSSchemaTest(unittest.TestCase):
    def test_split_migrations_create_expected_databases_and_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_dir = Path(temp_dir)
            first = migrate_all(db_dir)
            second = migrate_all(db_dir)

            self.assertEqual(["001_master_schema.sql"], first["master"][1])
            self.assertEqual(
                ["001_history_schema.sql", "002_investor_dna.sql", "003_investor_dna_v2.sql"],
                first["history"][1],
            )
            self.assertEqual(["001_analysis_schema.sql"], first["analysis"][1])
            for name in TARGETS:
                self.assertEqual([], second[name][1])

            self.assertTrue(EXPECTED_MASTER_TABLES.issubset(tables(db_dir / "master.db")))
            self.assertTrue(EXPECTED_HISTORY_TABLES.issubset(tables(db_dir / "history.db")))
            self.assertTrue(EXPECTED_ANALYSIS_TABLES.issubset(tables(db_dir / "analysis.db")))

    def test_fact_model_and_human_layers_remain_separate_across_databases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_dir = Path(temp_dir)
            migrate_all(db_dir)

            with sqlite3.connect(db_dir / "master.db") as master:
                master.execute(
                    "INSERT INTO decision_securities(security_code, name) VALUES (?, ?)",
                    ("6702", "富士通"),
                )
                master.commit()

            with sqlite3.connect(db_dir / "analysis.db") as analysis:
                analysis.execute(
                    """
                    INSERT INTO security_observations(
                        security_code, observed_at, timeframe, close, source
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    ("6702", "2026-08-07T10:00:00+09:00", "1m", 3674.0, "test"),
                )
                analysis.commit()

            with sqlite3.connect(db_dir / "history.db") as history:
                history.execute(
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
                candidate_id = history.execute(
                    "SELECT id FROM candidates WHERE security_code = '6702'"
                ).fetchone()[0]
                history.execute(
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
                history.commit()

            with sqlite3.connect(db_dir / "analysis.db") as analysis:
                observation_count = analysis.execute(
                    "SELECT COUNT(*) FROM security_observations"
                ).fetchone()[0]
            with sqlite3.connect(db_dir / "history.db") as history:
                decision_count = history.execute(
                    "SELECT COUNT(*) FROM decisions"
                ).fetchone()[0]

            self.assertEqual(1, observation_count)
            self.assertEqual(1, decision_count)

    def test_single_target_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_dir = Path(temp_dir)
            path, applied = migrate_target("master", db_dir)
            self.assertEqual(db_dir / "master.db", path)
            self.assertEqual(["001_master_schema.sql"], applied)
            self.assertFalse((db_dir / "history.db").exists())
            self.assertFalse((db_dir / "analysis.db").exists())


if __name__ == "__main__":
    unittest.main()
