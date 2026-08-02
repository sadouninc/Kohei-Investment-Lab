#!/usr/bin/env python3
"""Generate Markdown and CSV summaries from closed trades."""
from __future__ import annotations
import argparse
import csv
import sqlite3
import sys
from pathlib import Path

def yen(v): return f"{v:,.0f}円"

def main() -> int:
    ap = argparse.ArgumentParser(description="取引集計Markdown/CSVを生成")
    ap.add_argument("--db", "--database", dest="db", type=Path,
                    default=Path("data/database/investment_lab.sqlite"))
    ap.add_argument("--output-dir", "--output", dest="output_dir", type=Path,
                    default=Path("data/generated"))
    args = ap.parse_args()
    if not args.db.is_file(): ap.error(f"DBが見つかりません: {args.db}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(args.db) as db:
            db.row_factory = sqlite3.Row
            trades = db.execute("SELECT * FROM closed_trades ORDER BY close_date,id").fetchall()
            symbols = db.execute("""SELECT security_code,security_name,COUNT(*) trades,
              SUM(net_pnl) pnl,AVG(net_pnl>0)*100 win_rate,AVG(holding_days) avg_days
              FROM closed_trades GROUP BY security_code,security_name ORDER BY pnl DESC""").fetchall()
            months = db.execute("""SELECT substr(close_date,1,7) month,COUNT(*) trades,
              SUM(net_pnl) pnl,AVG(net_pnl>0)*100 win_rate
              FROM closed_trades GROUP BY month ORDER BY month""").fetchall()
            unmatched = db.execute("SELECT COUNT(*) FROM unmatched_executions").fetchone()[0]
        with (args.output_dir/"closed_trades.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f); w.writerow(trades[0].keys() if trades else
                ["id","open_execution_id","close_execution_id","security_code","security_name"])
            w.writerows([tuple(r) for r in trades])
        with (args.output_dir/"by_security.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w=csv.writer(f); w.writerow(["銘柄コード","銘柄名","決済ロット","純損益","勝率","平均保有日数"])
            w.writerows([tuple(r) for r in symbols])
        total = sum(r["net_pnl"] for r in trades)
        wins = sum(r["net_pnl"] > 0 for r in trades)
        gross_win = sum(max(r["net_pnl"],0) for r in trades)
        gross_loss = -sum(min(r["net_pnl"],0) for r in trades)
        pf = gross_win/gross_loss if gross_loss else None
        lines = ["# Trading Statistics","",
          f"- 決済ロット数: {len(trades)}", f"- 純損益: {yen(total)}",
          f"- 勝率: {(wins/len(trades)*100 if trades else 0):.1f}%",
          f"- プロフィットファクター: {pf:.2f}" if pf is not None else "- プロフィットファクター: N/A",
          f"- 未対応約定: {unmatched}件","","## 月次成績","",
          "| 月 | 決済ロット | 純損益 | 勝率 |","|---|---:|---:|---:|"]
        lines += [f"| {r['month']} | {r['trades']} | {yen(r['pnl'])} | {r['win_rate']:.1f}% |" for r in months]
        (args.output_dir/"Trading_Statistics.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
        print(f"生成先: {args.output_dir.resolve()} ({len(trades)}決済ロット)")
        return 0
    except sqlite3.Error as exc:
        print(f"レポート生成失敗: {exc}", file=sys.stderr); return 1

if __name__ == "__main__":
    raise SystemExit(main())

