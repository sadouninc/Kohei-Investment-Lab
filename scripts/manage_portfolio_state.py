#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.current_status_refresh import refresh_portfolio
from scripts.portfolio_repository import (
    build_from_repository,
    promote_verified_snapshot,
    read_json,
    verify_state,
    write_json_atomic,
)
from scripts.portfolio_state import PortfolioStateError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and persist Canonical Portfolio State from explicit repository facts"
    )
    parser.add_argument("--snapshot-dir", type=Path, default=Path("data/portfolio/snapshots"))
    parser.add_argument("--database", type=Path, default=Path("data/database/investment_lab.sqlite"))
    parser.add_argument("--output", type=Path, default=Path("data/portfolio/current.json"))
    parser.add_argument("--verify-positions", type=Path, help="explicit SBI-derived position snapshot JSON")
    parser.add_argument("--verification-source", help="required with --verify-positions")
    parser.add_argument("--verification-as-of", help="required with --verify-positions")
    parser.add_argument("--promote-verified", action="store_true")
    parser.add_argument("--refresh-current-status", type=Path)
    args = parser.parse_args()

    try:
        state = build_from_repository(args.snapshot_dir, args.database)
        if args.verify_positions:
            if not args.verification_source or not args.verification_as_of:
                parser.error("--verification-source and --verification-as-of are required with --verify-positions")
            payload = read_json(args.verify_positions)
            positions = payload.get("positions")
            if not isinstance(positions, list):
                raise PortfolioStateError("verification positions JSON requires a positions list")
            state = verify_state(
                state,
                positions,
                verification_source=args.verification_source,
                as_of=args.verification_as_of,
            )
        write_json_atomic(args.output, state)
        if args.promote_verified:
            promote_verified_snapshot(state, args.snapshot_dir)
        if args.refresh_current_status:
            if state.get("verification_status") == "MISMATCH":
                raise PortfolioStateError("MISMATCH state cannot refresh Current_Status.md")
            text = args.refresh_current_status.read_text(encoding="utf-8")
            args.refresh_current_status.write_text(refresh_portfolio(text, state), encoding="utf-8")
    except PortfolioStateError as exc:
        parser.exit(2, f"portfolio state error: {exc}\n")

    print(f"Canonical Portfolio State: {args.output} ({state['verification_status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
