from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site-src"
REPORT_DIR = ROOT / "05_Daily_Reports" / "Morning"
DIAG_DIR = ROOT / "data" / "generated" / "diagnostics" / "openai"


def front_matter(title: str, description: str, permalink: str) -> str:
    return (
        "---\n"
        "layout: site\n"
        f"title: {title}\n"
        f"description: {description}\n"
        f"permalink: {permalink}\n"
        "---\n\n"
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def strip_source_front_matter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            return text[end + 5 :].lstrip()
    return text


def report_date(path: Path) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem):
        return path.stem
    return path.stem


def build() -> None:
    sources = sorted(REPORT_DIR.glob("*.md"), reverse=True) if REPORT_DIR.exists() else []
    cards: list[str] = []
    for source in sources:
        day = report_date(source)
        url = f"/reports/morning/{day}/"
        diagnostics_path = DIAG_DIR / f"{day}.json"
        diagnostics = {}
        if diagnostics_path.exists():
            diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
        model = diagnostics.get("model", "unknown")
        tokens = diagnostics.get("total_tokens")
        status = diagnostics.get("dataset_status", "unknown")
        cards.append(
            f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}">'
            f"<strong>{day}</strong><span>Dataset {status} / {model} / tokens {tokens}</span></a>"
        )
        page = front_matter(
            f"AI Morning Report {day}",
            "Morning DatasetをOpenAI APIで分析した自動生成レポート",
            url,
        )
        page += (
            '<p class="breadcrumb"><a href="{{ \'/reports/morning/\' | relative_url }}">'
            f"AI Morning Reports</a> / {day}</p>\n\n"
        )
        page += strip_source_front_matter(source.read_text(encoding="utf-8"))
        if diagnostics:
            page += (
                "\n\n## API Diagnostics\n\n"
                f"- Model: `{model}`\n"
                f"- Dataset status: `{status}`\n"
                f"- Input tokens: `{diagnostics.get('input_tokens')}`\n"
                f"- Output tokens: `{diagnostics.get('output_tokens')}`\n"
                f"- Total tokens: `{tokens}`\n"
                f"- Execution: `{diagnostics.get('execution_seconds')} sec`\n"
                f"- Estimated cost USD: `{diagnostics.get('estimated_cost_usd')}` "
                f"({diagnostics.get('cost_basis')})\n"
            )
        write(SITE / "reports" / "morning" / day / "index.md", page)

    index = front_matter(
        "AI Morning Reports",
        "Morning Datasetを基にOpenAI APIが自動生成した朝の市場分析",
        "/reports/morning/",
    )
    index += (
        "# AI Morning Reports\n\n"
        "GitHub Actions が Morning Dataset を生成し、OpenAI API が分析した朝レポートの履歴です。"
        "AIの出力は判断材料であり、事実データと推論を分離して扱います。\n\n"
    )
    if cards:
        index += '<div class="content-grid">\n' + "\n".join(cards) + "\n</div>\n"
    else:
        index += "まだAI Morning Reportは生成されていません。\n"
    write(SITE / "reports" / "morning" / "index.md", index)


if __name__ == "__main__":
    build()
