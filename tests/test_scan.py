"""Tests for reading a recipe from photos of a cookbook page."""

from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.middagsro import media_source as ms, recipes as rc
import homeassistant.components.ai_task as ai_task_component  # noqa: F401 - patched in the tests
from homeassistant.components.media_source import MediaSourceItem, Unresolvable
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

PHOTO = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff jpeg").decode()
RECIPE = {
    "name": "Mormors frikadeller",
    "type": "normal",
    "servings": 4,
    "ingredients": [{"name": "hakket svine- og kalvekød", "amount": "500 g"}],
    "steps": [{"text": "Rør farsen.", "minutes": 5}, {"text": "Steg dem.", "minutes": 15}],
}


def _all_gone(paths: list[Path]) -> bool:
    return bool(paths) and not any(path.exists() for path in paths)


async def _ws(client: Any, msg_id: int, **msg: Any) -> dict[str, Any]:
    await client.send_json({"id": msg_id, **msg})
    result: dict[str, Any] = await client.receive_json()
    return result


async def test_media_source(hass: HomeAssistant, tmp_path: Any) -> None:
    """The photos are only there for the AI, while it reads them."""
    source = await ms.async_get_media_source(hass)
    item = MediaSourceItem(hass, "middagsro", "abc", None)
    with pytest.raises(Unresolvable):
        await source.async_resolve_media(item)
    ms.SCANS["abc"] = ms.ScannedPage(tmp_path / "a.jpg", "image/jpeg")
    media = await source.async_resolve_media(item)
    assert (media.path, media.mime_type) == (tmp_path / "a.jpg", "image/jpeg")
    del ms.SCANS["abc"]
    assert (await source.async_browse_media(item)).children == []


def test_decode_photo() -> None:
    """A data URL, or plain base64; never something else or too big."""
    assert rc._decode_photo(base64.b64encode(b"x").decode()) == (b"x", "image/jpeg")
    for bad in (
        "data:text/plain;base64,eA==",
        "data:image/png;base64,***",
        "",
        "data:image/png;base64,",
    ):
        with pytest.raises(ServiceValidationError):
            rc._decode_photo(bad)
    with patch.object(rc, "MAX_SCAN_BYTES", 2), pytest.raises(ServiceValidationError):
        rc._decode_photo(base64.b64encode(b"xyz").decode())
    assert "2 billeder" in rc.build_scan_prompt(2)
    assert "billedet" in rc.build_scan_prompt(1)


async def test_scan(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    ai_task: str,
) -> None:
    """The AI reads the photos; the recipe comes back to be edited, not saved."""
    planner = init_integration.runtime_data.planner
    client = await hass_ws_client(hass)
    seen: list[dict[str, Any]] = []
    seen_paths: list[Path] = []

    async def ai(hass: HomeAssistant, **kwargs: Any) -> SimpleNamespace:
        seen.append(kwargs)
        for attachment in kwargs["attachments"]:
            key = attachment["media_content_id"].removeprefix("media-source://middagsro/")
            seen_paths.append(ms.SCANS[key].path)  # there while the AI reads it
        return SimpleNamespace(data=RECIPE)

    with patch("homeassistant.components.ai_task.async_generate_data", new=ai):
        msg = await _ws(client, 1, type="middagsro/recipes/scan", photos=[PHOTO, PHOTO])
    assert msg["success"]
    recipe = msg["result"]
    assert (recipe["name"], recipe["source"], recipe["id"]) == ("Mormors frikadeller", "scan", None)
    assert len(seen[0]["attachments"]) == 2
    assert seen[0]["attachments"][0]["media_content_type"] == "image/jpeg"
    assert ms.SCANS == {}  # gone again
    assert _all_gone(seen_paths)
    assert init_integration.runtime_data.store.recipes == []

    # No recipe in the photo, or the AI fails.
    for answer in ({"name": None}, HomeAssistantError("for stort billede")):

        async def failing(hass: HomeAssistant, answer: Any = answer, **kwargs: Any) -> Any:
            if isinstance(answer, Exception):
                raise answer
            return SimpleNamespace(data=answer)

        with (
            patch("homeassistant.components.ai_task.async_generate_data", new=failing),
            pytest.raises(ServiceValidationError) as err,
        ):
            await rc.async_scan(planner, [PHOTO])
        assert err.value.translation_key in ("recipe_not_in_photo", "recipe_scan_failed")
    assert ms.SCANS == {}

    with pytest.raises(ServiceValidationError):
        await rc.async_scan(planner, [])
    msg = await _ws(
        client, 2, type="middagsro/recipes/scan", photos=["data:text/plain;base64,eA=="]
    )
    assert msg["error"]["message"] == "Billedet kunne ikke læses. Prøv at tage det igen"


async def test_scan_needs_an_ai_task(
    hass: HomeAssistant, init_integration: MockConfigEntry, ai_task: str
) -> None:
    """A conversation agent can't read photos."""
    planner = init_integration.runtime_data.planner
    store = init_integration.runtime_data.store
    assert planner.ai_task_available()
    hass.states.async_set("conversation.litellm", "unknown")
    await store.async_set_settings({**store.settings, "ai_task_entity": "conversation.litellm"})
    assert not planner.ai_task_available()
    with pytest.raises(ServiceValidationError) as err:
        await rc.async_scan(planner, [PHOTO])
    assert err.value.translation_key == "scan_needs_ai_task"


async def test_ai_task_preferred(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """No AI Task entity, but one is preferred in Home Assistant; or none at all."""
    planner = init_integration.runtime_data.planner
    assert not planner.ai_task_available()
    with patch.dict(hass.data, {"ai_task_preferences": SimpleNamespace(gen_data_entity_id="x")}):
        assert planner.ai_task_available()
