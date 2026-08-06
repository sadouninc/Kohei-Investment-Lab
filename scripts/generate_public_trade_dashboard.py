#!/usr/bin/env python3
"""Generate the public, analysis-complete Trade Analysis JSON.

Investment facts (security, quantity, price and P&L) are intentionally public.
Account identifiers, source paths, execution fingerprints and credentials are
never emitted.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys

from generate_advanced_trade_reports import build_analysis, load_closed_episodes

PUBLIC_SCHEMA_VERSION = 2
PRIVATE_KEYS = {
    "account",
    "episode_key",
    "execution_id",
    "first_execution_id",
    "final_execution_id",
    "source_file",
    "fingerprint",
    "login_id",
    "password",
    "api_key",
    "email",
    "phone",
    "address",
}


def rounded(value: float | None, digits: int = 2) -> float | None:
    return round(float(value), digits) if value is not None else None


def public_metrics(item: dict) -> dict:
    return {
        "label": item["label"],
        "trade_count": item["trade_count"],
        "win_count": item["win_count"],
        "loss_count": item["loss_count"],
        "breakeven_count": item["breakeven_count"],
        "win_rate": rounded(item["win_rate"], 6),
        "profit_factor": rounded(item["profit_factor"], 4),
        "payoff_ratio": rounded(item["payoff_ratio"], 4),
        "net_pnl": rounded(item["net_pnl"]),
        "gross_profit": rounded(item["gross_profit"]),
        "gross_loss": rounded(item["gross_loss"]),
        "average_win": rounded(item["average_win"]),
        "average_loss": rounded(item["average_loss"]),
        "average_holding_days": rounded(item["average_holding_days"]),
        "median_holding_days": rounded(item["median_holding_days"]),
        "max_win": rounded(item["max_win"]),
        "max_loss": rounded(item["max_loss"]),
    }


def equity_curve(points: list[dict]) -> dict:
    maximum = min((float(row["drawdown"]) for row in points), default=0.0)
    return {
        "points": [
            {
                "date": row["date"],
                "cumulative_pnl": rounded(row["cumulative_pnl"]),
                "high_water_pnl": rounded(row["high_water_pnl"]),
                "drawdown": rounded(row["drawdown"]),
            }
            for row in points
        ],
        "max_drawdown": rounded(maximum),
    }


def load_stock_master(path: Path | None) -> dict[str, dict]:
    if not path or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("stocks", payload)
    return {
        str(row["security_code"]): {
            "sector": row.get("sector") or "未分類",
            "primary_theme": row.get("primary_theme") or "未分類",
            "themes": row.get("themes") or [row.get("primary_theme") or "未分類"],
            "market": row.get("market") or "不明",
        }
        for row in rows
    }


def public_trade(row: dict, master: dict[str, dict]) -> dict:
    code = str(row.get("security_code") or "")
    tags = master.get(code, {})
    return {
        "id": row["id"],
        "security_code": code,
        "security_name": row.get("security_name") or "銘柄名不明",
        "market": tags.get("market", "不明"),
        "sector": tags.get("sector", "未分類"),
        "primary_theme": tags.get("primary_theme", "未分類"),
        "themes": tags.get("themes", ["未分類"]),
        "account_type": row.get("account_type") or "UNKNOWN",
        "position_side": row.get("position_side") or "UNKNOWN",
        "open_date": row.get("open_date"),
        "close_date": row.get("close_date"),
        "quantity": rounded(row.get("total_close_quantity")),
        "average_open_price": rounded(row.get("weighted_average_open_price")),
        "average_close_price": rounded(row.get("weighted_average_close_price")),
        "gross_pnl": rounded(row.get("gross_pnl")),
        "costs": rounded(row.get("allocated_costs")),
        "net_pnl": rounded(row.get("net_pnl")),
        "return_rate": rounded(
            float(row.get("net_pnl") or 0)
            / (
                float(row.get("weighted_average_open_price") or 0)
                * float(row.get("total_close_quantity") or 0)
            ),
            6,
        )
        if row.get("weighted_average_open_price") and row.get("total_close_quantity")
        else None,
        "holding_days": row.get("holding_days"),
        "open_execution_count": row.get("open_execution_count"),
        "close_execution_count": row.get("close_execution_count"),
    }


def grouped_trades(trades: list[dict], key: str) -> list[dict]:
    from generate_advanced_trade_reports import statistics_for

    groups: dict[str, list[dict]] = {}
    for trade in trades:
        labels = trade.get(key)
        labels = labels if isinstance(labels, list) else [labels]
        for label in labels:
            groups.setdefault(str(label or "未分類"), []).append(trade)
    return [
        {
            **public_metrics({"label": label, **statistics_for(rows)}),
            "is_reference_total": key == "themes",
        }
        for label, rows in sorted(groups.items())
    ]


def load_data_quality(db: sqlite3.Connection, trade_count: int) -> dict:
    def count(query: str) -> int:
        try:
            return int(db.execute(query).fetchone()[0])
        except sqlite3.OperationalError:
            return 0

    return {
        "source_csv_count": count("SELECT COUNT(DISTINCT source_file) FROM executions"),
        "source_record_count": count("SELECT COUNT(*) FROM executions"),
        "valid_record_count": count("SELECT COUNT(*) FROM executions"),
        "closed_episode_count": trade_count,
        "open_episode_count": count(
            "SELECT COUNT(*) FROM trade_episodes WHERE status='OPEN'"
        ),
        "unmatched_execution_count": count(
            "SELECT COUNT(*) FROM unmatched_executions"
        ),
        "unresolved_security_count": count(
            "SELECT COUNT(*) FROM executions "
            "WHERE security_name IS NULL OR trim(security_name)=''"
        ),
        "matching_method": "FIFO / Trade Episode",
        "trade_unit": "建玉がゼロから始まり、再びゼロに戻るまでを1取引とする",
    }


def build_public_payload(
    rows: list[dict],
    updated: str | None = None,
    quality: dict | None = None,
    stock_master: dict[str, dict] | None = None,
) -> dict:
    analysis = build_analysis(rows)
    overall = analysis["overall"]
    master = stock_master or {}
    trades = [public_trade(row, master) for row in rows]
    securities = grouped_trades(trades, "security_code")
    names = {trade["security_code"]: trade["security_name"] for trade in trades}
    for row in securities:
        row["security_code"] = row.pop("label")
        row["security_name"] = names.get(row["security_code"], "銘柄名不明")

    return {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "publication_policy": (
            "投資分析に必要な銘柄・数量・価格・損益は公開し、"
            "口座番号・認証情報・住所などの個人情報のみ除外する"
        ),
        "updated_date": updated or date.today().isoformat(),
        "period": analysis["period"],
        "summary": {
            **public_metrics({"label": "全期間", **overall}),
            "expectancy": rounded(overall["expectancy"]),
            "mean_pnl": rounded(overall["mean_pnl"]),
            "median_pnl": rounded(overall["median_pnl"]),
            "max_win_streak": overall["max_win_streak"],
            "max_loss_streak": overall["max_loss_streak"],
            "closed_trade_count": overall["trade_count"],
        },
        "years": [public_metrics(row) for row in analysis["by_year"]],
        "months": [public_metrics(row) for row in analysis["by_month"]],
        "equity_curve": equity_curve(analysis["equity_curve"]["points"]),
        "holding_periods": [
            public_metrics(row) for row in analysis["holding_periods"]
        ],
        "entry_weekdays": [
            public_metrics(row) for row in analysis["by_entry_weekday"]
        ],
        "exit_weekdays": [
            public_metrics(row) for row in analysis["by_exit_weekday"]
        ],
        "position_sides": [
            public_metrics(row) for row in analysis["by_position_side"]
        ],
        "account_types": [
            public_metrics(row) for row in analysis["by_account_type"]
        ],
        "securities": securities,
        "sectors": grouped_trades(trades, "sector"),
        "primary_themes": grouped_trades(trades, "primary_theme"),
        "theme_tags": grouped_trades(trades, "themes"),
        "trades": trades,
        "concentration": {
            key: rounded(value, 4)
            for key, value in analysis["concentration"].items()
        },
        "data_quality": quality or {
            "source_csv_count": None,
            "source_record_count": None,
            "valid_record_count": None,
            "closed_episode_count": overall["trade_count"],
            "open_episode_count": None,
            "unmatched_execution_count": None,
            "unresolved_security_count": None,
            "matching_method": "FIFO / Trade Episode",
            "trade_unit": "建玉がゼロから始まり、再びゼロに戻るまでを1取引とする",
        },
    }


def assert_no_private_data(payload: object, path: str = "$") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in PRIVATE_KEYS:
                raise ValueError(f"非公開キーを検出しました: {path}.{key}")
            assert_no_private_data(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_no_private_data(value, f"{path}[{index}]")


# Compatibility for callers from schema version 1.
assert_public = assert_no_private_data


def main() -> int:
    parser = argparse.ArgumentParser(description="公開用の実取引分析JSONを生成")
    parser.add_argument(
        "--db", "--database", dest="db", type=Path,
        default=Path("data/database/investment_lab.sqlite"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/generated/public/trade-analysis-summary.json"),
    )
    parser.add_argument(
        "--stock-master", type=Path,
        default=Path("data/masters/stocks.json"),
    )
    parser.add_argument("--updated-date", help="再現可能な生成日（YYYY-MM-DD）")
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error(f"DBが見つかりません: {args.db}")
    try:
        with sqlite3.connect(args.db) as db:
            rows = load_closed_episodes(db)
            quality = load_data_quality(db, len(rows))
        payload = build_public_payload(
            rows,
            args.updated_date,
            quality,
            load_stock_master(args.stock_master),
        )
        assert_no_private_data(payload)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"公開用実取引JSON: {args.output.resolve()}（{len(rows)}取引）")
        return 0
    except (sqlite3.Error, OSError, ValueError) as exc:
        print(f"公開用JSON生成失敗: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
