from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.portfolio_repository import (
    build_from_repository,
    load_latest_verified_snapshot,
    load_sbi_trades,
    promote_verified_snapshot,
    verify_state,
    write_json_atomic,
)
from scripts.portfolio_state import PortfolioStateError


BASE = {
    "schema_version": 1,
    "snapshot_id": "verified-2026-08-07",
    "as_of": "2026-08-07",
    "verification_status": "VERIFIED",
    "positions": [
        {"security_code": "4063", "security_name": "信越化学", "position_type": "cash", "account_type": "特定", "quantity": 100},
        {"security_code": "3110", "security_name": "日東紡", "position_type": "margin_long", "account_type": "特定", "quantity": 200},
    ],
}


def create_database(path: Path, rows: list[tuple]) -> None:
    with closing(sqlite3.connect(path)) as db:
        db.execute(
            """CREATE TABLE executions (
            id INTEGER PRIMARY KEY, source_file TEXT NOT NULL, source_row INTEGER NOT NULL,
            trade_date TEXT NOT NULL, transaction_type TEXT, account TEXT, security_code TEXT,
            security_name TEXT NOT NULL, quantity REAL NOT NULL
            )"""
        )
        db.executemany("INSERT INTO executions VALUES (?,?,?,?,?,?,?,?,?)", rows)
        db.commit()


class PortfolioRepositoryTest(unittest.TestCase):
    def test_latest_verified_snapshot_ignores_non_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json_atomic(root / "old.json", BASE)
            write_json_atomic(root / "mismatch.json", dict(BASE, snapshot_id="new", as_of="2026-08-08", verification_status="MISMATCH"))
            self.assertEqual("verified-2026-08-07", load_latest_verified_snapshot(root)["snapshot_id"])

    def test_build_uses_only_post_snapshot_explicit_sbi_trades(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "snapshots"
            write_json_atomic(snapshots / "base.json", BASE)
            database = root / "trades.sqlite"
            create_database(database, [
                (1, "old.csv", 2, "2026-08-07", "株式現物買", "特定", "4063", "信越化学", 100),
                (2, "week.csv", 3, "2026-08-08", "株式現物買", "特定", "4063", "信越化学", 100),
                (3, "week.csv", 4, "2026-08-08", "信用新規売", "特定", "3110", "日東紡", 100),
            ])
            state = build_from_repository(snapshots, database)
            cash = next(row for row in state["positions"] if row["security_code"] == "4063")
            short = next(row for row in state["positions"] if row["position_type"] == "margin_short")
            self.assertEqual(200, cash["quantity"])
            self.assertEqual(100, short["quantity"])
            self.assertEqual("PROVISIONAL", state["verification_status"])
            self.assertEqual(["sbi-execution:2", "sbi-execution:3"], state["applied_trade_ids"])
            self.assertEqual("特定", cash["account_type"])
            self.assertEqual("week.csv#row-3", state["applied_trade_references"][0]["source_reference"])

    def test_unsupported_transaction_is_not_inferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "trades.sqlite"
            create_database(database, [(1, "week.csv", 2, "2026-08-08", "要確認", "特定", "4063", "信越化学", 100)])
            with self.assertRaisesRegex(PortfolioStateError, "not inferred"):
                load_sbi_trades(database)

    def test_mismatch_is_persistable_but_not_promotable(self):
        with tempfile.TemporaryDirectory() as tmp:
            current = dict(BASE, base_snapshot=BASE["snapshot_id"])
            external = [dict(BASE["positions"][0], quantity=200), BASE["positions"][1]]
            result = verify_state(current, external, verification_source="sbi.csv", as_of="2026-08-08")
            self.assertEqual("MISMATCH", result["verification_status"])
            with self.assertRaises(PortfolioStateError):
                promote_verified_snapshot(result, Path(tmp))

    def test_verified_reconciliation_can_be_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            current = dict(BASE, base_snapshot=BASE["snapshot_id"])
            result = verify_state(current, BASE["positions"], verification_source="sbi.csv", as_of="2026-08-08")
            path = promote_verified_snapshot(result, Path(tmp))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("VERIFIED", payload["verification_status"])
            self.assertEqual("verified-2026-08-08", payload["snapshot_id"])

    def test_promoted_snapshot_preserves_audit_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            current = dict(
                BASE,
                base_snapshot=BASE["snapshot_id"],
                source_references={"weekly_intake": {"issue_number": 105}},
                applied_trade_references=[
                    {"trade_id": "sbi-execution:1", "source_reference": "week.csv#row-2"}
                ],
            )
            result = verify_state(
                current, BASE["positions"], verification_source="sbi.csv", as_of="2026-08-08"
            )

            path = promote_verified_snapshot(result, Path(tmp))
            payload = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(105, payload["source_references"]["weekly_intake"]["issue_number"])
            self.assertEqual(
                "sbi-execution:1", payload["applied_trade_references"][0]["trade_id"]
            )


if __name__ == "__main__":
    unittest.main()
