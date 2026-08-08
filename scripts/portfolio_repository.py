from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

from scripts.portfolio_state import PortfolioStateError, build_state, reconcile


TRANSACTION_MAP = {
    "株式現物買": ("cash", "buy"),
    "現物買": ("cash", "buy"),
    "株式現物売": ("cash", "sell"),
    "現物売": ("cash", "sell"),
    "信用新規買": ("margin_long", "open_long"),
    "信用返済売": ("margin_long", "close_long"),
    "信用新規売": ("margin_short", "open_short"),
    "信用返済買": ("margin_short", "close_short"),
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortfolioStateError(f"cannot read portfolio JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PortfolioStateError(f"portfolio JSON must be an object: {path}")
    return payload


def write_json_atomic(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def load_latest_verified_snapshot(directory: Path) -> dict[str, Any]:
    candidates: list[tuple[str, str, Path, dict[str, Any]]] = []
    if not directory.is_dir():
        raise PortfolioStateError(f"snapshot directory not found: {directory}")
    for path in directory.glob("*.json"):
        payload = read_json(path)
        if payload.get("verification_status") != "VERIFIED":
            continue
        as_of = payload.get("as_of")
        snapshot_id = payload.get("snapshot_id")
        if not isinstance(as_of, str) or not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise PortfolioStateError(f"verified snapshot requires snapshot_id and as_of: {path}")
        candidates.append((as_of, snapshot_id, path, payload))
    if not candidates:
        raise PortfolioStateError(f"no VERIFIED portfolio snapshot found in {directory}")
    return max(candidates, key=lambda row: (row[0], row[1], row[2].name))[3]


def normalize_execution(row: sqlite3.Row) -> dict[str, Any]:
    transaction = str(row["transaction_type"] or "").strip()
    mapping = TRANSACTION_MAP.get(transaction)
    if mapping is None:
        raise PortfolioStateError(
            f"execution {row['id']} has unsupported transaction_type {transaction!r}; "
            "portfolio facts were not inferred"
        )
    position_type, action = mapping
    return {
        "trade_id": f"sbi-execution:{row['id']}",
        "executed_at": row["trade_date"],
        "security_code": row["security_code"],
        "security_name": row["security_name"],
        "position_type": position_type,
        "account_type": row["account"],
        "action": action,
        "quantity": row["quantity"],
        "source_reference": f"{row['source_file']}#row-{row['source_row']}",
    }


def load_sbi_trades(database: Path, *, after: str | None = None) -> list[dict[str, Any]]:
    if not database.is_file():
        raise PortfolioStateError(f"SBI execution database not found: {database}")
    try:
        with closing(sqlite3.connect(database)) as connection:
            connection.row_factory = sqlite3.Row
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='executions'"
            ).fetchone()
            if not exists:
                raise PortfolioStateError(f"executions table not found: {database}")
            if after:
                rows = connection.execute(
                    "SELECT * FROM executions WHERE trade_date > ? ORDER BY trade_date, id", (after,)
                ).fetchall()
            else:
                rows = connection.execute("SELECT * FROM executions ORDER BY trade_date, id").fetchall()
    except sqlite3.Error as exc:
        raise PortfolioStateError(f"cannot read SBI executions from {database}: {exc}") from exc
    return [normalize_execution(row) for row in rows]


def build_from_repository(snapshot_directory: Path, database: Path) -> dict[str, Any]:
    snapshot = load_latest_verified_snapshot(snapshot_directory)
    trades = load_sbi_trades(database, after=str(snapshot["as_of"]))
    state = build_state(snapshot, trades)
    state["schema_version"] = 1
    state["authority"] = "verified_snapshot_plus_sbi_executions"
    state["source_references"] = {
        "snapshot_id": snapshot["snapshot_id"],
        "execution_database": str(database),
    }
    state["applied_trade_references"] = [
        {"trade_id": trade["trade_id"], "source_reference": trade["source_reference"]}
        for trade in trades
        if trade["trade_id"] in state["applied_trade_ids"]
    ]
    return state


def verify_state(
    current: dict[str, Any],
    verified_positions: Iterable[dict[str, Any]],
    *,
    verification_source: str,
    as_of: str,
) -> dict[str, Any]:
    result = reconcile(
        current,
        verified_positions,
        verification_source=verification_source,
        as_of=as_of,
    )
    result["schema_version"] = 1
    result["authority"] = "sbi_weekly_verification"
    return result


def promote_verified_snapshot(state: dict[str, Any], directory: Path) -> Path:
    if state.get("verification_status") != "VERIFIED":
        raise PortfolioStateError("only a VERIFIED state can be promoted to a snapshot")
    as_of = state.get("verification_as_of") or state.get("as_of")
    if not isinstance(as_of, str) or not as_of:
        raise PortfolioStateError("verified state requires an as_of date")
    source = str(state.get("verification_source") or "verified-state")
    snapshot_id = f"verified-{as_of}"
    snapshot = {
        "schema_version": 1,
        "snapshot_id": snapshot_id,
        "as_of": as_of,
        "verification_status": "VERIFIED",
        "verification_source": source,
        "positions": state.get("positions") or [],
        "applied_trade_ids": state.get("applied_trade_ids") or [],
    }
    return write_json_atomic(directory / f"{snapshot_id}.json", snapshot)
