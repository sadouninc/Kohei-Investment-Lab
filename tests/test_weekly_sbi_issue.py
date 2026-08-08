import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from scripts.weekly_sbi_issue import WeeklyIssue, has_duplicate, target_date, write_outputs


class WeeklySbiIssueTest(unittest.TestCase):
    def test_issue_uses_iso_week_and_monday_sunday_period(self):
        issue = WeeklyIssue.from_date(date(2026, 8, 7))

        self.assertEqual(issue.week_id, "2026-W32")
        self.assertEqual(issue.period_start, date(2026, 8, 3))
        self.assertEqual(issue.period_end, date(2026, 8, 9))
        self.assertEqual(issue.title, "[Weekly] SBI取引履歴CSV取込 — 2026-W32")

    def test_iso_year_boundary_is_not_calendar_year(self):
        issue = WeeklyIssue.from_date(date(2027, 1, 1))

        self.assertEqual(issue.week_id, "2026-W53")
        self.assertEqual(issue.period_start, date(2026, 12, 28))
        self.assertEqual(issue.period_end, date(2027, 1, 3))

    def test_current_date_is_resolved_in_jst(self):
        before_midnight_utc = datetime(2027, 1, 3, 14, 59, tzinfo=timezone.utc)
        after_midnight_jst = datetime(2027, 1, 3, 15, 1, tzinfo=timezone.utc)

        self.assertEqual(target_date(None, before_midnight_utc), date(2027, 1, 3))
        self.assertEqual(target_date(None, after_midnight_jst), date(2027, 1, 4))

    def test_body_has_owner_action_checklist_and_machine_marker(self):
        body = WeeklyIssue.from_date(date(2026, 8, 7)).render_body()

        for expected in (
            "<!-- sado-weekly-sbi-input:v1 week=2026-W32 -->",
            "## サドの対応",
            "## 完了チェック",
            "Canonical Portfolio State",
            "`VERIFIED` または `MISMATCH`",
            "state: `AWAITING_INPUT`",
        ):
            self.assertIn(expected, body)

    def test_duplicate_matches_exact_title_in_open_or_closed_export(self):
        issue = WeeklyIssue.from_date(date(2026, 8, 7))
        rows = [
            {"title": "unrelated", "body": ""},
            {"title": issue.title, "body": "closed issue body"},
        ]

        self.assertTrue(has_duplicate(rows, issue))

    def test_duplicate_matches_marker_even_if_title_was_edited(self):
        issue = WeeklyIssue.from_date(date(2026, 8, 7))
        rows = [{"title": "edited", "body": f"notes\n{issue.marker}\n"}]

        self.assertTrue(has_duplicate(rows, issue))
        self.assertFalse(has_duplicate([{"title": "other", "body": ""}], issue))

    def test_github_outputs_are_single_line_and_append_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output.txt"
            write_outputs(output, {"title": "example", "duplicate": "false"})
            write_outputs(output, {"week": "2026-W32"})

            self.assertEqual(
                output.read_text(encoding="utf-8").splitlines(),
                ["title=example", "duplicate=false", "week=2026-W32"],
            )


class WeeklySbiWorkflowTest(unittest.TestCase):
    def test_workflow_is_scheduled_friday_night_jst_and_manual_is_safe(self):
        workflow = Path(".github/workflows/weekly-sbi-csv-intake.yml").read_text(encoding="utf-8")

        self.assertIn('cron: "0 12 * * 5"', workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("--state all", workflow)
        self.assertIn("weekly-input sbi-csv action-required:sado", workflow)


if __name__ == "__main__":
    unittest.main()
