from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_site.py")
SPEC = importlib.util.spec_from_file_location("build_site", MODULE_PATH)
assert SPEC and SPEC.loader
build_site = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_site
SPEC.loader.exec_module(build_site)


class TradeJournalBuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        build_site.SITE = Path(self.temp_dir.name) / "site-src"
        self.entries = {
            entry.day.isoformat(): entry
            for entry in build_site.discover_journal_entries()
        }

    def page(self, day: str) -> str:
        return build_site.build_journal_page(self.entries[day])

    def test_2026_08_03_content_is_published(self) -> None:
        page = self.page("2026-08-03")

        for expected in (
            "## Market",
            "## Market Recognition",
            "住友電工",
            "安川電機",
            "テラドローン",
            "前日までにエントリー価格",
            "飯田グループHD",
            "原油・物流コスト",
        ):
            self.assertIn(expected, page)

    def test_2026_08_04_content_is_published_without_false_empty_messages(self) -> None:
        page = self.page("2026-08-04")

        for expected in (
            "## Market",
            "## Market Recognition",
            "日東紡",
            "住友電工",
            "富士通",
            "## Investment Ideas",
            "ダイヘン",
            "テラドローン",
            "## Reflection",
            "## Lessons Learned",
            "## Next Scenario",
        ):
            self.assertIn(expected, page)

        self.assertNotIn("記録されていません", page)
        self.assertNotIn("\n未記録\n", page)

    def test_2026_08_05_trade_and_review_are_published(self) -> None:
        page = self.page("2026-08-05")

        for expected in (
            "## Market",
            "## Market Recognition",
            "## Today's Trades",
            "JX金属",
            "4,285円",
            "## Investment Ideas",
            "日東紡",
            "Glass Core",
            "## Reflection",
            "## Lessons Learned",
            "## Next Scenario",
        ):
            self.assertIn(expected, page)

    def test_japanese_headings_remain_supported(self) -> None:
        entry = build_site.JournalEntry(
            day=date(2026, 8, 5),
            source=Path("unused.md"),
            content=(
                "### 市場環境\n\n"
                "#### 事実\n\n選別相場。\n\n"
                "#### 解釈\n\n個別テーマを見る。\n\n"
                "### 総括\n\n判断を振り返る。\n\n"
                "### 旧形式メモ\n\n"
                "#### 改善\n\n条件を準備する。\n\n"
                "#### 仮説\n\n需要継続を確認する。\n\n"
                "### 翌日のシナリオ\n\n資金流入を確認する。\n"
            ),
        )
        page = build_site.build_journal_page(entry)

        for expected in (
            "選別相場",
            "個別テーマを見る",
            "判断を振り返る",
            "条件を準備する",
            "需要継続を確認する",
            "資金流入を確認する",
        ):
            self.assertIn(expected, page)

    def test_optional_empty_sections_are_hidden(self) -> None:
        entry = build_site.JournalEntry(
            day=date(2026, 8, 6),
            source=Path("unused.md"),
            content="### Market\n\n小動き。\n",
        )
        page = build_site.build_journal_page(entry)

        self.assertIn("## Market Recognition\n\n未記録", page)
        self.assertIn("## Today's Trades\n\n未記録", page)
        self.assertIn("## Reflection\n\n未記録", page)
        self.assertNotIn("## Investment Ideas", page)
        self.assertNotIn("## Lessons Learned", page)
        self.assertNotIn("## Next Scenario", page)


if __name__ == "__main__":
    unittest.main()

