"""Build the weekly SBI CSV intake issue without accessing portfolio data."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")
MARKER_PREFIX = "sado-weekly-sbi-input:v1"


@dataclass(frozen=True)
class WeeklyIssue:
    iso_year: int
    iso_week: int
    period_start: date
    period_end: date

    @classmethod
    def from_date(cls, target: date) -> "WeeklyIssue":
        iso_year, iso_week, _ = target.isocalendar()
        return cls(
            iso_year=iso_year,
            iso_week=iso_week,
            period_start=date.fromisocalendar(iso_year, iso_week, 1),
            period_end=date.fromisocalendar(iso_year, iso_week, 7),
        )

    @property
    def week_id(self) -> str:
        return f"{self.iso_year}-W{self.iso_week:02d}"

    @property
    def title(self) -> str:
        return f"[Weekly] SBI取引履歴CSV取込 — {self.week_id}"

    @property
    def marker(self) -> str:
        return f"<!-- {MARKER_PREFIX} week={self.week_id} -->"

    @property
    def period(self) -> str:
        return f"{self.period_start.isoformat()} 〜 {self.period_end.isoformat()}"

    def render_body(self) -> str:
        return f"""{self.marker}

# SBI取引履歴CSV 週次取込

- ISO週: `{self.week_id}`
- 対象期間: `{self.period}`（JST）
- 担当: 👑サド（入力） / ♦️ソラ（受領確認） / 🤖カイ（実装・照合）

## サドの対応

1. SBI証券から対象期間を含む取引履歴CSVを出力する
2. 数量・口座区分・取引区分などを編集せず、このIssueへ添付する
3. 現物・信用の保有一覧に変化がある場合は、照合に必要な一覧も添付する
4. 添付後、完了チェックを入れてソラへ知らせる

機密情報や口座番号など、照合に不要な個人情報は添付前に確認してください。数量やPosition Typeが不明な場合、チームは推測で補完しません。

## 完了チェック

- [ ] 対象期間を含むSBI取引履歴CSVを添付した
- [ ] ファイルが開けることを確認した
- [ ] 必要に応じて現物・信用の保有一覧を添付した
- [ ] ♦️ソラへ受領確認を依頼した
- [ ] Canonical Portfolio Stateとの照合結果を記録した
- [ ] `VERIFIED` または `MISMATCH` と根拠を記録した

## 自動処理向け情報

- kind: `weekly-sbi-csv-intake`
- schema: `v1`
- week: `{self.week_id}`
- state: `AWAITING_INPUT`
"""


def target_date(value: str | None, now: datetime | None = None) -> date:
    if value:
        return date.fromisoformat(value)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return current.astimezone(JST).date()


def has_duplicate(rows: Iterable[dict[str, Any]], issue: WeeklyIssue) -> bool:
    for row in rows:
        if row.get("title") == issue.title:
            return True
        if issue.marker in (row.get("body") or ""):
            return True
    return False


def write_outputs(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as output:
        for key, value in values.items():
            if "\n" in value:
                raise ValueError(f"GitHub output {key} must be a single line")
            output.write(f"{key}={value}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-date", help="JST calendar date (YYYY-MM-DD)")
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--existing-issues", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    issue = WeeklyIssue.from_date(target_date(args.target_date))

    if args.body_file:
        args.body_file.write_text(issue.render_body(), encoding="utf-8", newline="\n")

    outputs = {
        "title": issue.title,
        "marker": issue.marker,
        "iso_week": issue.week_id,
        "period": issue.period,
    }
    if args.existing_issues:
        rows = json.loads(args.existing_issues.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("existing issues JSON must be a list")
        outputs["duplicate"] = str(has_duplicate(rows, issue)).lower()

    if args.github_output:
        write_outputs(args.github_output, outputs)
    else:
        sys.stdout.buffer.write(f"{issue.title}\n".encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
