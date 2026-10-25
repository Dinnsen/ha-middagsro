"""Photos of cookbook pages for the AI to read, as a media source.

The AI Task integration takes its attachments from media sources. The panel's
photos are kept here in memory for the few seconds the AI reads them; nothing
is saved or shown in the media browser.
"""

from __future__ import annotations

from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaImage,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN

SCANS: dict[str, MediaImage] = {}


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """The source of the scanned pages."""
    return ScannedPages()


class ScannedPages(MediaSource):
    """Photos the panel sent for the AI to read."""

    name = "Middagsro"

    def __init__(self) -> None:
        """Initialize the source."""
        super().__init__(DOMAIN)

    async def async_get_media_image(self, item: MediaSourceItem) -> MediaImage | None:
        """The photo itself, for the AI."""
        return SCANS.get(item.identifier)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """The photos can't be played or shown."""
        raise Unresolvable("Middagsro's scanned pages are only for the AI")

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Nothing to browse."""
        raise Unresolvable("Middagsro's scanned pages can't be browsed")
