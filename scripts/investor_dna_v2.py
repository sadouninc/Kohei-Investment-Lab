#!/usr/bin/env python3
"""Investor DNA v2: environment-aware, explainable personal strategy analysis.

This module extends the retrospective #55 engine without replacing it. It keeps
native trading evidence separate from execution constraints, measures lifetime
profit contribution and tail-risk concentration, represents style drift across
versioned environments, and exposes a small interface for daily candidate fit.

No opaque ML is used. Every score is backed by explicit factors and insufficient
evidence remains UNKNOWN / null.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
import sqlite3
from typing import Any

from investor_dna import (
    build_report as build_v1_report,
    confidence_for,
    load_price_history,
    mean,
    median,
    payoff_ratio,
    profit_factor,
)

MODEL_VERSION = "investor-dna-v0.2"
LEVEL_SCORE = {"LOW": 25.0, "MEDIUM": 60.0, "HIGH": 90.0, "UNKNOWN": 50.0}


def pnl(row: dict) -> float:
    return float(row.get("net_pnl") or 0.0)


def direction(row: dict) -> str:
    raw = str(row.get("direction") or row.get("position_side") or row.get("side") or "UNKNOWN").upper()
    if raw in {"LONG", "BUY", "買", "買い"}:
        return "LONG"
    if raw in {"SHORT", "SELL", "売", "売り"}:
        return "SHORT"
    return raw or "UNKNOWN"


def trade_date(row: dict) -> str | None:
    value = row.get("open_date") or row.get("entry_date") or row.get("trade_date")
    return str(value)[:10] if value else None


def theme(row: dict) -> str | None:
    value = row.get("primary_theme") or row.get("theme") or row.get("theme_name")
    return str(value).strip() if value else None


def gross_metrics(rows: list[dict]) -> dict[str, float | None]:
    values = [pnl(row) for row in rows]
    wins = [value for value in values if value > 0]
    losses = [-value for value in values if value < 0]
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    largest_win = max(wins, default=0.0)
    largest_loss = max(losses, default=0.0)
    top3_loss = sum(sorted(losses, reverse=True)[:3])
    return {
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "largest_win": round(largest_win, 2),
        "largest_loss": round(largest_loss, 2),
        "top1_loss_to_gross_profit": None if gross_profit <= 0 else round(largest_loss / gross_profit, 6),
        "top3_loss_to_gross_profit": None if gross_profit <= 0 else round(top3_loss / gross_profit, 6),
        "loss_concentration_ratio": None if gross_loss <= 0 else round(largest_loss / gross_loss, 6),
    }


def side_metrics(rows: list[dict]) -> dict[str, dict[str, float | int | None]]:
    result: dict[str, dict[str, float | int | None]] = {}
    for side in ("LONG", "SHORT"):
        subset = [row for row in rows if direction(row) == side]
        if not subset:
            result[side.lower()] = {"sample_count": 0, "net_pnl": 0.0, "win_rate": None, "profit_factor": None}
            continue
        wins = sum(pnl(row) > 0 for row in subset)
        result[side.lower()] = {
            "sample_count": len(subset),
            "net_pnl": round(sum(pnl(row) for row in subset), 2),
            "win_rate": round(wins / len(subset), 6),
            "profit_factor": None if profit_factor(subset) is None else round(float(profit_factor(subset)), 4),
        }
    return result


def load_environments(path: Path | None) -> dict:
    if not path or not path.is_file():
        return {"schema_version": 1, "environments": []}
    return json.loads(path.read_text(encoding="utf-8"))


def env_for_date(environments: list[dict], value: str | None) -> dict | None:
    if not value:
        return None
    for env in environments:
        start = str(env.get("effective_from") or "0000-00-00")
        end = str(env.get("effective_to") or "9999-12-31")
        if start <= value <= end:
            return env
    return None


def environment_fit(env: dict) -> dict:
    interval = int(env.get("expected_check_interval_minutes") or 180)
    interval_score = max(0.0, min(100.0, 100.0 - max(0, interval - 60) * 0.45))
    factors = {
        "market_open_monitoring": LEVEL_SCORE.get(str(env.get("market_open_monitoring", "UNKNOWN")).upper(), 50.0),
        "morning_execution_availability": LEVEL_SCORE.get(str(env.get("morning_execution_availability", "UNKNOWN")).upper(), 50.0),
        "network_reliability": LEVEL_SCORE.get(str(env.get("network_reliability", "UNKNOWN")).upper(), 50.0),
        "fast_reaction_capability": LEVEL_SCORE.get(str(env.get("fast_reaction_capability", "UNKNOWN")).upper(), 50.0),
        "premarket_analysis_availability": LEVEL_SCORE.get(str(env.get("premarket_analysis_availability", "UNKNOWN")).upper(), 50.0),
        "check_interval_fit": round(interval_score, 2),
    }
    score = (
        factors["market_open_monitoring"] * 0.25
        + factors["morning_execution_availability"] * 0.20
        + factors["network_reliability"] * 0.15
        + factors["fast_reaction_capability"] * 0.20
        + factors["premarket_analysis_availability"] * 0.10
        + factors["check_interval_fit"] * 0.10
    )
    known = sum(str(env.get(key, "UNKNOWN")).upper() != "UNKNOWN" for key in (
        "market_open_monitoring", "morning_execution_availability", "network_reliability",
        "fast_reaction_capability", "premarket_analysis_availability",
    ))
    confidence = round(min(1.0, known / 5.0), 4)
    return {
        "environment_key": env.get("environment_key"),
        "score": round(score, 2),
        "confidence": confidence,
        "factors": factors,
        "explanation": "Operational fit is a transparent heuristic based on monitoring, execution, network, reaction and check-frequency constraints; it is not a skill score.",
    }


def period_metrics(rows: list[dict], env: dict) -> dict:
    subset = [row for row in rows if env_for_date([env], trade_date(row))]
    holds = [float(row.get("holding_days")) for row in subset if row.get("holding_days") is not None]
    wins = sum(pnl(row) > 0 for row in subset)
    sides = side_metrics(subset)
    return {
        "period_key": str(env.get("environment_key")),
        "effective_from": env.get("effective_from"),
        "effective_to": env.get("effective_to"),
        "sample_count": len(subset),
        "win_rate": None if not subset else round(wins / len(subset), 6),
        "profit_factor": None if not subset or profit_factor(subset) is None else round(float(profit_factor(subset)), 4),
        "median_holding_days": median(holds),
        "average_holding_days": mean(holds),
        "long_pnl": sides["long"]["net_pnl"],
        "short_pnl": sides["short"]["net_pnl"],
        "drift_reason": env.get("drift_reason") or "UNKNOWN",
        "confidence": confidence_for(len(subset)) if subset else 0.0,
        "evidence": {
            "expected_check_interval_minutes": env.get("expected_check_interval_minutes"),
            "market_open_monitoring": env.get("market_open_monitoring"),
            "network_reliability": env.get("network_reliability"),
        },
    }


def native_dna(rows: list[dict]) -> dict:
    if not rows:
        return {"sample_count": 0, "strengths": [], "limitations": ["No trades available."]}
    short_rows = [row for row in rows if row.get("holding_days") is not None and float(row.get("holding_days") or 0) <= 5]
    short_wins = sum(pnl(row) > 0 for row in short_rows)
    short_pf = profit_factor(short_rows) if short_rows else None
    by_security = defaultdict(int)
    for row in rows:
        by_security[str(row.get("security_code") or "UNKNOWN")] += 1
    repeated_share = sum(count for count in by_security.values() if count >= 3) / len(rows)
    strengths = [
        {
            "key": "short_horizon_repeatability",
            "score": None if len(short_rows) < 3 else round(min(100.0, (short_wins / len(short_rows)) * 55 + min(float(short_pf or 0), 3.0) / 3.0 * 45), 2),
            "sample_count": len(short_rows),
            "evidence": {"win_rate": None if not short_rows else round(short_wins / len(short_rows), 6), "profit_factor": short_pf},
        },
        {
            "key": "repeated_security_execution",
            "score": round(repeated_share * 100, 2),
            "sample_count": len(rows),
            "evidence": {"share_of_trades_in_repeated_securities": round(repeated_share, 6)},
        },
    ]
    return {
        "sample_count": len(rows),
        "strengths": strengths,
        "limitations": [
            "High-volatility and trend-following fit require aligned market-price features; they are not inferred from P/L alone.",
            "Native DNA measures historical repeatability separately from current execution constraints.",
        ],
    }


def classify_security(base: dict, contribution_share: float | None, risk: dict) -> str:
    if int(base.get("sample_count") or 0) < 3:
        return "RESEARCH"
    if float(base.get("net_pnl") or 0) < 0 or risk.get("tail_risk_warning"):
        return "CHALLENGE"
    if contribution_share is not None and contribution_share >= 0.05 and float(base.get("confidence") or 0) >= 0.4:
        return "HERO"
    if float(base.get("compatibility_score") or 0) >= 70 and float(base.get("confidence") or 0) >= 0.4:
        return "COMPATIBLE"
    return "NORMAL"


def lifetime_contributions(rows: list[dict], base_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("security_code") or "")].append(row)
    base_by_code = {str(row["security_code"]): row for row in base_rows}
    positive_total = sum(max(sum(pnl(row) for row in subset), 0.0) for subset in grouped.values())
    security_rows: list[dict] = []
    for code, subset in grouped.items():
        net = sum(pnl(row) for row in subset)
        contribution = None if net <= 0 or positive_total <= 0 else net / positive_total
        metrics = gross_metrics(subset)
        sides = side_metrics(subset)
        base = base_by_code.get(code, {})
        tail_warning = bool(
            len(subset) >= 3 and (
                (metrics["top1_loss_to_gross_profit"] is not None and float(metrics["top1_loss_to_gross_profit"]) >= 0.5)
                or (base.get("profit_factor") is not None and float(base["profit_factor"]) < 1.0 and float(base.get("win_rate") or 0) >= 0.6)
            )
        )
        risk = {"tail_risk_warning": tail_warning}
        security_rows.append({
            "security_code": code,
            "security_name": base.get("security_name") or next((r.get("security_name") for r in subset if r.get("security_name")), "銘柄名不明"),
            "realized_pnl": round(net, 2),
            "profit_share": None if contribution is None else round(contribution, 6),
            "trade_count": len(subset),
            "win_rate": base.get("win_rate"),
            "profit_factor": base.get("profit_factor"),
            "payoff_ratio": base.get("payoff_ratio"),
            **metrics,
            "long_pnl": sides["long"]["net_pnl"],
            "short_pnl": sides["short"]["net_pnl"],
            "classification": classify_security(base, contribution, risk),
            "confidence": base.get("confidence") or confidence_for(len(subset)),
            "tail_risk_warning": tail_warning,
        })
    security_rows.sort(key=lambda row: row["realized_pnl"], reverse=True)

    themes: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if theme(row):
            themes[str(theme(row))].append(row)
    theme_rows = []
    positive_theme_total = sum(max(sum(pnl(r) for r in subset), 0.0) for subset in themes.values())
    for key, subset in themes.items():
        net = sum(pnl(row) for row in subset)
        theme_rows.append({
            "theme_key": key,
            "realized_pnl": round(net, 2),
            "profit_share": None if net <= 0 or positive_theme_total <= 0 else round(net / positive_theme_total, 6),
            "trade_count": len(subset),
            "confidence": confidence_for(len(subset)),
        })
    theme_rows.sort(key=lambda row: row["realized_pnl"], reverse=True)
    return security_rows, theme_rows


def risk_patterns(security_rows: list[dict]) -> list[dict]:
    alerts = []
    for row in security_rows:
        if not row.get("tail_risk_warning"):
            continue
        ratio = row.get("top1_loss_to_gross_profit")
        severity = "CRITICAL" if ratio is not None and float(ratio) >= 0.8 else "WARNING"
        alerts.append({
            "security_code": row["security_code"],
            "security_name": row["security_name"],
            "pattern_code": "TAIL_LOSS_DESTROYS_SMALL_WINS",
            "severity": severity,
            "confidence": row["confidence"],
            "evidence": {
                "win_rate": row.get("win_rate"),
                "profit_factor": row.get("profit_factor"),
                "largest_loss": row.get("largest_loss"),
                "gross_profit": row.get("gross_profit"),
                "top1_loss_to_gross_profit": ratio,
                "long_pnl": row.get("long_pnl"),
                "short_pnl": row.get("short_pnl"),
            },
            "explanation": "High win frequency is being offset by concentrated tail loss. Review position size, stop policy and long/short asymmetry rather than treating win rate alone as edge.",
        })
    return alerts


def daily_fit(candidate: dict, dna_lookup: dict[str, dict], current_env: dict | None) -> dict:
    code = str(candidate.get("security_code") or "")
    dna = dna_lookup.get(code, {})
    market_score = candidate.get("market_score")
    capital_fit = candidate.get("capital_fit_score")
    dna_score = dna.get("compatibility_score")
    env_score = current_env.get("score") if current_env else None
    execution_difficulty = float(candidate.get("execution_difficulty") or 50.0)
    weighted: list[tuple[float, float]] = []
    if market_score is not None:
        weighted.append((float(market_score), 0.40))
    if dna_score is not None:
        weighted.append((float(dna_score), 0.35))
    if env_score is not None:
        weighted.append((float(env_score), 0.25))
    if capital_fit is not None:
        weighted.append((float(capital_fit), 0.10))
    if not weighted:
        final = None
    else:
        total_weight = sum(weight for _, weight in weighted)
        raw = sum(value * weight for value, weight in weighted) / total_weight
        final = max(0.0, min(100.0, raw - max(0.0, execution_difficulty - 50.0) * 0.20))
    return {
        "security_code": code,
        "market_score": market_score,
        "dna_fit_score": dna_score,
        "environment_fit_score": env_score,
        "capital_fit_score": capital_fit,
        "execution_difficulty": execution_difficulty,
        "final_personal_fit": None if final is None else round(final, 2),
        "confidence": dna.get("confidence", 0.0),
        "factors": {
            "weights": {"market": 0.40, "dna": 0.35, "environment": 0.25, "capital_optional": 0.10},
            "execution_penalty_above_50": 0.20,
        },
    }


def build_report(trade_payload: dict, prices: dict[str, list[dict]] | None, env_payload: dict, candidates: list[dict] | None = None) -> dict:
    base = build_v1_report(trade_payload, prices or {})
    base["schema_version"] = 2
    base["model_version"] = MODEL_VERSION
    rows = list(trade_payload.get("trades") or [])
    environments = list(env_payload.get("environments") or [])
    env_assessments = [environment_fit(env) for env in environments]
    style_periods = [period_metrics(rows, env) for env in environments]
    contributions, theme_contributions = lifetime_contributions(rows, base["securities"])
    alerts = risk_patterns(contributions)
    current_env = None
    current_defs = [env for env in environments if not env.get("effective_to")]
    if current_defs:
        current_env = environment_fit(current_defs[-1])
    dna_lookup = {str(row["security_code"]): row for row in base["securities"]}
    daily = [daily_fit(row, dna_lookup, current_env) for row in (candidates or [])]
    daily.sort(key=lambda row: row["final_personal_fit"] if row["final_personal_fit"] is not None else -1, reverse=True)
    base.update({
        "native_dna": native_dna(rows),
        "environment_profiles": environments,
        "environment_fit_assessments": env_assessments,
        "current_environment_fit": current_env,
        "style_periods": style_periods,
        "security_lifetime_contributions": contributions,
        "theme_lifetime_contributions": theme_contributions,
        "risk_patterns": alerts,
        "daily_dna_fit": daily,
        "v2_principle": "Separate proven native edge from the environment in which that edge can currently be executed.",
    })
    return base


def persist_v2(report: dict, db_path: Path) -> None:
    with sqlite3.connect(db_path) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"investor_environment_profiles", "security_lifetime_contributions", "risk_pattern_assessments"}
        if not required.issubset(tables):
            raise RuntimeError("Investor DNA v2 migration is not applied to history.db")
        evaluated_at = report["generated_at"]
        for env in report.get("environment_profiles", []):
            db.execute(
                "INSERT OR REPLACE INTO investor_environment_profiles(environment_key,effective_from,effective_to,expected_check_interval_minutes,market_open_monitoring,morning_execution_availability,network_reliability,fast_reaction_capability,premarket_analysis_availability,work_constraint_level,notes,source_type,model_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (env["environment_key"], env["effective_from"], env.get("effective_to"), env.get("expected_check_interval_minutes"), env.get("market_open_monitoring", "UNKNOWN"), env.get("morning_execution_availability", "UNKNOWN"), env.get("network_reliability", "UNKNOWN"), env.get("fast_reaction_capability", "UNKNOWN"), env.get("premarket_analysis_availability", "UNKNOWN"), env.get("work_constraint_level", "UNKNOWN"), env.get("notes"), "USER_REPORTED", report["model_version"]),
            )
        for row in report.get("style_periods", []):
            db.execute(
                "INSERT OR REPLACE INTO investor_style_periods(period_key,effective_from,effective_to,sample_count,win_rate,profit_factor,median_holding_days,average_holding_days,long_pnl,short_pnl,drift_reason,confidence,evidence_json,model_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["period_key"], row["effective_from"], row.get("effective_to"), row["sample_count"], row.get("win_rate"), row.get("profit_factor"), row.get("median_holding_days"), row.get("average_holding_days"), row.get("long_pnl"), row.get("short_pnl"), row.get("drift_reason", "UNKNOWN"), row.get("confidence", 0), json.dumps(row.get("evidence") or {}, ensure_ascii=False), report["model_version"]),
            )
        for row in report.get("environment_fit_assessments", []):
            db.execute(
                "INSERT OR REPLACE INTO environment_fit_assessments(environment_key,evaluated_at,environment_fit_score,confidence,factor_json,explanation,model_version) VALUES (?,?,?,?,?,?,?)",
                (row["environment_key"], evaluated_at, row["score"], row["confidence"], json.dumps(row["factors"], ensure_ascii=False), row["explanation"], report["model_version"]),
            )
        for row in report.get("security_lifetime_contributions", []):
            db.execute(
                "INSERT OR REPLACE INTO security_lifetime_contributions(security_code,evaluated_at,realized_pnl,profit_share,trade_count,win_rate,profit_factor,payoff_ratio,largest_win,largest_loss,gross_profit,gross_loss,top1_loss_to_gross_profit,loss_concentration_ratio,long_pnl,short_pnl,classification,confidence,evidence_json,model_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["security_code"], evaluated_at, row["realized_pnl"], row.get("profit_share"), row["trade_count"], row.get("win_rate"), row.get("profit_factor"), row.get("payoff_ratio"), row.get("largest_win"), row.get("largest_loss"), row.get("gross_profit"), row.get("gross_loss"), row.get("top1_loss_to_gross_profit"), row.get("loss_concentration_ratio"), row.get("long_pnl"), row.get("short_pnl"), row["classification"], row["confidence"], json.dumps({"tail_risk_warning": row.get("tail_risk_warning")}, ensure_ascii=False), report["model_version"]),
            )
        for row in report.get("theme_lifetime_contributions", []):
            db.execute(
                "INSERT OR REPLACE INTO theme_lifetime_contributions(theme_key,evaluated_at,realized_pnl,profit_share,trade_count,confidence,evidence_json,model_version) VALUES (?,?,?,?,?,?,?,?)",
                (row["theme_key"], evaluated_at, row["realized_pnl"], row.get("profit_share"), row["trade_count"], row["confidence"], "{}", report["model_version"]),
            )
        db.execute("DELETE FROM risk_pattern_assessments WHERE evaluated_at=? AND model_version=?", (evaluated_at, report["model_version"]))
        for row in report.get("risk_patterns", []):
            db.execute(
                "INSERT INTO risk_pattern_assessments(security_code,evaluated_at,pattern_code,severity,confidence,evidence_json,explanation,model_version) VALUES (?,?,?,?,?,?,?,?)",
                (row.get("security_code"), evaluated_at, row["pattern_code"], row["severity"], row["confidence"], json.dumps(row["evidence"], ensure_ascii=False), row["explanation"], report["model_version"]),
            )
        for row in report.get("daily_dna_fit", []):
            db.execute(
                "INSERT OR REPLACE INTO daily_dna_fit_assessments(trade_date,security_code,evaluated_at,market_score,dna_fit_score,environment_fit_score,capital_fit_score,execution_difficulty,final_personal_fit,confidence,factor_json,model_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (evaluated_at[:10], row["security_code"], evaluated_at, row.get("market_score"), row.get("dna_fit_score"), row.get("environment_fit_score"), row.get("capital_fit_score"), row.get("execution_difficulty"), row.get("final_personal_fit"), row.get("confidence", 0), json.dumps(row.get("factors") or {}, ensure_ascii=False), report["model_version"]),
            )
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Investor DNA v2 report")
    parser.add_argument("--trade-json", type=Path, default=Path("data/generated/public/trade-analysis-summary.json"))
    parser.add_argument("--prices-json", type=Path)
    parser.add_argument("--environment-json", type=Path, default=Path("data/config/investor-environments.json"))
    parser.add_argument("--candidates-json", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/generated/public/investor-dna.json"))
    parser.add_argument("--history-db", type=Path)
    args = parser.parse_args()
    trade_payload = json.loads(args.trade_json.read_text(encoding="utf-8"))
    candidates: list[dict] | None = None
    if args.candidates_json and args.candidates_json.is_file():
        candidate_payload = json.loads(args.candidates_json.read_text(encoding="utf-8"))
        candidates = candidate_payload if isinstance(candidate_payload, list) else list(candidate_payload.get("candidates") or [])
    report = build_report(trade_payload, load_price_history(args.prices_json), load_environments(args.environment_json), candidates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.history_db:
        persist_v2(report, args.history_db)
    print(f"Investor DNA v2 report: {args.output}")


if __name__ == "__main__":
    main()
