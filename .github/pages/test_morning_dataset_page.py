from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("build_morning_dataset.py")
spec = importlib.util.spec_from_file_location("build_morning_dataset", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class MorningDatasetPageTest(unittest.TestCase):
    def test_diagnostics_page_contains_contract_and_status(self) -> None:
        payload = {
            "schema_version": "1.0",
            "generated_at": "2026-08-07T08:40:00+09:00",
            "as_of": "2026-08-07",
            "data_quality": {
                "status": "PARTIAL",
                "completeness": 1 / 7,
                "ok_sources": 1,
                "total_sources": 7,
                "completeness_label": "1 / 7",
            },
            "market": {"phase": None},
            "portfolio": None,
            "capital": None,
            "candidates": [],
            "investor_dna": {"native_dna": None},
            "events": None,
            "watchlist": None,
            "warnings": ["capital source is missing"],
            "source_status": [
                {"name": "market", "status": "OK", "as_of": "2026-08-07", "source": "test"},
                {"name": "capital", "status": "MISSING", "as_of": None, "source": None},
            ],
        }
        page = module.build_page(payload)
        self.assertIn("Morning Dataset Diagnostics", page)
        self.assertIn("PARTIAL", page)
        self.assertIn("capital source is missing", page)
        self.assertIn("morning-dataset.json", page)
        self.assertIn("1 / 7 sources", page)
        self.assertIn("14.3%", page)
        self.assertNotIn("714.3%", page)
        self.assertNotIn("Today Strategy", page)


if __name__ == "__main__":
    unittest.main()
