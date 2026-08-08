from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.trade_journal_integrator import integrate, load_plan, render_entry, target_path


class TradeJournalIntegratorTest(unittest.TestCase):
    def plan(self):
        return {
            "schema_version": 1,
            "date": "2026-08-08",
            "trade_journal": {
                "update": True,
                "summary": "Daily summary",
                "items": [
                    {"kind": "trade_execution", "classification": "fact", "confidence": "high", "text": "Bought 100 shares", "source": "issue"},
                    {"kind": "lesson", "classification": "lesson", "confidence": "high", "text": "Preserve liquidity", "source": "issue"},
                ],
            },
            "investor_dna": {"update_candidate": False, "items": []},
            "framework": {"update_candidate": False, "items": []},
            "company_updates": [],
            "unresolved": [{"text": "Approximate fee", "reason": "CSV not available"}],
            "routing": {"primary_target": "01_Portfolio/Transactions", "proposed_followups": []},
        }

    def test_target_uses_canonical_transaction_path(self):
        self.assertEqual(Path("01_Portfolio/Transactions/2026-08-08.md"), target_path(self.plan()))

    def test_render_preserves_classification_and_unresolved(self):
        text = render_entry(self.plan(), 75)
        self.assertIn("classification: `fact`", text)
        self.assertIn("Preserve liquidity", text)
        self.assertIn("Unresolved / Not Canonicalized", text)
        self.assertIn("SBI CSV-derived trade facts remain authoritative", text)

    def test_new_file_is_created_and_repeat_is_idempotent(self):
        generated = render_entry(self.plan(), 75)
        first, changed = integrate(None, generated)
        self.assertTrue(changed)
        second, changed_again = integrate(first, generated)
        self.assertFalse(changed_again)
        self.assertEqual(first, second)

    def test_existing_journal_is_preserved(self):
        generated = render_entry(self.plan(), 75)
        merged, changed = integrate("# Existing\n\nCanonical content.\n", generated)
        self.assertTrue(changed)
        self.assertTrue(merged.startswith("# Existing"))
        self.assertIn("### Daily Knowledge Integration", merged)

    def test_load_plan_rejects_wrong_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps({"status": "PLANNED", "next_stage": "wrong", "plan": self.plan()}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_plan(path)


if __name__ == "__main__":
    unittest.main()
