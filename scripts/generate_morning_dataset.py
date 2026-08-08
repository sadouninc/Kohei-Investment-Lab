#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.morning_dataset.generator import (
    build_dataset,
    build_dataset_from_providers,
    load_json_source,
    write_dataset,
)
from scripts.morning_dataset.providers import (
    CapitalProvider,
    CandidatesProvider,
    JsonFileProvider,
    MarketProvider,
    PortfolioProvider,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Morning Dataset v1")
    parser.add_argument("--market")
    parser.add_argument("--live-market", action="store_true", help="collect the public market snapshot via MarketProvider")
    parser.add_argument("--portfolio")
    parser.add_argument("--repo-portfolio", action="store_true", help="collect portfolio from repository Current_Status.md")
    parser.add_argument("--capital")
    parser.add_argument("--repo-capital", action="store_true", help="collect latest capital snapshot from repository history.db")
    parser.add_argument("--candidates")
    parser.add_argument("--repo-candidates", action="store_true", help="collect latest candidate snapshot from repository history.db")
    parser.add_argument("--investor-dna")
    parser.add_argument("--events")
    parser.add_argument("--watchlist")
    parser.add_argument("--output", default="data/generated/public/morning-dataset.json")
    args = parser.parse_args()

    if args.live_market and args.market:
        parser.error("--live-market and --market are mutually exclusive")
    if args.repo_portfolio and args.portfolio:
        parser.error("--repo-portfolio and --portfolio are mutually exclusive")
    if args.repo_capital and args.capital:
        parser.error("--repo-capital and --capital are mutually exclusive")
    if args.repo_candidates and args.candidates:
        parser.error("--repo-candidates and --candidates are mutually exclusive")

    source_paths = {
        "market": args.market,
        "portfolio": args.portfolio,
        "capital": args.capital,
        "candidates": args.candidates,
        "investor_dna": args.investor_dna,
        "events": args.events,
        "watchlist": args.watchlist,
    }

    if args.live_market or args.repo_portfolio or args.repo_capital or args.repo_candidates:
        providers = []
        if args.live_market:
            providers.append(MarketProvider())
        if args.repo_portfolio:
            providers.append(PortfolioProvider(Path("Current_Status.md")))
        if args.repo_capital:
            providers.append(CapitalProvider(Path("data/database/history.db")))
        if args.repo_candidates:
            providers.append(CandidatesProvider(Path("data/database/history.db")))
        providers.extend(
            JsonFileProvider(name, Path(path))
            for name, path in source_paths.items()
            if path
            and not (name == "market" and args.live_market)
            and not (name == "portfolio" and args.repo_portfolio)
            and not (name == "capital" and args.repo_capital)
            and not (name == "candidates" and args.repo_candidates)
        )
        dataset = build_dataset_from_providers(providers)
    else:
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
    quality = dataset.get("data_quality") or {}
    print(f"Completeness: {quality.get('completeness_count', '—')} / status={quality.get('status', '—')}")


if __name__ == "__main__":
    main()
