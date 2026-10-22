"""The family's food budget: an amount a month, and every purchase booked against it.

The month's amount is spread over its days (5.000 kr. in October is 161 kr. a
day), so a week is seven days' worth, also a week that runs into the next month.
What a week doesn't use goes on to the next week of the same month (and what it
overspends is taken from them); a new month starts afresh on the 1st.
"""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
import logging
import re
from typing import TYPE_CHECKING, Any
import uuid

from homeassistant.components import persistent_notification
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from .chains import CHAINS, REMA_ID
from .const import DOMAIN
from .dishes import household_portions

if TYPE_CHECKING:
    from .mealplan import MealPlanner
    from .storage import RemaPlanStore

_LOGGER = logging.getLogger(__name__)

MAX_PURCHASES = 5000
MAX_AMOUNT = 100_000.0
OTHER = "other"
WEEKS_SHOWN = 12
NOTIFY_SHARE = 0.8  # tell the family when this much of the week is used
WEEKDAYS_DA = ("mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag")


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def store_of(text: Any) -> str:
    """The shop a purchase is from: a Tjek dealer id, REMA's, or "other".

    Takes an id, or a name as a card payment shows it ("REMA 1000 VALBY", "Netto").
    """
    value = str(text or "").strip()
    if value == REMA_ID or value in CHAINS:
        return value
    lowered = value.lower()
    if "rema" in lowered:
        return REMA_ID
    for dealer_id, name in CHAINS.items():
        if re.search(rf"(^|\W){re.escape(name.lower())}(\W|$)", lowered):
            return dealer_id
    return OTHER


def clean_purchase(raw: Any, old: dict[str, Any] | None = None) -> dict[str, Any]:
    """A purchase as it is stored: {id, date, amount, store, note, source}."""
    if not isinstance(raw, dict):
        raise _invalid("purchase_amount")
    old = old or {}
    try:
        amount = round(float(str(raw.get("amount", old.get("amount"))).replace(",", ".")), 2)
    except (TypeError, ValueError) as err:
        raise _invalid("purchase_amount") from err
    if not 0 < amount <= MAX_AMOUNT:
        raise _invalid("purchase_amount")
    when = raw.get("date", old.get("date"))
    try:
        day = date.fromisoformat(str(when)[:10]) if when else dt_util.now().date()
    except ValueError as err:
        raise _invalid("purchase_date") from err
    if day > dt_util.now().date() + timedelta(days=1):
        raise _invalid("purchase_date")
    store = store_of(raw["store"]) if raw.get("store") else old.get("store", REMA_ID)
    note = str(raw.get("note", old.get("note")) or "").strip()[:120]
    if store == OTHER and not note and raw.get("store"):
        note = str(raw["store"]).strip()[:120]  # "Bager Jensen": the shop's own name
    return {
        "id": old.get("id") or uuid.uuid4().hex[:10],
        "date": day.isoformat(),
        "amount": amount,
        "store": store,
        "note": note,
        "source": str(old.get("source") or raw.get("source") or "panel")[:20],
        "created": old.get("created") or dt_util.now().isoformat(timespec="seconds"),
    }


async def async_add(store: RemaPlanStore, raw: Any) -> dict[str, Any]:
    """Book a purchase. Returns it."""
    purchase = clean_purchase(raw)
    store.purchases.append(purchase)
    store.purchases.sort(key=lambda p: (p["date"], p["created"]))
    del store.purchases[: max(0, len(store.purchases) - MAX_PURCHASES)]
    await store.async_save()
    return purchase


async def async_edit(store: RemaPlanStore, purchase_id: str, raw: Any) -> dict[str, Any]:
    """Change a purchase (amount, date, shop or note)."""
    old = next((p for p in store.purchases if p["id"] == purchase_id), None)
    if old is None:
        raise _invalid("purchase_not_found")
    new = clean_purchase(raw, old)
    old.clear()
    old.update(new)
    store.purchases.sort(key=lambda p: (p["date"], p["created"]))
    await store.async_save()
    return old


async def async_delete(store: RemaPlanStore, purchase_id: str) -> None:
    """Remove a purchase."""
    kept = [p for p in store.purchases if p["id"] != purchase_id]
    if len(kept) == len(store.purchases):
        raise _invalid("purchase_not_found")
    store.purchases = kept
    await store.async_save()


# ------------------------------------------------------------------ the sums


def daily_rate(monthly: float, day: date) -> float:
    """The budget for one day: the month's amount over its days."""
    return monthly / monthrange(day.year, day.month)[1]


def week_start(day: date, start_weekday: int) -> date:
    """The family's first weekday on or before a date."""
    return day - timedelta(days=(day.weekday() - start_weekday) % 7)


def week_number(start: date) -> int:
    """The week's number: the ISO week of its middle (a sunday-to-saturday week is its monday's)."""
    return (start + timedelta(days=3)).isocalendar().week


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


class Ledger:
    """The purchases, summed by day, for quick sums over any period."""

    def __init__(self, purchases: list[dict[str, Any]]) -> None:
        """Index the purchases by date."""
        self.by_day: dict[date, float] = defaultdict(float)
        self.items = purchases
        for p in purchases:
            self.by_day[date.fromisoformat(p["date"])] += p["amount"]

    def spent(self, first: date, last: date) -> float:
        """Spent from one date to another, both included."""
        if last < first:
            return 0.0
        return sum(v for d, v in self.by_day.items() if first <= d <= last)

    @property
    def first(self) -> date | None:
        """The day of the first purchase."""
        return min(self.by_day) if self.by_day else None


def since(store: RemaPlanStore) -> date:
    """The day the family started keeping the budget: days before it have no budget."""
    try:
        return date.fromisoformat(str(store.settings.get("budget_since") or "")[:10])
    except ValueError:
        return date.min


def budget_between(store: RemaPlanStore, first: date, last: date) -> float:
    """The budget for the days from one date to another (none before it was kept)."""
    monthly = float(store.settings["monthly_budget"])
    return sum(daily_rate(monthly, d) for d in _days(max(first, since(store)), last))


def week_numbers(store: RemaPlanStore, start: date, ledger: Ledger) -> dict[str, float]:
    """A week's budget, what the month brings into it, and what is spent in it."""
    end = start + timedelta(days=6)
    first = max(start.replace(day=1), since(store))
    before = start - timedelta(days=1)
    return {
        "budget": budget_between(store, start, end),
        "carry": budget_between(store, first, before) - ledger.spent(first, before),
        "spent": ledger.spent(start, end),
    }


def planned(store: RemaPlanStore, first: date, last: date) -> float:
    """What the plans' lists still to be bought cost, from one date to another.

    A line is bought on its plan's first day, or later in the week (buy_from);
    sent lines (in the REMA app) count too, until a purchase is booked that day.
    """
    total = 0.0
    seen: set[str] = set()
    for day in _days(first, last):
        plan = store.plan_covering(day)
        if plan is None or plan["id"] in seen:
            continue
        seen.add(plan["id"])
        for line in plan.get("shopping") or []:
            when = line.get("buy_from") or plan.get("start_date")
            if line.get("buy_at") or not when:  # bought in another shop: its own price
                continue
            on = date.fromisoformat(str(when)[:10])
            if first <= on <= last:
                total += float(line.get("cost") or 0)
    return total


def plan_budget(store: RemaPlanStore, start: date, today: date | None = None) -> int | None:
    """The budget for a plan that starts on a date: what is left of its week.

    What the lists to be bought before then cost is taken off. Never below 40 %
    of the week's own budget, so a plan can still be made in a week that went
    over. None when the family has no monthly budget.
    """
    if not store.settings.get("monthly_budget"):
        return None
    today = today or dt_util.now().date()
    ledger = Ledger(store.purchases)
    first = week_start(start, store.settings["start_weekday"])
    week = week_numbers(store, first, ledger)
    left = week["budget"] + week["carry"] - week["spent"]
    if start > today:
        before = max(today, first)
        left -= planned(store, before, start - timedelta(days=1)) if before < start else 0
    return round(max(left, week["budget"] * 0.4))


def summary(store: RemaPlanStore, today: date | None = None) -> dict[str, Any] | None:
    """Everything the economy page shows. None when there is no monthly budget."""
    monthly = float(store.settings.get("monthly_budget") or 0)
    if not monthly:
        return None
    today = today or dt_util.now().date()
    ledger = Ledger(store.purchases)
    start_weekday = store.settings["start_weekday"]
    return {
        "monthly": monthly,
        "daily": round(daily_rate(monthly, today), 2),
        "week": _week(store, ledger, today, start_weekday),
        "month": _month(store, ledger, today),
        "weeks": _weeks(store, ledger, today, start_weekday),
        "year": _year(store, ledger, today),
        "stats": _stats(store, ledger, today),
        "purchases": [
            p
            for p in reversed(store.purchases)
            if p["date"] >= (today - timedelta(days=62)).isoformat()
        ][:80],
    }


def _week(store: RemaPlanStore, ledger: Ledger, today: date, start_weekday: int) -> dict[str, Any]:
    start = week_start(today, start_weekday)
    end = start + timedelta(days=6)
    week = week_numbers(store, start, ledger)
    available = week["budget"] + week["carry"]
    remaining = available - week["spent"]
    coming = planned(store, today + timedelta(days=1), end)
    # By the end of today, at an even pace, this much would be used.
    pace = available * ((today - start).days + 1) / 7
    days_left = (end - today).days + 1
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "week": week_number(start),
        "budget": round(week["budget"], 2),
        "carry": round(week["carry"], 2),
        "available": round(available, 2),
        "spent": round(week["spent"], 2),
        "remaining": round(remaining, 2),
        "pace": round(pace, 2),
        "planned": round(coming, 2),
        "after_planned": round(remaining - coming, 2),
        "per_day": round(remaining / days_left, 2) if days_left else 0,
        "days_left": days_left,
    }


def _month(store: RemaPlanStore, ledger: Ledger, today: date) -> dict[str, Any]:
    monthly = float(store.settings["monthly_budget"])
    first = today.replace(day=1)
    last = first.replace(day=monthrange(first.year, first.month)[1])
    spent = ledger.spent(first, today)
    budget = budget_between(store, first, last)  # the first month only from the day it began
    # The family's own pace: the last eight weeks (or what there is), else the budget's.
    begin = max(today - timedelta(days=55), ledger.first or today, since(store))
    known = (today - begin).days + 1
    rate = ledger.spent(begin, today) / known if known >= 14 else daily_rate(monthly, today)
    coming = planned(store, today + timedelta(days=1), last)
    days_left = (last - today).days
    forecast = spent + max(rate * days_left, coming)
    running = 0.0
    series = []
    for day in _days(first, today):
        running += ledger.by_day.get(day, 0.0)
        series.append(round(running, 2))
    return {
        "first": first.isoformat(),
        "days": last.day,
        "budget": round(budget, 2),
        "spent": round(spent, 2),
        "remaining": round(budget - spent, 2),
        "forecast": round(forecast, 2),
        "series": series,
        "planned": round(coming, 2),
    }


def _weeks(
    store: RemaPlanStore, ledger: Ledger, today: date, start_weekday: int
) -> list[dict[str, Any]]:
    out = []
    start = week_start(today, start_weekday) - timedelta(weeks=WEEKS_SHOWN - 1)
    for _ in range(WEEKS_SHOWN):
        end = start + timedelta(days=6)
        if end >= since(store):  # not the weeks before the budget was kept
            out.append(
                {
                    "start": start.isoformat(),
                    "week": week_number(start),
                    "budget": round(budget_between(store, start, end), 2),
                    "spent": round(ledger.spent(start, end), 2),
                    "current": start <= today <= end,
                }
            )
        start += timedelta(weeks=1)
    return out


def _year(store: RemaPlanStore, ledger: Ledger, today: date) -> dict[str, Any]:
    months: list[dict[str, Any]] = []
    began = since(store)
    for number in range(1, 13):
        first = date(today.year, number, 1)
        last = first.replace(day=monthrange(today.year, number)[1])
        kept = last >= began
        months.append(
            {
                "month": number,
                "spent": round(ledger.spent(first, min(last, today)), 2)
                if kept and first <= today
                else None,
                "budget": round(budget_between(store, first, last), 2) if kept else None,
            }
        )
    done = [m for m in months if m["spent"] is not None and m["month"] < today.month]
    return {
        "year": today.year,
        "months": months,
        "spent": round(sum(m["spent"] or 0 for m in months), 2),
        "budget": round(sum(m["budget"] or 0 for m in months), 2),
        "average": round(sum(m["spent"] or 0 for m in done) / len(done), 2) if done else None,
    }


def _stats(store: RemaPlanStore, ledger: Ledger, today: date) -> dict[str, Any]:
    recent = [p for p in ledger.items if p["date"] >= (today - timedelta(days=90)).isoformat()]
    by_weekday: dict[int, list[float]] = defaultdict(list)
    by_store: dict[str, float] = defaultdict(float)
    per_day: dict[str, float] = defaultdict(float)
    for p in recent:
        per_day[p["date"]] += p["amount"]
        by_store[p["store"]] += p["amount"]
    for day, amount in per_day.items():
        by_weekday[date.fromisoformat(day).weekday()].append(amount)
    trips: list[dict[str, Any]] = sorted(
        (
            {"weekday": WEEKDAYS_DA[wd], "average": round(sum(v) / len(v), 2), "count": len(v)}
            for wd, v in by_weekday.items()
        ),
        key=lambda t: -int(t["count"]),
    )
    # Two shopping days are the plan; the rest are extra trips.
    main = {t["weekday"] for t in trips[:2] if t["count"] >= 2}
    extra = [
        amount
        for day, amount in per_day.items()
        if WEEKDAYS_DA[date.fromisoformat(day).weekday()] not in main
    ]
    first = today.replace(day=1)
    spent_month = ledger.spent(first, today)
    portions = household_portions(store.settings)
    days = (today - max(first, since(store))).days + 1
    saved, sent = _month_lists(store, first, today)
    return {
        "trips": trips[:3],
        # Only once the usual shopping days show (at least twice each in 90 days).
        "extra_trips": len(extra) if main else None,
        "extra_average": round(sum(extra) / len(extra), 2) if main and extra else None,
        "per_portion_day": round(spent_month / days / portions, 2) if spent_month else None,
        "stores": sorted(
            ({"store": s, "amount": round(v, 2)} for s, v in by_store.items()),
            key=lambda s: -s["amount"],
        ),
        "saved_on_offers": round(saved, 2),
        "outside_lists": round(spent_month - sent, 2) if sent else None,
    }


def _month_lists(store: RemaPlanStore, first: date, today: date) -> tuple[float, float]:
    """(saved on offers, what the lists cost) for the lines sent this month."""
    saved = 0.0
    cost = 0.0
    for plan in store.plans:
        for line in plan.get("shopping") or []:
            sent = str(line.get("sent") or "")[:10]
            if not sent or not first.isoformat() <= sent <= today.isoformat():
                continue
            cost += float(line.get("cost") or 0)
            product = line.get("product") or {}
            normal, price = product.get("normal_price"), product.get("price")
            if normal and price and normal > price:
                saved += (normal - price) * int(line.get("packages") or 1)
    return saved, cost


# ------------------------------------------------------------------ telling the family


def crossed(store: RemaPlanStore, today: date | None = None) -> dict[str, Any] | None:
    """The week, if this purchase took it past 80 % (once a week)."""
    data = summary(store, today)
    if data is None or not store.settings.get("budget_notify"):
        return None
    week = data["week"]
    if week["available"] <= 0 or week["spent"] < week["available"] * NOTIFY_SHARE:
        return None
    if store.budget_told == week["start"]:
        return None
    store.budget_told = week["start"]
    told: dict[str, Any] = week
    return told


def format_kr(value: float) -> str:
    """1127.4 -> '1.127 kr.'"""
    return f"{round(value):,} kr.".replace(",", ".")


def week_message(week: dict[str, Any]) -> tuple[str, str]:
    """(title, message) for the notification."""
    if week["remaining"] < 0:
        title = f"💸 Ugens madbudget er overskredet med {format_kr(-week['remaining'])}"
    else:
        title = f"💰 {format_kr(week['remaining'])} tilbage af ugens madbudget"
    message = f"Brugt {format_kr(week['spent'])} af {format_kr(week['available'])}"
    if week["planned"]:
        message += f" – resten af ugens lister er anslået til {format_kr(week['planned'])}"
    return title, message


async def async_book(planner: MealPlanner, raw: Any) -> dict[str, Any]:
    """Book a purchase, tell the family if the week is nearly used, and return the summary."""
    store = planner.store
    if not store.settings.get("monthly_budget"):
        raise _invalid("no_monthly_budget")
    await async_add(store, raw)
    if (week := crossed(store)) is not None:
        await store.async_save()
        await _async_tell(planner, *week_message(week))
    planner._notify()
    data = summary(store)
    assert data is not None
    return data


async def _async_tell(planner: MealPlanner, title: str, message: str) -> None:
    target = str(planner.store.settings.get("watch_notify") or "")
    try:
        if target == "persistent_notification":
            persistent_notification.async_create(
                planner.hass, message, title, notification_id=f"{DOMAIN}_budget"
            )
        elif target.startswith("notify."):
            await planner.hass.services.async_call(
                "notify",
                target.removeprefix("notify."),
                {
                    "title": title,
                    "message": message,
                    "data": {
                        "url": "/middagsro",
                        "clickAction": "/middagsro",
                        "notification_icon": "mdi:wallet-outline",
                        "tag": f"{DOMAIN}-budget",
                    },
                },
                blocking=True,
            )
    except (HomeAssistantError, ValueError) as err:
        _LOGGER.warning("Could not tell about the food budget: %s", err)
