"""Work out item statistics and compact views from digital receipts.

The Scan Selv backend returns full receipts with their lines (api.py). Here we
turn the whole history into:

* a per-item summary for the "Varer" tab - how often each item was bought, its
  lowest and highest unit price, and the most recent one, and
* compact receipt summaries for the "Indkøb" tab (the full receipt, with its
  lines, is sent on demand).

A line's ``price`` is what one piece cost (after its discount), and ``quantity``
how many: the line's total is the two multiplied. Every receipt is also split on
the eight varegrupper (groups.py), scaled to what the receipt cost.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, tzinfo
from typing import Any

from .api import Receipt, ReceiptItem
from .groups import GROUPS, group_of

# An item bought more than this many times is flagged as a regular buy.
FREQUENT_THRESHOLD = 5


def normalize_name(name: str | None) -> str:
    """A loose key so the same product groups across receipts."""
    return " ".join(str(name or "").lower().split())


def line_total(item: ReceiptItem) -> float | None:
    """What a line cost: the price of one piece times how many."""
    if item.price is None:
        return None
    return round(item.price * (item.quantity or 1), 2)


def receipt_groups(receipt: Receipt) -> dict[str, float]:
    """What a receipt went to, per varegruppe, scaled to what was paid.

    The lines do not always add up to the total (deposits, rounding), so the
    groups keep their shares and the receipt's total decides the size.
    """
    sums: dict[str, float] = {}
    for item in receipt.items:
        total = line_total(item)
        if total is None or total <= 0:
            continue
        group = group_of(item.name)
        sums[group] = sums.get(group, 0.0) + total
    lines = sum(sums.values())
    paid = float(receipt.total) if receipt.total else lines
    if not lines or not paid:
        return {}
    return {g: round(sums[g] / lines * paid, 2) for g in GROUPS if sums.get(g)}


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
                    "group": group_of(item.name),
                }
            entry["count"] += item.quantity or 1
            entry["times"] += 1
            unit = round(item.price, 2) if item.price is not None else None
            if unit is not None:
                entry["min_price"] = (
                    unit if entry["min_price"] is None else min(entry["min_price"], unit)
                )
                entry["max_price"] = (
                    unit if entry["max_price"] is None else max(entry["max_price"], unit)
                )
            total = line_total(item)
            if total is not None:
                entry["total_spent"] = round(entry["total_spent"] + total, 2)
            if when and (entry["last_date"] is None or when > entry["last_date"]):
                entry["last_date"] = when
                if unit is not None:
                    entry["last_price"] = unit
    items = list(agg.values())
    for entry in items:
        entry["frequent"] = entry["count"] > FREQUENT_THRESHOLD
    items.sort(key=lambda e: (-e["count"], e["name"].lower()))
    return items


def _local(when: datetime, tz: tzinfo | None) -> datetime:
    """A receipt's time where the family lives (receipts come in UTC)."""
    if tz is None or when.tzinfo is None:
        return when
    return when.astimezone(tz)


def _week_start(day: date) -> date:
    """The Sunday a Middagsro week starts on (the budget's week)."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def _bucket_keys(day: date) -> dict[str, str]:
    """The week/month/year bucket keys for a date (weeks start on Sunday)."""
    return {
        "week": _week_start(day).isoformat(),
        "month": f"{day.year}-{day.month:02d}",
        "year": f"{day.year}",
    }


# How many of the most recent buckets to send per granularity: one turn of the
# panel's clock is a year in weeks and in months, and five years in years.
_WINDOW = {"week": 52, "month": 12, "year": 6}


def _fill_weeks(buckets: dict[str, dict[str, Any]], today: date | None) -> None:
    """Weeks without a trip are there too, so a year is always 52 weeks round."""
    if not buckets:
        return
    last = _week_start(today) if today else max(date.fromisoformat(k) for k in buckets)
    for n in range(_WINDOW["week"]):
        key = (last - timedelta(weeks=n)).isoformat()
        buckets.setdefault(key, _empty(key, week=True))


def _empty(key: str, week: bool = False) -> dict[str, Any]:
    bucket: dict[str, Any] = {"key": key, "spent": 0.0, "saved": 0.0, "count": 0, "groups": {}}
    if week:
        bucket["days"] = [0.0] * 7
    return bucket


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


def spending_overview(
    receipts: list[Receipt], tz: tzinfo | None = None, today: date | None = None
) -> dict[str, Any]:
    """REMA spend by week (from Sunday), month and year, and the family's rhythm.

    Built straight from the receipts (not the budget), so it is REMA-only and
    never double-counts the family's other booked purchases. Each granularity:
    ``{buckets: [{key, spent, saved, count, groups[, days]}], high, low, avg,
    saved_total, total}``; a week's ``days`` is what each weekday took, Sunday
    first. ``rhythm`` has every trip by weekday (``[[trips, kroner]] * 7``, Sunday
    first) and by hour of the day, all of them and Sundays alone.
    """
    grans: dict[str, dict[str, dict[str, Any]]] = {"week": {}, "month": {}, "year": {}}
    weekdays = [[0, 0.0] for _ in range(7)]
    hours = [0] * 24
    sunday_hours = [0] * 24
    for receipt in receipts:
        if receipt.date is None or not receipt.total:
            continue
        when = _local(receipt.date, tz)
        day = when.date()
        weekday = (day.weekday() + 1) % 7  # Sunday = 0
        total = round(float(receipt.total), 2)
        saved = round(float(receipt.total_discount or 0.0), 2)
        groups = receipt_groups(receipt)
        weekdays[weekday][0] += 1
        weekdays[weekday][1] = round(weekdays[weekday][1] + total, 2)
        hours[when.hour] += 1
        if weekday == 0:
            sunday_hours[when.hour] += 1
        for gran, key in _bucket_keys(day).items():
            bucket = grans[gran].get(key)
            if bucket is None:
                bucket = grans[gran][key] = _empty(key, week=gran == "week")
            bucket["spent"] = round(bucket["spent"] + total, 2)
            bucket["saved"] = round(bucket["saved"] + saved, 2)
            bucket["count"] += 1
            for group, amount in groups.items():
                bucket["groups"][group] = round(bucket["groups"].get(group, 0.0) + amount, 2)
            if gran == "week":
                bucket["days"][weekday] = round(bucket["days"][weekday] + total, 2)
    _fill_weeks(grans["week"], today)
    result: dict[str, Any] = {gran: _granularity(grans[gran], _WINDOW[gran]) for gran in grans}
    result["rhythm"] = {"weekdays": weekdays, "hours": hours, "sunday_hours": sunday_hours}
    return result


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
        "groups": receipt_groups(receipt),
        "store": store.name if store else None,
        "city": store.city if store else None,
    }
