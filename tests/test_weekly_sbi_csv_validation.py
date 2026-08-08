import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_weekly_sbi_csv import append_audit, validate


HEADER = ["約定日", "銘柄", "銘柄コード", "取引", "預り", "約定数量", "約定単価"]


def write_csv(path: Path, records: list[list[str]], *, encoding: str = "cp932", preface=True):
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.writer(handle)
        if preface:
            writer.writerow(["約定履歴照会"])
            writer.writerow([])
        writer.writerow(HEADER)
        writer.writerows(records)


class WeeklySbiCsvValidationTest(unittest.TestCase):
    def test_validates_cp932_long_history_and_preserves_repeated_fills(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "history.csv"
            write_csv(
                source,
                [
                    ["2024/07/25", "例株式会社", "1001", "株式現物買", "特定", "100", "1000"],
                    ["2026/08/07", "Terra Drone", "278A", "信用新規買", "特定", "100", "11900"],
                    ["2026/08/07", "Terra Drone", "278A", "信用新規買", "特定", "100", "11900"],
                ],
            )

            report = validate(source, issue_number=105, iso_week="2026-W32")

            self.assertEqual("VALID", report["status"])
            self.assertEqual("cp932", report["encoding"])
            self.assertEqual(3, report["source_record_count"])
            self.assertEqual(2, report["target_week_record_count"])
            self.assertEqual(3, report["record_identity_count"])
            self.assertTrue(report["record_identities_unique"])
            self.assertFalse(report["portfolio_mutated"])

    def test_empty_target_week_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "history.csv"
            write_csv(
                source,
                [["2026/07/31", "例株式会社", "1001", "株式現物買", "特定", "100", "1000"]],
            )

            unconfirmed = validate(source, issue_number=105, iso_week="2026-W32")
            confirmed = validate(
                source, issue_number=105, iso_week="2026-W32", confirm_no_trades=True
            )

            self.assertEqual("VALIDATION_FAILED", unconfirmed["status"])
            self.assertIn(
                "TARGET_WEEK_EMPTY_UNCONFIRMED",
                {error["code"] for error in unconfirmed["errors"]},
            )
            self.assertEqual("VALID", confirmed["status"])
            self.assertTrue(confirmed["no_trades_confirmed"])

    def test_rejects_possible_credentials_without_leaking_values(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "history.csv"
            write_csv(
                source,
                [["2026/08/07", "例株式会社", "1001", "株式現物買", "特定", "100", "1000"]],
            )
            with source.open("a", encoding="cp932") as handle:
                handle.write("取引パスワード: do-not-copy\n")

            report = validate(source, issue_number=105, iso_week="2026-W32")
            serialized = json.dumps(report, ensure_ascii=False)

            self.assertEqual("VALIDATION_FAILED", report["status"])
            self.assertIn("POSSIBLE_SECRET", {error["code"] for error in report["errors"]})
            self.assertNotIn("do-not-copy", serialized)

    def test_rejects_missing_required_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bad.csv"
            source.write_text("date,name\n2026-08-07,example\n", encoding="utf-8-sig")

            report = validate(source, issue_number=105, iso_week="2026-W32")

            self.assertEqual("VALIDATION_FAILED", report["status"])
            self.assertIn("SCHEMA", {error["code"] for error in report["errors"]})

    def test_same_file_hash_is_not_accepted_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "history.csv"
            audit = Path(directory) / "audit.jsonl"
            write_csv(
                source,
                [["2026/08/07", "例株式会社", "1001", "株式現物買", "特定", "100", "1000"]],
            )
            first = validate(source, issue_number=105, iso_week="2026-W32")
            append_audit(audit, first)

            second = validate(
                source,
                issue_number=105,
                iso_week="2026-W32",
                audit_rows=[json.loads(audit.read_text(encoding="utf-8"))],
            )

            self.assertEqual("DUPLICATE_INPUT", second["status"])
            self.assertEqual("DUPLICATE_FILE", second["errors"][0]["code"])

    def test_missing_file_fails_without_guessing(self):
        report = validate(
            Path("does-not-exist.csv"), issue_number=105, iso_week="2026-W32"
        )

        self.assertEqual("VALIDATION_FAILED", report["status"])
        self.assertEqual("FILE_NOT_FOUND", report["errors"][0]["code"])


if __name__ == "__main__":
    unittest.main()
