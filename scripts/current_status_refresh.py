#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
AS_OF_RE = re.compile(r"^>\s*as_of:\s*20\d{2}-\d{2}-\d{2}\s*$", re.IGNORECASE)


def replace_section(text: str, heading: str, body: list[str]) -> str:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if HEADING_RE.match(line) and HEADING_RE.match(line).group(1).strip().lower() == heading.lower()), None)
    if start is None:
        raise ValueError(f"section not found: {heading}")
    end = next((i for i in range(start + 1, len(lines)) if HEADING_RE.match(lines[i])), len(lines))
    replacement = [lines[start], ""] + body + [""]
    return "\n".join(lines[:start] + replacement + lines[end:]).rstrip() + "\n"


def refresh_portfolio(text: str, snapshot: dict) -> str:
    as_of = snapshot.get("as_of")
    positions = snapshot.get("positions")
    if not isinstance(as_of, str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", as_of):
        raise ValueError("portfolio snapshot requires YYYY-MM-DD as_of")
    if not isinstance(positions, list) or not positions:
        raise ValueError("portfolio snapshot requires non-empty positions")
    status = snapshot.get("verification_status")
    if status not in {None, "VERIFIED", "PROVISIONAL"}:
        raise ValueError(f"portfolio snapshot cannot be published with status {status!r}")
    authority = snapshot.get("authority") or "deterministic portfolio snapshot"
    body = [f"> as_of: {as_of}", f"> authority: {authority}"]
    if status:
        body.append(f"> verification_status: {status}")
    body.append("")
    for position in positions:
        if not isinstance(position, dict):
            raise ValueError("each position must be an object")
        raw_name = position.get("name") or position.get("security_name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError("each position requires a name")
        name = raw_name.strip()
        details = position.get("details")
        if not details and position.get("position_type") and position.get("quantity") is not None:
            labels = {"cash": "現物", "margin_long": "信用買い", "margin_short": "信用売り"}
            position_type = position["position_type"]
            if position_type not in labels:
                raise ValueError(f"unknown position_type: {position_type!r}")
            details = f"{labels[position_type]}{position['quantity']}株"
        body.append(f"- {name}（{details.strip()}）" if isinstance(details, str) and details.strip() else f"- {name}")
    return replace_section(text, "Portfolio", body)


def touch_focus(text: str, as_of: str) -> str:
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", as_of):
        raise ValueError("focus as_of must be YYYY-MM-DD")
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if HEADING_RE.match(line) and HEADING_RE.match(line).group(1).strip().lower() == "current focus"), None)
    if start is None:
        raise ValueError("Current Focus section not found")
    end = next((i for i in range(start + 1, len(lines)) if HEADING_RE.match(lines[i])), len(lines))
    for i in range(start + 1, end):
        if AS_OF_RE.match(lines[i]):
            lines[i] = f"> as_of: {as_of}"
            return "\n".join(lines).rstrip() + "\n"
    lines.insert(start + 2, f"> as_of: {as_of}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely refresh independently-authoritative Current_Status sections")
    parser.add_argument("--file", type=Path, default=Path("Current_Status.md"))
    parser.add_argument("--portfolio-snapshot", type=Path)
    parser.add_argument("--confirm-focus-as-of", help="human/reviewed confirmation date; does not rewrite focus text")
    args = parser.parse_args()
    text = args.file.read_text(encoding="utf-8")
    if args.portfolio_snapshot:
        snapshot = json.loads(args.portfolio_snapshot.read_text(encoding="utf-8"))
        text = refresh_portfolio(text, snapshot)
    if args.confirm_focus_as_of:
        text = touch_focus(text, args.confirm_focus_as_of)
    args.file.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
