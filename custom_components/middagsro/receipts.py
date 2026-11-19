"""Work out item statistics and compact views from digital receipts.

The Scan Selv backend returns full receipts with their lines (api.py). Here we
turn the whole history into:

* a per-item summary for the "Varer" tab - how often each item was bought, its
  lowest and highest unit price, and the most recent one, and
* compact receipt summaries for the "Indkøb" tab (the full receipt, with its
  lines, is sent on demand).
"""

from __future__ import annotations

from typing import Any

from .api import Receipt

# An item bought more than this many times is flagged as a regular buy.
FREQUENT_THRESHOLD = 5


def normalize_name(name: str | None) -> str:
    """A loose key so the same product groups across receipts."""
    return " ".join(str(name or "").lower().split())


def _unit_price(price: float | None, quantity: int | None) -> float | None:
    """The price of one unit, from a line's printed price and its quantity."""
    if price is None:
        return None
    qty = quantity or 1
    return round(price / qty, 2) if qty else round(price, 2)


def aggregate_items(receipts: list[Receipt]) -> list[dict[str, Any]]:
    """Every bought item across all receipts, most bought first.

    Each entry: ``{name, count, times, min_price, max_price, last_price,
    last_date, total_spent, frequent}`` where ``count`` sums the quantities,
    ``times`` counts the receipts it appeared on, and ``frequent`` marks the
    items bought more than :data:`FREQUENT_THRESHOLD` times.
    """
    agg: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        when = receipt.date.isoformat() if receipt.date else None
        for item in receipt.items:
            key = normalize_name(item.name)
            if not key:
                continue
            entry = agg.get(key)
            if entry is None:
                entry = agg[key] = {
                    "name": item.name,
                    "count": 0,
                    "times": 0,
                    "min_price": None,
                    "max_price": None,
                    "last_price": None,
                    "last_date": None,
                    "total_spent": 0.0,
                }
            entry["count"] += item.quantity or 1
            entry["times"] += 1
            unit = _unit_price(item.price, item.quantity)
            if unit is not None:
                entry["min_price"] = (
                    unit if entry["min_price"] is None else min(entry["min_price"], unit)
                )
                entry["max_price"] = (
                    unit if entry["max_price"] is None else max(entry["max_price"], unit)
                )
            if item.price is not None:
                entry["total_spent"] = round(entry["total_spent"] + item.price, 2)
            if when and (entry["last_date"] is None or when > entry["last_date"]):
                entry["last_date"] = when
                if unit is not None:
                    entry["last_price"] = unit
    items = list(agg.values())
    for entry in items:
        entry["frequent"] = entry["count"] > FREQUENT_THRESHOLD
    items.sort(key=lambda e: (-e["count"], e["name"].lower()))
    return items


def _bucket_keys(day: Any) -> dict[str, str]:
    """The week/month/year bucket keys for a date."""
    iso_year, iso_week, _ = day.isocalendar()
    return {
        "week": f"{iso_year}-W{iso_week:02d}",
        "month": f"{day.year}-{day.month:02d}",
        "year": f"{day.year}",
    }


# How many of the most recent buckets to send per granularity (keeps the chart
# legible and the payload small); stats are computed over what is sent.
_WINDOW = {"week": 26, "month": 12, "year": 6}


def _granularity(buckets: dict[str, dict[str, Any]], limit: int) -> dict[str, Any]:
    """Order a granularity's buckets, keep the most recent, and sum up the stats."""
    ordered = [buckets[key] for key in sorted(buckets)]
    shown = ordered[-limit:]
    with_spend = [b for b in shown if b["count"]]
    high = max(with_spend, key=lambda b: b["spent"], default=None)
    low = min(with_spend, key=lambda b: b["spent"], default=None)
    avg = round(sum(b["spent"] for b in with_spend) / len(with_spend), 2) if with_spend else 0.0
    return {
        "buckets": shown,
        "high": {"key": high["key"], "spent": high["spent"]} if high else None,
        "low": {"key": low["key"], "spent": low["spent"]} if low else None,
        "avg": avg,
        "saved_total": round(sum(b["saved"] for b in shown), 2),
        "total": round(sum(b["spent"] for b in shown), 2),
    }


def spending_overview(receipts: list[Receipt]) -> dict[str, Any]:
    """REMA spend grouped by week, month and year, with high/low/average/saved.

    Built straight from the receipts (not the budget), so it is REMA-only and
    never double-counts the family's other booked purchases. Each granularity:
    ``{buckets: [{key, spent, saved, count}], high, low, avg, saved_total, total}``.
    """
    grans: dict[str, dict[str, dict[str, Any]]] = {"week": {}, "month": {}, "year": {}}
    for receipt in receipts:
        if receipt.date is None or not receipt.total:
            continue
        day = receipt.date.date()
        total = round(float(receipt.total), 2)
        saved = round(float(receipt.total_discount or 0.0), 2)
        for gran, key in _bucket_keys(day).items():
            bucket = grans[gran].get(key)
            if bucket is None:
                bucket = grans[gran][key] = {"key": key, "spent": 0.0, "saved": 0.0, "count": 0}
            bucket["spent"] = round(bucket["spent"] + total, 2)
            bucket["saved"] = round(bucket["saved"] + saved, 2)
            bucket["count"] += 1
    return {gran: _granularity(grans[gran], _WINDOW[gran]) for gran in grans}


def receipt_summary(receipt: Receipt) -> dict[str, Any]:
    """A compact receipt for the list (the lines are fetched on demand)."""
    store = receipt.store
    return {
        "id": receipt.id,
        "display_id": receipt.display_id,
        "date": receipt.date.isoformat() if receipt.date else None,
        "total": receipt.total,
        "gross": receipt.gross,
        "total_discount": receipt.total_discount,
        "items": len(receipt.items),
        "store": store.name if store else None,
        "city": store.city if store else None,
    }
