import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.portfolio_repository import write_json_atomic
from scripts.portfolio_state import PortfolioStateError
from scripts.reconcile_weekly_sbi import reconcile_week


BASE_SNAPSHOT = {
    "schema_version": 1,
    "snapshot_id": "verified-2026-08-02",
    "as_of": "2026-08-02",
    "verification_status": "VERIFIED",
    "positions": [
        {
            "security_code": "4063",
            "security_name": "信越化学",
            "position_type": "cash",
            "account_type": "特定",
            "quantity": 100,
        }
    ],
}

CURRENT_STATUS = """# Current Status
> 最終更新: 2026-08-02

## Portfolio
> as_of: 2026-08-02
- 信越化学（現物100株）

## Current Strategy
- preserve
"""


def write_csv(path: Path) -> None:
    with path.open("w", encoding="cp932", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["約定履歴照会"])
        writer.writerow([])
        writer.writerow(
            ["約定日", "銘柄", "銘柄コード", "取引", "預り", "約定数量", "約定単価"]
        )
        writer.writerow(
            ["2026/08/03", "信越化学", "4063", "株式現物買", "特定", "100", "6000"]
        )


def write_validation(path: Path, source: Path, *, status: str = "VALID") -> None:
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    write_json_atomic(
        path,
        {
            "schema_version": 1,
            "kind": "weekly-sbi-csv-validation",
            "status": status,
            "portfolio_mutated": False,
            "issue_number": 105,
            "iso_week": "2026-W32",
            "validation_id": "validation-1",
            "source_sha256": source_hash,
        },
    )


class WeeklySbiReconciliationTest(unittest.TestCase):
    def setup_case(self, root: Path, *, verified_quantity: int):
        source = root / "week.csv"
        validation = root / "validation.json"
        positions = root / "positions.json"
        snapshots = root / "snapshots"
        database = root / "trades.sqlite"
        output = root / "current.json"
        result = root / "result.json"
        current_status = root / "Current_Status.md"
        write_csv(source)
        write_validation(validation, source)
        write_json_atomic(snapshots / "base.json", BASE_SNAPSHOT)
        write_json_atomic(
            positions,
            {
                "as_of": "2026-08-08",
                "positions": [dict(BASE_SNAPSHOT["positions"][0], quantity=verified_quantity)],
            },
        )
        current_status.write_text(CURRENT_STATUS, encoding="utf-8")
        return source, validation, positions, snapshots, database, output, result, current_status

    def test_verified_promotes_snapshot_and_refreshes_consumers(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.setup_case(Path(directory), verified_quantity=200)
            source, validation, positions, snapshots, database, output, result, current_status = paths

            reconciliation = reconcile_week(
                source=source,
                validation_report=validation,
                issue_number=105,
                iso_week="2026-W32",
                database=database,
                snapshot_directory=snapshots,
                verified_positions_path=positions,
                output=output,
                result_report=result,
                current_status_path=current_status,
            )

            self.assertEqual("VERIFIED", reconciliation["verification_status"])
            self.assertEqual([], reconciliation["verification_diff"])
            self.assertEqual(1, reconciliation["import_audit"]["inserted_count"])
            self.assertTrue((snapshots / "verified-2026-08-08.json").is_file())
            self.assertIn("現物200株", current_status.read_text(encoding="utf-8"))
            self.assertEqual("OK", reconciliation["morning_dataset_portfolio_provider"]["status"])
            self.assertEqual(
                "VERIFIED",
                reconciliation["morning_dataset_portfolio_provider"]["verification_status"],
            )
            self.assertFalse(reconciliation["automatic_correction_applied"])

    def test_mismatch_persists_diff_without_promotion_or_status_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.setup_case(Path(directory), verified_quantity=150)
            source, validation, positions, snapshots, database, output, result, current_status = paths

            reconciliation = reconcile_week(
                source=source,
                validation_report=validation,
                issue_number=105,
                iso_week="2026-W32",
                database=database,
                snapshot_directory=snapshots,
                verified_positions_path=positions,
                output=output,
                result_report=result,
                current_status_path=current_status,
            )

            self.assertEqual("MISMATCH", reconciliation["verification_status"])
            self.assertEqual(-50, reconciliation["verification_diff"][0]["difference"])
            self.assertFalse((snapshots / "verified-2026-08-08.json").exists())
            self.assertEqual(CURRENT_STATUS, current_status.read_text(encoding="utf-8"))
            self.assertEqual(
                "PARTIAL", reconciliation["morning_dataset_portfolio_provider"]["status"]
            )
            self.assertFalse(reconciliation["automatic_correction_applied"])

    def test_non_valid_report_blocks_before_database_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.setup_case(Path(directory), verified_quantity=200)
            source, validation, positions, snapshots, database, output, result, _ = paths
            write_validation(validation, source, status="VALIDATION_FAILED")

            with self.assertRaisesRegex(PortfolioStateError, "must be VALID"):
                reconcile_week(
                    source=source,
                    validation_report=validation,
                    issue_number=105,
                    iso_week="2026-W32",
                    database=database,
                    snapshot_directory=snapshots,
                    verified_positions_path=positions,
                    output=output,
                    result_report=result,
                )

            self.assertFalse(database.exists())
            self.assertFalse(output.exists())

    def test_hash_mismatch_blocks_before_import(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.setup_case(Path(directory), verified_quantity=200)
            source, validation, positions, snapshots, database, output, result, _ = paths
            with source.open("a", encoding="cp932") as handle:
                handle.write("changed\n")

            with self.assertRaisesRegex(PortfolioStateError, "SHA-256"):
                reconcile_week(
                    source=source,
                    validation_report=validation,
                    issue_number=105,
                    iso_week="2026-W32",
                    database=database,
                    snapshot_directory=snapshots,
                    verified_positions_path=positions,
                    output=output,
                    result_report=result,
                )

            self.assertFalse(database.exists())

    def test_duplicate_external_position_is_rejected_not_merged(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.setup_case(Path(directory), verified_quantity=200)
            source, validation, positions, snapshots, database, output, result, _ = paths
            payload = json.loads(positions.read_text(encoding="utf-8"))
            payload["positions"].append(dict(payload["positions"][0]))
            write_json_atomic(positions, payload)

            with self.assertRaisesRegex(PortfolioStateError, "duplicate verification position"):
                reconcile_week(
                    source=source,
                    validation_report=validation,
                    issue_number=105,
                    iso_week="2026-W32",
                    database=database,
                    snapshot_directory=snapshots,
                    verified_positions_path=positions,
                    output=output,
                    result_report=result,
                )

            self.assertFalse(output.exists())
            self.assertFalse(database.exists())

    def test_position_snapshot_date_must_belong_to_requested_week(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.setup_case(Path(directory), verified_quantity=200)
            source, validation, positions, snapshots, database, output, result, _ = paths
            payload = json.loads(positions.read_text(encoding="utf-8"))
            payload["as_of"] = "2026-08-10"
            write_json_atomic(positions, payload)

            with self.assertRaisesRegex(PortfolioStateError, "outside the requested ISO week"):
                reconcile_week(
                    source=source,
                    validation_report=validation,
                    issue_number=105,
                    iso_week="2026-W32",
                    database=database,
                    snapshot_directory=snapshots,
                    verified_positions_path=positions,
                    output=output,
                    result_report=result,
                )

            self.assertFalse(database.exists())


if __name__ == "__main__":
    unittest.main()
