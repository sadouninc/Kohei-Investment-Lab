from __future__ import annotations

import json
import unittest

from scripts.morning_dataset.context_optimizer import optimize_dataset


class ContextOptimizerTest(unittest.TestCase):
    def test_large_market_history_is_not_forwarded(self) -> None:
        dataset = {
            "schema_version": "1.0",
            "generated_at": "2026-08-07T08:40:00+09:00",
            "as_of": "2026-08-07",
            "data_quality": {"status": "PARTIAL"},
            "warnings": [],
            "source_status": [],
            "market": {
                "phase": "AI_BULL",
                "indices": {"nikkei": 42000},
                "history": [{"x": i, "blob": "x" * 500} for i in range(1000)],
            },
            "portfolio": None,
            "capital": None,
            "candidates": None,
            "investor_dna": None,
            "events": None,
            "watchlist": None,
        }
        optimized, diagnostics = optimize_dataset(dataset)
        self.assertEqual("AI_BULL", optimized["market"]["phase"])
        self.assertNotIn("history", optimized["market"])
        self.assertEqual("OK", diagnostics["status"])
        self.assertGreater(diagnostics["reduction_ratio"], 0.9)

    def test_lists_are_limited(self) -> None:
        dataset = {
            "schema_version": "1.0",
            "generated_at": "2026-08-07T08:40:00+09:00",
            "as_of": "2026-08-07",
            "data_quality": {"status": "OK"},
            "warnings": [],
            "source_status": [],
            "market": None,
            "portfolio": None,
            "capital": None,
            "candidates": [{"code": str(i)} for i in range(30)],
            "investor_dna": None,
            "events": None,
            "watchlist": list(range(30)),
        }
        optimized, _ = optimize_dataset(dataset)
        self.assertEqual(10, len(optimized["candidates"]))
        self.assertEqual(10, len(optimized["watchlist"]))

    def test_optimizer_never_adds_investment_facts(self) -> None:
        dataset = {
            "schema_version": "1.0",
            "generated_at": "2026-08-07T08:40:00+09:00",
            "as_of": "2026-08-07",
            "data_quality": {"status": "MISSING"},
            "warnings": ["market source is missing"],
            "source_status": [{"name": "market", "status": "MISSING"}],
            "market": None,
            "portfolio": None,
            "capital": None,
            "candidates": None,
            "investor_dna": None,
            "events": None,
            "watchlist": None,
        }
        optimized, _ = optimize_dataset(dataset)
        serialized = json.dumps(optimized, ensure_ascii=False)
        self.assertIn("MISSING", serialized)
        self.assertIsNone(optimized["market"])
        self.assertNotIn("recommendation", serialized.lower())


if __name__ == "__main__":
    unittest.main()
