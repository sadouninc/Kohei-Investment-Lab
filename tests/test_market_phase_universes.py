import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIVERSES = ROOT / "data" / "market" / "universes"


class MarketPhaseUniverseTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((UNIVERSES / name).read_text(encoding="utf-8"))

    def test_existing_semiconductor_universe_remains_40_symbols(self):
        universe = self.load("ai-semiconductor-40.json")
        self.assertEqual("ai-semiconductor-40", universe["id"])
        self.assertEqual(40, len(universe["symbols"]))

    def test_catalog_has_industry_and_ecosystem_layers(self):
        catalog = self.load("catalog.json")
        entries = {item["id"]: item for item in catalog["universes"]}
        self.assertEqual("industry", entries["ai-semiconductor-40"]["layer"])
        self.assertEqual("ecosystem", entries["ai-ecosystem-v1"]["layer"])

    def test_ecosystem_has_all_categories_and_balanced_initial_list(self):
        universe = self.load("ai-ecosystem-v1.json")
        expected = set(universe["category_order"])
        counts = {category: 0 for category in expected}
        for symbol in universe["symbols"]:
            self.assertIn(symbol["category"], expected)
            counts[symbol["category"]] += 1
        self.assertEqual(8, len(expected))
        self.assertTrue(all(count >= 5 for count in counts.values()), counts)
        self.assertGreater(len(universe["symbols"]), 40)

    def test_ecosystem_symbol_contract_and_uniqueness(self):
        universe = self.load("ai-ecosystem-v1.json")
        codes = []
        for symbol in universe["symbols"]:
            self.assertTrue({"code", "name", "category", "roles", "rationale"} <= symbol.keys())
            self.assertTrue(symbol["roles"])
            self.assertTrue(symbol["rationale"])
            codes.append(symbol["code"])
        self.assertEqual(len(codes), len(set(codes)))

    def test_ecosystem_is_broader_than_semiconductors(self):
        universe = self.load("ai-ecosystem-v1.json")
        categories = {symbol["category"] for symbol in universe["symbols"]}
        self.assertIn("AI Software / SI", categories)
        self.assertIn("Robotics / Factory Automation", categories)
        self.assertIn("Power / Cooling Infrastructure", categories)


if __name__ == "__main__":
    unittest.main()
