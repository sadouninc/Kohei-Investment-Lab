#!/usr/bin/env python3
"""Reconcile a validated weekly SBI CSV against an explicit position snapshot."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date
import hashlib
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.current_status_refresh import refresh_portfolio
from scripts.morning_dataset.providers.portfolio import PortfolioProvider
from scripts.portfolio_repository import (
    build_from_repository,
    promote_verified_snapshot,
    read_json,
    verify_state,
    write_json_atomic,
)
from scripts.portfolio_state import PortfolioStateError
from scripts.validate_weekly_sbi_csv import parse_week


def verify_validation_contract(
    report: dict[str, Any], source: Path, *, issue_number: int, iso_week: str
) -> None:
    if report.get("kind") != "weekly-sbi-csv-validation" or report.get("schema_version") != 1:
        raise PortfolioStateError("unsupported weekly SBI validation report")
    if report.get("status") != "VALID":
        raise PortfolioStateError("CSV validation status must be VALID before reconciliation")
    if report.get("portfolio_mutated") is not False:
        raise PortfolioStateError("validation report must confirm portfolio_mutated=false")
    if report.get("issue_number") != issue_number or report.get("iso_week") != iso_week:
        raise PortfolioStateError("validation report does not match the requested Issue and ISO week")
    if not source.is_file():
        raise PortfolioStateError(f"validated SBI CSV not found: {source}")
    actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if report.get("source_sha256") != actual_hash:
        raise PortfolioStateError("SBI CSV SHA-256 does not match the validation report")


def import_validated_csv(source: Path, database: Path) -> None:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "import_sbi_executions.py"),
        "--input",
        str(source),
        "--database",
        str(database),
        "--strict",
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    if completed.returncode != 0:
        raise PortfolioStateError(
            f"validated SBI CSV strict import failed with exit code {completed.returncode}"
        )


def latest_import_audit(database: Path) -> dict[str, int]:
    try:
        with closing(sqlite3.connect(database)) as connection:
            row = connection.execute(
                """SELECT source_record_count, inserted_count, duplicate_count, error_count
                   FROM import_audit ORDER BY id DESC LIMIT 1"""
            ).fetchone()
    except sqlite3.Error as exc:
        raise PortfolioStateError(f"cannot read SBI import audit: {exc}") from exc
    if row is None:
        raise PortfolioStateError("SBI import produced no audit record")
    return {
        "source_record_count": int(row[0]),
        "inserted_count": int(row[1]),
        "duplicate_count": int(row[2]),
        "error_count": int(row[3]),
    }


def reconcile_week(
    *,
    source: Path,
    validation_report: Path,
    issue_number: int,
    iso_week: str,
    database: Path,
    snapshot_directory: Path,
    verified_positions_path: Path,
    output: Path,
    result_report: Path,
    current_status_path: Path | None = None,
) -> dict[str, Any]:
    validation = read_json(validation_report)
    verify_validation_contract(
        validation, source, issue_number=issue_number, iso_week=iso_week
    )
    position_snapshot = read_json(verified_positions_path)
    positions = position_snapshot.get("positions")
    verification_as_of = position_snapshot.get("as_of")
    if not isinstance(positions, list):
        raise PortfolioStateError("verification position snapshot requires a positions list")
    if not isinstance(verification_as_of, str):
        raise PortfolioStateError("verification position snapshot requires an explicit as_of date")
    try:
        provider_today = date.fromisoformat(verification_as_of[:10])
    except ValueError as exc:
        raise PortfolioStateError("verification position snapshot as_of must be YYYY-MM-DD") from exc
    week_start, week_end = parse_week(iso_week)
    if not week_start <= provider_today <= week_end:
        raise PortfolioStateError("verification position snapshot as_of is outside the requested ISO week")

    # Validate every explicit position and reject duplicate keys before mutating the local DB.
    verify_state(
        {"positions": []},
        positions,
        verification_source="position-snapshot-preflight",
        as_of=verification_as_of,
    )

    import_validated_csv(source, database)
    import_audit = latest_import_audit(database)
    if import_audit["error_count"]:
        raise PortfolioStateError("SBI strict import audit contains errors")

    calculated = build_from_repository(snapshot_directory, database)
    source_hash = str(validation["source_sha256"])
    verification_source = (
        f"weekly-sbi:issue-{issue_number}:{iso_week}:sha256-{source_hash[:16]}"
    )
    state = verify_state(
        calculated,
        positions,
        verification_source=verification_source,
        as_of=verification_as_of,
    )
    state.setdefault("source_references", {})["weekly_intake"] = {
        "issue_number": issue_number,
        "iso_week": iso_week,
        "validation_id": validation.get("validation_id"),
        "source_sha256": source_hash,
    }
    write_json_atomic(output, state)

    promoted_snapshot: str | None = None
    current_status_refreshed = False
    if state["verification_status"] == "VERIFIED":
        promoted_snapshot = str(promote_verified_snapshot(state, snapshot_directory))
        if current_status_path is not None:
            current_text = current_status_path.read_text(encoding="utf-8")
            current_status_path.write_text(
                refresh_portfolio(current_text, state), encoding="utf-8"
            )
            current_status_refreshed = True

    provider = PortfolioProvider(path=output, max_age_days=3, today=provider_today).collect()
    result = {
        "schema_version": 1,
        "kind": "weekly-sbi-reconciliation",
        "issue_number": issue_number,
        "iso_week": iso_week,
        "validation_id": validation.get("validation_id"),
        "source_sha256": source_hash,
        "verification_as_of": verification_as_of,
        "verification_status": state["verification_status"],
        "verification_diff": state.get("verification_diff") or [],
        "import_audit": import_audit,
        "canonical_output": str(output),
        "promoted_snapshot": promoted_snapshot,
        "current_status_refreshed": current_status_refreshed,
        "morning_dataset_portfolio_provider": {
            "status": provider.status,
            "as_of": provider.as_of,
            "verification_status": (
                provider.data.get("verification_status") if provider.data else None
            ),
        },
        "automatic_correction_applied": False,
    }
    write_json_atomic(result_report, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a validated weekly SBI CSV and reconcile Canonical Portfolio State"
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--validation-report", required=True, type=Path)
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--week", required=True)
    parser.add_argument("--verify-positions", required=True, type=Path)
    parser.add_argument("--database", type=Path, default=Path("data/database/investment_lab.sqlite"))
    parser.add_argument("--snapshot-dir", type=Path, default=Path("data/portfolio/snapshots"))
    parser.add_argument("--output", type=Path, default=Path("data/portfolio/current.json"))
    parser.add_argument(
        "--result-report", required=True, type=Path,
        help="local/private reconciliation result JSON",
    )
    parser.add_argument("--refresh-current-status", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = reconcile_week(
            source=args.input,
            validation_report=args.validation_report,
            issue_number=args.issue_number,
            iso_week=args.week,
            database=args.database,
            snapshot_directory=args.snapshot_dir,
            verified_positions_path=args.verify_positions,
            output=args.output,
            result_report=args.result_report,
            current_status_path=args.refresh_current_status,
        )
    except (OSError, PortfolioStateError) as exc:
        print(f"weekly reconciliation error: {exc}", file=sys.stderr)
        return 2
    print(
        f"{result['verification_status']}: Issue #{args.issue_number} {args.week}, "
        f"diff={len(result['verification_diff'])}"
    )
    return 0 if result["verification_status"] == "VERIFIED" else 4


if __name__ == "__main__":
    raise SystemExit(main())
