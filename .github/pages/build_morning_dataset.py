from __future__ import annotations

import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "data" / "generated" / "public" / "morning-dataset.json"
SITE = ROOT / "site-src" / "research" / "morning-dataset"


def esc(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.1%}" if 0 <= value <= 1 else f"{value:,.2f}"
    return esc(value)


def build_page(payload: dict) -> str:
    quality = payload.get("data_quality") or {}
    sources = payload.get("source_status") or []
    warnings = payload.get("warnings") or []

    page = """---
layout: site
title: Morning Dataset Diagnostics
description: AI判断前にGitHub Actions / Pythonが準備したFact・Featureの状態を確認する
permalink: /research/morning-dataset/
---

<p class="breadcrumb"><a href="{{ '/' | relative_url }}">Home</a> / Research / Morning Dataset</p>

# Morning Dataset Diagnostics

このページは **AIが判断を始める前の入力データ** を確認するためのDiagnosticsです。
ここでは銘柄の推奨・優先順位付け・売買判断は行いません。

> Data / Feature preparation → Morning Dataset → AI reasoning → Human decision

"""
    page += (
        '<div class="metric-grid">'
        f'<div class="metric-card"><span>Schema</span><strong>{esc(payload.get("schema_version", "—"))}</strong></div>'
        f'<div class="metric-card"><span>As of</span><strong>{esc(payload.get("as_of", "—"))}</strong></div>'
        f'<div class="metric-card"><span>Quality</span><strong>{esc(quality.get("status", "—"))}</strong></div>'
        f'<div class="metric-card"><span>Completeness</span><strong>{fmt(quality.get("completeness"))}</strong></div>'
        '</div>\n\n'
    )

    page += "## Source Status\n\n"
    page += "| Source | Status | As of | Source reference |\n|---|---|---|---|\n"
    for row in sources:
        page += (
            f'| {esc(row.get("name", "—"))} | **{esc(row.get("status", "—"))}** | '
            f'{esc(row.get("as_of") or "—")} | {esc(row.get("source") or "—")} |\n'
        )

    page += "\n## Warnings\n\n"
    if warnings:
        for warning in warnings:
            page += f"- {esc(warning)}\n"
    else:
        page += "- なし\n"

    page += "\n## Input Sections\n\n"
    sections = ("market", "portfolio", "capital", "candidates", "investor_dna", "events", "watchlist")
    for key in sections:
        value = payload.get(key)
        page += f"### {key}\n\n"
        if value is None:
            page += "`MISSING`\n\n"
        else:
            rendered = json.dumps(value, ensure_ascii=False, indent=2)
            page += f"```json\n{rendered}\n```\n\n"

    page += (
        "## Public JSON\n\n"
        "AI入力契約そのものは [`morning-dataset.json`](./morning-dataset.json) で確認できます。\n\n"
        "不足データは0や推測値で補完せず、`null` / `MISSING` / `PARTIAL` として残します。\n"
    )
    return page


def main() -> None:
    if not REPORT.is_file():
        raise FileNotFoundError(f"Morning Dataset not found: {REPORT}")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.md").write_text(build_page(payload), encoding="utf-8")
    shutil.copyfile(REPORT, SITE / "morning-dataset.json")


if __name__ == "__main__":
    main()
