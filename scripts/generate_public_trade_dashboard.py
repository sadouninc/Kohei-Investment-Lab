#!/usr/bin/env python3
"""Create an anonymized aggregate-only JSON payload for GitHub Pages."""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys

from generate_advanced_trade_reports import build_analysis, load_closed_episodes

PUBLIC_SCHEMA_VERSION = 1
FORBIDDEN_KEYS = {
    "security_code", "security_name", "account", "episode_key",
    "execution_id", "price", "quantity", "net_pnl", "gross_pnl",
    "realized_pnl", "amount",
}


def indexed_expectancy(rows: list[dict], expectancy: float) -> float:
    absolute_mean = (
        sum(abs(float(row["net_pnl"])) for row in rows) / len(rows) if rows else 0
    )
    return round(100 + (expectancy / absolute_mean * 100), 2) if absolute_mean else 100.0


def index_value(value: float, scale: float) -> float:
    return round(value / scale * 100, 2) if scale else 0.0


def safe_metrics(item: dict, scale: float) -> dict:
    return {
        "label": item["label"],
        "trade_count": item["trade_count"],
        "win_count": item["win_count"],
        "loss_count": item["loss_count"],
        "breakeven_count": item["breakeven_count"],
        "win_rate": round(item["win_rate"], 6),
        "profit_factor": (
            round(item["profit_factor"], 4)
            if item["profit_factor"] is not None else None
        ),
        "payoff_ratio": (
            round(item["payoff_ratio"], 4)
            if item["payoff_ratio"] is not None else None
        ),
        "average_holding_days": round(item["average_holding_days"], 2),
        "median_holding_days": round(item["median_holding_days"], 2),
        "indexed_net_result": index_value(item["net_pnl"], scale),
        "indexed_gross_gain": index_value(item["gross_profit"], scale),
        "indexed_gross_decline": index_value(item["gross_loss"], scale),
        "indexed_average_gain": index_value(item["average_win"], scale),
        "indexed_average_decline": index_value(item["average_loss"], scale),
        "indexed_max_gain": index_value(item["max_win"], scale),
        "indexed_max_decline": index_value(abs(item["max_loss"]), scale),
    }


def monthly_curve(months: list[dict], scale: float) -> dict:
    cumulative = 0.0
    high_water = 0.0
    max_drawdown = 0.0
    points = []
    max_start = max_end = None
    peak_month = None
    for item in months:
        cumulative += item["net_pnl"]
        if cumulative >= high_water:
            high_water = cumulative
            peak_month = item["label"]
        drawdown = cumulative - high_water
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            max_start = peak_month
            max_end = item["label"]
        points.append({
            "month": item["label"],
            "indexed_month_result": index_value(item["net_pnl"], scale),
            "indexed_cumulative_result": index_value(cumulative, scale),
            "indexed_drawdown": index_value(drawdown, scale),
        })
    return {
        "points": points,
        "indexed_max_drawdown": index_value(max_drawdown, scale),
        "max_drawdown_start_month": max_start,
        "max_drawdown_end_month": max_end,
    }


def load_data_quality(db: sqlite3.Connection) -> dict:
    def count(query: str) -> int:
        try:
            return db.execute(query).fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    audit_exists = count(
        """SELECT COUNT(*) FROM sqlite_master
           WHERE type='table' AND name='import_audit'"""
    )
    audit_source_records = duplicate_count = None
    if audit_exists:
        audit_source_records = count(
            """SELECT COALESCE(SUM(source_record_count),0) FROM import_audit
               WHERE id IN (SELECT MAX(id) FROM import_audit GROUP BY source_file)"""
        )
        duplicate_count = count(
            """SELECT COALESCE(SUM(duplicate_count),0) FROM import_audit
               WHERE id IN (SELECT MAX(id) FROM import_audit GROUP BY source_file)"""
        )
    return {
        "source_csv_count": count("SELECT COUNT(DISTINCT source_file) FROM executions"),
        "source_record_count": (
            audit_source_records
            if audit_source_records is not None
            else count("SELECT COUNT(*) FROM executions")
        ),
        "valid_record_count": count("SELECT COUNT(*) FROM executions"),
        "duplicate_excluded_count": duplicate_count,
        "closed_episode_count": count(
            "SELECT COUNT(*) FROM trade_episodes WHERE status='CLOSED'"
        ),
        "open_episode_count": count(
            "SELECT COUNT(*) FROM trade_episodes WHERE status='OPEN'"
        ),
        "unmatched_execution_count": count(
            "SELECT COUNT(*) FROM unmatched_executions"
        ),
        "unresolved_security_count": count(
            """SELECT COUNT(*) FROM executions
               WHERE security_name IS NULL OR trim(security_name)=''"""
        ),
        "theme_unclassified_count": None,
        "matching_method": "FIFO / Trade Episode",
    }


def build_public_payload(
    rows: list[dict], updated: str | None = None, quality: dict | None = None
) -> dict:
    analysis = build_analysis(rows)
    overall = analysis["overall"]
    scale = (
        sum(abs(float(row["net_pnl"])) for row in rows) / len(rows)
        if rows else 0.0
    )
    years = [safe_metrics(item, scale) for item in analysis["by_year"]]
    months = [safe_metrics(item, scale) for item in analysis["by_month"]]
    return {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "updated_date": updated or date.today().isoformat(),
        "period": analysis["period"],
        "summary": {
            "trade_count": overall["trade_count"],
            "win_rate": round(overall["win_rate"], 6),
            "profit_factor": (
                round(overall["profit_factor"], 4)
                if overall["profit_factor"] is not None else None
            ),
            "payoff_ratio": (
                round(overall["payoff_ratio"], 4)
                if overall["payoff_ratio"] is not None else None
            ),
            "indexed_expectancy": indexed_expectancy(rows, overall["expectancy"]),
            "average_holding_days": round(overall["average_holding_days"], 2),
            "median_holding_days": round(overall["median_holding_days"], 2),
            "max_win_streak": overall["max_win_streak"],
            "max_loss_streak": overall["max_loss_streak"],
            "win_count": overall["win_count"],
            "loss_count": overall["loss_count"],
            "breakeven_count": overall["breakeven_count"],
            "closed_trade_count": overall["trade_count"],
            "indexed_net_result": index_value(overall["net_pnl"], scale),
            "indexed_gross_gain": index_value(overall["gross_profit"], scale),
            "indexed_gross_decline": index_value(overall["gross_loss"], scale),
            "indexed_average_gain": index_value(overall["average_win"], scale),
            "indexed_average_decline": index_value(overall["average_loss"], scale),
            "indexed_max_gain": index_value(overall["max_win"], scale),
            "indexed_max_decline": index_value(abs(overall["max_loss"]), scale),
        },
        "years": years,
        "months": months,
        "monthly_equity_curve": monthly_curve(analysis["by_month"], scale),
        "holding_periods": [
            safe_metrics(item, scale) for item in analysis["holding_periods"]
        ],
        "entry_weekdays": [
            safe_metrics(item, scale) for item in analysis["by_entry_weekday"]
        ],
        "exit_weekdays": [
            safe_metrics(item, scale) for item in analysis["by_exit_weekday"]
        ],
        "position_sides": [
            safe_metrics(item, scale) for item in analysis["by_position_side"]
        ],
        "account_types": [
            safe_metrics(item, scale) for item in analysis["by_account_type"]
        ],
        "concentration": {
            key: (round(value, 4) if value is not None else None)
            for key, value in analysis["concentration"].items()
        },
        "data_quality": quality or {
            "source_csv_count": None,
            "source_record_count": None,
            "valid_record_count": None,
            "duplicate_excluded_count": None,
            "closed_episode_count": overall["trade_count"],
            "open_episode_count": None,
            "unmatched_execution_count": None,
            "unresolved_security_count": None,
            "theme_unclassified_count": None,
            "matching_method": "FIFO / Trade Episode",
        },
    }


def assert_public(payload: object, path: str = "$") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = key.lower()
            if lowered in FORBIDDEN_KEYS:
                raise ValueError(f"公開禁止キーを検出しました: {path}.{key}")
            assert_public(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_public(value, f"{path}[{index}]")


def main() -> int:
    parser = argparse.ArgumentParser(description="匿名化した公開用取引統計JSONを生成")
    parser.add_argument(
        "--db", "--database", dest="db", type=Path,
        default=Path("data/database/investment_lab.sqlite"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/generated/public/trade-analysis-summary.json"),
    )
    parser.add_argument("--updated-date", help="再現可能な生成用の日付（YYYY-MM-DD）")
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error(f"DBが見つかりません: {args.db}")
    try:
        with sqlite3.connect(args.db) as db:
            rows = load_closed_episodes(db)
            quality = load_data_quality(db)
        payload = build_public_payload(rows, args.updated_date, quality)
        assert_public(payload)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"公開用匿名統計: {args.output.resolve()}（{len(rows)}取引）")
        return 0
    except (sqlite3.Error, OSError, ValueError) as exc:
        print(f"公開用JSON生成失敗: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

