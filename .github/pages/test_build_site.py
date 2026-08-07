from __future__ import annotations

import importlib.util
import json
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

    def test_2026_08_07_trade_journal_is_published(self) -> None:
        page = self.page("2026-08-07")

        for expected in (
            "## Market",
            "## Market Recognition",
            "## Today's Trades",
            "テラドローン",
            "11,900円",
            "12,150円",
            "ソフトバンクグループ",
            "オンコリスバイオファーマ",
            "積水化学工業",
            "失効 / 未約定",
            "約 +58,000円",
            "Investor DNA",
            "信用買残の増減 × 株価反応",
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

    def test_trade_analysis_includes_improvement_cycle(self) -> None:
        build_site.build_trade_analysis_landing()
        page = (
            build_site.SITE / "trade-analysis" / "index.md"
        ).read_text(encoding="utf-8")

        for expected in (
            "Today's Lesson",
            "AI先生コメント",
            "Next Action",
            "Framework Candidate",
            "Today's Score",
            "投資改善サイクル",
        ):
            self.assertIn(expected, page)
        self.assertNotIn("日東紡", page)
        self.assertNotIn("JX金属", page)

        for expected in (
            "全期間",
            "年別パフォーマンス",
            "月別パフォーマンス",
            "累積結果・ドローダウン",
            "データ品質",
            "2024",
            "2025",
            "2026-07",
        ):
            self.assertIn(expected, page)

        fixture = json.loads(
            build_site.TRADE_DATA_FIXTURE.read_text(encoding="utf-8")
        )
        july = next(
            item for item in fixture["months"] if item["label"] == "2026-07"
        )
        self.assertEqual(july["trade_count"], 3)
        self.assertEqual(july["win_count"], 2)

    def test_nittobo_company_report_is_published(self) -> None:
        build_site.build_companies()
        page = (
            build_site.SITE / "companies" / "semiconductor"
            / "3110-nittobo" / "index.md"
        ).read_text(encoding="utf-8")
        index = (
            build_site.SITE / "companies" / "index.md"
        ).read_text(encoding="utf-8")

        for expected in (
            "Sado投資レポート",
            "Investment Thesis",
            "Sado投資評価",
            "投資仮説タイムライン",
            "96 / 100",
        ):
            self.assertIn(expected, page)
        self.assertIn("3110-nittobo", index)

    def test_market_analysis_page_and_index_are_published(self) -> None:
        build_site.build_market_analysis()
        page = (
            build_site.SITE / "market-analysis" / "2026"
            / "2026-08-05" / "index.md"
        ).read_text(encoding="utf-8")
        index = (
            build_site.SITE / "market-analysis" / "index.md"
        ).read_text(encoding="utf-8")

        for expected in (
            "2026年8月5日 市場動向分析",
            "data:image/jpeg;base64,",
            "主要な下落要因を吹き出しで注釈した市場分析図",
            "## 分析の目的",
            "## 注意事項",
        ):
            self.assertIn(expected, page)
        self.assertNotIn("MARKET_CHART_DATA_URI", page)
        self.assertIn("/market-analysis/2026/2026-08-05/", index)

    def test_market_phase_report_is_published(self) -> None:
        build_site.build_market_phase()
        page = (
            build_site.SITE / "research" / "market-phase"
            / "ai-semiconductor" / "index.md"
        ).read_text(encoding="utf-8")
        for expected in (
            "Sado Market Phase Analyzer",
            "正規化比較チャート",
            "相関ヒートマップ",
            'id="phase-data"',
            "先行・遅行候補",
        ):
            self.assertIn(expected, page)


if __name__ == "__main__":
    unittest.main()
