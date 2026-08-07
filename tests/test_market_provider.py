from __future__ import annotations

from datetime import datetime, timezone
import unittest

from scripts.morning_dataset.providers.market import MARKET_SYMBOLS, MarketProvider


def chart(close_values: list[float]) -> dict:
    base = int(datetime(2026, 8, 6, tzinfo=timezone.utc).timestamp())
    return {
        "chart": {
            "result": [{
                "timestamp": [base + 86400 * i for i in range(len(close_values))],
                "indicators": {"quote": [{"close": close_values}]},
            }],
            "error": None,
        }
    }


class MarketProviderTest(unittest.TestCase):
    def test_complete_snapshot_is_ok(self) -> None:
        def fetcher(symbol: str) -> dict:
            return chart([100.0, 102.0])

        result = MarketProvider(fetcher=fetcher).collect()
        self.assertEqual("OK", result.status)
        self.assertEqual(len(MARKET_SYMBOLS), result.data["coverage"]["available"])
        self.assertIn("nikkei_225", result.data["indices"])
        self.assertIn("usdjpy", result.data["macro"])
        self.assertAlmostEqual(2.0, result.data["indices"]["nikkei_225"]["change_pct"])
        # Yahoo ^TNX is ten times the percentage yield; provider normalizes it.
        self.assertAlmostEqual(10.2, result.data["macro"]["us_10y"]["value"])
        self.assertTrue(result.as_of)
        self.assertTrue(result.source_reference)

    def test_individual_failure_returns_partial_with_preserved_data(self) -> None:
        failed_symbol = MARKET_SYMBOLS["vix"]["symbol"]

        def fetcher(symbol: str) -> dict:
            if symbol == failed_symbol:
                raise TimeoutError("simulated")
            return chart([100.0, 101.0])

        result = MarketProvider(fetcher=fetcher).collect()
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual(len(MARKET_SYMBOLS) - 1, result.data["coverage"]["available"])
        self.assertEqual(1, len(result.data["coverage"]["missing"]))
        self.assertIn("1 of", result.reason)

    def test_all_failures_are_missing(self) -> None:
        def fetcher(symbol: str) -> dict:
            raise TimeoutError("simulated")

        result = MarketProvider(fetcher=fetcher).collect()
        self.assertEqual("MISSING", result.status)
        self.assertIsNone(result.data)
        self.assertIn("all public market quote requests failed", result.reason)


if __name__ == "__main__":
    unittest.main()
