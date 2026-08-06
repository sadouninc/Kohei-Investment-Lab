from __future__ import annotations

import csv
import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.market_phase.analysis import (
    cluster, correlation_matrix, daily_returns, lead_lag, normalize,
)
from scripts.market_phase.pipeline import build_report


class MarketPhaseAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.prices = {
            f"2026-01-{day:02d}": 100.0 + day + math.sin(day / 3)
            for day in range(1, 29)
        }

    def test_normalization_starts_at_100(self):
        normalized = normalize(self.prices)
        self.assertEqual(next(iter(normalized.values())), 100.0)

    def test_log_returns_are_correct(self):
        result = daily_returns({"2026-01-01": 100, "2026-01-02": 110})
        self.assertAlmostEqual(result["2026-01-02"], math.log(1.1))

    def test_correlation_is_symmetric_with_unit_diagonal(self):
        returns = {
            "A": daily_returns(self.prices),
            "B": daily_returns({day: value * 2 for day, value in self.prices.items()}),
        }
        matrix, samples = correlation_matrix(returns, minimum=5)
        self.assertAlmostEqual(matrix["A"]["A"], 1.0)
        self.assertAlmostEqual(matrix["A"]["B"], matrix["B"]["A"])
        self.assertEqual(samples["A"]["B"], samples["B"]["A"])
        self.assertGreaterEqual(1 - matrix["A"]["B"], 0)

    def test_each_symbol_has_exactly_one_cluster(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.9, "C": -0.2},
            "B": {"A": 0.9, "B": 1.0, "C": -0.1},
            "C": {"A": -0.2, "B": -0.1, "C": 1.0},
        }
        assignments = cluster(matrix, target=2)
        self.assertEqual(set(assignments), {"A", "B", "C"})
        self.assertEqual(len(assignments), 3)

    def test_lead_lag_sign_and_labels_agree(self):
        base = {f"2026-01-{day:02d}": float(day % 7) for day in range(1, 29)}
        shifted = {
            f"2026-01-{day:02d}": float((day - 2) % 7)
            for day in range(1, 29)
        }
        result = lead_lag({"A": base, "B": shifted}, max_lag=4, minimum=10)[0]
        if result["lag"] > 0:
            self.assertEqual((result["leader"], result["follower"]), ("A", "B"))
        elif result["lag"] < 0:
            self.assertEqual((result["leader"], result["follower"]), ("B", "A"))

    def test_insufficient_overlap_is_warned_by_null_correlation(self):
        matrix, samples = correlation_matrix(
            {"A": {"2026-01-01": 1}, "B": {"2026-01-01": 2}},
            minimum=5,
        )
        self.assertIsNone(matrix["A"]["B"])
        self.assertEqual(samples["A"]["B"], 1)

    def test_pipeline_is_deterministic_except_timestamp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            universe = root / "universe.json"
            universe.write_text(json.dumps({
                "id": "fixture", "name": "fixture",
                "symbols": [
                    {"code": "A", "name": "A", "group": "one"},
                    {"code": "B", "name": "B", "group": "two"},
                ],
            }), encoding="utf-8")
            prices = root / "prices"
            prices.mkdir()
            for code, multiplier in (("A", 1), ("B", 2)):
                with (prices / f"{code}.csv").open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["Date", "AdjustedClose"])
                    writer.writeheader()
                    for day, value in self.prices.items():
                        writer.writerow({"Date": day, "AdjustedClose": value * multiplier})
            first = build_report(universe, prices)
            second = build_report(universe, prices)
            first.pop("generated_at")
            second.pop("generated_at")
            self.assertEqual(first, second)
            self.assertEqual(first["data_quality"]["included"], 2)
            for assignments in first["clusters_by_period"].values():
                self.assertEqual(set(assignments), {"A", "B"})
            self.assertIn("autocorrelation", first["cycle_summary"]["A"])


if __name__ == "__main__":
    unittest.main()
