import json
import tempfile
import unittest
from pathlib import Path

import build_site


class TradeAnalysisV2BuildTest(unittest.TestCase):
    def test_raw_dashboard_contains_filters_and_embedded_trades(self):
        payload = json.loads(build_site.PUBLIC_TRADE_DATA.read_text(encoding="utf-8"))
        self.assertGreaterEqual(payload["schema_version"], 2)
        self.assertTrue(payload["trades"])
        sample = payload["trades"][0]
        for key in (
            "security_name", "security_code", "quantity",
            "average_open_price", "average_close_price", "net_pnl",
        ):
            self.assertIn(key, sample)
        serialized = json.dumps(payload, ensure_ascii=False)
        for key in ("episode_key", "first_execution_id", "final_execution_id"):
            self.assertNotIn(f'"{key}"', serialized)
        self.assertNotIn('"account":', serialized)

        with tempfile.TemporaryDirectory() as temporary:
            original = build_site.SITE
            build_site.SITE = Path(temporary)
            try:
                build_site.build_trade_analysis_v2()
                page = (
                    build_site.SITE / "trade-analysis" / "index.md"
                ).read_text(encoding="utf-8")
            finally:
                build_site.SITE = original
        self.assertIn('id="ta-year"', page)
        self.assertIn('id="ta-symbol"', page)
        self.assertIn('id="ta-theme"', page)
        self.assertIn('id="ta-trades"', page)
        self.assertIn("trade-analysis-data", page)
        self.assertIn(sample["security_name"], page)


if __name__ == "__main__":
    unittest.main()
