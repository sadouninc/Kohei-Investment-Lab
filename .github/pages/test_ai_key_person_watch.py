from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_site.py")
SPEC = importlib.util.spec_from_file_location("watch_build_site", MODULE_PATH)
assert SPEC and SPEC.loader
build_site = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_site
SPEC.loader.exec_module(build_site)


class KeyPersonWatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.source = root / "news"
        self.site = root / "site"
        build_site.KEY_PERSON_SOURCE_DIRS = (self.source,)
        build_site.SITE = self.site

    def write_month(self, content: str) -> None:
        path = self.source / "2026" / "2026-08.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_structured_news_builds_latest_person_and_archive_pages(self) -> None:
        self.write_month(
            "# AI Key Person Watch — 2026-08\n\n"
            "## 2026-08-08 17:00 JST\n\n"
            "### ジェンスン・フアン / Physical AI\n\n"
            "- 関連企業・テーマ: FANUC / ロボティクス\n"
            "- 何が変わったか: 新しい方針を公表。\n"
            "- 投資上の意味: 日本企業への波及を確認する。\n"
            "- Source: Example — https://example.com/news\n"
        )

        build_site.build_key_person_watch()

        index = (self.site / "research" / "ai-key-person-watch" / "index.md").read_text(encoding="utf-8")
        archive = (self.site / "research" / "ai-key-person-watch" / "2026" / "2026-08" / "index.md").read_text(encoding="utf-8")
        for expected in ("最新ニュース", "人物別", "主なテーマ", "ジェンスン・フアン", "FANUC", "2026-08"):
            self.assertIn(expected, index)
        self.assertIn('markdown="1"', index)
        self.assertIn("https://example.com/news", archive)

    def test_no_update_and_incomplete_records_are_not_published(self) -> None:
        self.write_month(
            "## 2026-08-08 18:00 JST\n\n### リサ・スー / AI半導体\n\n追加情報なし\n\n"
            "## 2026-08-08 17:00 JST\n\n### 孫正義 / AI\n\n- 何が変わったか: Sourceなし。\n"
        )

        self.assertEqual([], build_site.discover_key_person_news())
        build_site.build_key_person_watch()
        index = (self.site / "research" / "ai-key-person-watch" / "index.md").read_text(encoding="utf-8")
        self.assertIn("重要な追加情報はまだ記録されていません", index)
        self.assertNotIn("追加情報なし", index)


if __name__ == "__main__":
    unittest.main()
