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


def safe_metrics(item: dict) -> dict:
    return {
        "label": item["label"],
        "trade_count": item["trade_count"],
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
    }


def build_public_payload(rows: list[dict], updated: str | None = None) -> dict:
    analysis = build_analysis(rows)
    overall = analysis["overall"]
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
        },
        "holding_periods": [safe_metrics(item) for item in analysis["holding_periods"]],
        "entry_weekdays": [safe_metrics(item) for item in analysis["by_entry_weekday"]],
        "exit_weekdays": [safe_metrics(item) for item in analysis["by_exit_weekday"]],
        "position_sides": [safe_metrics(item) for item in analysis["by_position_side"]],
        "account_types": [safe_metrics(item) for item in analysis["by_account_type"]],
        "concentration": {
            key: (round(value, 4) if value is not None else None)
            for key, value in analysis["concentration"].items()
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
        payload = build_public_payload(rows, args.updated_date)
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
