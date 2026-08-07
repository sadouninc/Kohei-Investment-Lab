from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .base import ProviderResult


class JsonFileProvider:
    """Deterministic provider for repository-generated JSON sources."""

    def __init__(
        self,
        name: str,
        path: Path,
        *,
        as_of_getter: Callable[[Any], str | None] | None = None,
    ) -> None:
        self.name = name
        self.path = path
        self.as_of_getter = as_of_getter or self._default_as_of

    @staticmethod
    def _default_as_of(data: Any) -> str | None:
        if isinstance(data, dict):
            value = data.get("as_of") or data.get("generated_at")
            return str(value) if value is not None else None
        return None

    def collect(self) -> ProviderResult:
        source_reference = str(self.path)
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="source file does not exist",
                source_reference=source_reference,
            )

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                reason=f"source file could not be read: {exc.__class__.__name__}",
                source_reference=source_reference,
            )

        if data is None:
            return ProviderResult.unavailable(
                self.name,
                reason="source JSON contains null",
                source_reference=source_reference,
            )

        return ProviderResult.ok(
            self.name,
            data,
            as_of=self.as_of_getter(data),
            source_reference=source_reference,
        )
