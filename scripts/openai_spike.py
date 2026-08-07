#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI


OUTPUT = Path("data/generated/openai/api-test.json")


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = os.environ.get("OPENAI_MODEL", "gpt-5")
    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        input=(
            "You are performing a connectivity test for Sado Investment Lab. "
            "Return exactly this JSON object and nothing else: "
            '{"status":"OK","message":"OpenAI API connected successfully."}'
        ),
    )

    text = response.output_text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI response was not valid JSON: {text!r}") from exc

    if payload.get("status") != "OK":
        raise RuntimeError(f"Unexpected API response: {payload}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Do not print credentials or request headers. Only print non-sensitive result data.
    print(payload["message"])
    print(f"model={model}")
    print(f"artifact={OUTPUT}")


if __name__ == "__main__":
    main()
