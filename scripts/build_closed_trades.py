#!/usr/bin/env python3
"""Match executions into closed trades using FIFO."""
from __future__ import annotations
import argparse
import sqlite3
import sys
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

def is_short_open(transaction: str, side: str) -> bool:
    t = transaction or ""
    return side == "SELL" and ("新規" in t or "信用売" in t)

def is_short_close(transaction: str, side: str) -> bool:
    t = transaction or ""
    return side == "BUY" and ("返済" in t or "信用買" in t)

def main() -> int:
    ap = argparse.ArgumentParser(description="約定をFIFOで対応付け、決済取引を構築")
    ap.add_argument("--db", "--database", dest="db", type=Path,
                    default=Path("data/database/investment_lab.sqlite"))
    ap.add_argument("--keep-existing", action="store_true")
    args = ap.parse_args()
    if not args.db.is_file():
        ap.error(f"DBが見つかりません: {args.db}")
    try:
        with sqlite3.connect(args.db) as db:
            db.row_factory = sqlite3.Row
            if not args.keep_existing:
                db.execute("DELETE FROM closed_trades")
                db.execute("DELETE FROM unmatched_executions")
            rows = db.execute("SELECT * FROM executions ORDER BY trade_date,id").fetchall()
            lots = defaultdict(lambda: {"LONG": deque(), "SHORT": deque()})
            matched = 0
            for r in rows:
                key = (r["security_code"] or r["security_name"], r["account"] or "")
                side = r["side"]
                short_open = is_short_open(r["transaction_type"], side)
                short_close = is_short_close(r["transaction_type"], side)
                position = "SHORT" if short_open or short_close else "LONG"
                opens = (side == "BUY" and not short_close) or short_open
                if opens:
                    lots[key][position].append([r, float(r["quantity"])])
                    continue
                remaining = float(r["quantity"])
                queue = lots[key][position]
                while remaining > 1e-9 and queue:
                    opening, available = queue[0]
                    qty = min(remaining, available)
                    gross = ((r["price"] - opening["price"]) if position == "LONG"
                             else (opening["price"] - r["price"])) * qty
                    open_cost = (opening["fee"] or 0) + (opening["tax"] or 0)
                    close_cost = (r["fee"] or 0) + (r["tax"] or 0)
                    costs = open_cost * qty / opening["quantity"] + close_cost * qty / r["quantity"]
                    days = (date.fromisoformat(r["trade_date"]) -
                            date.fromisoformat(opening["trade_date"])).days
                    db.execute("""INSERT OR REPLACE INTO closed_trades
                      (open_execution_id,close_execution_id,security_code,security_name,
                       account,position_side,open_date,close_date,quantity,open_price,
                       close_price,gross_pnl,allocated_costs,net_pnl,holding_days)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (opening["id"], r["id"], r["security_code"], r["security_name"],
                        r["account"], position, opening["trade_date"], r["trade_date"], qty,
                        opening["price"], r["price"], gross, costs, gross-costs, days))
                    matched += 1
                    remaining -= qty
                    available -= qty
                    if available <= 1e-9: queue.popleft()
                    else: queue[0][1] = available
                if remaining > 1e-9:
                    db.execute("INSERT OR REPLACE INTO unmatched_executions VALUES(?,?,?)",
                               (r["id"], remaining, "対応する建玉がありません"))
            for positions in lots.values():
                for queue in positions.values():
                    for opening, qty in queue:
                        db.execute("INSERT OR REPLACE INTO unmatched_executions VALUES(?,?,?)",
                                   (opening["id"], qty, "未決済建玉"))
            unmatched = db.execute("SELECT COUNT(*) FROM unmatched_executions").fetchone()[0]
        print(f"決済ロット: {matched}件 / 未対応約定: {unmatched}件")
        return 0
    except sqlite3.Error as exc:
        print(f"DB処理失敗: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

