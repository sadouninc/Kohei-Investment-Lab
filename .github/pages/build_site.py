from __future__ import annotations

import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / ".github" / "pages"
SITE = ROOT / "site-src"

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


def build_trade_analysis_landing() -> None:
    page = front_matter(
        "Trade Analysis",
        "公開可能な売買検証を蓄積するための入口",
        "/trade-analysis/",
    )
    page += (
        "# Trade Analysis\n\n"
        "売買記録や検証結果のうち、公開可能な文書を将来掲載するためのページです。\n\n"
        "> 現在、公開対象の文書はありません。\n"
    )
    write(SITE / "trade-analysis" / "index.md", page)


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
    build_trade_analysis_landing()


if __name__ == "__main__":
    main()

