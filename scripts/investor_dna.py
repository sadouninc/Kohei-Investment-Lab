#!/usr/bin/env python3
"""Explainable retrospective Investor DNA analysis.

The MVP intentionally avoids opaque ML. It combines realized trade episodes with
optional post-exit price history and emits evidence-backed compatibility causes.
If the evidence is insufficient, the cause remains UNKNOWN.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime
import json
import math
from pathlib import Path
import sqlite3
import statistics
from typing import Iterable

MODEL_VERSION = "investor-dna-v0.1"
HORIZONS = (1, 3, 5, 10, 20)
MIN_CAUSE_SAMPLE = 3


def median(values: Iterable[float]) -> float | None:
    rows = [float(v) for v in values if v is not None]
    return statistics.median(rows) if rows else None


def mean(values: Iterable[float]) -> float | None:
    rows = [float(v) for v in values if v is not None]
    return statistics.fmean(rows) if rows else None


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def profit_factor(trades: list[dict]) -> float | None:
    wins = sum(max(float(row.get("net_pnl") or 0), 0.0) for row in trades)
    losses = -sum(min(float(row.get("net_pnl") or 0), 0.0) for row in trades)
    if losses == 0:
        return None if wins == 0 else 99.0
    return wins / losses


def payoff_ratio(trades: list[dict]) -> float | None:
    wins = [float(row["net_pnl"]) for row in trades if float(row.get("net_pnl") or 0) > 0]
    losses = [-float(row["net_pnl"]) for row in trades if float(row.get("net_pnl") or 0) < 0]
    if not wins or not losses:
        return None
    return statistics.fmean(wins) / statistics.fmean(losses)


def confidence_for(sample_count: int, price_sample_count: int = 0) -> float:
    trade_conf = min(1.0, math.sqrt(sample_count / 20.0))
    if price_sample_count:
        trade_conf = (trade_conf + min(1.0, math.sqrt(price_sample_count / 12.0))) / 2
    return round(trade_conf, 4)


def load_price_history(path: Path | None) -> dict[str, list[dict]]:
    if not path or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, list[dict]] = {}
    for code, rows in payload.items():
        result[str(code)] = sorted(
            ({"date": str(row["date"]), "close": float(row["close"])} for row in rows),
            key=lambda row: row["date"],
        )
    return result


def post_exit_observations(trade: dict, prices: list[dict]) -> dict | None:
    close_date = trade.get("close_date")
    close_price = trade.get("average_close_price")
    if not close_date or not close_price or not prices:
        return None
    future = [row for row in prices if row["date"] > str(close_date)]
    if not future:
        return None
    start = float(close_price)
    returns: dict[str, float | None] = {}
    for horizon in HORIZONS:
        if len(future) >= horizon:
            returns[f"return_{horizon}d"] = future[horizon - 1]["close"] / start - 1.0
        else:
            returns[f"return_{horizon}d"] = None
    window = future[:20]
    peak_index = max(range(len(window)), key=lambda idx: window[idx]["close"])
    returns["days_to_peak"] = peak_index + 1
    returns["peak_return_20d"] = window[peak_index]["close"] / start - 1.0
    return returns


def realized_fit_score(win_rate: float, pf: float | None, avg_return: float | None) -> dict[str, float]:
    win_score = clamp(win_rate * 100)
    pf_value = 2.0 if pf is None else min(float(pf), 2.0)
    pf_score = clamp(pf_value / 2.0 * 100)
    return_score = 50.0 if avg_return is None else clamp(50 + avg_return * 1000)
    total = win_score * 0.4 + pf_score * 0.4 + return_score * 0.2
    return {
        "historical_win_fit": round(win_score, 2),
        "profit_factor_fit": round(pf_score, 2),
        "realized_return_fit": round(return_score, 2),
        "score": round(total, 2),
    }


def diagnose(
    trades: list[dict],
    investor_median_holding: float | None,
    post_exit: list[dict],
) -> tuple[str, str, str | None, str | None, list[dict]]:
    sample = len(trades)
    holds = [float(row.get("holding_days") or 0) for row in trades if row.get("holding_days") is not None]
    sec_median = median(holds)
    pf = profit_factor(trades)
    win_rate = sum(float(row.get("net_pnl") or 0) > 0 for row in trades) / sample if sample else 0
    factors: list[dict] = []

    post5 = median(row.get("return_5d") for row in post_exit)
    days_to_peak = median(row.get("days_to_peak") for row in post_exit)
    factors.append({"factor_key": "sample_count", "evidence_value": sample})
    factors.append({"factor_key": "median_holding_days", "evidence_value": sec_median})
    factors.append({"factor_key": "profit_factor", "evidence_value": pf})
    if post5 is not None:
        factors.append({"factor_key": "median_post_exit_return_5d", "evidence_value": post5})
    if days_to_peak is not None:
        factors.append({"factor_key": "median_days_to_post_exit_peak", "evidence_value": days_to_peak})

    if sample < MIN_CAUSE_SAMPLE:
        return "UNKNOWN", "サンプル不足のため原因を推測しません。", None, None, factors

    if post5 is not None and post5 >= 0.03:
        if days_to_peak is not None and sec_median is not None and days_to_peak > max(3, sec_median * 0.75):
            return (
                "HOLDING_PERIOD_TOO_SHORT",
                f"売却後5営業日の中央値が{post5:.1%}で、売却後ピークまで中央値{days_to_peak:.1f}営業日あります。利益確定が上昇波より早い可能性があります。",
                "TREND_LONGER_HORIZON",
                "10-20D",
                factors,
            )
        return (
            "EARLY_PROFIT_TAKING",
            f"売却後5営業日の中央値が{post5:.1%}上昇しており、早売りを検証する価値があります。",
            "TREND",
            "5-20D",
            factors,
        )

    if pf is not None and pf < 1.0 and win_rate >= 0.6:
        return (
            "LATE_STOP",
            "勝率は高い一方でPFが1未満です。少数の大きな損失が利益を相殺している可能性があります。",
            "RESEARCH",
            None,
            factors,
        )

    if investor_median_holding and sec_median:
        if sec_median > investor_median_holding * 2 and pf is not None and pf < 1.2:
            return (
                "HOLDING_PERIOD_TOO_LONG",
                "この銘柄の実際の保有期間が通常より大幅に長く、資金拘束に対して成績が弱い傾向です。",
                "CORE_REVIEW",
                "LONGER_TERM",
                factors,
            )

    return "UNKNOWN", "現時点の実取引だけでは再現可能な原因を特定できません。市場価格履歴を追加して周期・売却後推移を検証します。", None, None, factors


def build_report(trade_payload: dict, prices: dict[str, list[dict]] | None = None) -> dict:
    trades = list(trade_payload.get("trades") or [])
    prices = prices or {}
    all_holds = [float(row["holding_days"]) for row in trades if row.get("holding_days") is not None]
    investor_median = median(all_holds)
    investor_average = mean(all_holds)
    overall_pf = profit_factor(trades)
    overall_win_rate = sum(float(row.get("net_pnl") or 0) > 0 for row in trades) / len(trades) if trades else 0

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in trades:
        grouped[str(row.get("security_code") or "")].append(row)

    securities = []
    for code, rows in grouped.items():
        name = next((row.get("security_name") for row in rows if row.get("security_name")), "銘柄名不明")
        post_exit = [
            obs for row in rows
            if (obs := post_exit_observations(row, prices.get(code, []))) is not None
        ]
        wins = sum(float(row.get("net_pnl") or 0) > 0 for row in rows)
        sec_pf = profit_factor(rows)
        sec_payoff = payoff_ratio(rows)
        avg_return = mean(row.get("return_rate") for row in rows)
        fit = realized_fit_score(wins / len(rows), sec_pf, avg_return)
        cause, explanation, role, horizon, factors = diagnose(rows, investor_median, post_exit)
        post = {
            f"median_post_exit_return_{h}d": median(row.get(f"return_{h}d") for row in post_exit)
            for h in HORIZONS
        }
        post["median_days_to_post_exit_peak"] = median(row.get("days_to_peak") for row in post_exit)
        confidence = confidence_for(len(rows), len(post_exit))
        securities.append({
            "security_code": code,
            "security_name": name,
            "sample_count": len(rows),
            "win_rate": round(wins / len(rows), 6),
            "profit_factor": None if sec_pf is None else round(sec_pf, 4),
            "payoff_ratio": None if sec_payoff is None else round(sec_payoff, 4),
            "average_holding_days": round(mean(row.get("holding_days") for row in rows) or 0, 2),
            "median_holding_days": round(median(row.get("holding_days") for row in rows) or 0, 2),
            "average_return_rate": None if avg_return is None else round(avg_return, 6),
            "net_pnl": round(sum(float(row.get("net_pnl") or 0) for row in rows), 2),
            "compatibility_score": fit["score"],
            "compatibility_factors": {k: v for k, v in fit.items() if k != "score"},
            "confidence": confidence,
            "primary_mismatch_code": cause,
            "explanation": explanation,
            "recommended_portfolio_role": role,
            "recommended_horizon": horizon,
            "post_exit_sample_count": len(post_exit),
            **post,
            "evidence": factors,
        })

    securities.sort(key=lambda row: (row["compatibility_score"] * row["confidence"], row["sample_count"]), reverse=True)
    return {
        "schema_version": 1,
        "model_version": MODEL_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_updated_date": trade_payload.get("updated_date"),
        "principle": "Compatibility is an unresolved pattern to explain, not a permanent label.",
        "investor_profile": {
            "sample_count": len(trades),
            "win_rate": round(overall_win_rate, 6),
            "profit_factor": None if overall_pf is None else round(overall_pf, 4),
            "median_holding_days": investor_median,
            "average_holding_days": None if investor_average is None else round(investor_average, 2),
        },
        "price_followup_available": bool(prices),
        "securities": securities,
        "limitations": [
            "MFE/MAE and price-cycle mismatch require security price history in analysis.db or --prices-json.",
            "UNKNOWN means evidence is insufficient; the engine does not invent a cause.",
            "Compatibility changes the suggested strategy/horizon and is not an automatic buy/sell veto.",
        ],
    }


def persist_report(report: dict, db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        required = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "compatibility_assessments" not in required:
            raise RuntimeError("Investor DNA migration is not applied to history.db")
        evaluated_at = report["generated_at"]
        profile = report["investor_profile"]
        db.execute(
            "INSERT OR REPLACE INTO investor_dna_profiles(evaluated_at,sample_count,win_rate,profit_factor,median_holding_days,average_holding_days,model_version,source_reference) VALUES (?,?,?,?,?,?,?,?)",
            (evaluated_at, profile["sample_count"], profile["win_rate"], profile["profit_factor"], profile["median_holding_days"], profile["average_holding_days"], report["model_version"], report.get("source_updated_date")),
        )
        for row in report["securities"]:
            db.execute(
                "INSERT OR REPLACE INTO security_behavior_profiles(security_code,evaluated_at,sample_count,win_rate,profit_factor,payoff_ratio,median_holding_days,average_holding_days,average_return_rate,median_post_exit_return_1d,median_post_exit_return_3d,median_post_exit_return_5d,median_post_exit_return_10d,median_post_exit_return_20d,median_days_to_post_exit_peak,model_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["security_code"], evaluated_at, row["sample_count"], row["win_rate"], row["profit_factor"], row["payoff_ratio"], row["median_holding_days"], row["average_holding_days"], row["average_return_rate"], row["median_post_exit_return_1d"], row["median_post_exit_return_3d"], row["median_post_exit_return_5d"], row["median_post_exit_return_10d"], row["median_post_exit_return_20d"], row["median_days_to_post_exit_peak"], report["model_version"]),
            )
            cur = db.execute(
                "INSERT OR REPLACE INTO compatibility_assessments(security_code,evaluated_at,sample_count,compatibility_score,confidence,primary_mismatch_code,recommended_portfolio_role,recommended_horizon,explanation,model_version) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (row["security_code"], evaluated_at, row["sample_count"], row["compatibility_score"], row["confidence"], row["primary_mismatch_code"], row["recommended_portfolio_role"], row["recommended_horizon"], row["explanation"], report["model_version"]),
            )
            assessment_id = cur.lastrowid or db.execute("SELECT id FROM compatibility_assessments WHERE security_code=? AND evaluated_at=? AND model_version=?", (row["security_code"], evaluated_at, report["model_version"])).fetchone()[0]
            db.execute("DELETE FROM compatibility_factors WHERE assessment_id=?", (assessment_id,))
            for key, score in row["compatibility_factors"].items():
                db.execute("INSERT INTO compatibility_factors(assessment_id,factor_key,factor_score) VALUES (?,?,?)", (assessment_id, key, score))
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate explainable Investor DNA report")
    parser.add_argument("--trade-json", type=Path, default=Path("data/generated/public/trade-analysis-summary.json"))
    parser.add_argument("--prices-json", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/generated/public/investor-dna.json"))
    parser.add_argument("--history-db", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.trade_json.read_text(encoding="utf-8"))
    report = build_report(payload, load_price_history(args.prices_json))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.history_db:
        persist_report(report, args.history_db)
    print(f"Investor DNA report: {args.output}")


if __name__ == "__main__":
    main()
