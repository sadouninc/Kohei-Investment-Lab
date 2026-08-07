import json
import tempfile
import unittest
from pathlib import Path

from scripts.daily_knowledge_planner import (
    build_diagnostic,
    extract_output_text,
    parse_json_text,
    validate_plan,
)


class DailyKnowledgePlannerTests(unittest.TestCase):
    def valid_plan(self):
        return {
            "schema_version": 1,
            "date": "2026-08-07",
            "trade_journal": {
                "update": True,
                "summary": "daily investment conversation",
                "items": [
                    {
                        "kind": "reflection",
                        "classification": "interpretation",
                        "text": "High-volatility rising stocks fit the user's short-cycle trading style.",
                        "confidence": "medium",
                        "source": "issue",
                    }
                ],
            },
            "investor_dna": {
                "update_candidate": True,
                "items": ["high-volatility trend following"],
            },
            "framework": {
                "update_candidate": True,
                "items": ["evaluate margin balance together with price reaction"],
            },
            "company_updates": [
                {
                    "code": "3110",
                    "company": "Nittobo",
                    "topic": "margin balance",
                    "classification": "lesson",
                    "text": "Do not interpret margin balance in isolation.",
                }
            ],
            "unresolved": [],
            "routing": {
                "primary_target": "01_Portfolio/Transactions",
                "proposed_followups": ["investor_dna", "framework", "company:3110"],
            },
        }

    def test_validate_plan_accepts_expected_shape(self):
        plan = self.valid_plan()
        self.assertIs(validate_plan(plan), plan)

    def test_validate_plan_rejects_fact_upgrade_shape_errors(self):
        plan = self.valid_plan()
        plan["trade_journal"]["items"][0]["classification"] = "certain-fact"
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_validate_plan_requires_canonical_primary_target(self):
        plan = self.valid_plan()
        plan["routing"]["primary_target"] = "main"
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_parse_json_text_tolerates_json_fence(self):
        text = "```json\n" + json.dumps(self.valid_plan()) + "\n```"
        parsed = parse_json_text(text)
        self.assertEqual(parsed["date"], "2026-08-07")

    def test_extract_output_text(self):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": json.dumps(self.valid_plan())}
                    ],
                }
            ]
        }
        self.assertIn("schema_version", extract_output_text(response))

    def test_build_diagnostic_is_traceable(self):
        capture = {
            "issue": {"number": 75, "url": "https://example.test/issues/75"},
        }
        response = {
            "id": "resp_test",
            "model": "gpt-5",
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        }
        diagnostic = build_diagnostic(capture, self.valid_plan(), response, 1.234, "gpt-5")
        self.assertEqual(diagnostic["status"], "PLANNED")
        self.assertEqual(diagnostic["next_stage"], "trade-journal-integrator")
        self.assertEqual(diagnostic["issue"]["number"], 75)
        self.assertEqual(diagnostic["usage"]["total_tokens"], 150)


if __name__ == "__main__":
    unittest.main()
