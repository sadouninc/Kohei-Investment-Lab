from __future__ import annotations

from datetime import date, datetime, timezone
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.morning_dataset.generator import build_dataset, write_dataset
from scripts.morning_dataset.validator import MorningDatasetValidationError, validate_dataset


class MorningDatasetTest(unittest.TestCase):
    def test_missing_sources_remain_missing_not_guessed(self) -> None:
        payload = build_dataset(
            generated_at=datetime(2026, 8, 7, 8, 40, tzinfo=timezone.utc),
            as_of=date(2026, 8, 7),
        )
        self.assertEqual("1.0", payload["schema_version"])
        self.assertEqual("MISSING", payload["data_quality"]["status"])
        self.assertIsNone(payload["capital"]["buying_power"])
        self.assertTrue(payload["warnings"])

    def test_supplied_facts_are_preserved_without_ai_ranking(self) -> None:
        candidates = [{"security_code": "6702", "score": 92.0}]
        dna = {"native_dna": {"type": "MOMENTUM"}, "environment_fit": {"score": 58}}
        payload = build_dataset(
            generated_at=datetime(2026, 8, 7, 8, 40, tzinfo=timezone.utc),
            as_of=date(2026, 8, 7),
            candidates=candidates,
            investor_dna=dna,
        )
        self.assertEqual(candidates, payload["candidates"])
        self.assertEqual(dna, payload["investor_dna"])
        self.assertNotIn("recommendation", payload)
        self.assertEqual("PARTIAL", payload["data_quality"]["status"])

    def test_all_sources_produce_ok_quality(self) -> None:
        payload = build_dataset(
            market={}, portfolio={}, capital={}, candidates=[], investor_dna={}, events={}, watchlist=[]
        )
        self.assertEqual("OK", payload["data_quality"]["status"])
        self.assertEqual(1.0, payload["data_quality"]["completeness"])

    def test_validator_rejects_bad_schema(self) -> None:
        payload = build_dataset()
        payload["schema_version"] = "999"
        with self.assertRaises(MorningDatasetValidationError):
            validate_dataset(payload)

    def test_output_is_json_serializable(self) -> None:
        payload = build_dataset(market={"phase": {"name": "BULL"}})
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_dataset(payload, Path(temp_dir) / "morning.json")
            loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], loaded["schema_version"])


if __name__ == "__main__":
    unittest.main()
