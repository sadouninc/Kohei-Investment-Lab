from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

VALID_POSITION_TYPES = {"cash", "margin_long", "margin_short"}
OPEN_ACTIONS = {"buy", "open_long", "open_short"}
CLOSE_ACTIONS = {"sell", "close_long", "close_short"}


class PortfolioStateError(ValueError):
    pass


@dataclass(frozen=True)
class PositionKey:
    security_code: str | None
    security_name: str
    position_type: str
    account_type: str | None


def _quantity(value: Any) -> Decimal:
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PortfolioStateError(f"invalid quantity: {value!r}") from exc
    if quantity <= 0:
        raise PortfolioStateError(f"quantity must be positive: {value!r}")
    return quantity


def _key(row: dict[str, Any]) -> PositionKey:
    name = str(row.get("security_name") or "").strip()
    if not name:
        raise PortfolioStateError("security_name is required")
    position_type = str(row.get("position_type") or "").strip()
    if position_type not in VALID_POSITION_TYPES:
        raise PortfolioStateError(f"unknown position_type: {position_type!r}")
    code = row.get("security_code")
    account = row.get("account_type") or row.get("account")
    return PositionKey(
        str(code).strip() if code not in (None, "") else None,
        name,
        position_type,
        str(account).strip() if account not in (None, "") else None,
    )


def _expected_action(position_type: str, action: str) -> int:
    if position_type == "cash":
        if action == "buy": return 1
        if action == "sell": return -1
    elif position_type == "margin_long":
        if action in {"buy", "open_long"}: return 1
        if action in {"sell", "close_long"}: return -1
    elif position_type == "margin_short":
        if action in {"sell", "open_short"}: return 1
        if action in {"buy", "close_short"}: return -1
    raise PortfolioStateError(f"action {action!r} is incompatible with {position_type!r}")


def build_state(snapshot: dict[str, Any], trades: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build a deterministic current portfolio from a verified snapshot + trades.

    Inputs are explicit normalized facts. No quantity, position type, or action is inferred.
    Duplicate trade ids are rejected by ignoring the later duplicate and recording it.
    """
    if snapshot.get("verification_status") != "VERIFIED":
        raise PortfolioStateError("base snapshot must be VERIFIED")

    positions: dict[PositionKey, Decimal] = {}
    for row in snapshot.get("positions") or []:
        key = _key(row)
        if key in positions:
            raise PortfolioStateError(f"duplicate snapshot position: {key}")
        positions[key] = _quantity(row.get("quantity"))

    applied: list[str] = []
    duplicates: list[str] = []
    seen: set[str] = set()
    last_as_of = snapshot.get("as_of")

    ordered = sorted(trades, key=lambda row: (str(row.get("executed_at") or ""), str(row.get("trade_id") or "")))
    for trade in ordered:
        trade_id = str(trade.get("trade_id") or "").strip()
        if not trade_id:
            raise PortfolioStateError("trade_id is required")
        if trade_id in seen:
            duplicates.append(trade_id)
            continue
        seen.add(trade_id)

        key = _key(trade)
        action = str(trade.get("action") or "").strip()
        delta = _quantity(trade.get("quantity")) * _expected_action(key.position_type, action)
        new_quantity = positions.get(key, Decimal("0")) + delta
        if new_quantity < 0:
            raise PortfolioStateError(f"trade {trade_id} would make position negative: {key}")
        if new_quantity == 0:
            positions.pop(key, None)
        else:
            positions[key] = new_quantity
        applied.append(trade_id)
        last_as_of = trade.get("executed_at") or last_as_of

    rows = [
        {
            "security_code": key.security_code,
            "security_name": key.security_name,
            "position_type": key.position_type,
            "account_type": key.account_type,
            "quantity": int(qty) if qty == qty.to_integral() else str(qty),
        }
        for key, qty in sorted(positions.items(), key=lambda item: ((item[0].security_code or ""), item[0].security_name, item[0].position_type, item[0].account_type or ""))
    ]
    return {
        "as_of": last_as_of,
        "verification_status": "PROVISIONAL" if applied else "VERIFIED",
        "base_snapshot": snapshot.get("snapshot_id"),
        "positions": rows,
        "applied_trade_ids": applied,
        "duplicate_trade_ids": duplicates,
    }


def reconcile(current: dict[str, Any], verified_positions: Iterable[dict[str, Any]], *, verification_source: str, as_of: str) -> dict[str, Any]:
    """Compare calculated state with an external SBI-derived position snapshot."""
    calculated = {_key(row): _quantity(row.get("quantity")) for row in current.get("positions") or []}
    external: dict[PositionKey, Decimal] = {}
    for row in verified_positions:
        key = _key(row)
        if key in external:
            raise PortfolioStateError(f"duplicate verification position: {key}")
        external[key] = _quantity(row.get("quantity"))
    diffs = []
    for key in sorted(set(calculated) | set(external), key=lambda k: ((k.security_code or ""), k.security_name, k.position_type, k.account_type or "")):
        calc = calculated.get(key, Decimal("0"))
        actual = external.get(key, Decimal("0"))
        if calc != actual:
            diffs.append({
                "security_code": key.security_code,
                "security_name": key.security_name,
                "position_type": key.position_type,
                "account_type": key.account_type,
                "calculated_quantity": int(calc),
                "verified_quantity": int(actual),
                "difference": int(actual - calc),
            })
    result = dict(current)
    result["as_of"] = as_of
    result["verification_status"] = "VERIFIED" if not diffs else "MISMATCH"
    result["verification_source"] = verification_source
    result["verification_as_of"] = as_of
    result["verification_diff"] = diffs
    return result
