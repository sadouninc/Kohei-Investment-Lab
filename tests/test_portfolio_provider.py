from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import tempfile
import unittest

from scripts.morning_dataset.providers.portfolio import PortfolioProvider


class PortfolioProviderTest(unittest.TestCase):
    def write(self, root: Path, body: str) -> Path:
        path = root / "Current_Status.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_ok_when_fresh_and_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), """# Current Status\n> 最終更新: 2026-08-08\n\n## Portfolio\n- 日東紡（信用買い800株・信用売り100株）\n- 信越化学\n\n## Current Strategy\n- test\n""")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual("2026-08-08", result.as_of)
            self.assertEqual("日東紡", result.data["positions"][0]["name"])
            self.assertEqual("信用買い800株・信用売り100株", result.data["positions"][0]["details"])
            self.assertIsNone(result.data["positions"][1]["details"])

    def test_stale_preserves_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), """# Current Status\n> 最終更新: 2026-08-04\n\n## Portfolio\n- ダイヘン\n""")
            result = PortfolioProvider(path, max_age_days=3, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertEqual("ダイヘン", result.data["positions"][0]["name"])
            self.assertIn("4 days old", result.reason)

    def test_missing_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = PortfolioProvider(Path(tmp) / "missing.md", today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertIsNone(result.data)

    def test_missing_portfolio_section_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "# Current Status\n> 最終更新: 2026-08-08\n\n## TODO\n- test\n")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

    def test_no_last_updated_is_partial_not_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "# Current Status\n\n## Portfolio\n- GENDA\n")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIsNone(result.as_of)
            self.assertEqual("GENDA", result.data["positions"][0]["name"])

    def test_non_bullet_content_marks_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "# Current Status\n> 最終更新: 2026-08-08\n\n## Portfolio\n- GENDA\nneeds-review\n")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual(1, len(result.data["positions"]))

    def test_canonical_verified_json_is_primary_machine_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.json"
            path.write_text(json.dumps({
                "as_of": "2026-08-08",
                "verification_status": "VERIFIED",
                "base_snapshot": "verified-2026-08-08",
                "positions": [{
                    "security_code": "4063", "security_name": "信越化学",
                    "position_type": "cash", "quantity": 100,
                }],
            }, ensure_ascii=False), encoding="utf-8")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual("VERIFIED", result.data["verification_status"])
            self.assertEqual("4063", result.data["positions"][0]["security_code"])

    def test_canonical_mismatch_is_partial_with_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.json"
            path.write_text(json.dumps({
                "as_of": "2026-08-08",
                "verification_status": "MISMATCH",
                "positions": [{
                    "security_code": "4063", "security_name": "信越化学",
                    "position_type": "cash", "quantity": 100,
                }],
                "verification_diff": [{"security_code": "4063", "difference": 100}],
            }, ensure_ascii=False), encoding="utf-8")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual(100, result.data["verification_diff"][0]["difference"])

    def test_canonical_invalid_date_is_partial_not_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.json"
            path.write_text(json.dumps({
                "as_of": "unknown",
                "verification_status": "PROVISIONAL",
                "positions": [{
                    "security_code": "4063", "security_name": "信越化学",
                    "position_type": "cash", "quantity": 100,
                }],
            }, ensure_ascii=False), encoding="utf-8")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIn("YYYY-MM-DD", result.reason)


if __name__ == "__main__":
    unittest.main()
