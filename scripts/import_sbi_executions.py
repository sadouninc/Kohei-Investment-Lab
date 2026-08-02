#!/usr/bin/env python3
"""Import SBI execution-history CSV files into SQLite."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ALIASES = {
    "trade_date": ("約定日", "受渡日", "日付"),
    "account": ("口座", "預り", "預り区分", "口座区分"),
    "product": ("商品", "商品区分"),
    "transaction": ("取引", "取引区分"),
    "side": ("売買", "売買区分"),
    "code": ("銘柄コード", "コード"),
    "name": ("銘柄", "銘柄名", "ファンド名"),
    "quantity": ("約定数量", "数量", "株数"),
    "price": ("約定単価", "単価", "約定価格"),
    "amount": ("受渡金額/決済損益", "受渡金額", "約定代金", "金額"),
    "fee": ("手数料/諸経費等", "手数料", "諸経費"),
    "tax": ("税額", "消費税"),
    "realized_pnl": ("受渡金額/決済損益", "決済損益", "譲渡損益", "損益"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS executions (
 id INTEGER PRIMARY KEY, source_file TEXT NOT NULL, source_row INTEGER NOT NULL,
 fingerprint TEXT NOT NULL UNIQUE, trade_date TEXT NOT NULL, account TEXT,
 product TEXT, transaction_type TEXT, side TEXT NOT NULL, security_code TEXT,
 security_name TEXT NOT NULL, quantity REAL NOT NULL CHECK(quantity > 0),
 price REAL NOT NULL CHECK(price >= 0), amount REAL, fee REAL, tax REAL,
 realized_pnl REAL, raw_json TEXT NOT NULL, imported_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exec_fifo
 ON executions(security_code, security_name, account, trade_date, id);
CREATE TABLE IF NOT EXISTS closed_trades (
 id INTEGER PRIMARY KEY, open_execution_id INTEGER NOT NULL,
 close_execution_id INTEGER NOT NULL, security_code TEXT, security_name TEXT NOT NULL,
 account TEXT, position_side TEXT NOT NULL, open_date TEXT NOT NULL,
 close_date TEXT NOT NULL, quantity REAL NOT NULL, open_price REAL NOT NULL,
 close_price REAL NOT NULL, gross_pnl REAL NOT NULL, allocated_costs REAL NOT NULL DEFAULT 0,
 net_pnl REAL NOT NULL, holding_days INTEGER NOT NULL,
 UNIQUE(open_execution_id, close_execution_id),
 FOREIGN KEY(open_execution_id) REFERENCES executions(id),
 FOREIGN KEY(close_execution_id) REFERENCES executions(id)
);
CREATE TABLE IF NOT EXISTS unmatched_executions (
 execution_id INTEGER PRIMARY KEY, unmatched_quantity REAL NOT NULL,
 reason TEXT NOT NULL, FOREIGN KEY(execution_id) REFERENCES executions(id)
);
"""

def clean(s: str | None) -> str:
    return (s or "").replace("\u3000", " ").strip()

def number(s: str | None) -> float | None:
    t = clean(s)
    if not t or t in {"-", "--"}:
        return None
    negative = t.startswith("(") and t.endswith(")")
    t = re.sub(r"[,\s円株%()]", "", t)
    try:
        value = float(t)
        return -value if negative else value
    except ValueError as exc:
        raise ValueError(f"数値として解釈できません: {s!r}") from exc

def date_value(s: str) -> str:
    t = clean(s).split()[0]
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y年%m月%d日", "%y/%m/%d"):
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"日付として解釈できません: {s!r}")

def pick(row: dict[str, str], key: str) -> str:
    normalized = {clean(k).replace("\ufeff", ""): v for k, v in row.items() if k}
    for name in ALIASES[key]:
        if name in normalized:
            return clean(normalized[name])
    return ""

def normalize_side(row: dict[str, str]) -> str:
    text = " ".join((pick(row, "side"), pick(row, "transaction")))
    if "売" in text or "解約" in text:
        return "SELL"
    if "買" in text or "再投資" in text:
        return "BUY"
    raise ValueError(f"売買区分を判定できません: {text!r}")

def open_csv(path: Path, encoding: str):
    if encoding != "auto":
        return path.open("r", encoding=encoding, newline="")
    for enc in ("cp932", "utf-8-sig"):
        try:
            path.read_text(encoding=enc)
            return path.open("r", encoding=enc, newline="")
        except UnicodeDecodeError:
            continue
    raise UnicodeError("CP932/UTF-8のどちらでも読み込めません")

def main() -> int:
    ap = argparse.ArgumentParser(description="SBI約定履歴CSVをSQLiteへ登録")
    ap.add_argument("csv", nargs="?", type=Path, help="入力CSV（--inputでも指定可能）")
    ap.add_argument("--input", dest="input_csv", type=Path, help="入力CSV")
    ap.add_argument("--db", "--database", dest="db", type=Path,
                    default=Path("data/database/investment_lab.sqlite"))
    ap.add_argument("--encoding", default="auto")
    ap.add_argument("--strict", action="store_true", help="不正行があれば全体を失敗")
    args = ap.parse_args()
    csv_path = args.input_csv or args.csv
    if not csv_path:
        ap.error("入力CSVを指定してください")
    if not csv_path.is_file():
        ap.error(f"CSVが見つかりません: {csv_path}")
    args.db.parent.mkdir(parents=True, exist_ok=True)
    inserted = duplicates = 0
    errors: list[str] = []
    try:
        with open_csv(csv_path, args.encoding) as fh, sqlite3.connect(args.db) as db:
            db.executescript(SCHEMA)
            # SBI exports include search conditions and notes before the actual
            # execution header. Locate that header instead of assuming line 1.
            raw_reader = csv.reader(fh)
            header = None
            header_line = 0
            for header_line, candidate in enumerate(raw_reader, 1):
                normalized = {clean(x).replace("\ufeff", "") for x in candidate}
                if "約定日" in normalized and ("銘柄" in normalized or "銘柄名" in normalized):
                    header = candidate
                    break
            if not header:
                raise ValueError("約定明細のヘッダー行がありません")
            reader = csv.DictReader(fh, fieldnames=header)
            occurrences: dict[str, int] = defaultdict(int)
            for line, row in enumerate(reader, header_line + 1):
                try:
                    name, code = pick(row, "name"), pick(row, "code")
                    qty, price = number(pick(row, "quantity")), number(pick(row, "price"))
                    if not name or qty is None or price is None:
                        raise ValueError("銘柄名・数量・単価は必須です")
                    transaction = pick(row, "transaction")
                    combined_amount = number(pick(row, "amount"))
                    is_credit_close = "信用返済" in transaction
                    values = {
                        "trade_date": date_value(pick(row, "trade_date")),
                        "account": pick(row, "account"), "product": pick(row, "product"),
                        "transaction": transaction, "side": normalize_side(row),
                        "code": code, "name": name, "quantity": qty, "price": price,
                        "amount": None if is_credit_close else combined_amount,
                        "fee": number(pick(row, "fee")), "tax": number(pick(row, "tax")),
                        "pnl": combined_amount if is_credit_close else number(pick(row, "realized_pnl"))
                        if pick(row, "realized_pnl") != pick(row, "amount") else None,
                    }
                    canonical = json.dumps(values, ensure_ascii=False, sort_keys=True)
                    # Preserve genuinely repeated fills while making a re-import idempotent.
                    occurrences[canonical] += 1
                    identity = f"{canonical}\noccurrence={occurrences[canonical]}"
                    fp = hashlib.sha256(identity.encode()).hexdigest()
                    cur = db.execute("""INSERT OR IGNORE INTO executions
                      (source_file,source_row,fingerprint,trade_date,account,product,
                       transaction_type,side,security_code,security_name,quantity,price,
                       amount,fee,tax,realized_pnl,raw_json,imported_at)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (csv_path.name, line, fp, values["trade_date"], values["account"],
                       values["product"], values["transaction"], values["side"], code, name,
                       qty, price, values["amount"], values["fee"], values["tax"], values["pnl"],
                       json.dumps(row, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")))
                    inserted += cur.rowcount
                    duplicates += cur.rowcount == 0
                except Exception as exc:
                    errors.append(f"{line}行目: {exc}")
                    if args.strict:
                        raise
            if errors and args.strict:
                raise ValueError(errors[0])
        print(f"登録: {inserted}件 / 重複スキップ: {duplicates}件 / エラー: {len(errors)}件")
        for msg in errors[:10]:
            print(msg, file=sys.stderr)
        return 0 if not errors else 2
    except Exception as exc:
        print(f"インポート失敗: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

