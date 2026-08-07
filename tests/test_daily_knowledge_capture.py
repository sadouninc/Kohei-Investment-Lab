from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.daily_knowledge_capture import build_diagnostic, write_diagnostic


class DailyKnowledgeCaptureTest(unittest.TestCase):
    def event(self, label: str = "daily-knowledge") -> dict:
        return {
            "label": {"name": label},
            "repository": {
                "full_name": "sadouninc/Kohei-Investment-Lab",
                "default_branch": "main",
            },
            "issue": {
                "number": 123,
                "html_url": "https://github.com/sadouninc/Kohei-Investment-Lab/issues/123",
                "title": "Daily Conversation Capture — 2026-08-07",
                "body": "## Confirmed Trades\n- example",
                "user": {"login": "sadouninc"},
            },
        }

    def test_builds_traceable_capture_payload(self) -> None:
        payload = build_diagnostic(self.event())

        self.assertEqual(payload["status"], "CAPTURED")
        self.assertEqual(payload["trigger"]["label"], "daily-knowledge")
        self.assertEqual(payload["issue"]["number"], 123)
        self.assertEqual(payload["issue"]["author"], "sadouninc")
        self.assertEqual(payload["next_stage"], "ai-integration-planner")
        self.assertIn("captured_at", payload)

    def test_rejects_unrelated_label(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported label"):
            build_diagnostic(self.event("bug"))

    def test_requires_issue_identity(self) -> None:
        event = self.event()
        event["issue"]["number"] = None
        with self.assertRaisesRegex(ValueError, "issue.number"):
            build_diagnostic(event)

    def test_writes_issue_scoped_json(self) -> None:
        payload = build_diagnostic(self.event())
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_diagnostic(payload, Path(temp_dir))
            self.assertEqual(path.name, "issue-123.json")
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["issue"]["title"], payload["issue"]["title"])


if __name__ == "__main__":
    unittest.main()
