#!/usr/bin/env python3
"""Validate a weekly SBI execution CSV before any portfolio mutation."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_sbi_executions import ALIASES, clean, date_value, normalize_side, number, pick


WEEK_PATTERN = re.compile(r"^(?P<year>\d{4})-W(?P<week>\d{2})$")
SECRET_PATTERNS = {
    "password": re.compile(r"(?i)(?:password|passwd|passphrase)\s*[:=]"),
    "api_key": re.compile(r"(?i)api[ _-]?key\s*[:=]"),
    "access_token": re.compile(r"(?i)(?:access[ _-]?token|bearer)\s*[:= ]"),
    "login_password_ja": re.compile(r"(?:ログイン|取引)パスワード\s*[:：=]"),
}
REQUIRED_FIELDS = ("trade_date", "name", "quantity", "price")


def parse_week(value: str) -> tuple[date, date]:
    match = WEEK_PATTERN.fullmatch(value)
    if not match:
        raise ValueError("week must use ISO format YYYY-Www")
    year, week = int(match.group("year")), int(match.group("week"))
    try:
        return date.fromisocalendar(year, week, 1), date.fromisocalendar(year, week, 7)
    except ValueError as exc:
        raise ValueError(f"invalid ISO week: {value}") from exc


def decode_csv(path: Path) -> tuple[str, str]:
    payload = path.read_bytes()
    for encoding in ("cp932", "utf-8-sig"):
        try:
            return payload.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError("CSV must be CP932 or UTF-8 with optional BOM")


def find_header(rows: list[list[str]]) -> tuple[int, list[str]]:
    for index, candidate in enumerate(rows):
        normalized = {clean(value).replace("\ufeff", "") for value in candidate}
        if all(any(alias in normalized for alias in ALIASES[field]) for field in REQUIRED_FIELDS):
            return index, candidate
    raise ValueError("SBI execution header with required columns was not found")


def secret_matches(text: str) -> list[str]:
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]


def semantic_identity(values: dict[str, Any], occurrence: int) -> str:
    canonical = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{canonical}\noccurrence={occurrence}".encode("utf-8")).hexdigest()


def read_audit(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid audit JSON at line {line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"invalid audit entry at line {line_number}")
        rows.append(row)
    return rows


def append_audit(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "validation_id": report["validation_id"],
        "issue_number": report["issue_number"],
        "iso_week": report["iso_week"],
        "source_sha256": report["source_sha256"],
        "status": report["status"],
        "validated_at": report["validated_at"],
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def validate(
    source: Path,
    *,
    issue_number: int,
    iso_week: str,
    audit_rows: Iterable[dict[str, Any]] = (),
    confirm_no_trades: bool = False,
) -> dict[str, Any]:
    week_start, week_end = parse_week(iso_week)
    validated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    base: dict[str, Any] = {
        "schema_version": 1,
        "kind": "weekly-sbi-csv-validation",
        "issue_number": issue_number,
        "iso_week": iso_week,
        "target_period": {"start": week_start.isoformat(), "end": week_end.isoformat()},
        "validated_at": validated_at,
        "portfolio_mutated": False,
        "errors": [],
    }
    if issue_number <= 0:
        base["errors"].append({"code": "INVALID_ISSUE", "message": "issue number must be positive"})
    if not source.is_file():
        base.update({"status": "VALIDATION_FAILED", "source_sha256": None})
        base["errors"].append({"code": "FILE_NOT_FOUND", "message": "input CSV was not found"})
        return base

    raw = source.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    base.update({"source_sha256": source_hash, "source_size_bytes": len(raw)})
    base["validation_id"] = hashlib.sha256(
        f"issue={issue_number}\nweek={iso_week}\nsha256={source_hash}".encode("utf-8")
    ).hexdigest()

    if any(row.get("source_sha256") == source_hash and row.get("status") == "VALID" for row in audit_rows):
        base["status"] = "DUPLICATE_INPUT"
        base["errors"].append(
            {"code": "DUPLICATE_FILE", "message": "this exact CSV was already accepted"}
        )
        return base

    try:
        text, encoding = decode_csv(source)
        base["encoding"] = encoding
    except (OSError, UnicodeError) as exc:
        base["status"] = "VALIDATION_FAILED"
        base["errors"].append({"code": "ENCODING", "message": str(exc)})
        return base

    matches = secret_matches(text)
    if matches:
        base["errors"].append(
            {
                "code": "POSSIBLE_SECRET",
                "message": "possible credential fields were detected; remove them before intake",
                "rules": matches,
            }
        )

    rows = list(csv.reader(text.splitlines()))
    try:
        header_index, header = find_header(rows)
        reader = csv.DictReader(text.splitlines()[header_index + 1 :], fieldnames=header)
        occurrences: dict[str, int] = defaultdict(int)
        execution_dates: list[date] = []
        record_ids: list[str] = []
        row_errors: list[dict[str, Any]] = []
        for source_row, row in enumerate(reader, header_index + 2):
            try:
                trade_date = date.fromisoformat(date_value(pick(row, "trade_date")))
                name = pick(row, "name")
                quantity = number(pick(row, "quantity"))
                price = number(pick(row, "price"))
                if not name or quantity is None or quantity <= 0 or price is None or price < 0:
                    raise ValueError("name, positive quantity, and non-negative price are required")
                values = {
                    "trade_date": trade_date.isoformat(),
                    "account": pick(row, "account"),
                    "transaction": pick(row, "transaction"),
                    "side": normalize_side(row),
                    "security_code": pick(row, "code"),
                    "security_name": name,
                    "quantity": quantity,
                    "price": price,
                }
                canonical = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                occurrences[canonical] += 1
                record_ids.append(semantic_identity(values, occurrences[canonical]))
                execution_dates.append(trade_date)
            except Exception as exc:
                row_errors.append(
                    {
                        "source_row": source_row,
                        "code": "INVALID_RECORD",
                        "message": "record does not match the required SBI execution schema",
                        "error_type": type(exc).__name__,
                    }
                )
        if row_errors:
            base["errors"].extend(row_errors)
        if not execution_dates:
            base["errors"].append({"code": "NO_RECORDS", "message": "no execution records found"})
        else:
            target_count = sum(week_start <= value <= week_end for value in execution_dates)
            base.update(
                {
                    "source_record_count": len(execution_dates),
                    "source_date_range": {
                        "start": min(execution_dates).isoformat(),
                        "end": max(execution_dates).isoformat(),
                    },
                    "target_week_record_count": target_count,
                    "record_identity_count": len(record_ids),
                    "record_identities_unique": len(record_ids) == len(set(record_ids)),
                }
            )
            if target_count == 0 and not confirm_no_trades:
                base["errors"].append(
                    {
                        "code": "TARGET_WEEK_EMPTY_UNCONFIRMED",
                        "message": "no target-week executions found; explicit no-trade confirmation is required",
                    }
                )
            base["no_trades_confirmed"] = target_count == 0 and confirm_no_trades
    except (csv.Error, ValueError) as exc:
        base["errors"].append({"code": "SCHEMA", "message": str(exc)})

    base["status"] = "VALID" if not base["errors"] else "VALIDATION_FAILED"
    return base


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and link an SBI CSV to a weekly intake Issue without mutating Portfolio State"
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--week", required=True, help="ISO week, for example 2026-W32")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--audit-file", type=Path, default=Path("data/private/sbi-intake-audit.jsonl")
    )
    parser.add_argument(
        "--confirm-no-trades",
        action="store_true",
        help="explicitly confirm that an empty target week is expected",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = validate(
            args.input,
            issue_number=args.issue_number,
            iso_week=args.week,
            audit_rows=read_audit(args.audit_file),
            confirm_no_trades=args.confirm_no_trades,
        )
    except ValueError as exc:
        print(f"validation configuration error: {exc}", file=sys.stderr)
        return 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if report["status"] == "VALID":
        append_audit(args.audit_file, report)
        print(
            f"VALID: Issue #{args.issue_number} {args.week}, "
            f"records={report['source_record_count']}, "
            f"target_week={report['target_week_record_count']}, sha256={report['source_sha256']}"
        )
        return 0
    print(f"{report['status']}: report={args.report}", file=sys.stderr)
    return 3 if report["status"] == "DUPLICATE_INPUT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
