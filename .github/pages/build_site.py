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


def build_trade_analysis_landing() -> None:
    source = PUBLIC_TRADE_DATA if PUBLIC_TRADE_DATA.is_file() else TRADE_DATA_FIXTURE
    payload = json.loads(source.read_text(encoding="utf-8"))
    summary = payload["summary"]
    period = payload["period"]
    page = front_matter(
        "Trade Analysis",
        "匿名化した集計指標で売買の再現性と改善点を検証する",
        "/trade-analysis/",
    )
    page += (
        "# Trade Analysis\n\n"
        "個別の銘柄、価格、数量、損益額を公開せず、集計指標だけで売買を振り返ります。\n\n"
        f'<p class="dashboard-period">対象期間: {period["start"] or "—"} 〜 '
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
        "</div>\n\n"
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
    shutil.copy2(ROOT / "assets" / "images" / "overview.png", SITE / "assets" / "images" / "overview.png")
    shutil.copy2(PAGES / "home.md", SITE / "index.md")

    build_framework()
    build_themes()
    build_companies()
    build_trade_journal()
    build_trade_analysis_landing()


if __name__ == "__main__":
    main()
