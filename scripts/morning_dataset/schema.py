from __future__ import annotations

SCHEMA_VERSION = "1.0"
STATUS_VALUES = {"OK", "STALE", "MISSING", "PARTIAL"}

TOP_LEVEL_FIELDS = (
    "schema_version",
    "generated_at",
    "as_of",
    "data_quality",
    "market",
    "portfolio",
    "capital",
    "candidates",
    "investor_dna",
    "events",
    "watchlist",
    "warnings",
    "source_status",
)

EMPTY_DATASET = {
    "market": {
        "phase": None,
        "indices": None,
        "breadth": None,
        "sentiment": None,
        "risk_state": None,
    },
    "portfolio": {
        "positions": None,
        "exposure": None,
        "pnl": None,
    },
    "capital": {
        "cash_available": None,
        "buying_power": None,
        "margin_usage": None,
        "target_reserve": None,
        "capital_state": None,
    },
    "candidates": None,
    "investor_dna": {
        "native_dna": None,
        "environment_fit": None,
        "style_drift": None,
        "risk_patterns": None,
    },
    "events": {
        "earnings": None,
        "economic": None,
        "company": None,
    },
    "watchlist": None,
    "warnings": [],
    "source_status": [],
}
