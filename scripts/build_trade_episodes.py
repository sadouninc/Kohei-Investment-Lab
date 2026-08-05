#!/usr/bin/env python3
"""Aggregate executions into zero-position-to-zero-position trade episodes."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from decimal import Decimal
import hashlib
import sqlite3
import sys
from pathlib import Path

TOLERANCE = Decimal("0.000000001")

SCHEMA = """
CREATE TABLE IF NOT EXISTS trade_episodes (
 id INTEGER PRIMARY KEY,
 episode_key TEXT NOT NULL UNIQUE,
 security_code TEXT,
 security_name TEXT NOT NULL,
 account TEXT,
 account_type TEXT NOT NULL,
 position_side TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('OPEN', 'CLOSED')),
 open_date TEXT NOT NULL,
 close_date TEXT,
 total_open_quantity REAL NOT NULL,
 total_close_quantity REAL NOT NULL,
 weighted_average_open_price REAL NOT NULL,
 weighted_average_close_price REAL,
 gross_pnl REAL,
 allocated_costs REAL NOT NULL,
 net_pnl REAL,
 holding_days INTEGER,
 open_execution_count INTEGER NOT NULL,
 close_execution_count INTEGER NOT NULL,
 closed_trade_lot_count INTEGER NOT NULL,
 first_execution_id INTEGER NOT NULL,
 final_execution_id INTEGER NOT NULL,
 FOREIGN KEY(first_execution_id) REFERENCES executions(id),
 FOREIGN KEY(final_execution_id) REFERENCES executions(id)
);
CREATE INDEX IF NOT EXISTS idx_trade_episodes_status_close
 ON trade_episodes(status, close_date);
CREATE INDEX IF NOT EXISTS idx_trade_episodes_security
 ON trade_episodes(security_code, security_name, account, position_side);
"""


def decimal(value: object | None) -> Decimal:
    return Decimal(str(value or 0))


def is_credit(transaction: str | None) -> bool:
    text = transaction or ""
    return "信用" in text or "菫｡逕ｨ" in text


def is_short_open(transaction: str | None, side: str) -> bool:
    text = transaction or ""
    return side == "SELL" and (
        "新規" in text or "信用売" in text or "譁ｰ隕" in text or "菫｡逕ｨ螢ｲ" in text
    )


def is_short_close(transaction: str | None, side: str) -> bool:
    text = transaction or ""
    return side == "BUY" and (
        "返済" in text or "信用買" in text or "霑疲ｸ" in text or "菫｡逕ｨ雋ｷ" in text
    )


def classify(row: sqlite3.Row) -> tuple[str, str, bool]:
    transaction = row["transaction_type"] or ""
    short_open = is_short_open(transaction, row["side"])
    short_close = is_short_close(transaction, row["side"])
    position_side = "SHORT" if short_open or short_close else "LONG"
    opens = (row["side"] == "BUY" and not short_close) or short_open
    return ("MARGIN" if is_credit(transaction) else "CASH", position_side, opens)


def stable_key(group: tuple[str, str, str, str], first_execution_id: int) -> str:
    raw = "|".join((*group, str(first_execution_id)))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_episode(row: sqlite3.Row, group: tuple[str, str, str, str]) -> dict:
    qty = decimal(row["quantity"])
    price = decimal(row["price"])
    costs = decimal(row["fee"]) + decimal(row["tax"])
    return {
        "episode_key": stable_key(group, row["id"]),
        "security_code": row["security_code"],
        "security_name": row["security_name"],
        "account": row["account"],
        "account_type": group[2],
        "position_side": group[3],
        "status": "OPEN",
        "open_date": row["trade_date"],
        "close_date": None,
        "open_qty": qty,
        "close_qty": Decimal(0),
        "open_value": qty * price,
        "close_value": Decimal(0),
        "costs": costs,
        "open_ids": [row["id"]],
        "close_ids": [],
        "first_execution_id": row["id"],
        "final_execution_id": row["id"],
    }


def finalize(episode: dict, closed: bool) -> dict:
    open_qty = episode["open_qty"]
    close_qty = episode["close_qty"]
    episode["status"] = "CLOSED" if closed else "OPEN"
    episode["weighted_open"] = episode["open_value"] / open_qty
    episode["weighted_close"] = (
        episode["close_value"] / close_qty if close_qty > TOLERANCE else None
    )
    if closed:
        gross = (
            episode["close_value"] - episode["open_value"]
            if episode["position_side"] == "LONG"
            else episode["open_value"] - episode["close_value"]
        )
        episode["gross_pnl"] = gross
        episode["net_pnl"] = gross - episode["costs"]
        episode["holding_days"] = (
            date.fromisoformat(episode["close_date"])
            - date.fromisoformat(episode["open_date"])
        ).days
    else:
        episode["gross_pnl"] = None
        episode["net_pnl"] = None
        episode["holding_days"] = None
    return episode


def build_episodes(db: sqlite3.Connection) -> list[dict]:
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM executions ORDER BY trade_date, id").fetchall()
    active: dict[tuple[str, str, str, str], dict] = {}
    completed: list[dict] = []

    for row in rows:
        account_type, position_side, opens = classify(row)
        security_identity = row["security_code"] or row["security_name"]
        group = (security_identity, row["account"] or "", account_type, position_side)
        qty = decimal(row["quantity"])
        price = decimal(row["price"])
        costs = decimal(row["fee"]) + decimal(row["tax"])

        if opens:
            if group not in active:
                active[group] = new_episode(row, group)
            else:
                episode = active[group]
                episode["open_qty"] += qty
                episode["open_value"] += qty * price
                episode["costs"] += costs
                episode["open_ids"].append(row["id"])
                episode["final_execution_id"] = row["id"]
            continue

        episode = active.get(group)
        if episode is None:
            continue
        remaining = episode["open_qty"] - episode["close_qty"]
        matched_qty = min(qty, remaining)
        if matched_qty <= TOLERANCE:
            continue
        episode["close_qty"] += matched_qty
        episode["close_value"] += matched_qty * price
        episode["costs"] += costs * matched_qty / qty
        episode["close_ids"].append(row["id"])
        episode["close_date"] = row["trade_date"]
        episode["final_execution_id"] = row["id"]
        if abs(episode["open_qty"] - episode["close_qty"]) <= TOLERANCE:
            completed.append(finalize(episode, True))
            del active[group]

    completed.extend(finalize(episode, False) for episode in active.values())
    return completed


def lot_count(db: sqlite3.Connection, episode: dict) -> int:
    if not episode["open_ids"] or not episode["close_ids"]:
        return 0
    open_marks = ",".join("?" for _ in episode["open_ids"])
    close_marks = ",".join("?" for _ in episode["close_ids"])
    query = (
        f"SELECT COUNT(*) FROM closed_trades "
        f"WHERE open_execution_id IN ({open_marks}) "
        f"AND close_execution_id IN ({close_marks})"
    )
    return db.execute(
        query, (*episode["open_ids"], *episode["close_ids"])
    ).fetchone()[0]


def persist(db: sqlite3.Connection, episodes: list[dict]) -> None:
    db.executescript(SCHEMA)
    keys: list[str] = []
    for episode in episodes:
        keys.append(episode["episode_key"])
        values = (
            episode["episode_key"], episode["security_code"], episode["security_name"],
            episode["account"], episode["account_type"], episode["position_side"],
            episode["status"], episode["open_date"], episode["close_date"],
            float(episode["open_qty"]), float(episode["close_qty"]),
            float(episode["weighted_open"]),
            float(episode["weighted_close"]) if episode["weighted_close"] is not None else None,
            float(episode["gross_pnl"]) if episode["gross_pnl"] is not None else None,
            float(episode["costs"]),
            float(episode["net_pnl"]) if episode["net_pnl"] is not None else None,
            episode["holding_days"], len(episode["open_ids"]), len(episode["close_ids"]),
            lot_count(db, episode), episode["first_execution_id"],
            episode["final_execution_id"],
        )
        db.execute(
            """
            INSERT INTO trade_episodes (
              episode_key,security_code,security_name,account,account_type,position_side,
              status,open_date,close_date,total_open_quantity,total_close_quantity,
              weighted_average_open_price,weighted_average_close_price,gross_pnl,
              allocated_costs,net_pnl,holding_days,open_execution_count,
              close_execution_count,closed_trade_lot_count,first_execution_id,
              final_execution_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(episode_key) DO UPDATE SET
              status=excluded.status,close_date=excluded.close_date,
              total_open_quantity=excluded.total_open_quantity,
              total_close_quantity=excluded.total_close_quantity,
              weighted_average_open_price=excluded.weighted_average_open_price,
              weighted_average_close_price=excluded.weighted_average_close_price,
              gross_pnl=excluded.gross_pnl,allocated_costs=excluded.allocated_costs,
              net_pnl=excluded.net_pnl,holding_days=excluded.holding_days,
              open_execution_count=excluded.open_execution_count,
              close_execution_count=excluded.close_execution_count,
              closed_trade_lot_count=excluded.closed_trade_lot_count,
              final_execution_id=excluded.final_execution_id
            """,
            values,
        )
    if keys:
        marks = ",".join("?" for _ in keys)
        db.execute(f"DELETE FROM trade_episodes WHERE episode_key NOT IN ({marks})", keys)
    else:
        db.execute("DELETE FROM trade_episodes")


def main() -> int:
    parser = argparse.ArgumentParser(description="約定を建玉ゼロからゼロまでの取引単位へ集約")
    parser.add_argument(
        "--db", "--database", dest="db", type=Path,
        default=Path("data/database/investment_lab.sqlite"),
    )
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error(f"DBが見つかりません: {args.db}")
    try:
        with sqlite3.connect(args.db) as db:
            episodes = build_episodes(db)
            persist(db, episodes)
        closed = sum(item["status"] == "CLOSED" for item in episodes)
        print(f"取引エピソード: {len(episodes)}件（決済済み {closed}件）")
        return 0
    except sqlite3.Error as exc:
        print(f"取引エピソード生成失敗: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
