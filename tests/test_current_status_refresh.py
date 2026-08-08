from datetime import date
import unittest
from pathlib import Path
import tempfile

from scripts.current_status_refresh import refresh_portfolio, touch_focus
from scripts.morning_dataset.providers.portfolio import PortfolioProvider
from scripts.morning_dataset.providers.watchlist import WatchlistProvider

BASE = """# Current Status
> 最終更新: 2026-08-01

## Portfolio
> as_of: 2026-08-01
- Old Holding

## Current Strategy
- preserve me

## Current Focus
> as_of: 2026-08-02
- preserve focus

## TODO
- preserve todo
"""

class CurrentStatusRefreshTest(unittest.TestCase):
    def test_portfolio_refresh_preserves_human_sections(self):
        updated = refresh_portfolio(BASE, {"as_of":"2026-08-08","positions":[{"name":"New Holding","details":"100株"}]})
        self.assertIn("- New Holding（100株）", updated)
        self.assertIn("- preserve me", updated)
        self.assertIn("- preserve focus", updated)
        self.assertIn("- preserve todo", updated)
        self.assertIn("> as_of: 2026-08-02", updated)

    def test_focus_confirmation_changes_only_focus_date(self):
        updated = touch_focus(BASE, "2026-08-08")
        self.assertIn("> as_of: 2026-08-01\n- Old Holding", updated)
        self.assertIn("> as_of: 2026-08-08\n- preserve focus", updated)

    def test_canonical_positions_include_type_quantity_and_status(self):
        updated = refresh_portfolio(BASE, {
            "as_of": "2026-08-08",
            "verification_status": "PROVISIONAL",
            "authority": "verified_snapshot_plus_sbi_executions",
            "positions": [{
                "security_code": "3110", "security_name": "日東紡",
                "position_type": "margin_long", "quantity": 800,
            }],
        })
        self.assertIn("- 日東紡（信用買い800株）", updated)
        self.assertIn("> verification_status: PROVISIONAL", updated)
        self.assertIn("> authority: verified_snapshot_plus_sbi_executions", updated)

    def test_mismatch_never_refreshes_current_status(self):
        with self.assertRaises(ValueError):
            refresh_portfolio(BASE, {
                "as_of": "2026-08-08", "verification_status": "MISMATCH",
                "positions": [{"security_name": "日東紡", "position_type": "margin_long", "quantity": 800}],
            })

    def test_providers_use_independent_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Current_Status.md"
            path.write_text(BASE, encoding="utf-8")
            portfolio = PortfolioProvider(path, max_age_days=6, today=date(2026,8,8)).collect()
            watchlist = WatchlistProvider(path, max_age_days=6, today=date(2026,8,8)).collect()
            self.assertEqual("STALE", portfolio.status)
            self.assertEqual("OK", watchlist.status)
            self.assertEqual("2026-08-01", portfolio.as_of)
            self.assertEqual("2026-08-02", watchlist.as_of)

if __name__ == "__main__":
    unittest.main()
