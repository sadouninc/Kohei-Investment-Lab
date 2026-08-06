#!/usr/bin/env python3
"""Generate private advanced reports from closed trade episodes."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
import sqlite3
import statistics
import sys

HOLDING_BUCKETS = (
    ("当日", 0, 0), ("1日", 1, 1), ("2〜5日", 2, 5),
    ("6〜10日", 6, 10), ("11〜20日", 11, 20),
    ("21〜60日", 21, 60), ("61〜120日", 61, 120),
    ("121日以上", 121, None),
)
WEEKDAYS = ("月", "火", "水", "木", "金", "土", "日")


def d(value: object | None) -> Decimal:
    return Decimal(str(value or 0))


def divide(numerator: Decimal, denominator: Decimal) -> float | None:
    return float(numerator / denominator) if denominator else None


def streaks(values: list[Decimal]) -> tuple[int, int]:
    max_win = max_loss = current_win = current_loss = 0
    for value in values:
        if value > 0:
            current_win += 1
            current_loss = 0
        elif value < 0:
            current_loss += 1
            current_win = 0
        else:
            current_win = current_loss = 0
        max_win = max(max_win, current_win)
        max_loss = max(max_loss, current_loss)
    return max_win, max_loss


def statistics_for(rows: list[dict]) -> dict:
    pnls = [d(row["net_pnl"]) for row in rows]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    breakeven = [value for value in pnls if value == 0]
    gross_profit = sum(wins, Decimal(0))
    gross_loss = -sum(losses, Decimal(0))
    average_win = sum(wins, Decimal(0)) / len(wins) if wins else Decimal(0)
    average_loss = -sum(losses, Decimal(0)) / len(losses) if losses else Decimal(0)
    holding = [int(row["holding_days"]) for row in rows if row["holding_days"] is not None]
    max_win_streak, max_loss_streak = streaks(pnls)
    return {
        "trade_count": len(rows),
        "win_count": len(wins),
        "loss_count": len(losses),
        "breakeven_count": len(breakeven),
        "win_rate": len(wins) / len(rows) if rows else 0.0,
        "gross_profit": float(gross_profit),
        "gross_loss": float(gross_loss),
        "net_pnl": float(sum(pnls, Decimal(0))),
        "profit_factor": divide(gross_profit, gross_loss),
        "mean_pnl": float(statistics.fmean(map(float, pnls))) if pnls else 0.0,
        "median_pnl": float(statistics.median(map(float, pnls))) if pnls else 0.0,
        "average_win": float(average_win),
        "average_loss": float(average_loss),
        "payoff_ratio": divide(average_win, average_loss),
        "expectancy": float(sum(pnls, Decimal(0)) / len(pnls)) if pnls else 0.0,
        "max_win": float(max(wins)) if wins else 0.0,
        "max_loss": float(min(losses)) if losses else 0.0,
        "pnl_stddev": statistics.pstdev(map(float, pnls)) if len(pnls) > 1 else 0.0,
        "average_holding_days": statistics.fmean(holding) if holding else 0.0,
        "median_holding_days": statistics.median(holding) if holding else 0.0,
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
    }


def grouped(rows: list[dict], key) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(key(row))].append(row)
    return [
        {"label": label, **statistics_for(items)}
        for label, items in sorted(groups.items())
    ]


def weekdays_grouped(rows: list[dict], date_key: str) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        label = WEEKDAYS[date.fromisoformat(row[date_key]).weekday()]
        groups[label].append(row)
    return [
        {"label": label, **statistics_for(groups[label])}
        for label in WEEKDAYS if label in groups
    ]


def holding_periods(rows: list[dict]) -> list[dict]:
    result = []
    for label, minimum, maximum in HOLDING_BUCKETS:
        matches = [
            row for row in rows
            if row["holding_days"] is not None
            and int(row["holding_days"]) >= minimum
            and (maximum is None or int(row["holding_days"]) <= maximum)
        ]
        result.append({"label": label, **statistics_for(matches)})
    return result


def concentration(rows: list[dict]) -> dict:
    by_security: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows:
        identity = row["security_code"] or row["security_name"]
        by_security[identity] += d(row["net_pnl"])
    total = sum(by_security.values(), Decimal(0))
    ranked_securities = sorted(by_security.items(), key=lambda item: item[1], reverse=True)
    ranked_trades = sorted(rows, key=lambda row: d(row["net_pnl"]), reverse=True)
    output: dict[str, float | None] = {}
    for count in (1, 3, 5):
        top_security = sum((value for _, value in ranked_securities[:count]), Decimal(0))
        output[f"top_{count}_security_contribution"] = divide(top_security, total)
        output[f"profit_factor_excluding_top_{count}_trades"] = statistics_for(
            ranked_trades[count:]
        )["profit_factor"]
    return output


def equity_curve(rows: list[dict]) -> dict:
    """Build a realized-P&L curve in close-date order.

    This is not total account equity because deposits, withdrawals and
    unrealized P&L are outside the execution database.
    """
    cumulative = Decimal(0)
    high_water = Decimal(0)
    peak_date: str | None = None
    max_drawdown = Decimal(0)
    max_drawdown_start: str | None = None
    max_drawdown_end: str | None = None
    points: list[dict] = []
    for row in sorted(rows, key=lambda item: (item["close_date"], item["id"])):
        cumulative += d(row["net_pnl"])
        if cumulative >= high_water:
            high_water = cumulative
            peak_date = row["close_date"]
        drawdown = cumulative - high_water
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            max_drawdown_start = peak_date
            max_drawdown_end = row["close_date"]
        points.append({
            "date": row["close_date"],
            "cumulative_pnl": float(cumulative),
            "high_water_pnl": float(high_water),
            "drawdown": float(drawdown),
        })
    duration = None
    if max_drawdown_start and max_drawdown_end:
        duration = (
            date.fromisoformat(max_drawdown_end)
            - date.fromisoformat(max_drawdown_start)
        ).days
    return {
        "points": points,
        "max_drawdown": float(max_drawdown),
        "max_drawdown_start": max_drawdown_start,
        "max_drawdown_end": max_drawdown_end,
        "max_drawdown_days": duration,
    }


def load_closed_episodes(db: sqlite3.Connection) -> list[dict]:
    db.row_factory = sqlite3.Row
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='trade_episodes'"
    ).fetchone()
    if not exists:
        raise sqlite3.OperationalError(
            "trade_episodesがありません。先にbuild_trade_episodes.pyを実行してください"
        )
    return [
        dict(row) for row in db.execute(
            "SELECT * FROM trade_episodes WHERE status='CLOSED' ORDER BY close_date,id"
        ).fetchall()
    ]


def build_analysis(rows: list[dict]) -> dict:
    return {
        "period": {
            "start": min((row["open_date"] for row in rows), default=None),
            "end": max((row["close_date"] for row in rows), default=None),
        },
        "overall": statistics_for(rows),
        "by_position_side": grouped(rows, lambda row: row["position_side"]),
        "by_account_type": grouped(rows, lambda row: row["account_type"]),
        "by_security": grouped(
            rows, lambda row: row["security_code"] or row["security_name"]
        ),
        "by_year": grouped(rows, lambda row: row["close_date"][:4]),
        "by_month": grouped(rows, lambda row: row["close_date"][:7]),
        "by_entry_weekday": weekdays_grouped(rows, "open_date"),
        "by_exit_weekday": weekdays_grouped(rows, "close_date"),
        "holding_periods": holding_periods(rows),
        "concentration": concentration(rows),
        "equity_curve": equity_curve(rows),
    }


def yen(value: float) -> str:
    return f"{value:,.0f}円"


def rate(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def ratio(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def markdown_table(items: list[dict]) -> list[str]:
    lines = [
        "| 区分 | 取引数 | 勝率 | PF | 純損益 | 平均保有日数 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        f"| {item['label']} | {item['trade_count']} | {rate(item['win_rate'])} | "
        f"{ratio(item['profit_factor'])} | {yen(item['net_pnl'])} | "
        f"{item['average_holding_days']:.1f} |"
        for item in items
    )
    return lines


def write_reports(output: Path, rows: list[dict], analysis: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "trade_episodes.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [
            "id", "episode_key", "security_code", "security_name", "account",
            "account_type", "position_side", "status", "open_date", "close_date",
        ])
        writer.writeheader()
        writer.writerows(rows)

    overall = analysis["overall"]
    lines = [
        "# Advanced Trade Statistics", "",
        "> このファイルは個人用です。公開リポジトリへコミットしないでください。", "",
        "## 全体", "",
        f"- 取引数: {overall['trade_count']}",
        f"- 勝 / 負 / 引分: {overall['win_count']} / {overall['loss_count']} / {overall['breakeven_count']}",
        f"- 勝率: {rate(overall['win_rate'])}",
        f"- 純損益: {yen(overall['net_pnl'])}",
        f"- 平均損益 / 中央値: {yen(overall['mean_pnl'])} / {yen(overall['median_pnl'])}",
        f"- 平均利益 / 平均損失: {yen(overall['average_win'])} / {yen(overall['average_loss'])}",
        f"- プロフィットファクター: {ratio(overall['profit_factor'])}",
        f"- ペイオフレシオ: {ratio(overall['payoff_ratio'])}",
        f"- 期待値: {yen(overall['expectancy'])}",
        f"- 最大利益 / 最大損失: {yen(overall['max_win'])} / {yen(overall['max_loss'])}",
        f"- 損益標準偏差: {yen(overall['pnl_stddev'])}",
        f"- 平均 / 中央保有日数: {overall['average_holding_days']:.1f} / {overall['median_holding_days']:.1f}",
        f"- 最大連勝 / 連敗: {overall['max_win_streak']} / {overall['max_loss_streak']}",
        "", "## 売買方向", "",
        *markdown_table(analysis["by_position_side"]),
        "", "## 現物・信用", "",
        *markdown_table(analysis["by_account_type"]),
        "", "## 銘柄別", "",
        *markdown_table(analysis["by_security"]),
        "", "## 年別", "",
        *markdown_table(analysis["by_year"]),
        "", "## 月別", "",
        *markdown_table(analysis["by_month"]),
        "", "## 保有期間", "",
        *markdown_table(analysis["holding_periods"]),
        "", "## 曜日（エントリー）", "",
        *markdown_table(analysis["by_entry_weekday"]),
        "", "## 曜日（決済）", "",
        *markdown_table(analysis["by_exit_weekday"]),
        "", "## 集中度", "",
    ]
    for count in (1, 3, 5):
        contribution = analysis["concentration"][f"top_{count}_security_contribution"]
        excluded_pf = analysis["concentration"][f"profit_factor_excluding_top_{count}_trades"]
        lines.append(
            f"- 上位{count}銘柄の利益寄与率: {rate(contribution)} / "
            f"上位{count}取引除外後PF: {ratio(excluded_pf)}"
        )
    (output / "Advanced_Trading_Statistics.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="取引エピソードから高度な個人用レポートを生成")
    parser.add_argument(
        "--db", "--database", dest="db", type=Path,
        default=Path("data/database/investment_lab.sqlite"),
    )
    parser.add_argument(
        "--output-dir", "--output", dest="output", type=Path,
        default=Path("data/generated"),
    )
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error(f"DBが見つかりません: {args.db}")
    try:
        with sqlite3.connect(args.db) as db:
            rows = load_closed_episodes(db)
        analysis = build_analysis(rows)
        write_reports(args.output, rows, analysis)
        print(f"高度な取引レポート: {args.output.resolve()}（{len(rows)}取引）")
        return 0
    except (sqlite3.Error, OSError, ValueError) as exc:
        print(f"レポート生成失敗: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

