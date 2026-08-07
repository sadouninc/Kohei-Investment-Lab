#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.morning_dataset.generator import build_dataset, load_json_source, write_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Morning Dataset v1")
    parser.add_argument("--market")
    parser.add_argument("--portfolio")
    parser.add_argument("--capital")
    parser.add_argument("--candidates")
    parser.add_argument("--investor-dna")
    parser.add_argument("--events")
    parser.add_argument("--watchlist")
    parser.add_argument("--output", default="data/generated/public/morning-dataset.json")
    args = parser.parse_args()

    def read(value: str | None):
        return load_json_source(Path(value)) if value else None

    dataset = build_dataset(
        market=read(args.market),
        portfolio=read(args.portfolio),
        capital=read(args.capital),
        candidates=read(args.candidates),
        investor_dna=read(args.investor_dna),
        events=read(args.events),
        watchlist=read(args.watchlist),
    )
    path = write_dataset(dataset, Path(args.output))
    print(f"Morning Dataset: {path}")


if __name__ == "__main__":
    main()
