#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TARGET_ROOT = Path("01_Portfolio/Transactions")
SECTION_ORDER = [
    ("trade_execution", "Today's Trades"),
    ("decision", "Investment Decisions"),
    ("market_observation", "Market Recognition"),
    ("reflection", "Reflection"),
    ("lesson", "Lessons Learned"),
]


def load_plan(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "PLANNED":
        raise ValueError("input diagnostic must have status PLANNED")
    if payload.get("next_stage") != "trade-journal-integrator":
        raise ValueError("input diagnostic is not routed to trade-journal-integrator")
    plan = payload.get("plan")
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("invalid integration plan")
    return payload


def target_path(plan: dict[str, Any]) -> Path:
    date = plan.get("date")
    if not isinstance(date, str) or not date:
        raise ValueError("Trade Journal update requires a confirmed plan date")
    return TARGET_ROOT / f"{date}.md"


def render_entry(plan: dict[str, Any], issue_number: int | None) -> str:
    journal = plan["trade_journal"]
    if not journal.get("update"):
        return ""
    items = journal.get("items") or []
    lines = [f"# Trade Journal — {plan['date']}", "", f"## {plan['date']}", ""]
    summary = str(journal.get("summary") or "").strip()
    if summary:
        lines += ["### Summary", "", summary, ""]
    for kind, heading in SECTION_ORDER:
        selected = [item for item in items if item.get("kind") == kind]
        if not selected:
            continue
        lines += [f"### {heading}", ""]
        for item in selected:
            classification = item.get("classification", "interpretation")
            confidence = item.get("confidence", "medium")
            text = str(item.get("text") or "").strip()
            lines.append(f"- {text}  ")
            lines.append(f"  - classification: `{classification}` / confidence: `{confidence}` / source: Issue #{issue_number}")
        lines.append("")
    unresolved = plan.get("unresolved") or []
    if unresolved:
        lines += ["### Unresolved / Not Canonicalized", ""]
        for item in unresolved:
            lines.append(f"- {item.get('text')} — {item.get('reason')}")
        lines.append("")
    lines += ["### Integration Note", "", "This entry was generated from a validated Daily Knowledge integration plan. Exact SBI CSV-derived trade facts remain authoritative if a conflict is found.", ""]
    return "\n".join(lines)


def integrate(existing: str | None, generated: str) -> tuple[str, bool]:
    if not generated:
        return existing or "", False
    if existing is None or not existing.strip():
        return generated, True
    marker = "### Daily Knowledge Integration"
    block = generated.split("\n", 4)[-1].strip()
    if block in existing:
        return existing, False
    merged = existing.rstrip() + "\n\n" + marker + "\n\n" + block + "\n"
    return merged, True


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply a validated Daily Knowledge plan to a Trade Journal working tree")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--repo-root", default=Path("."), type=Path)
    parser.add_argument("--diagnostic", type=Path)
    args = parser.parse_args()

    diagnostic = load_plan(args.input)
    plan = diagnostic["plan"]
    journal = plan["trade_journal"]
    issue_number = (diagnostic.get("issue") or {}).get("number")
    result: dict[str, Any] = {
        "schema_version": 1,
        "issue_number": issue_number,
        "status": "NO_CHANGE",
        "target_file": None,
        "changed": False,
        "proposals": {
            "investor_dna": plan.get("investor_dna"),
            "framework": plan.get("framework"),
            "company_updates": plan.get("company_updates"),
        },
        "unresolved": plan.get("unresolved") or [],
    }
    if journal.get("update"):
        relative = target_path(plan)
        path = args.repo_root / relative
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        content, changed = integrate(existing, render_entry(plan, issue_number))
        result["target_file"] = str(relative)
        result["changed"] = changed
        if changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            result["status"] = "UPDATED"
    if args.diagnostic:
        args.diagnostic.parent.mkdir(parents=True, exist_ok=True)
        args.diagnostic.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
