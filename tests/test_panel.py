"""Tests for the sidebar panel registration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.middagsro import panel
from homeassistant.components import frontend
from homeassistant.core import HomeAssistant


def test_frontend_revision_tracks_both_modules(tmp_path: Path) -> None:
    """Local test packages invalidate both panel and dashboard-card imports."""
    folder = tmp_path / "frontend"
    folder.mkdir()
    panel_file = folder / "middagsro-panel.js"
    cards_file = folder / "middagsro-cards.js"
    panel_file.write_text("panel one", encoding="utf-8")
    cards_file.write_text("cards one", encoding="utf-8")
    with patch.object(panel, "__file__", str(tmp_path / "panel.py")):
        first = panel._frontend_revision()
        assert panel._frontend_revision() == first
        panel_file.write_text("panel two", encoding="utf-8")
        second = panel._frontend_revision()
        assert second != first
        cards_file.write_text("cards two", encoding="utf-8")
        assert panel._frontend_revision() not in (first, second)


async def test_register_and_remove_panel(hass: HomeAssistant) -> None:
    """Files are served once, the panel is added once and removed again."""
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    async def fake_register(hass: HomeAssistant, **kwargs: object) -> None:
        hass.data.setdefault(frontend.DATA_PANELS, {})[kwargs["frontend_url_path"]] = kwargs

    with (
        patch.object(panel.panel_custom, "async_register_panel", side_effect=fake_register) as add,
        patch.object(panel.frontend, "async_remove_panel") as remove,
        patch.object(panel.frontend, "add_extra_js_url") as add_js,
        patch.object(panel.frontend, "remove_extra_js_url") as remove_js,
    ):
        await panel.async_register_panel(hass)
        await panel.async_register_panel(hass)  # second account: nothing new

        assert hass.http.async_register_static_paths.await_count == 2
        paths = [p for c in hass.http.async_register_static_paths.call_args_list for p in c.args[0]]
        assert [(p.url_path, p.cache_headers) for p in paths] == [
            ("/middagsro_static", True),
            ("/middagsro_app", False),
            ("/rema1000_app", False),  # home-screen apps from before 1.1.0
        ]
        add.assert_called_once()
        kwargs = add.call_args.kwargs
        assert kwargs["frontend_url_path"] == "middagsro"
        assert kwargs["webcomponent_name"] == "middagsro-panel"
        version = kwargs["config"]["version"]
        assert kwargs["module_url"] == f"/middagsro_static/middagsro-panel.js?v={version}"
        assert kwargs["require_admin"] is False
        # The dashboard cards are loaded once, on every dashboard.
        add_js.assert_called_once_with(hass, f"/middagsro_static/middagsro-cards.js?v={version}")

        panel.async_unregister_panel(hass)
        remove.assert_called_once_with(hass, "middagsro")
        remove_js.assert_called_once_with(hass, f"/middagsro_static/middagsro-cards.js?v={version}")

        hass.data[frontend.DATA_PANELS].clear()
        panel.async_unregister_panel(hass)  # already gone
        remove.assert_called_once()
        remove_js.assert_called_once()
