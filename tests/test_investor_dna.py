from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from init_decision_os_db import migrate_all  # noqa: E402
from investor_dna import build_report, persist_report  # noqa: E402


def trade(code: str, name: str, pnl: float, holding: int, close_date: str, close_price: float = 100.0) -> dict:
    return {
        "id": f"{code}-{close_date}-{pnl}",
        "security_code": code,
        "security_name": name,
        "open_date": "2026-01-01",
        "close_date": close_date,
        "average_close_price": close_price,
        "holding_days": holding,
        "net_pnl": pnl,
        "return_rate": pnl / 10000.0,
    }


class InvestorDNATest(unittest.TestCase):
    def test_insufficient_sample_is_unknown(self) -> None:
        payload = {
            "updated_date": "2026-08-07",
            "trades": [
                trade("1111", "Sample", 1000, 3, "2026-01-10"),
                trade("1111", "Sample", -200, 4, "2026-01-20"),
            ],
        }
        report = build_report(payload)
        row = report["securities"][0]
        self.assertEqual("UNKNOWN", row["primary_mismatch_code"])
        self.assertLess(row["confidence"], 0.5)

    def test_post_exit_rally_flags_holding_period_too_short(self) -> None:
        payload = {
            "updated_date": "2026-08-07",
            "trades": [
                trade("2222", "Rhythm", 500, 2, "2026-01-05"),
                trade("2222", "Rhythm", 700, 2, "2026-02-05"),
                trade("2222", "Rhythm", 400, 3, "2026-03-05"),
                trade("9999", "Baseline", 100, 8, "2026-04-05"),
                trade("9999", "Baseline", 100, 8, "2026-05-05"),
            ],
        }
        prices = {
            "2222": [
                {"date": "2026-01-06", "close": 101},
                {"date": "2026-01-07", "close": 102},
                {"date": "2026-01-08", "close": 103},
                {"date": "2026-01-09", "close": 104},
                {"date": "2026-01-10", "close": 106},
                {"date": "2026-02-06", "close": 101},
                {"date": "2026-02-07", "close": 102},
                {"date": "2026-02-08", "close": 103},
                {"date": "2026-02-09", "close": 104},
                {"date": "2026-02-10", "close": 107},
                {"date": "2026-03-06", "close": 101},
                {"date": "2026-03-07", "close": 102},
                {"date": "2026-03-08", "close": 103},
                {"date": "2026-03-09", "close": 104},
                {"date": "2026-03-10", "close": 108},
            ]
        }
        report = build_report(payload, prices)
        row = next(r for r in report["securities"] if r["security_code"] == "2222")
        self.assertEqual("HOLDING_PERIOD_TOO_SHORT", row["primary_mismatch_code"])
        self.assertGreater(row["median_post_exit_return_5d"], 0.03)

    def test_profitable_high_win_security_scores_above_weak_security(self) -> None:
        payload = {
            "trades": [
                trade("A", "Strong", 1000, 5, "2026-01-05"),
                trade("A", "Strong", 800, 5, "2026-01-10"),
                trade("A", "Strong", -100, 6, "2026-01-15"),
                trade("B", "Weak", 100, 5, "2026-02-05"),
                trade("B", "Weak", -1000, 5, "2026-02-10"),
                trade("B", "Weak", -800, 6, "2026-02-15"),
            ]
        }
        report = build_report(payload)
        scores = {row["security_code"]: row["compatibility_score"] for row in report["securities"]}
        self.assertGreater(scores["A"], scores["B"])

    def test_report_persists_to_history_database(self) -> None:
        payload = {"updated_date": "2026-08-07", "trades": [
            trade("3333", "Persist", 100, 3, "2026-01-05"),
            trade("3333", "Persist", 200, 4, "2026-01-10"),
            trade("3333", "Persist", -50, 5, "2026-01-15"),
        ]}
        report = build_report(payload)
        with tempfile.TemporaryDirectory() as temp_dir:
            db_dir = Path(temp_dir)
            migrate_all(db_dir)
            persist_report(report, db_dir / "history.db")
            with sqlite3.connect(db_dir / "history.db") as db:
                self.assertEqual(1, db.execute("SELECT COUNT(*) FROM investor_dna_profiles").fetchone()[0])
                self.assertEqual(1, db.execute("SELECT COUNT(*) FROM compatibility_assessments").fetchone()[0])
                self.assertGreater(db.execute("SELECT COUNT(*) FROM compatibility_factors").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
