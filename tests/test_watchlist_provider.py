from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest

from scripts.morning_dataset.providers.watchlist import WatchlistProvider


class WatchlistProviderTest(unittest.TestCase):
    def write(self, root: str, content: str) -> Path:
        path = Path(root) / "Current_Status.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_collects_current_focus_without_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, """# Current Status
> 最終更新: 2026-08-08

## Current Focus

- 信越化学の決算
- 原子力
- テラドローンの需給と事前エントリー条件

## TODO
- [ ] something
""")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual(3, len(result.data["items"]))
            self.assertEqual("信越化学の決算", result.data["items"][0]["text"])
            self.assertIsNone(result.data["items"][0]["security_code"])
            self.assertIsNone(result.data["items"][0]["priority"])

    def test_stale_source_preserves_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, """> 最終更新: 2026-08-01
## Current Focus
- 送電網
""")
            result = WatchlistProvider(path, max_age_days=3, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertEqual("送電網", result.data["items"][0]["text"])

    def test_missing_section_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "> 最終更新: 2026-08-08\n## Portfolio\n- 信越化学\n")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertIsNone(result.data)

    def test_missing_update_date_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "## Current Focus\n- 原子力\n")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual("原子力", result.data["items"][0]["text"])

    def test_malformed_line_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "> 最終更新: 2026-08-08\n## Current Focus\n- 原子力\nplain text\n")
            result = WatchlistProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual(1, len(result.data["items"]))


if __name__ == "__main__":
    unittest.main()
