"""Sidebar panel for Middagsro."""

from __future__ import annotations

import contextlib
import hashlib
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import async_get_integration

from .const import DOMAIN

PANEL_URL = "middagsro"
STATIC_URL = "/middagsro_static"
APP_URL = "/middagsro_app"
LEGACY_APP_URL = "/rema1000_app"
WEBCOMPONENT = "middagsro-panel"
CARDS_MODULE = "middagsro-cards"
_STATIC_KEY = f"{DOMAIN}_static_registered"
_CARDS_KEY = f"{DOMAIN}_cards_url"


def _frontend_revision() -> str:
    """Invalidate browser caches when locally installed frontend files change."""
    folder = Path(__file__).parent / "frontend"
    digest = hashlib.sha256()
    for module in (WEBCOMPONENT, CARDS_MODULE):
        digest.update((folder / f"{module}.js").read_bytes())
    return digest.hexdigest()[:12]


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve the panel files and add the panel to the sidebar."""
    if not hass.data.get(_STATIC_KEY):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), True),
                # Home-screen web app; not cached, so the launcher can change.
                StaticPathConfig(APP_URL, str(Path(__file__).parent / "app"), False),
            ]
        )
        # Home-screen apps added before 1.1.0 open the old address (unless the
        # old integration still serves it).
        with contextlib.suppress(RuntimeError, ValueError):
            await hass.http.async_register_static_paths(
                [StaticPathConfig(LEGACY_APP_URL, str(Path(__file__).parent / "app"), False)]
            )
        hass.data[_STATIC_KEY] = True

    integration_version = (await async_get_integration(hass, DOMAIN)).version
    revision = await hass.async_add_executor_job(_frontend_revision)
    version = f"{integration_version}-{revision}"
    # The dashboard cards, loaded on every dashboard: no resource to add, nothing to install.
    if not hass.data.get(_CARDS_KEY):
        cards_url = f"{STATIC_URL}/{CARDS_MODULE}.js?v={version}"
        frontend.add_extra_js_url(hass, cards_url)
        hass.data[_CARDS_KEY] = cards_url
    if PANEL_URL in hass.data.get(frontend.DATA_PANELS, {}):
        return
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name=WEBCOMPONENT,
        sidebar_title="Middagsro",
        sidebar_icon="mdi:pot-steam-outline",
        module_url=f"{STATIC_URL}/{WEBCOMPONENT}.js?v={version}",
        config={"static_url": STATIC_URL, "version": version},
        require_admin=False,
    )


@callback
def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the panel and the cards when the last account is unloaded."""
    if PANEL_URL in hass.data.get(frontend.DATA_PANELS, {}):
        frontend.async_remove_panel(hass, PANEL_URL)
    if cards_url := hass.data.pop(_CARDS_KEY, None):
        frontend.remove_extra_js_url(hass, cards_url)
