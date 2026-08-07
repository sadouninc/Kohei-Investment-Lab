from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from scripts.morning_dataset.schema import STATUS_VALUES


@dataclass(frozen=True)
class ProviderResult:
    """Normalized result returned by a deterministic Morning Dataset provider."""

    name: str
    data: Any = None
    status: str = "MISSING"
    as_of: str | None = None
    source_reference: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in STATUS_VALUES:
            raise ValueError(f"Unsupported provider status: {self.status}")
        if self.status == "OK" and self.data is None:
            raise ValueError("OK provider result must contain data")
        if self.status != "OK" and not self.reason:
            raise ValueError(f"{self.status} provider result must include a reason")

    @classmethod
    def ok(
        cls,
        name: str,
        data: Any,
        *,
        as_of: str | None = None,
        source_reference: str | None = None,
    ) -> "ProviderResult":
        return cls(
            name=name,
            data=data,
            status="OK",
            as_of=as_of,
            source_reference=source_reference,
        )

    @classmethod
    def unavailable(
        cls,
        name: str,
        *,
        status: str = "MISSING",
        as_of: str | None = None,
        source_reference: str | None = None,
        reason: str,
        data: Any = None,
    ) -> "ProviderResult":
        return cls(
            name=name,
            data=data,
            status=status,
            as_of=as_of,
            source_reference=source_reference,
            reason=reason,
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "as_of": self.as_of,
            "source_reference": self.source_reference,
            "reason": self.reason,
        }


class MorningSourceProvider(Protocol):
    """Provider interface. Implementations must be deterministic and must not use AI."""

    name: str

    def collect(self) -> ProviderResult:
        ...
