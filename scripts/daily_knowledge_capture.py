#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_LABEL = "daily-knowledge"


def load_event(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_diagnostic(event: dict[str, Any]) -> dict[str, Any]:
    issue = event.get("issue") or {}
    label = event.get("label") or {}
    repository = event.get("repository") or {}

    label_name = label.get("name")
    if label_name != EXPECTED_LABEL:
        raise ValueError(
            f"unsupported label: expected {EXPECTED_LABEL!r}, got {label_name!r}"
        )

    issue_number = issue.get("number")
    issue_url = issue.get("html_url")
    issue_title = issue.get("title")
    issue_body = issue.get("body") or ""

    if not isinstance(issue_number, int) or issue_number <= 0:
        raise ValueError("issue.number must be a positive integer")
    if not issue_url:
        raise ValueError("issue.html_url is required")
    if not issue_title:
        raise ValueError("issue.title is required")

    return {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "trigger": {
            "event": "issues.labeled",
            "label": label_name,
        },
        "repository": {
            "full_name": repository.get("full_name"),
            "default_branch": repository.get("default_branch"),
        },
        "issue": {
            "number": issue_number,
            "url": issue_url,
            "title": issue_title,
            "body": issue_body,
            "author": (issue.get("user") or {}).get("login"),
        },
        "next_stage": "ai-integration-planner",
        "status": "CAPTURED",
    }


def write_diagnostic(payload: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    issue_number = payload["issue"]["number"]
    path = output_dir / f"issue-{issue_number}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture a daily-knowledge GitHub issue event for later AI integration"
    )
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument(
        "--output-dir",
        default=Path("data/generated/diagnostics/daily-knowledge"),
        type=Path,
    )
    args = parser.parse_args()

    payload = build_diagnostic(load_event(args.event))
    path = write_diagnostic(payload, args.output_dir)
    print(f"Daily Knowledge diagnostic: {path}")


if __name__ == "__main__":
    main()
