#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib import request, error

from scripts.morning_dataset.context_optimizer import optimize_dataset

API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")

SYSTEM_PROMPT = """You are the AI Morning Analyst for Sado Investment Lab.
Use only the supplied optimized Morning Dataset as factual input.
Never invent missing market data, prices, events, portfolio facts, or news.
Clearly distinguish facts from interpretation.
If data quality is PARTIAL, MISSING, or STALE, say so prominently.
Do not place orders and do not present output as guaranteed investment advice.
Write concise Japanese Markdown with these sections exactly:
# AI Morning Report
## データ品質
## 市場概況
## 前日の重要ポイント
## 今日の注目イベント
## 保有株へ影響しそうなテーマ
## リスク要因
## 今日の戦略
## 注目銘柄
## 次回確認時に見る条件
For sections unsupported by the dataset, write 「データ不足のため判断保留」.
"""


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


def call_openai(dataset: dict[str, Any], *, model: str, api_key: str, timeout: int = 120) -> tuple[str, dict[str, Any], float]:
    user_input = (
        "Analyze the following optimized Morning Dataset JSON. Preserve null/MISSING/PARTIAL as uncertainty.\n\n"
        + json.dumps(dataset, ensure_ascii=False, separators=(",", ":"))
    )
    body = {
        "model": model,
        "instructions": SYSTEM_PROMPT,
        "input": user_input,
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
    return extract_output_text(raw), raw, elapsed


def estimate_cost(usage: dict[str, Any]) -> tuple[float | None, str]:
    input_rate = os.environ.get("OPENAI_INPUT_COST_PER_MILLION")
    output_rate = os.environ.get("OPENAI_OUTPUT_COST_PER_MILLION")
    if not input_rate or not output_rate:
        return None, "pricing_not_configured"
    try:
        cost = (
            float(usage.get("input_tokens", 0)) * float(input_rate)
            + float(usage.get("output_tokens", 0)) * float(output_rate)
        ) / 1_000_000
    except (TypeError, ValueError):
        return None, "pricing_invalid"
    return round(cost, 6), "estimated_from_repository_variables"


def render_report(ai_markdown: str, dataset: dict[str, Any], model: str) -> str:
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    quality = dataset.get("data_quality", {})
    meta = (
        "---\n"
        f"generated_at: {generated_at}\n"
        f"dataset_as_of: {dataset.get('as_of')}\n"
        f"dataset_status: {quality.get('status')}\n"
        f"model: {model}\n"
        "source: OpenAI Responses API + optimized Morning Dataset\n"
        "---\n\n"
    )
    return meta + ai_markdown.strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AI Morning Report from Morning Dataset")
    parser.add_argument("--input", default="data/generated/public/morning-dataset.json")
    parser.add_argument("--report-dir", default="05_Daily_Reports/Morning")
    parser.add_argument("--diagnostics-dir", default="data/generated/diagnostics/openai")
    parser.add_argument("--optimized-output", default="data/generated/diagnostics/openai/optimized-morning-dataset.json")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not configured")

    input_path = Path(args.input)
    dataset = json.loads(input_path.read_text(encoding="utf-8"))
    dataset_bytes = input_path.read_bytes()
    optimized, optimization = optimize_dataset(dataset)
    if optimization["status"] != "OK":
        raise RuntimeError("Context optimizer could not reduce the Morning Dataset below the hard cap")

    optimized_path = Path(args.optimized_output)
    optimized_path.parent.mkdir(parents=True, exist_ok=True)
    optimized_path.write_text(json.dumps(optimized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_text, response, elapsed = call_openai(optimized, model=args.model, api_key=api_key)

    day = str(dataset.get("as_of") or datetime.now().astimezone().date())
    report_path = Path(args.report_dir) / f"{day}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(report_text, dataset, args.model), encoding="utf-8")

    usage = response.get("usage") or {}
    estimated_cost, cost_basis = estimate_cost(usage)
    diagnostics = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dataset_as_of": dataset.get("as_of"),
        "dataset_schema_version": dataset.get("schema_version"),
        "dataset_status": (dataset.get("data_quality") or {}).get("status"),
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "model": response.get("model", args.model),
        "response_id": response.get("id"),
        "execution_seconds": round(elapsed, 3),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "estimated_cost_usd": estimated_cost,
        "cost_basis": cost_basis,
        "context_optimization": optimization,
        "optimized_dataset_path": str(optimized_path),
        "report_path": str(report_path),
        "status": "OK",
    }
    diagnostics_path = Path(args.diagnostics_dir) / f"{day}.json"
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"AI Morning Report: {report_path}")
    print(f"Diagnostics: {diagnostics_path}")
    print(
        "Context: "
        f"{optimization['raw_dataset_chars']} -> {optimization['optimized_prompt_chars']} chars "
        f"({optimization['reduction_ratio']:.1%} reduction; ~{optimization['estimated_input_tokens']} tokens)"
    )
    print(f"Model: {diagnostics['model']}; tokens: {diagnostics['total_tokens']}")


if __name__ == "__main__":
    main()
