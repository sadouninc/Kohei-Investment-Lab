from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from scripts.morning_dataset.providers.events import EventsProvider


class EventsProviderTest(unittest.TestCase):
    def write(self, root: Path, payload: dict) -> Path:
        path = root / "calendar.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def complete_payload(self, as_of: str = "2026-08-08") -> dict:
        return {
            "as_of": as_of,
            "source": "official/manual-reviewed aggregation",
            "coverage": {
                "earnings": True,
                "economic": True,
                "policy": True,
                "market_calendar": True,
                "company": True,
            },
            "events": {
                "earnings": [
                    {"title": "Example earnings", "date": "2026-08-08", "security_code": "9999", "source": "https://example.invalid/ir"}
                ],
                "economic": [
                    {"title": "Example economic indicator", "scheduled_at": "2026-08-08T21:30:00+09:00", "source": "official"}
                ],
                "policy": [],
                "market_calendar": [],
                "company": [],
            },
        }

    def test_ok_for_fresh_complete_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), self.complete_payload())
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual("2026-08-08", result.as_of)
            self.assertEqual(1, len(result.data["earnings"]))
            self.assertEqual(1, len(result.data["economic"]))

    def test_stale_calendar_preserves_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), self.complete_payload("2026-08-05"))
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertTrue(result.data["earnings"])

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = EventsProvider(Path(tmp) / "missing.json", today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

    def test_partial_when_coverage_not_explicitly_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.complete_payload()
            payload["coverage"]["policy"] = False
            path = self.write(Path(tmp), payload)
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIn("coverage", result.reason)

    def test_partial_when_event_item_is_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.complete_payload()
            payload["events"]["company"] = [{"title": "missing date"}]
            path = self.write(Path(tmp), payload)
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual([], result.data["company"])

    def test_empty_calendar_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.complete_payload()
            for key in payload["events"]:
                payload["events"][key] = []
            path = self.write(Path(tmp), payload)
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

            payload["empty_confirmed"] = True
            path = self.write(Path(tmp), payload)
            result = EventsProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)


if __name__ == "__main__":
    unittest.main()
