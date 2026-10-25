"""Photos of cookbook pages for the AI to read, as a media source.

The AI Task integration takes its attachments from media sources, as files.
The panel's photos are written to a temporary file for the few seconds the AI
reads them, and deleted again; nothing is shown in the media browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN


@dataclass(slots=True)
class ScannedPage:
    """A photo the panel sent, written to a temporary file."""

    path: Path
    mime_type: str


SCANS: dict[str, ScannedPage] = {}


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """The source of the scanned pages."""
    return ScannedPages()


class ScannedPages(MediaSource):
    """Photos the panel sent for the AI to read."""

    name = "Middagsro"

    def __init__(self) -> None:
        """Initialize the source."""
        super().__init__(DOMAIN)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """The photo's file, for the AI."""
        page = SCANS.get(item.identifier)
        if page is None:
            raise Unresolvable("The scanned page is gone")
        return PlayMedia(f"/{DOMAIN}/scan/{item.identifier}", page.mime_type, path=page.path)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Nothing to browse."""
        raise Unresolvable("Middagsro's scanned pages can't be browsed")
