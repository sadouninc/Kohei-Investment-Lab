from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / ".github" / "pages"
SITE = ROOT / "site-src"
PUBLIC_TRADE_DATA = ROOT / "data" / "generated" / "public" / "trade-analysis-summary.json"
TRADE_DATA_FIXTURE = PAGES / "fixtures" / "trade-analysis-summary.json"
TRADE_IMPROVEMENT_NOTES = ROOT / "08_Trade_Analysis" / "Improvement_Notes.md"

FRAMEWORK_CHAPTERS = [
    ("philosophy", ROOT / "00_Framework" / "01_Investment_Philosophy.md"),
    ("psychology", ROOT / "00_Framework" / "02_Market_Psychology.md"),
    ("thinking", ROOT / "00_Framework" / "03_Thinking_Process.md"),
    ("rules", ROOT / "00_Framework" / "04_Investment_Rules.md"),
    ("evaluation", ROOT / "00_Framework" / "05_Evaluation_Framework.md"),
    ("allocation", ROOT / "00_Framework" / "06_Capital_Allocation.md"),
    ("lessons", ROOT / "00_Framework" / "07_Lessons_Learned.md"),
    ("metrics", ROOT / "00_Framework" / "08_Original_Metrics.md"),
]

JOURNAL_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


@dataclass(frozen=True)
class JournalEntry:
    day: date
    content: str
    source: Path


def front_matter(title: str, description: str, permalink: str) -> str:
    return (
        "---\n"
        "layout: site\n"
        f"title: {title}\n"
        f"description: {description}\n"
        f"permalink: {permalink}\n"
        "---\n\n"
    )


def title_from_markdown(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("_", " ")


def slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def normalize_math(text: str) -> str:
    return re.sub(
        r"```math\s*\n(.*?)\n```",
        lambda match: "\n$\n" + match.group(1).strip() + "\n$\n",
        text,
        flags=re.DOTALL,
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalize_math(content).rstrip() + "\n", encoding="utf-8")


def build_framework() -> None:
    output = (PAGES / "book-header.md").read_text(encoding="utf-8").rstrip()
    for anchor, source in FRAMEWORK_CHAPTERS:
        output += (
            f'\n\n<section class="book-chapter" id="{anchor}" markdown="1">\n\n'
            + source.read_text(encoding="utf-8").strip()
            + "\n\n</section>"
        )
    output += '\n\n<p class="book-end">Sado Investment Lab — Framework</p>\n'
    write(SITE / "framework" / "index.md", output)


def build_themes() -> None:
    sources = sorted((ROOT / "02_Themes").glob("*.md"))
    cards: list[str] = []
    for source in sources:
        page_slug = slug(source.stem)
        title = title_from_markdown(source)
        url = f"/themes/{page_slug}/"
        cards.append(
            f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}">'
            f"<strong>{title}</strong><span>{source.name}</span></a>"
        )
        page = front_matter(title, f"{title}のテーマ分析", url)
        page += '<p class="breadcrumb"><a href="{{ \'/themes/\' | relative_url }}">Themes</a> / '
        page += f"{title}</p>\n\n"
        page += source.read_text(encoding="utf-8")
        write(SITE / "themes" / page_slug / "index.md", page)

    index = front_matter("Themes", "社会変化と需要の波及から投資テーマを考える", "/themes/")
    index += "# Themes\n\n社会変化から需要の流れ、ボトルネック、関連企業を整理します。\n\n"
    index += '<div class="content-grid">\n' + "\n".join(cards) + "\n</div>\n"
    write(SITE / "themes" / "index.md", index)


def build_companies() -> None:
    sources = sorted(
        path
        for path in (ROOT / "03_Companies").glob("*/*.md")
        if path.name.lower() != "readme.md"
    )
    groups: dict[str, list[str]] = {}
    for source in sources:
        category = source.parent.name
        category_slug = slug(category)
        page_slug = slug(source.stem)
        title = title_from_markdown(source)
        url = f"/companies/{category_slug}/{page_slug}/"
        groups.setdefault(category, []).append(
            f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}">'
            f"<strong>{title}</strong><span>{source.name}</span></a>"
        )
        page = front_matter(title, f"{title}の企業分析", url)
        page += '<p class="breadcrumb"><a href="{{ \'/companies/\' | relative_url }}">Companies</a>'
        page += f" / {category} / {title}</p>\n\n"
        page += source.read_text(encoding="utf-8")
        write(SITE / "companies" / category_slug / page_slug / "index.md", page)

    index = front_matter("Companies", "企業品質と投資機会を複数時間軸で分析する", "/companies/")
    index += "# Companies\n\n企業の長期的な強さと、現在の投資タイミングを分けて分析します。\n"
    for category, cards in groups.items():
        index += f"\n## {category}\n\n"
        index += '<div class="content-grid">\n' + "\n".join(cards) + "\n</div>\n"
    if not groups:
        index += "\n公開中の企業分析はありません。\n"
    write(SITE / "companies" / "index.md", index)


def build_market_analysis() -> None:
    sources = sorted(
        (ROOT / "04_Market" / "Analysis").glob("*/*.md"),
        reverse=True,
    )
    cards: list[str] = []
    for source in sources:
        year = source.parent.name
        page_slug = slug(source.stem)
        title = title_from_markdown(source)
        url = f"/market-analysis/{year}/{page_slug}/"
        cards.append(
            f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}">'
            f"<strong>{title}</strong>"
            "<span>日経平均 日足チャート：上昇相場中の主な下げ要因分析</span></a>"
        )
        page = front_matter(title, "市場変動の背景と投資判断を記録する", url)
        page += (
            '<p class="breadcrumb"><a href="{{ \'/market-analysis/\' | relative_url }}">'
            f"Market Analysis</a> / {year} / {title}</p>\n\n"
        )
        page += source.read_text(encoding="utf-8")
        write(SITE / "market-analysis" / year / page_slug / "index.md", page)

    index = front_matter(
        "Market Analysis",
        "チャートと公開情報から市場変動の背景を整理する",
        "/market-analysis/",
    )
    index += (
        "# Market Analysis\n\n"
        "市場の値動きと背景を記録し、一時的な需給調整と構造的な変化を分けて考えます。\n\n"
    )
    if cards:
        index += '<div class="content-grid">\n' + "\n".join(cards) + "\n</div>\n"
    else:
        index += "公開中の市場分析はありません。\n"
    write(SITE / "market-analysis" / "index.md", index)


def metric(value: float | None, *, percent: bool = False) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%" if percent else f"{value:.2f}"


def analysis_table(title: str, rows: list[dict]) -> str:
    output = [
        f"## {title}", "",
        "| 区分 | 取引数 | 勝率 | PF | 平均保有日数 |",
        "|---|---:|---:|---:|---:|",
    ]
    output.extend(
        f"| {row['label']} | {row['trade_count']} | "
        f"{metric(row['win_rate'], percent=True)} | "
        f"{metric(row['profit_factor'])} | {row['average_holding_days']:.1f} |"
        for row in rows
    )
    return "\n".join(output) + "\n\n"


def indexed(value: float | None) -> str:
    return "—" if value is None else f"{value:,.1f}"


def period_table(title: str, rows: list[dict], label: str) -> str:
    output = [
        f"## {title}", "",
        f"| {label} | 取引数 | 結果指数 | 勝率 | PF | 平均保有日数 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    output.extend(
        f"| {row['label']} | {row['trade_count']} | "
        f"{indexed(row['indexed_net_result'])} | "
        f"{metric(row['win_rate'], percent=True)} | "
        f"{metric(row['profit_factor'])} | {row['average_holding_days']:.1f} |"
        for row in rows
    )
    return "\n".join(output) + "\n\n"


def bar_chart(title: str, rows: list[dict], key: str, *, percent: bool = False) -> str:
    values = [abs(float(row.get(key) or 0)) for row in rows]
    maximum = max(values, default=0) or 1
    chart = [f'<div class="analysis-chart" aria-label="{title}">', f"<h3>{title}</h3>"]
    for row in rows:
        value = float(row.get(key) or 0)
        width = abs(value) / maximum * 100
        display = f"{value * 100:.1f}%" if percent else f"{value:,.1f}"
        direction = "negative" if value < 0 else "positive"
        chart.append(
            f'<div class="chart-row"><span>{row["label"]}</span>'
            f'<i class="{direction}" style="width:{width:.2f}%"></i>'
            f"<strong>{display}</strong></div>"
        )
    chart.append("</div>")
    return "\n".join(chart) + "\n\n"


def line_chart(title: str, points: list[dict], keys: tuple[str, str]) -> str:
    if not points:
        return ""
    values = [float(point[key] or 0) for point in points for key in keys]
    low, high = min(values), max(values)
    span = high - low or 1
    width, height, padding = 720, 240, 18

    def coordinates(key: str) -> str:
        result = []
        denominator = max(len(points) - 1, 1)
        for index, point in enumerate(points):
            x = padding + index / denominator * (width - padding * 2)
            y = padding + (high - float(point[key] or 0)) / span * (
                height - padding * 2
            )
            result.append(f"{x:.1f},{y:.1f}")
        return " ".join(result)

    labels = f"{points[0]['month']} 〜 {points[-1]['month']}"
    return (
        f'<figure class="line-chart"><figcaption>{title}</figcaption>'
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{title}">'
        f'<polyline class="line-primary" points="{coordinates(keys[0])}" />'
        f'<polyline class="line-secondary" points="{coordinates(keys[1])}" />'
        "</svg>"
        f"<small>{labels}　<span>累積結果指数</span> / <span>ドローダウン指数</span></small>"
        "</figure>\n\n"
    )


def build_trade_analysis_landing() -> None:
    source = PUBLIC_TRADE_DATA if PUBLIC_TRADE_DATA.is_file() else TRADE_DATA_FIXTURE
    payload = json.loads(source.read_text(encoding="utf-8"))
    summary = payload["summary"]
    period = payload["period"]
    years = payload.get("years", [])
    months = payload.get("months", [])
    curve = payload.get("monthly_equity_curve", {"points": []})
    quality = payload.get("data_quality", {})
    notes = (
        TRADE_IMPROVEMENT_NOTES.read_text(encoding="utf-8")
        if TRADE_IMPROVEMENT_NOTES.is_file() else ""
    )
    lesson = section_content(notes, "Today's Lesson", level=2)
    teacher_comment = section_content(notes, "AI先生コメント", level=2)
    next_action = section_content(notes, "Next Action", level=2)
    framework_candidate = section_content(notes, "Framework Candidate", level=2)
    today_score = section_content(notes, "Today's Score", level=2)
    page = front_matter(
        "Trade Analysis",
        "匿名化した集計指標で売買の再現性と改善点を検証する",
        "/trade-analysis/",
    )
    page += (
        "# Trade Analysis\n\n"
        "過去の成績を見るだけでなく、分析から学び、次のトレードとFrameworkを改善するためのページです。\n\n"
        "個別の銘柄、価格、数量、損益額を公開せず、集計指標だけで売買を振り返ります。\n\n"
        '<div class="improvement-flow" aria-label="投資改善サイクル">'
        "<span>分析</span><b>→</b><span>学び</span><b>→</b><span>改善</span>"
        "<b>→</b><span>ルール更新</span><b>→</b><span>次回トレード</span></div>\n\n"
        + (f'<section class="insight-panel lesson-panel" markdown="1">\n\n'
           f"## Today's Lesson\n\n{lesson}\n\n</section>\n\n" if lesson else "")
        + f'<p class="dashboard-period">対象期間: {period["start"] or "—"} 〜 '
        f'{period["end"] or "—"} / 更新: {payload["updated_date"]}</p>\n\n'
        '<div class="metric-grid">\n'
        f'<div class="metric-card"><span>取引数</span><strong>{summary["trade_count"]}</strong></div>\n'
        f'<div class="metric-card"><span>勝率</span><strong>{metric(summary["win_rate"], percent=True)}</strong></div>\n'
        f'<div class="metric-card"><span>PF</span><strong>{metric(summary["profit_factor"])}</strong></div>\n'
        f'<div class="metric-card"><span>ペイオフレシオ</span><strong>{metric(summary["payoff_ratio"])}</strong></div>\n'
        f'<div class="metric-card"><span>期待値指数</span><strong>{summary["indexed_expectancy"]:.1f}</strong></div>\n'
        f'<div class="metric-card"><span>平均保有日数</span><strong>{summary["average_holding_days"]:.1f}</strong></div>\n'
        f'<div class="metric-card"><span>最大連勝</span><strong>{summary["max_win_streak"]}</strong></div>\n'
        f'<div class="metric-card"><span>最大連敗</span><strong>{summary["max_loss_streak"]}</strong></div>\n'
        f'<div class="metric-card"><span>利益取引</span><strong>{summary.get("win_count", "—")}</strong></div>\n'
        f'<div class="metric-card"><span>損失取引</span><strong>{summary.get("loss_count", "—")}</strong></div>\n'
        f'<div class="metric-card"><span>総結果指数</span><strong>{indexed(summary.get("indexed_net_result"))}</strong></div>\n'
        f'<div class="metric-card"><span>最大DD指数</span><strong>{indexed(curve.get("indexed_max_drawdown"))}</strong></div>\n'
        "</div>\n\n"
        "> 金額に関する指標は、実損益を公開しないため相対指数で表示します。"
        "100は全期間の1取引あたり絶対損益平均です。\n\n"
        "### 集計単位\n\n"
        "一つの取引は、同一銘柄・口座区分・売買方向の建玉がゼロから始まり、"
        "再びゼロへ戻るまでの **Trade Episode** です。分割買いと部分決済を"
        "一つの判断として扱い、未決済Episodeは損益統計から除外します。"
        "保有日数は営業日ではなく暦日です。\n\n"
    )
    if years:
        page += period_table("年別パフォーマンス", years, "年")
        page += bar_chart("年別結果指数", years, "indexed_net_result")
        page += bar_chart("年別勝率", years, "win_rate", percent=True)
        page += bar_chart("年別プロフィットファクター", years, "profit_factor")
    if months:
        options = "".join(
            f'<option value="{row["label"]}">{row["label"]}</option>' for row in months
        )
        page += (
            "## 月別パフォーマンス\n\n"
            '<label class="period-selector">表示月 '
            f'<select id="month-selector"><option value="all">全期間</option>{options}'
            "</select></label>\n\n"
            '<div class="month-table"><table><thead><tr><th>年月</th><th>取引数</th>'
            "<th>結果指数</th><th>勝率</th><th>PF</th><th>平均保有日数</th>"
            "</tr></thead><tbody>\n"
        )
        for row in months:
            page += (
                f'<tr data-month="{row["label"]}"><td>{row["label"]}</td>'
                f'<td>{row["trade_count"]}</td>'
                f'<td>{indexed(row["indexed_net_result"])}</td>'
                f'<td>{metric(row["win_rate"], percent=True)}</td>'
                f'<td>{metric(row["profit_factor"])}</td>'
                f'<td>{row["average_holding_days"]:.1f}</td></tr>\n'
            )
        page += (
            "</tbody></table></div>\n\n"
            "<script>document.addEventListener('DOMContentLoaded',()=>{"
            "const s=document.getElementById('month-selector');if(!s)return;"
            "s.addEventListener('change',()=>document.querySelectorAll('[data-month]')"
            ".forEach(r=>r.hidden=s.value!=='all'&&r.dataset.month!==s.value));});"
            "</script>\n\n"
        )
        page += bar_chart("月別結果指数", months, "indexed_net_result")
        page += bar_chart("月別勝率推移", months, "win_rate", percent=True)
        page += bar_chart("月別取引件数", months, "trade_count")
    if curve.get("points"):
        page += "## 累積結果・ドローダウン\n\n"
        page += (
            "この曲線は、入出金や含み損益を含む証券口座の総資産推移ではなく、"
            "記録された決済済みTrade Episodeの実現結果を月単位で累積した指数です。\n\n"
        )
        page += line_chart(
            "累積結果指数とドローダウン指数",
            curve["points"],
            ("indexed_cumulative_result", "indexed_drawdown"),
        )
    page += analysis_table("保有期間別", payload["holding_periods"])
    page += analysis_table("エントリー曜日別", payload["entry_weekdays"])
    if payload["exit_weekdays"]:
        page += analysis_table("決済曜日別", payload["exit_weekdays"])
    page += analysis_table("売買方向別", payload["position_sides"])
    page += analysis_table("現物・信用別", payload["account_types"])
    concentration = payload["concentration"]
    page += (
        "## 集中度\n\n| 指標 | 値 |\n|---|---:|\n"
        f"| 上位1銘柄の利益寄与率 | {metric(concentration['top_1_security_contribution'], percent=True)} |\n"
        f"| 上位3銘柄の利益寄与率 | {metric(concentration['top_3_security_contribution'], percent=True)} |\n"
        f"| 上位5銘柄の利益寄与率 | {metric(concentration['top_5_security_contribution'], percent=True)} |\n"
        f"| 上位1取引除外後PF | {metric(concentration['profit_factor_excluding_top_1_trades'])} |\n"
        f"| 上位3取引除外後PF | {metric(concentration['profit_factor_excluding_top_3_trades'])} |\n"
        f"| 上位5取引除外後PF | {metric(concentration['profit_factor_excluding_top_5_trades'])} |\n\n"
        "> 期待値指数は金額を公開しないための相対指標です。100を中立基準とします。\n"
    )
    if teacher_comment:
        page += (
            '\n<section class="insight-panel teacher-panel" markdown="1">\n\n'
            f"## AI先生コメント\n\n{teacher_comment}\n\n</section>\n"
        )
    if next_action:
        page += f"\n## Next Action\n\n{next_action}\n"
    if framework_candidate:
        page += (
            '\n<section class="framework-candidate" markdown="1">\n\n'
            f"## Framework Candidate\n\n{framework_candidate}\n\n"
            '<p class="candidate-note">「未反映」を確認し、内容を検証してから'
            'Frameworkへ昇格します。</p>\n\n</section>\n'
        )
    if today_score:
        page += f"\n## Today's Score\n\n{today_score}\n"
    page += "\n## データ品質\n\n"
    page += (
        f"- 集計対象期間: {period.get('start') or '—'} 〜 {period.get('end') or '—'}\n"
        f"- 最終更新日: {payload.get('updated_date') or '—'}\n"
        f"- 読み込んだCSV数: {quality.get('source_csv_count') if quality.get('source_csv_count') is not None else '記録なし'}\n"
        f"- 有効約定レコード数: {quality.get('valid_record_count') if quality.get('valid_record_count') is not None else '記録なし'}\n"
        f"- 決済済みEpisode数: {quality.get('closed_episode_count') if quality.get('closed_episode_count') is not None else '記録なし'}\n"
        f"- 未決済Episode数: {quality.get('open_episode_count') if quality.get('open_episode_count') is not None else '記録なし'}\n"
        f"- 対応不能約定数: {quality.get('unmatched_execution_count') if quality.get('unmatched_execution_count') is not None else '記録なし'}\n"
        f"- 銘柄名未解決件数: {quality.get('unresolved_security_count') if quality.get('unresolved_security_count') is not None else '記録なし'}\n"
        f"- 重複除外件数: {quality.get('duplicate_excluded_count') if quality.get('duplicate_excluded_count') is not None else '既存DBには監査値なし'}\n"
        f"- 対応付け: {quality.get('matching_method') or 'FIFO / Trade Episode'}\n\n"
        "元CSVの同一約定はfingerprintで重複登録を防止します。既存DBは取り込み時の"
        "重複スキップ件数を保持していないため、重複除外件数は次回インポート監査の"
        "改善項目です。株式分割等の調整は元約定を書き換えず、将来の注記マスタで扱います。\n"
    )
    write(SITE / "trade-analysis" / "index.md", page)


def section_content(text: str, heading: str, level: int = 3) -> str:
    marker = "#" * level
    pattern = re.compile(
        rf"^{marker} {re.escape(heading)}\s*$\n(.*?)(?=^{'#' * level} |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def subsection_content(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^#### {re.escape(heading)}\s*$\n(.*?)(?=^#### |^### |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def journal_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^### (.+?)\s*$", text, re.MULTILINE))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[match.end():end].strip()))
    return sections


def first_section(text: str, *headings: str) -> str:
    """Return the first matching level-three section in priority order."""
    sections = dict(journal_sections(text))
    for heading in headings:
        content = sections.get(heading)
        if content:
            return content
    return ""


def nested_sections(text: str, *headings: str) -> list[str]:
    """Collect content only from matching level-four headings."""
    results: list[str] = []
    for heading in headings:
        pattern = re.compile(
            rf"^#### {re.escape(heading)}\s*$\n(.*?)(?=^#### |^### |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        results.extend(match.group(1).strip() for match in pattern.finditer(text))
    return [result for result in results if result]


def nested_sections_with_parent(text: str, heading: str) -> list[str]:
    """Preserve the parent topic when reading a legacy nested section."""
    results: list[str] = []
    for parent, content in journal_sections(text):
        nested = nested_sections(content, heading)
        if nested:
            results.append(f"### {parent}\n\n" + "\n\n".join(nested))
    return results


def promote_headings(text: str) -> str:
    """Move nested source headings up one level for the published section."""
    return re.sub(r"^####(#?) ", lambda match: "###" + match.group(1) + " ", text, flags=re.MULTILINE)


def render_journal_section(title: str, content: str, *, required: bool = False) -> str:
    if not content and not required:
        return ""
    body = content or "未記録"
    return f"---\n\n## {title}\n\n{body}\n\n"


def discover_journal_entries() -> list[JournalEntry]:
    entries: list[JournalEntry] = []
    for source in sorted((ROOT / "01_Portfolio" / "Transactions").glob("*.md")):
        text = source.read_text(encoding="utf-8")
        matches = list(JOURNAL_HEADING.finditer(text))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            entries.append(
                JournalEntry(
                    day=date.fromisoformat(match.group(1)),
                    content=text[match.end():end].strip(),
                    source=source,
                )
            )
    return sorted(entries, key=lambda entry: entry.day, reverse=True)


def trade_rows_for_day(entry: JournalEntry) -> dict[str, list[str]]:
    grouped = {"Buy": [], "Sell": []}
    if not entry.source.exists():
        return grouped
    source = entry.source.read_text(encoding="utf-8")
    rows = [
        line for line in source.splitlines()
        if line.startswith(f"| {entry.day.isoformat()} |")
    ]
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) < 7:
            continue
        item = f"- **{cells[1]}** — {cells[2]}、{cells[3]}、{cells[4]}（{cells[5]}）"
        if "買い" in cells[2] and "返済買い" not in cells[2]:
            grouped["Buy"].append(item)
        else:
            grouped["Sell"].append(item)
    return grouped


def build_journal_page(entry: JournalEntry) -> str:
    market = first_section(entry.content, "Market", "市場環境")
    recognition = first_section(entry.content, "Market Recognition", "市場認識")
    if not recognition:
        recognition = subsection_content(market, "解釈")
    market_facts = subsection_content(market, "事実")
    if market_facts:
        market = market_facts

    trades = first_section(entry.content, "Today's Trades", "本日の取引", "売買履歴")
    if trades:
        trades = promote_headings(trades)
    else:
        grouped = trade_rows_for_day(entry)
        trade_parts: list[str] = []
        if grouped["Buy"]:
            trade_parts.append("### Buy\n\n" + "\n".join(grouped["Buy"]))
        if grouped["Sell"]:
            trade_parts.append("### Sell\n\n" + "\n".join(grouped["Sell"]))
        trades = "\n\n".join(trade_parts)

    ideas = first_section(entry.content, "Investment Ideas", "投資アイデア")
    if not ideas:
        ideas = "\n\n".join(nested_sections_with_parent(entry.content, "仮説"))
    reflection = first_section(entry.content, "Reflection", "振り返り", "総括")
    lessons = first_section(entry.content, "Lessons Learned", "改善点")
    if not lessons:
        lessons = "\n\n".join(nested_sections_with_parent(entry.content, "改善"))
    next_scenario = first_section(entry.content, "Next Scenario", "翌日のシナリオ")

    url = f"/trade-journal/{entry.day:%Y/%m}/{entry.day.isoformat()}/"
    page = front_matter(
        f"Trade Journal — {entry.day.isoformat()}",
        f"{entry.day.isoformat()}の市場認識、売買、反省、改善",
        url,
    )
    page += (
        '<p class="breadcrumb"><a href="{{ \'/trade-journal/\' | relative_url }}">'
        f"Trade Journal</a> / {entry.day:%Y / %m} / {entry.day.isoformat()}</p>\n\n"
        f"# Trade Journal — {entry.day.isoformat()}\n\n"
        + render_journal_section("Market", market, required=True)
        + render_journal_section("Market Recognition", recognition, required=True)
        + render_journal_section("Today's Trades", trades, required=True)
        + render_journal_section("Investment Ideas", promote_headings(ideas))
        + render_journal_section("Reflection", reflection, required=True)
        + render_journal_section("Lessons Learned", lessons)
        + render_journal_section("Next Scenario", next_scenario)
        + '<details class="source-journal">\n'
        "<summary>元の投資日誌を表示</summary>\n\n"
        f"{entry.content}\n\n"
        "</details>\n"
    )
    return page


def build_trade_journal() -> None:
    entries = discover_journal_entries()
    groups: dict[int, dict[int, list[JournalEntry]]] = {}
    for entry in entries:
        groups.setdefault(entry.day.year, {}).setdefault(entry.day.month, []).append(entry)
        output = SITE / "trade-journal" / f"{entry.day:%Y}" / f"{entry.day:%m}"
        write(output / entry.day.isoformat() / "index.md", build_journal_page(entry))

    index = front_matter(
        "Trade Journal",
        "市場認識、投資判断、売買、反省、改善を時系列で振り返る",
        "/trade-journal/",
    )
    index += (
        "# Trade Journal\n\n"
        "思考から改善までを一続きの研究記録として公開します。"
        "日誌は `01_Portfolio/Transactions/` の日付見出しから自動生成されます。\n"
    )
    for year, months in sorted(groups.items(), reverse=True):
        index += f"\n## {year}\n"
        for month, month_entries in sorted(months.items(), reverse=True):
            index += f"\n### {MONTH_NAMES[month]}\n\n<div class=\"content-grid\">\n"
            for entry in month_entries:
                url = f"/trade-journal/{entry.day:%Y/%m}/{entry.day.isoformat()}/"
                index += (
                    f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}">'
                    f"<strong>{entry.day.isoformat()}</strong>"
                    f"<span>{entry.source.name}</span></a>\n"
                )
            index += "</div>\n"
    if not entries:
        index += "\n公開中の投資日誌はありません。\n"
    write(SITE / "trade-journal" / "index.md", index)


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "_layouts").mkdir(parents=True)
    (SITE / "assets" / "images").mkdir(parents=True)

    shutil.copy2(PAGES / "site.html", SITE / "_layouts" / "site.html")
    shutil.copy2(PAGES / "book.css", SITE / "assets" / "book.css")
    shutil.copytree(
        ROOT / "assets" / "images",
        SITE / "assets" / "images",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        ROOT / "assets" / "images" / "market-analysis" / "2026"
        / "nikkei-daily-decline-factors-2026-08-05.png",
        SITE / "assets" / "images" / "nikkei-daily-decline-factors-2026-08-05.png",
    )
    shutil.copy2(PAGES / "home.md", SITE / "index.md")

    build_framework()
    build_themes()
    build_companies()
    build_market_analysis()
    build_trade_journal()
    build_trade_analysis_landing()


if __name__ == "__main__":
    main()

