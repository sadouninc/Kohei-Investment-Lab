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
description: 自分が銘柄ごとに利益を出せる・出せない理由を、実取引から説明可能に分析する
permalink: /research/investor-dna/
---

<p class="breadcrumb"><a href="{{ '/' | relative_url }}">Home</a> / Research / Investor DNA</p>

# Investor DNA Engine

「相性が悪い」を固定ラベルにせず、**まだ解明できていない勝ちパターン**として原因を分解します。

> Poor result → Cause decomposition → Measured mismatch → Testable rule → Re-test

"""
    page += (
        '<div class="metric-grid">'
        f'<div class="metric-card"><span>Trade Episodes</span><strong>{profile["sample_count"]}</strong></div>'
        f'<div class="metric-card"><span>Win Rate</span><strong>{pct(profile["win_rate"])}</strong></div>'
        f'<div class="metric-card"><span>PF</span><strong>{num(profile["profit_factor"], 2)}</strong></div>'
        f'<div class="metric-card"><span>Median Hold</span><strong>{num(profile["median_holding_days"])}日</strong></div>'
        '</div>\n\n'
    )
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
    page += "\n低サンプルや価格履歴不足では `UNKNOWN` を返し、原因を推測で埋めません。\n"

    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.md").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
