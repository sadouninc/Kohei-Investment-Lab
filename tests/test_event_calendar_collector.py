from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.event_calendar_collector import SourceSpec, collect


class EventCalendarCollectorTest(unittest.TestCase):
    def source(self, root: str, name: str, payload: dict) -> Path:
        path = Path(root) / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_collects_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            one = self.source(tmp, "a.json", {"coverage_confirmed": True, "events": [{"title": "BOJ meeting", "date": "2026-08-08", "source_url": "official-a"}]})
            two = self.source(tmp, "b.json", {"coverage_confirmed": True, "events": [{"title": "BOJ meeting", "date": "2026-08-08", "source_url": "official-b"}]})
            result = collect([SourceSpec("policy", one, "a"), SourceSpec("policy", two, "b")], as_of="2026-08-08")
            self.assertEqual(1, len(result["events"]["policy"]))
            self.assertTrue(result["coverage"]["policy"])

    def test_partial_source_availability_never_confirms_missing_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            earnings = self.source(tmp, "earnings.json", {"coverage_confirmed": True, "events": [{"title": "Example earnings", "scheduled_at": "2026-08-08T15:00:00+09:00"}]})
            missing = Path(tmp) / "missing.json"
            result = collect([SourceSpec("earnings", earnings, "official"), SourceSpec("economic", missing, "official")], as_of="2026-08-08")
            self.assertTrue(result["coverage"]["earnings"])
            self.assertFalse(result["coverage"]["economic"])
            self.assertNotIn("empty_confirmed", result)

    def test_malformed_event_is_ignored_without_false_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.source(tmp, "company.json", {"coverage_confirmed": False, "events": [{"title": "No date"}]})
            result = collect([SourceSpec("company", path, "ir")], as_of="2026-08-08")
            self.assertEqual([], result["events"]["company"])
            self.assertFalse(result["coverage"]["company"])
            self.assertIn("malformed", result["collector_diagnostics"][0]["error"])

    def test_empty_confirmed_requires_all_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = []
            for category in ("earnings", "economic", "policy", "market_calendar", "company"):
                path = self.source(tmp, f"{category}.json", {"coverage_confirmed": True, "events": []})
                specs.append(SourceSpec(category, path, category))
            result = collect(specs, as_of="2026-08-08")
            self.assertTrue(result["empty_confirmed"])

    def test_preserves_timezone_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.source(tmp, "economic.json", {"coverage_confirmed": True, "events": [{"name": "US CPI", "timestamp": "2026-08-08T21:30:00+09:00", "timezone": "Asia/Tokyo", "source_url": "https://example.invalid/official"}]})
            result = collect([SourceSpec("economic", path, "government")], as_of="2026-08-08")
            event = result["events"]["economic"][0]
            self.assertEqual("Asia/Tokyo", event["timezone"])
            self.assertEqual("government", event["source"])
            self.assertIn("source_url", event)


if __name__ == "__main__":
    unittest.main()
