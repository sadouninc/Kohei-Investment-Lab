import importlib.util
import json
from contextlib import closing
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_script(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


episodes_module = load_script("build_trade_episodes")
reports_module = load_script("generate_advanced_trade_reports")
public_module = load_script("generate_public_trade_dashboard")

EXECUTION_SCHEMA = """
CREATE TABLE executions (
 id INTEGER PRIMARY KEY, trade_date TEXT NOT NULL, account TEXT,
 product TEXT, transaction_type TEXT, side TEXT NOT NULL, security_code TEXT,
 security_name TEXT NOT NULL, quantity REAL NOT NULL, price REAL NOT NULL,
 fee REAL, tax REAL
);
CREATE TABLE closed_trades (
 id INTEGER PRIMARY KEY, open_execution_id INTEGER, close_execution_id INTEGER
);
"""


def insert_execution(db, values):
    db.execute(
        """INSERT INTO executions
        (id,trade_date,account,product,transaction_type,side,security_code,
         security_name,quantity,price,fee,tax)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        values,
    )


class AdvancedTradeAnalysisTest(unittest.TestCase):
    def create_database(self, path):
        db = sqlite3.connect(path)
        db.executescript(EXECUTION_SCHEMA)
        rows = [
            (1, "2026-07-01", "特定", "株式", "現物買", "BUY", "1001", "銘柄A", 100, 1000, 10, 0),
            (2, "2026-07-02", "特定", "株式", "現物買", "BUY", "1001", "銘柄A", 50, 1100, 5, 0),
            (3, "2026-07-03", "特定", "株式", "現物売", "SELL", "1001", "銘柄A", 70, 1200, 7, 0),
            (4, "2026-07-06", "特定", "株式", "現物売", "SELL", "1001", "銘柄A", 80, 1300, 8, 0),
            (5, "2026-07-07", "特定", "信用", "信用新規売", "SELL", "2002", "銘柄B", 100, 2000, 10, 0),
            (6, "2026-07-09", "特定", "信用", "信用返済買", "BUY", "2002", "銘柄B", 100, 1800, 10, 0),
            (7, "2026-07-10", "一般", "株式", "現物買", "BUY", "3003", "銘柄C", 100, 500, 0, 0),
            (8, "2026-07-11", "一般", "株式", "現物売", "SELL", "3003", "銘柄C", 40, 550, 0, 0),
        ]
        for row in rows:
            insert_execution(db, row)
        db.commit()
        db.close()

    def test_episode_boundaries_partial_fills_and_stable_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trades.sqlite"
            self.create_database(path)
            with closing(sqlite3.connect(path)) as db:
                episodes = episodes_module.build_episodes(db)
                episodes_module.persist(db, episodes)
                first_ids = dict(db.execute(
                    "SELECT episode_key,id FROM trade_episodes"
                ).fetchall())
                episodes_module.persist(db, episodes_module.build_episodes(db))
                second_ids = dict(db.execute(
                    "SELECT episode_key,id FROM trade_episodes"
                ).fetchall())
                rows = db.execute(
                    "SELECT * FROM trade_episodes ORDER BY first_execution_id"
                ).fetchall()

            self.assertEqual(first_ids, second_ids)
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["status"], "CLOSED")
            self.assertEqual(rows[0]["open_execution_count"], 2)
            self.assertEqual(rows[0]["close_execution_count"], 2)
            self.assertEqual(rows[0]["holding_days"], 5)
            self.assertAlmostEqual(rows[0]["gross_pnl"], 33000)
            self.assertEqual(rows[1]["position_side"], "SHORT")
            self.assertAlmostEqual(rows[1]["gross_pnl"], 20000)
            self.assertEqual(rows[2]["status"], "OPEN")
            self.assertEqual(rows[2]["total_close_quantity"], 40)

    def test_advanced_metrics_and_public_payload_are_anonymous(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trades.sqlite"
            self.create_database(path)
            with closing(sqlite3.connect(path)) as db:
                episodes_module.persist(db, episodes_module.build_episodes(db))
                rows = reports_module.load_closed_episodes(db)
            analysis = reports_module.build_analysis(rows)
            self.assertEqual(analysis["overall"]["trade_count"], 2)
            self.assertEqual(analysis["overall"]["win_count"], 2)
            self.assertEqual(analysis["overall"]["max_win_streak"], 2)
            self.assertEqual(len(analysis["holding_periods"]), 8)

            payload = public_module.build_public_payload(rows, "2026-08-05")
            public_module.assert_public(payload)
            serialized = json.dumps(payload, ensure_ascii=False)
            for private_value in ("銘柄A", "銘柄B", "1001", "2002", "33000", "20000"):
                self.assertNotIn(private_value, serialized)
            self.assertEqual(payload["summary"]["trade_count"], 2)
            self.assertIn("indexed_expectancy", payload["summary"])

    def test_period_breakdowns_reconcile_with_all_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trades.sqlite"
            self.create_database(path)
            with closing(sqlite3.connect(path)) as db:
                episodes_module.persist(db, episodes_module.build_episodes(db))
                rows = reports_module.load_closed_episodes(db)
            analysis = reports_module.build_analysis(rows)
            overall = analysis["overall"]

            for key in ("by_year", "by_month", "by_account_type", "holding_periods"):
                self.assertEqual(
                    sum(item["trade_count"] for item in analysis[key]),
                    overall["trade_count"],
                    key,
                )
            for key in ("by_year", "by_month"):
                self.assertAlmostEqual(
                    sum(item["net_pnl"] for item in analysis[key]),
                    overall["net_pnl"],
                    msg=key,
                )
            self.assertEqual(
                overall["win_count"]
                + overall["loss_count"]
                + overall["breakeven_count"],
                overall["trade_count"],
            )

    def test_empty_dataset_builds_public_payload(self):
        payload = public_module.build_public_payload([], "2026-08-05")
        public_module.assert_public(payload)
        self.assertEqual(payload["summary"]["trade_count"], 0)
        self.assertEqual(payload["years"], [])
        self.assertEqual(payload["months"], [])
        self.assertEqual(payload["monthly_equity_curve"]["points"], [])

    def test_private_outputs_remain_under_generated_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "trades.sqlite"
            output = root / "data" / "generated"
            self.create_database(path)
            with closing(sqlite3.connect(path)) as db:
                episodes_module.persist(db, episodes_module.build_episodes(db))
                rows = reports_module.load_closed_episodes(db)
            reports_module.write_reports(output, rows, reports_module.build_analysis(rows))
            self.assertTrue((output / "trade_episodes.csv").is_file())
            self.assertTrue((output / "Advanced_Trading_Statistics.md").is_file())


if __name__ == "__main__":
    unittest.main()

