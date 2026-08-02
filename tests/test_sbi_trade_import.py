import csv
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )


def write_fixture(path):
    rows = [
        ["約定履歴照会"],
        [],
        ["商品指定", "明細数"],
        ["すべての商品", "4"],
        [],
        ["約定日", "銘柄", "銘柄コード", "取引", "預り", "約定数量",
         "約定単価", "手数料/諸経費等", "税額", "受渡金額/決済損益"],
        ["2024/07/18", "匿名A", "1001", "株式現物買", "特定", "100", "1000", "--", "--", "100000"],
        ["2024/07/19", "匿名A", "1001", "株式現物売", "特定", "100", "1100", "--", "--", "110000"],
        ["2024/07/20", "匿名B", "2002", "信用新規売", "特定", "100", "2000", "--", "--", "-200000"],
        ["2024/07/22", "匿名B", "2002", "信用返済買", "特定", "100", "1800", "--", "--", "20000"],
    ]
    with path.open("w", encoding="cp932", newline="") as f:
        csv.writer(f).writerows(rows)


class TradeImportTest(unittest.TestCase):
    def test_import_is_idempotent_and_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            source = tmp_path / "fixture.csv"
            database = tmp_path / "trades.sqlite"
            output = tmp_path / "reports"
            write_fixture(source)

            first = run("import_sbi_executions.py", "--input", source, "--database", database, "--strict")
            second = run("import_sbi_executions.py", "--input", source, "--database", database, "--strict")
            run("build_closed_trades.py", "--database", database)
            run("generate_trade_reports.py", "--database", database, "--output", output)

            self.assertIn("登録: 4件", first.stdout)
            self.assertIn("重複スキップ: 4件", second.stdout)
            db = sqlite3.connect(database)
            try:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM executions").fetchone()[0], 4)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM closed_trades").fetchone()[0], 2)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM unmatched_executions").fetchone()[0], 0)
            finally:
                db.close()
            self.assertTrue((output / "Trading_Statistics.md").is_file())
            self.assertTrue((output / "closed_trades.csv").is_file())
            self.assertTrue((output / "by_security.csv").is_file())


if __name__ == "__main__":
    unittest.main()

