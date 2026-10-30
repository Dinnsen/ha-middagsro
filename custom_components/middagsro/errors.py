"""Errors the panel shows translated."""

from __future__ import annotations

import logging

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    """An error caused by what was asked for, with a translated message."""
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def _failed(key: str, **placeholders: str) -> HomeAssistantError:
    """An error while doing what was asked, with a translated message."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )
