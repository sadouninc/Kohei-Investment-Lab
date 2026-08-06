from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.market_phase.analysis import (
    cluster, correlation_matrix, cycle_summary, daily_returns, lead_lag, normalize, top_pairs,
)


def read_prices(path: Path) -> dict[str, float]:
    rows: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            value = row.get("AdjustedClose") or row.get("Adj Close") or row.get("Close")
            if value not in (None, ""):
                rows[row["Date"]] = float(value)
    return rows


def build_report(universe_path: Path, prices_dir: Path) -> dict:
    universe = json.loads(universe_path.read_text(encoding="utf-8"))
    metadata = {row["code"]: row for row in universe["symbols"]}
    prices, quality, excluded = {}, {}, []
    for code, meta in metadata.items():
        path = prices_dir / f"{code}.csv"
        if not path.exists():
            excluded.append({"code": code, "reason": "price_file_missing"})
            continue
        values = read_prices(path)
        if len(values) < 21:
            excluded.append({"code": code, "reason": "insufficient_history", "rows": len(values)})
            continue
        prices[code] = values
        quality[code] = {
            "rows": len(values), "start": min(values), "end": max(values),
            "missing_values": 0,
        }
    returns = {code: daily_returns(values) for code, values in prices.items()}
    pearson_matrix, samples = correlation_matrix(returns, "pearson")
    spearman_matrix, _ = correlation_matrix(returns, "spearman")
    assignments = cluster(pearson_matrix)
    clusters_by_period = {}
    for label, days in (("3m", 66), ("6m", 132), ("1y", 252)):
        period_returns = {
            code: dict(list(values.items())[-days:])
            for code, values in returns.items()
        }
        period_matrix, _ = correlation_matrix(period_returns, "pearson")
        clusters_by_period[label] = cluster(period_matrix)
    return {
        "schema_version": 1,
        "universe": {"id": universe["id"], "name": universe["name"], "requested": len(metadata)},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "symbols": [
            {**metadata[code], "cluster": assignments.get(code)}
            for code in sorted(prices)
        ],
        "normalized": {code: normalize(values) for code, values in prices.items()},
        "correlation": {"pearson": pearson_matrix, "spearman": spearman_matrix, "samples": samples},
        "top_positive_pairs": top_pairs(pearson_matrix, True),
        "top_negative_pairs": top_pairs(pearson_matrix, False),
        "clusters": assignments,
        "clusters_by_period": clusters_by_period,
        "lead_lag": lead_lag(returns)[:50],
        "cycle_summary": {
            code: cycle_summary(prices[code], values)
            for code, values in returns.items()
        },
        "data_quality": {"included": len(prices), "excluded": excluded, "symbols": quality},
        "notes": [
            "相関は日次対数リターンから計算し、因果関係を示しません。",
            "先行・遅行は統計上の候補であり、サンプル外での再検証が必要です。",
            "欠損日は前方補完していません。",
        ],
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    report = build_report(
        root / "data" / "market" / "universes" / "ai-semiconductor-40.json",
        root / "data" / "market" / "prices",
    )
    output = root / "data" / "generated" / "public" / "market-phase" / "ai-semiconductor.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {output}: {report['data_quality']['included']} symbols")


if __name__ == "__main__":
    main()
