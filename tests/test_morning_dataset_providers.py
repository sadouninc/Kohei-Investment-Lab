from __future__ import annotations

from datetime import date, datetime, timezone
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.morning_dataset.generator import build_dataset_from_providers
from scripts.morning_dataset.providers import JsonFileProvider, ProviderResult, collect_providers


class StaticProvider:
    def __init__(self, result: ProviderResult) -> None:
        self.name = result.name
        self.result = result

    def collect(self) -> ProviderResult:
        return self.result


class MorningDatasetProviderTest(unittest.TestCase):
    def test_json_file_provider_returns_ok_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "market.json"
            path.write_text(json.dumps({"as_of": "2026-08-07", "phase": "BULL"}), encoding="utf-8")
            result = JsonFileProvider("market", path).collect()

        self.assertEqual("OK", result.status)
        self.assertEqual("2026-08-07", result.as_of)
        self.assertEqual({"as_of": "2026-08-07", "phase": "BULL"}, result.data)

    def test_missing_json_source_is_explicit(self) -> None:
        result = JsonFileProvider("market", Path("does-not-exist.json")).collect()
        self.assertEqual("MISSING", result.status)
        self.assertIn("does not exist", result.reason or "")

    def test_duplicate_provider_names_are_rejected(self) -> None:
        provider = StaticProvider(ProviderResult.ok("market", {"phase": "BULL"}))
        with self.assertRaises(ValueError):
            collect_providers([provider, provider])

    def test_provider_status_is_preserved_in_dataset(self) -> None:
        providers = [
            StaticProvider(
                ProviderResult.unavailable(
                    "market",
                    status="STALE",
                    data={"phase": "BULL"},
                    as_of="2026-08-06",
                    source_reference="data/market.json",
                    reason="older than freshness threshold",
                )
            ),
            StaticProvider(
                ProviderResult.ok(
                    "investor_dna",
                    {"native_dna": {"type": "MOMENTUM"}},
                    as_of="2026-08-07",
                    source_reference="data/investor-dna.json",
                )
            ),
        ]
        payload = build_dataset_from_providers(
            providers,
            generated_at=datetime(2026, 8, 7, 8, 45, tzinfo=timezone.utc),
            as_of=date(2026, 8, 7),
        )

        status = {row["name"]: row for row in payload["source_status"]}
        self.assertEqual("STALE", status["market"]["status"])
        self.assertEqual("older than freshness threshold", status["market"]["reason"])
        self.assertEqual("data/market.json", status["market"]["source_reference"])
        self.assertEqual("OK", status["investor_dna"]["status"])
        self.assertEqual("MISSING", status["portfolio"]["status"])
        self.assertEqual("PARTIAL", payload["data_quality"]["status"])
        self.assertIn("market source is stale", payload["warnings"][0])

    def test_ok_without_data_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProviderResult(name="market", status="OK", data=None)


if __name__ == "__main__":
    unittest.main()
