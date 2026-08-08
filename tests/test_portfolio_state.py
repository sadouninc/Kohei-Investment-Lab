from __future__ import annotations

import unittest

from scripts.portfolio_state import PortfolioStateError, build_state, reconcile


BASE = {
    "snapshot_id": "verified-2026-08-07",
    "as_of": "2026-08-07",
    "verification_status": "VERIFIED",
    "positions": [
        {"security_code": "4063", "security_name": "信越化学", "position_type": "cash", "quantity": 100},
        {"security_code": "3110", "security_name": "日東紡", "position_type": "margin_long", "quantity": 200},
    ],
}


class PortfolioStateTest(unittest.TestCase):
    def test_snapshot_only_remains_verified(self):
        result = build_state(BASE, [])
        self.assertEqual("VERIFIED", result["verification_status"])
        self.assertEqual(2, len(result["positions"]))

    def test_buy_makes_state_provisional(self):
        result = build_state(BASE, [{"trade_id": "t1", "executed_at": "2026-08-08T09:10:00+09:00", "security_code": "4063", "security_name": "信越化学", "position_type": "cash", "action": "buy", "quantity": 100}])
        row = next(row for row in result["positions"] if row["security_code"] == "4063")
        self.assertEqual(200, row["quantity"])
        self.assertEqual("PROVISIONAL", result["verification_status"])

    def test_full_close_removes_position(self):
        result = build_state(BASE, [{"trade_id": "t1", "executed_at": "2026-08-08", "security_code": "3110", "security_name": "日東紡", "position_type": "margin_long", "action": "close_long", "quantity": 200}])
        self.assertFalse(any(row["security_code"] == "3110" for row in result["positions"]))

    def test_margin_short_open_and_close(self):
        trades = [
            {"trade_id": "s1", "executed_at": "2026-08-08T09:00:00+09:00", "security_code": "9999", "security_name": "例", "position_type": "margin_short", "action": "open_short", "quantity": 100},
            {"trade_id": "s2", "executed_at": "2026-08-08T10:00:00+09:00", "security_code": "9999", "security_name": "例", "position_type": "margin_short", "action": "close_short", "quantity": 100},
        ]
        result = build_state(BASE, trades)
        self.assertFalse(any(row["security_code"] == "9999" for row in result["positions"]))

    def test_duplicate_trade_is_not_applied_twice(self):
        trade = {"trade_id": "t1", "executed_at": "2026-08-08", "security_code": "4063", "security_name": "信越化学", "position_type": "cash", "action": "buy", "quantity": 100}
        result = build_state(BASE, [trade, trade])
        row = next(row for row in result["positions"] if row["security_code"] == "4063")
        self.assertEqual(200, row["quantity"])
        self.assertEqual(["t1"], result["duplicate_trade_ids"])

    def test_invalid_quantity_is_never_inferred(self):
        with self.assertRaises(PortfolioStateError):
            build_state(BASE, [{"trade_id": "t1", "security_code": "4063", "security_name": "信越化学", "position_type": "cash", "action": "buy", "quantity": None}])

    def test_over_close_is_rejected(self):
        with self.assertRaises(PortfolioStateError):
            build_state(BASE, [{"trade_id": "t1", "security_code": "4063", "security_name": "信越化学", "position_type": "cash", "action": "sell", "quantity": 200}])

    def test_reconcile_match_verifies(self):
        current = build_state(BASE, [])
        result = reconcile(current, BASE["positions"], verification_source="sbi.csv", as_of="2026-08-08")
        self.assertEqual("VERIFIED", result["verification_status"])
        self.assertEqual([], result["verification_diff"])

    def test_reconcile_mismatch_reports_diff(self):
        current = build_state(BASE, [])
        external = [dict(BASE["positions"][0], quantity=200), BASE["positions"][1]]
        result = reconcile(current, external, verification_source="sbi.csv", as_of="2026-08-08")
        self.assertEqual("MISMATCH", result["verification_status"])
        self.assertEqual(100, result["verification_diff"][0]["difference"])


if __name__ == "__main__":
    unittest.main()
