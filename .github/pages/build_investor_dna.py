from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "data" / "generated" / "public" / "investor-dna.json"
SITE = ROOT / "site-src" / "research" / "investor-dna"


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def num(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def yen(value: float | None) -> str:
    return "—" if value is None else f"{value:,.0f}円"


def esc(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    if not REPORT.is_file():
        return
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    profile = payload["investor_profile"]
    rows = payload["securities"]
    strong = [row for row in rows if row["sample_count"] >= 3][:10]
    hard = sorted(
        (row for row in rows if row["sample_count"] >= 3),
        key=lambda row: (row["compatibility_score"] * row["confidence"], -row["sample_count"]),
    )[:10]

    page = """---
layout: site
title: Investor DNA
description: 自分の勝ち方と現在の実行環境を分離し、再現可能な投資エッジを説明可能に分析する
permalink: /research/investor-dna/
---

<p class="breadcrumb"><a href="{{ '/' | relative_url }}">Home</a> / Research / Investor DNA</p>

# Investor DNA Engine

「相性が悪い」を固定ラベルにせず、**まだ解明できていない勝ちパターン**として原因を分解します。

> Market opportunity × Native Investor DNA × Current Environment × Capital feasibility

"""
    page += (
        '<div class="metric-grid">'
        f'<div class="metric-card"><span>Trade Episodes</span><strong>{profile["sample_count"]}</strong></div>'
        f'<div class="metric-card"><span>Win Rate</span><strong>{pct(profile["win_rate"])}</strong></div>'
        f'<div class="metric-card"><span>PF</span><strong>{num(profile["profit_factor"], 2)}</strong></div>'
        f'<div class="metric-card"><span>Median Hold</span><strong>{num(profile["median_holding_days"])}日</strong></div>'
        '</div>\n\n'
    )

    native = payload.get("native_dna") or {}
    if native:
        page += "## Native DNA — 本来の強み\n\n"
        page += "現在の仕事・通信環境とは分離して、実取引で再現した能力だけを表示します。\n\n"
        page += "| 特性 | Score | Sample | 根拠 |\n|---|---:|---:|---|\n"
        for item in native.get("strengths", []):
            evidence = ", ".join(f"{k}={v}" for k, v in (item.get("evidence") or {}).items())
            page += f'| {esc(item["key"])} | {num(item.get("score"))} | {item.get("sample_count", 0)} | {esc(evidence)} |\n'
        page += "\n"
        for item in native.get("limitations", []):
            page += f'- {esc(item)}\n'
        page += "\n"

    current_env = payload.get("current_environment_fit")
    if current_env:
        page += "## Current Environment Fit — 今、実行できる強み\n\n"
        page += (
            '<div class="metric-grid">'
            f'<div class="metric-card"><span>Environment Fit</span><strong>{num(current_env.get("score"))} / 100</strong></div>'
            f'<div class="metric-card"><span>Confidence</span><strong>{num(current_env.get("confidence"), 2)}</strong></div>'
            '</div>\n\n'
        )
        page += "| Factor | Score |\n|---|---:|\n"
        for key, value in current_env.get("factors", {}).items():
            page += f'| {esc(key)} | {num(value)} |\n'
        page += f'\n{esc(current_env.get("explanation") or "")}\n\n'

    periods = payload.get("style_periods") or []
    if periods:
        page += "## Style Drift — スタイル変化と環境変化\n\n"
        page += "| Period | Sample | Win Rate | PF | Median Hold | LONG P/L | SHORT P/L | Drift Reason |\n|---|---:|---:|---:|---:|---:|---:|---|\n"
        for row in periods:
            end = row.get("effective_to") or "current"
            page += (
                f'| {esc(row.get("effective_from"))} → {esc(end)} | {row.get("sample_count", 0)} | '
                f'{pct(row.get("win_rate"))} | {num(row.get("profit_factor"), 2)} | {num(row.get("median_holding_days"))}日 | '
                f'{yen(row.get("long_pnl"))} | {yen(row.get("short_pnl"))} | {esc(row.get("drift_reason"))} |\n'
            )
        page += "\n"

    contributions = payload.get("security_lifetime_contributions") or []
    if contributions:
        page += "## Lifetime Profit Contribution — 資産形成への寄与\n\n"
        page += "| Class | 銘柄 | 実現損益 | Positive Contribution | Trades | 勝率 | PF | 最大損失 |\n|---|---|---:|---:|---:|---:|---:|---:|\n"
        for row in contributions[:20]:
            page += (
                f'| **{esc(row.get("classification"))}** | {esc(row.get("security_name"))} ({esc(row.get("security_code"))}) | '
                f'{yen(row.get("realized_pnl"))} | {pct(row.get("profit_share"))} | {row.get("trade_count", 0)} | '
                f'{pct(row.get("win_rate"))} | {num(row.get("profit_factor"), 2)} | {yen(-float(row.get("largest_loss") or 0))} |\n'
            )
        page += "\n`HERO` は資産形成への寄与と再現性、`CHALLENGE` は改善余地またはテールリスクを表す研究ラベルです。売買許可ではありません。\n\n"

    alerts = payload.get("risk_patterns") or []
    if alerts:
        page += "## Danger Patterns — 勝率では見えない大損パターン\n\n"
        for alert in alerts:
            ev = alert.get("evidence") or {}
            page += f'### {esc(alert.get("security_name"))} — {esc(alert.get("severity"))}\n\n'
            page += f'- Pattern: `{esc(alert.get("pattern_code"))}`\n'
            page += f'- Win Rate: **{pct(ev.get("win_rate"))}** / PF: **{num(ev.get("profit_factor"), 2)}**\n'
            page += f'- Largest Loss: **{yen(-float(ev.get("largest_loss") or 0))}** / Gross Profit: **{yen(ev.get("gross_profit"))}**\n'
            page += f'- LONG P/L: **{yen(ev.get("long_pnl"))}** / SHORT P/L: **{yen(ev.get("short_pnl"))}**\n'
            page += f'- {esc(alert.get("explanation"))}\n\n'

    page += "## 相性が高い銘柄（実績ベース）\n\n"
    page += "| 銘柄 | 取引数 | Score | Confidence | 勝率 | PF | 主な診断 |\n|---|---:|---:|---:|---:|---:|---|\n"
    for row in strong:
        page += (
            f'| {esc(row["security_name"])} ({esc(row["security_code"])}) | {row["sample_count"]} | '
            f'{row["compatibility_score"]:.1f} | {row["confidence"]:.2f} | {pct(row["win_rate"])} | '
            f'{num(row["profit_factor"], 2)} | {esc(row["primary_mismatch_code"])} |\n'
        )

    page += "\n## 利益化が難しい銘柄候補\n\n"
    page += "| 銘柄 | 取引数 | Score | Confidence | 保有中央値 | 原因 |\n|---|---:|---:|---:|---:|---|\n"
    for row in hard:
        page += (
            f'| {esc(row["security_name"])} ({esc(row["security_code"])}) | {row["sample_count"]} | '
            f'{row["compatibility_score"]:.1f} | {row["confidence"]:.2f} | '
            f'{num(row["median_holding_days"])}日 | {esc(row["primary_mismatch_code"])} |\n'
        )

    daily = payload.get("daily_dna_fit") or []
    if daily:
        page += "\n## Daily DNA Fit — Candidate Engine 接続口\n\n"
        page += "| 銘柄 | Market | DNA | Environment | Capital | Difficulty | Personal Fit |\n|---|---:|---:|---:|---:|---:|---:|\n"
        for row in daily[:10]:
            page += (
                f'| {esc(row.get("security_code"))} | {num(row.get("market_score"))} | {num(row.get("dna_fit_score"))} | '
                f'{num(row.get("environment_fit_score"))} | {num(row.get("capital_fit_score"))} | '
                f'{num(row.get("execution_difficulty"))} | **{num(row.get("final_personal_fit"))}** |\n'
            )

    page += "\n## 銘柄別診断\n\n"
    for row in rows:
        if row["sample_count"] < 3:
            continue
        page += f'### {esc(row["security_name"])} ({esc(row["security_code"])})\n\n'
        page += (
            f'- Compatibility Score: **{row["compatibility_score"]:.1f} / 100**\n'
            f'- Confidence: **{row["confidence"]:.2f}** / Sample: **{row["sample_count"]}**\n'
            f'- Holding: median **{num(row["median_holding_days"])}日** / average **{num(row["average_holding_days"])}日**\n'
            f'- Win Rate: **{pct(row["win_rate"])}** / PF: **{num(row["profit_factor"], 2)}**\n'
            f'- Primary cause: `{esc(row["primary_mismatch_code"])}`\n'
            f'- Diagnosis: {esc(row["explanation"])}\n'
        )
        if row.get("median_post_exit_return_5d") is not None:
            page += f'- 売却後5営業日中央値: **{pct(row["median_post_exit_return_5d"])}**\n'
        if row.get("recommended_portfolio_role"):
            page += f'- Strategy experiment: **{esc(row["recommended_portfolio_role"])} / {esc(row.get("recommended_horizon") or "—")}**\n'
        page += "\n"

    page += "## データ品質と限界\n\n"
    page += f'- Market price follow-up: **{"available" if payload["price_followup_available"] else "not yet available"}**\n'
    for item in payload.get("limitations", []):
        page += f'- {esc(item)}\n'
    page += "\n低サンプルや価格履歴不足では `UNKNOWN` を返し、原因を推測で埋めません。環境スコアは能力評価ではなく、現在その能力を実行できる条件の評価です。\n"

    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.md").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
