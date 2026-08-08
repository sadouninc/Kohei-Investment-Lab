from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.morning_dataset.providers.capital import CapitalProvider


SCHEMA = """
CREATE TABLE capital_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    cash_buying_power REAL,
    margin_buying_power REAL,
    cash_ratio REAL,
    margin_exposure REAL,
    margin_ratio REAL,
    total_exposure REAL,
    reserve_amount REAL,
    source TEXT,
    source_version TEXT
);
"""


class CapitalProviderTest(unittest.TestCase):
    def database(self, root: Path, row: tuple | None = None) -> Path:
        path = root / "history.db"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(SCHEMA)
            if row is not None:
                connection.execute(
                    """
                    INSERT INTO capital_snapshots (
                        snapshot_at, cash_buying_power, margin_buying_power,
                        cash_ratio, margin_exposure, margin_ratio,
                        total_exposure, reserve_amount, source, source_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
            connection.commit()
        finally:
            connection.close()
        return path

    def test_ok_from_fresh_canonical_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-08T08:30:00+09:00", 1_200_000, 3_000_000, 0.24, 2_400_000, 0.48, 5_000_000, 500_000, "brokerage_snapshot", "v1"),
            )
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual("2026-08-08", result.as_of)
            self.assertEqual(1_200_000, result.data["buying_power"]["cash"])
            self.assertEqual(3_000_000, result.data["buying_power"]["margin"])
            self.assertEqual(2_400_000, result.data["margin_usage"]["exposure"])
            self.assertEqual(500_000, result.data["target_reserve"])
            self.assertIsNone(result.data["cash_available"])

    def test_latest_snapshot_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-07", 100, 200, None, None, None, None, None, "old", "v1"),
            )
            connection = sqlite3.connect(path)
            try:
                connection.execute(
                    "INSERT INTO capital_snapshots (snapshot_at, cash_buying_power, margin_buying_power, source) VALUES (?, ?, ?, ?)",
                    ("2026-08-08", 300, 400, "new"),
                )
                connection.commit()
            finally:
                connection.close()
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual(300, result.data["buying_power"]["cash"])
            self.assertEqual("new", result.data["capital_state"]["source"])

    def test_stale_preserves_latest_known_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-01", 100, 200, None, 300, None, None, None, "manual", "v1"),
            )
            result = CapitalProvider(path, max_age_days=3, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertEqual(100, result.data["buying_power"]["cash"])
            self.assertIn("7 days old", result.reason)

    def test_fresh_snapshot_without_buying_power_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-08", None, None, 0.30, 500, 0.20, 2_000, 200, "manual", "v1"),
            )
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual(500, result.data["margin_usage"]["exposure"])
            self.assertIn("buying-power", result.reason)

    def test_empty_snapshot_values_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(
                Path(tmp),
                ("2026-08-08", None, None, None, None, None, None, None, "manual", "v1"),
            )
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertIsNone(result.data)

    def test_no_snapshot_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.database(Path(tmp))
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

    def test_missing_database_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = CapitalProvider(Path(tmp) / "missing.db", today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

    def test_missing_table_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.db"
            sqlite3.connect(path).close()
            result = CapitalProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)


if __name__ == "__main__":
    unittest.main()
