from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from investor_dna_v2 import build_report, daily_fit, environment_fit  # noqa: E402


class InvestorDnaV2Test(unittest.TestCase):
    def _trade(self, code: str, pnl: float, open_date: str, direction: str = "LONG", hold: int = 1) -> dict:
        return {
            "security_code": code,
            "security_name": f"SEC-{code}",
            "net_pnl": pnl,
            "return_rate": pnl / 1_000_000,
            "holding_days": hold,
            "open_date": open_date,
            "close_date": open_date,
            "average_close_price": 1000,
            "direction": direction,
        }

    def test_current_environment_is_separate_from_native_skill(self) -> None:
        high = {
            "environment_key": "old",
            "expected_check_interval_minutes": 60,
            "market_open_monitoring": "HIGH",
            "morning_execution_availability": "HIGH",
            "network_reliability": "HIGH",
            "fast_reaction_capability": "HIGH",
            "premarket_analysis_availability": "HIGH",
        }
        low = {
            "environment_key": "current",
            "expected_check_interval_minutes": 180,
            "market_open_monitoring": "LOW",
            "morning_execution_availability": "LOW",
            "network_reliability": "LOW",
            "fast_reaction_capability": "LOW",
            "premarket_analysis_availability": "HIGH",
        }
        self.assertGreater(environment_fit(high)["score"], environment_fit(low)["score"])
        self.assertEqual(environment_fit(low)["confidence"], 1.0)

    def test_tail_loss_warning_detects_high_win_rate_but_bad_pf(self) -> None:
        trades = [self._trade("5801", 20_000, "2026-03-01") for _ in range(9)]
        trades.append(self._trade("5801", -900_000, "2026-04-10", direction="SHORT"))
        payload = {"updated_date": "2026-08-07", "trades": trades}
        environments = {
            "environments": [
                {
                    "environment_key": "current",
                    "effective_from": "2026-04-01",
                    "effective_to": None,
                    "expected_check_interval_minutes": 180,
                    "market_open_monitoring": "LOW",
                    "morning_execution_availability": "LOW",
                    "network_reliability": "LOW",
                    "fast_reaction_capability": "LOW",
                    "premarket_analysis_availability": "HIGH",
                    "drift_reason": "WORK_ENVIRONMENT_CHANGE",
                }
            ]
        }
        report = build_report(payload, {}, environments)
        row = report["security_lifetime_contributions"][0]
        self.assertEqual(row["classification"], "CHALLENGE")
        self.assertTrue(row["tail_risk_warning"])
        self.assertLess(row["profit_factor"], 1.0)
        self.assertGreaterEqual(row["win_rate"], 0.8)
        self.assertLess(row["short_pnl"], 0)
        self.assertEqual(report["risk_patterns"][0]["pattern_code"], "TAIL_LOSS_DESTROYS_SMALL_WINS")

    def test_lifetime_profit_contribution_creates_hero(self) -> None:
        trades = []
        for _ in range(8):
            trades.append(self._trade("285A", 50_000, "2026-02-01"))
        for _ in range(5):
            trades.append(self._trade("9984", 10_000, "2026-02-02"))
        payload = {"updated_date": "2026-08-07", "trades": trades}
        report = build_report(payload, {}, {"environments": []})
        top = report["security_lifetime_contributions"][0]
        self.assertEqual(top["security_code"], "285A")
        self.assertEqual(top["classification"], "HERO")
        self.assertGreater(top["profit_share"], 0.8)

    def test_style_drift_uses_environment_periods(self) -> None:
        trades = [
            self._trade("A", 10_000, "2026-03-10", hold=1),
            self._trade("A", 10_000, "2026-03-11", hold=1),
            self._trade("A", 10_000, "2026-04-10", hold=7),
        ]
        environments = {
            "environments": [
                {"environment_key": "old", "effective_from": "2024-01-01", "effective_to": "2026-03-31", "expected_check_interval_minutes": 60, "market_open_monitoring": "HIGH", "morning_execution_availability": "HIGH", "network_reliability": "HIGH", "fast_reaction_capability": "HIGH", "premarket_analysis_availability": "HIGH", "drift_reason": "BASELINE"},
                {"environment_key": "new", "effective_from": "2026-04-01", "effective_to": None, "expected_check_interval_minutes": 180, "market_open_monitoring": "LOW", "morning_execution_availability": "LOW", "network_reliability": "LOW", "fast_reaction_capability": "LOW", "premarket_analysis_availability": "HIGH", "drift_reason": "WORK_ENVIRONMENT_CHANGE"},
            ]
        }
        report = build_report({"trades": trades}, {}, environments)
        old, new = report["style_periods"]
        self.assertEqual(old["sample_count"], 2)
        self.assertEqual(new["sample_count"], 1)
        self.assertEqual(new["drift_reason"], "WORK_ENVIRONMENT_CHANGE")
        self.assertGreater(new["median_holding_days"], old["median_holding_days"])

    def test_daily_fit_penalizes_execution_difficulty(self) -> None:
        dna = {"X": {"compatibility_score": 90, "confidence": 0.8}}
        env = {"score": 50}
        easy = daily_fit({"security_code": "X", "market_score": 90, "execution_difficulty": 30}, dna, env)
        hard = daily_fit({"security_code": "X", "market_score": 90, "execution_difficulty": 90}, dna, env)
        self.assertGreater(easy["final_personal_fit"], hard["final_personal_fit"])


if __name__ == "__main__":
    unittest.main()
