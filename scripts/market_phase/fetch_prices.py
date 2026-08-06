from __future__ import annotations

import argparse
import json
import os
from abc import ABC, abstractmethod
from datetime import date, timedelta
from pathlib import Path


class PriceProvider(ABC):
    @abstractmethod
    def fetch(self, code: str, start: date, end: date) -> list[dict]: ...


class YahooFinanceProvider(PriceProvider):
    def fetch(self, code: str, start: date, end: date) -> list[dict]:
        import yfinance as yf

        frame = yf.download(
            f"{code}.T", start=start.isoformat(), end=end.isoformat(),
            auto_adjust=False, progress=False, actions=False, threads=False,
        )
        if frame.empty:
            raise RuntimeError("empty response")
        rows = []
        for stamp, row in frame.iterrows():
            def number(column):
                value = row[column]
                if hasattr(value, "iloc"):
                    value = value.iloc[0]
                return float(value)
            rows.append({
                "Date": stamp.date().isoformat(), "Open": number("Open"),
                "High": number("High"), "Low": number("Low"), "Close": number("Close"),
                "AdjustedClose": number("Adj Close"), "Volume": int(number("Volume")),
            })
        return rows


FIELDS = ["Date", "Open", "High", "Low", "Close", "AdjustedClose", "Volume"]


def write_atomic(path: Path, rows: list[dict]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=2)
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    universe = json.loads(
        (root / "data/market/universes/ai-semiconductor-40.json").read_text(encoding="utf-8")
    )
    provider = YahooFinanceProvider()
    end = date.today() + timedelta(days=1)
    failures = []
    for symbol in universe["symbols"]:
        code = symbol["code"]
        path = root / "data" / "market" / "prices" / f"{code}.csv"
        start = date.today() - timedelta(days=365 * args.years + 10)
        if path.exists():
            import csv
            existing = list(csv.DictReader(path.open(encoding="utf-8")))
            if existing:
                start = date.fromisoformat(existing[-1]["Date"]) + timedelta(days=1)
        else:
            existing = []
        try:
            new_rows = provider.fetch(code, start, end) if start < end else []
            merged = {row["Date"]: row for row in [*existing, *new_rows]}
            if merged:
                write_atomic(path, [merged[key] for key in sorted(merged)])
            print(f"{code}: {len(new_rows)} new, {len(merged)} total")
        except Exception as error:
            failures.append({"code": code, "error": str(error)})
            print(f"ERROR {code}: {error}")
            if not args.continue_on_error:
                raise
    if failures:
        print(json.dumps({"failures": failures}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
