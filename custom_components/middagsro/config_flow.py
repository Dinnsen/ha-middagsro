"""Config flow: the shop (REMA 1000 with its login, or another shop without one)."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import RemaAuthError, RemaClient, RemaConnectionError, RemaError
from .const import DOMAIN
from .migrate import MIGRATE_FROM, old_entries
from .schema import vol
from .store_client import CONF_STORE, REMA, STORES, rema_only, store_name, store_of

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)
STORE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STORE, default=REMA): SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=key, label=name) for key, name in STORES.items()],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)
REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)


def _missing(store: str) -> str:
    """What only works with REMA 1000, as a list for a form's description."""
    return "\n".join(f"- {line}" for line in rema_only(store))


def _store_unique_id(store: str) -> str:
    return f"store_{store}"


class RemaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow: choose the shop, and log in when it is REMA 1000."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._store = REMA

    async def _async_validate(self, email: str, password: str) -> tuple[int | None, dict[str, str]]:
        """Try to log in. Returns (user id, errors)."""
        session = async_create_clientsession(self.hass, auto_cleanup=False)
        try:
            user_id = await RemaClient(session, email, password).async_login()
        except RemaAuthError:
            return None, {"base": "invalid_auth"}
        except RemaConnectionError:
            return None, {"base": "cannot_connect"}
        except RemaError as err:
            # REMA's site is unhappy (maintenance, a changed login page): not a wrong password.
            _LOGGER.warning("REMA 1000 login failed: %s", err)
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error while logging in to REMA 1000")
            return None, {"base": "unknown"}
        finally:
            # Release the session without closing HA's shared connector.
            session.detach()
        return user_id, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the shop (or move an account of the old integration over)."""
        if user_input is None and old_entries(self.hass):
            return await self.async_step_migrate()
        if user_input is not None:
            self._store = store_of(user_input)
            if self._store == REMA:
                return await self.async_step_rema()
            return await self.async_step_store()
        return self.async_show_form(step_id="user", data_schema=STORE_SCHEMA)

    async def async_step_store(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Another shop than REMA 1000: no login; tell what only works with REMA."""
        name = store_name(self._store)
        if user_input is not None:
            await self.async_set_unique_id(_store_unique_id(self._store))
            self._abort_if_unique_id_configured()
            if any(store_of(e.data) == self._store for e in self._async_current_entries()):
                return self.async_abort(reason="already_configured")
            return self.async_create_entry(
                title=f"Middagsro – {name}", data={CONF_STORE: self._store}
            )
        return self.async_show_form(
            step_id="store",
            description_placeholders={"store": name, "missing": _missing(self._store)},
        )

    async def async_step_rema(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the REMA 1000 e-mail and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            user_id, errors = await self._async_validate(email, user_input[CONF_PASSWORD])
            if not errors:
                await self.async_set_unique_id(str(user_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="rema",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, {CONF_EMAIL: (user_input or {}).get(CONF_EMAIL)}
            ),
            errors=errors,
        )

    async def async_step_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Move the account from the old REMA 1000 integration, with all its data."""
        found = old_entries(self.hass)
        if not found:
            return self.async_abort(reason="already_configured")
        old = found[0]
        if user_input is not None:
            await self.async_set_unique_id(old.unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=old.title, data={**old.data, MIGRATE_FROM: old.entry_id}
            )
        return self.async_show_form(
            step_id="migrate", description_placeholders={"account": old.title}
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start reauthentication when the password no longer works."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id, errors = await self._async_validate(
                entry.data[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if not errors:
                await self.async_set_unique_id(str(user_id))
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the shop (plans, recipes and settings are kept), or the REMA login."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            self._store = store_of(user_input)
            if self._store == REMA:
                return await self.async_step_reconfigure_rema()
            return await self.async_step_reconfigure_store()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STORE_SCHEMA, {CONF_STORE: store_of(entry.data)}
            ),
            description_placeholders={"store": store_name(store_of(entry.data))},
        )

    def _taken(self, unique_id: str, store: str) -> bool:
        """Another entry has this REMA account or shop.

        An entry keeps its unique id when the shop changes (its entities are named
        by it), so the shop in each entry's data is looked at too.
        """
        entry = self._get_reconfigure_entry()
        return any(
            other.entry_id != entry.entry_id
            and (other.unique_id == unique_id or (store != REMA and store_of(other.data) == store))
            for other in self._async_current_entries(include_ignore=False)
        )

    async def async_step_reconfigure_store(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change to another shop than REMA 1000 (the REMA login is forgotten)."""
        entry = self._get_reconfigure_entry()
        name = store_name(self._store)
        if user_input is not None:
            if self._taken(_store_unique_id(self._store), self._store):
                return self.async_abort(reason="already_configured")
            return self.async_update_reload_and_abort(
                entry, title=f"Middagsro – {name}", data={CONF_STORE: self._store}
            )
        return self.async_show_form(
            step_id="reconfigure_store",
            description_placeholders={"store": name, "missing": _missing(self._store)},
        )

    async def async_step_reconfigure_rema(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in to REMA 1000: the entry's own account, or any account for an entry
        that was set up for another shop."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            user_id, errors = await self._async_validate(email, user_input[CONF_PASSWORD])
            if not errors:
                if not str(entry.unique_id).startswith("store_"):
                    await self.async_set_unique_id(str(user_id))
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                elif self._taken(str(user_id), REMA):
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry,
                    title=email,
                    data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="reconfigure_rema",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA,
                {CONF_EMAIL: (user_input or {}).get(CONF_EMAIL) or entry.data.get(CONF_EMAIL)},
            ),
            errors=errors,
        )
