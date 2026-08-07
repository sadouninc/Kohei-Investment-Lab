from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .base import MorningSourceProvider, ProviderResult

EXPECTED_SOURCES = (
    "market",
    "portfolio",
    "capital",
    "candidates",
    "investor_dna",
    "events",
    "watchlist",
)


def collect_providers(providers: Iterable[MorningSourceProvider]) -> dict[str, ProviderResult]:
    """Collect providers once and return normalized results keyed by source name."""
    results: dict[str, ProviderResult] = {}
    for provider in providers:
        if provider.name in results:
            raise ValueError(f"Duplicate Morning Dataset provider: {provider.name}")
        result = provider.collect()
        if result.name != provider.name:
            raise ValueError(
                f"Provider name mismatch: provider={provider.name}, result={result.name}"
            )
        results[provider.name] = result
    return results


def dataset_inputs(results: dict[str, ProviderResult]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Convert provider results into build_dataset keyword values and metadata.

    Non-OK providers may still carry partial/stale data; data is preserved when
    present while status metadata remains explicit.
    """
    values: dict[str, Any] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for name in EXPECTED_SOURCES:
        result = results.get(name)
        if result is None:
            values[name] = None
            metadata[name] = {
                "status": "MISSING",
                "as_of": None,
                "source_reference": None,
                "reason": "provider not configured",
            }
            continue
        values[name] = result.data
        metadata[name] = result.metadata()
    return values, metadata
