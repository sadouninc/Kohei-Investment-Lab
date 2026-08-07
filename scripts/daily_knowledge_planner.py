#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")

SYSTEM_PROMPT = """You are the Daily Knowledge Integration Planner for Sado Investment Lab.
Your job is classification and planning only. Do not edit repository files.
Use only the supplied GitHub Issue capture as factual input.
Never upgrade an interpretation or hypothesis into a confirmed fact.
Preserve uncertainty and ambiguity explicitly.
If exact trade values appear to be approximate, mark them as approximate and do not claim they override SBI CSV-derived canonical data.
Return JSON only, with no Markdown fences and no explanatory prose.

Required JSON shape:
{
  "schema_version": 1,
  "date": "YYYY-MM-DD or null",
  "trade_journal": {
    "update": true,
    "summary": "short description",
    "items": [
      {
        "kind": "trade_execution|decision|market_observation|reflection|lesson",
        "classification": "fact|interpretation|hypothesis|lesson",
        "text": "...",
        "confidence": "high|medium|low",
        "source": "issue"
      }
    ]
  },
  "investor_dna": {
    "update_candidate": false,
    "items": []
  },
  "framework": {
    "update_candidate": false,
    "items": []
  },
  "company_updates": [
    {
      "code": "optional security code",
      "company": "optional company name",
      "topic": "...",
      "classification": "fact|interpretation|hypothesis|lesson",
      "text": "..."
    }
  ],
  "unresolved": [
    {
      "text": "...",
      "reason": "..."
    }
  ],
  "routing": {
    "primary_target": "01_Portfolio/Transactions",
    "proposed_followups": []
  }
}

Rules:
- schema_version must be integer 1.
- date must be null if the issue does not establish a date.
- trade_journal.update is true only if journal-worthy investment content exists.
- investor_dna/framework are proposal-only in this phase; do not claim they were written.
- company_updates are proposal-only in this phase.
- unresolved must contain anything unsafe to write as canonical fact.
"""

ALLOWED_KINDS = {
    "trade_execution",
    "decision",
    "market_observation",
    "reflection",
    "lesson",
}
ALLOWED_CLASSIFICATIONS = {"fact", "interpretation", "hypothesis", "lesson"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def extract_output_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])
    text = "\n".join(parts).strip()
    if not text:
        raise RuntimeError("OpenAI response did not contain output_text")
    return text


def parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"planner output is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("planner output must be a JSON object")
    return payload


def _require_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")
    return value


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")

    date = plan.get("date")
    if date is not None:
        if not isinstance(date, str) or not DATE_RE.fullmatch(date):
            raise ValueError("date must be YYYY-MM-DD or null")

    journal = plan.get("trade_journal")
    if not isinstance(journal, dict):
        raise ValueError("trade_journal must be an object")
    _require_bool(journal.get("update"), "trade_journal.update")
    if not isinstance(journal.get("summary", ""), str):
        raise ValueError("trade_journal.summary must be string")
    items = journal.get("items")
    if not isinstance(items, list):
        raise ValueError("trade_journal.items must be an array")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"trade_journal.items[{index}] must be an object")
        if item.get("kind") not in ALLOWED_KINDS:
            raise ValueError(f"invalid journal kind at index {index}")
        if item.get("classification") not in ALLOWED_CLASSIFICATIONS:
            raise ValueError(f"invalid classification at index {index}")
        if item.get("confidence") not in ALLOWED_CONFIDENCE:
            raise ValueError(f"invalid confidence at index {index}")
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError(f"journal item text missing at index {index}")
        if item.get("source") != "issue":
            raise ValueError(f"journal item source must be 'issue' at index {index}")

    for key in ("investor_dna", "framework"):
        section = plan.get(key)
        if not isinstance(section, dict):
            raise ValueError(f"{key} must be an object")
        _require_bool(section.get("update_candidate"), f"{key}.update_candidate")
        if not isinstance(section.get("items"), list):
            raise ValueError(f"{key}.items must be an array")

    companies = plan.get("company_updates")
    if not isinstance(companies, list):
        raise ValueError("company_updates must be an array")
    for index, item in enumerate(companies):
        if not isinstance(item, dict):
            raise ValueError(f"company_updates[{index}] must be an object")
        if item.get("classification") not in ALLOWED_CLASSIFICATIONS:
            raise ValueError(f"invalid company classification at index {index}")
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError(f"company update text missing at index {index}")

    unresolved = plan.get("unresolved")
    if not isinstance(unresolved, list):
        raise ValueError("unresolved must be an array")
    for index, item in enumerate(unresolved):
        if not isinstance(item, dict):
            raise ValueError(f"unresolved[{index}] must be an object")
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError(f"unresolved text missing at index {index}")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise ValueError(f"unresolved reason missing at index {index}")

    routing = plan.get("routing")
    if not isinstance(routing, dict):
        raise ValueError("routing must be an object")
    if routing.get("primary_target") != "01_Portfolio/Transactions":
        raise ValueError("routing.primary_target must be 01_Portfolio/Transactions")
    if not isinstance(routing.get("proposed_followups"), list):
        raise ValueError("routing.proposed_followups must be an array")

    return plan


def call_openai(capture: dict[str, Any], *, model: str, api_key: str, timeout: int = 120) -> tuple[dict[str, Any], dict[str, Any], float]:
    body = {
        "model": model,
        "instructions": SYSTEM_PROMPT,
        "input": "Classify and plan integration for this captured Issue JSON:\n\n"
        + json.dumps(capture, ensure_ascii=False, separators=(",", ":")),
    }
    req = request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {detail[:1000]}") from exc
    elapsed = time.monotonic() - started
    plan = validate_plan(parse_json_text(extract_output_text(raw)))
    return plan, raw, elapsed


def build_diagnostic(capture: dict[str, Any], plan: dict[str, Any], response: dict[str, Any], elapsed: float, model: str) -> dict[str, Any]:
    usage = response.get("usage") or {}
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "issue": {
            "number": (capture.get("issue") or {}).get("number"),
            "url": (capture.get("issue") or {}).get("url"),
        },
        "model": response.get("model", model),
        "response_id": response.get("id"),
        "execution_seconds": round(elapsed, 3),
        "usage": {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "plan": plan,
        "status": "PLANNED",
        "next_stage": "trade-journal-integrator",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an AI integration plan for a captured daily-knowledge issue")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not configured")

    capture = json.loads(args.input.read_text(encoding="utf-8"))
    if capture.get("status") != "CAPTURED":
        raise ValueError("input diagnostic must have status CAPTURED")
    if capture.get("next_stage") != "ai-integration-planner":
        raise ValueError("input diagnostic is not routed to ai-integration-planner")

    plan, response, elapsed = call_openai(capture, model=args.model, api_key=api_key)
    diagnostic = build_diagnostic(capture, plan, response, elapsed, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Daily Knowledge plan: {args.output}")
    print(f"Issue: {diagnostic['issue']['number']}; model: {diagnostic['model']}; tokens: {diagnostic['usage']['total_tokens']}")


if __name__ == "__main__":
    main()
