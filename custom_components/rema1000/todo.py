"""The primary REMA 1000 shopping list as a to-do list."""

from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import RemaError, ShoppingListItem, split_amount
from .const import DOMAIN
from .coordinator import RemaConfigEntry, RemaShoppingListCoordinator
from .entity import RemaEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the shopping list."""
    async_add_entities([RemaShoppingListEntity(entry.runtime_data.shopping_list, entry)])


def _format_price(value: float) -> str:
    """Format a price the Danish way."""
    return f"{value:.2f}".replace(".", ",") + " kr."


def _to_todo(item: ShoppingListItem) -> TodoItem:
    """Map a REMA list line to a to-do item."""
    summary = f"{item.amount} × {item.name}" if item.amount > 1 else item.name
    details: list[str] = []
    if item.underline:
        details.append(item.underline)
    if item.total_price is not None:
        details.append(_format_price(item.total_price))
    if item.is_on_discount:
        details.append("Tilbud")
    return TodoItem(
        uid=str(item.id),
        summary=summary,
        status=TodoItemStatus.COMPLETED if item.bought else TodoItemStatus.NEEDS_ACTION,
        description=" · ".join(details) or None,
    )


class RemaShoppingListEntity(RemaEntity[RemaShoppingListCoordinator], TodoListEntity):
    """The primary shopping list, shared with the REMA 1000 app."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: RemaShoppingListCoordinator, entry: RemaConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entry, "shopping_list")
        self._entry = entry
        self._update_items()

    @callback
    def _update_items(self) -> None:
        """Rebuild the to-do items from coordinator data."""
        data = self.coordinator.data
        self._attr_todo_items = [_to_todo(item) for item in data.items] if data else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle new data from REMA."""
        self._update_items()
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Show which REMA list is used."""
        data = self.coordinator.data
        if not data:
            return None
        return {"list_id": data.id, "list_name": data.name}

    def _item(self, uid: str | None) -> ShoppingListItem:
        """Find a line on the list by uid."""
        for item in self.coordinator.data.items if self.coordinator.data else []:
            if str(item.id) == uid:
                return item
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="item_not_found",
            translation_placeholders={"uid": str(uid)},
        )

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add a line, matched to a REMA product when one fits ('3 x mælk' adds 3)."""
        if not (item.summary or "").strip():
            return
        try:
            await self._entry.runtime_data.planner.async_quick_add(item.summary)
        except RemaError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Tick off, change amount or rename a line."""
        current = self._item(item.uid)
        changes: dict[str, object] = {}
        if item.status is not None:
            bought = item.status == TodoItemStatus.COMPLETED
            if bought != current.bought:
                changes["bought"] = bought
        # Only read amount/name when the text was actually edited, so product
        # names such as "4 X 1,5 L COLA" are not mistaken for an amount.
        if item.summary is not None and item.summary != _to_todo(current).summary:
            amount, name = split_amount(item.summary)
            if amount != current.amount:
                changes["amount"] = amount
            # Products keep REMA's own name; only free-text lines can be renamed.
            if current.product_id is None and name and name != current.name:
                changes["name"] = name
        if not changes:
            return
        try:
            await self.coordinator.client.async_update_item(
                self.coordinator.data.id, current.id, **changes
            )
        except RemaError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete lines."""
        ids = [self._item(uid).id for uid in uids]
        try:
            await self.coordinator.client.async_delete_items(self.coordinator.data.id, ids)
        except RemaError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_refresh()
