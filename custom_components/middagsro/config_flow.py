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
from .bilka import BILKA_ID, BilkaSearch
from .bilka_cart import CONF_PICKUP, CONF_PICKUP_NAME, CONF_PRICE_STORE, BilkaCart
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
# BilkaToGo's login is optional: without it, Bilka has prices and a list kept here.
BILKA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
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
        self._bilka_data: dict[str, Any] = {}
        self._bilka_locations: list[dict[str, str]] = []
        self._bilka_reconfigure = False

    async def _async_validate_bilka(
        self,
        email: str,
        password: str,
    ) -> tuple[int | None, list[dict[str, str]], dict[str, str]]:
        """Validate the account and discover physical pickup stores without changing it."""
        session = async_create_clientsession(self.hass, auto_cleanup=False)
        try:
            cart = BilkaCart(session, BilkaSearch(self.hass), email, password)
            uid = await cart.async_login()
            locations = await cart.async_locations()
            if not locations:
                return None, [], {"base": "cannot_connect"}
            return uid, locations, {}
        except RemaAuthError:
            return None, [], {"base": "invalid_auth"}
        except RemaError:
            return None, [], {"base": "cannot_connect"}
        finally:
            session.detach()

    async def async_step_bilka(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Log in with the same Salling Group account as the BilkaToGo app, or not.

        Without a login Bilka still has its prices on every item, and the shopping
        list is kept in Home Assistant (as before BilkaToGo's cart).
        """
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry() if self._bilka_reconfigure else None
        if user_input is not None:
            email = str(user_input.get(CONF_EMAIL) or "").strip()
            password = str(user_input.get(CONF_PASSWORD) or "")
            if not email and not password:
                self._store = BILKA_ID
                if entry:
                    return await self.async_step_reconfigure_store()
                return await self.async_step_store()
            uid: int | None = None
            locations: list[dict[str, str]] = []
            if not email or not password:
                errors = {"base": "missing_login"}
            else:
                uid, locations, errors = await self._async_validate_bilka(email, password)
            if not errors:
                if entry and entry.data.get("bilka_user_id") not in (None, uid):
                    return self.async_abort(reason="wrong_account")
                self._bilka_data = {
                    CONF_STORE: BILKA_ID,
                    CONF_EMAIL: email,
                    CONF_PASSWORD: password,
                    "bilka_user_id": uid,
                }
                self._bilka_locations = locations
                return await self.async_step_bilka_pickup()
        return self.async_show_form(
            step_id="reconfigure_bilka" if entry else "bilka",
            data_schema=self.add_suggested_values_to_schema(
                BILKA_SCHEMA,
                {
                    CONF_EMAIL: (user_input or {}).get(CONF_EMAIL)
                    or (entry.data.get(CONF_EMAIL) if entry else None)
                },
            ),
            errors=errors,
        )

    async def async_step_reconfigure_bilka(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Change BilkaToGo login or pickup store."""
        self._bilka_reconfigure = True
        return await self.async_step_bilka(user_input)

    async def async_step_bilka_pickup(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose the physical store used for both prices and the remote cart."""
        errors: dict[str, str] = {}
        if user_input is not None:
            location = next(
                (a for a in self._bilka_locations if a["id"] == user_input.get(CONF_PICKUP)), None
            )
            if location:
                data = {
                    **self._bilka_data,
                    CONF_PICKUP: location["id"],
                    CONF_PICKUP_NAME: location["name"],
                    CONF_PRICE_STORE: location["sid"],
                }
                if self._bilka_reconfigure:
                    previous = self._get_reconfigure_entry()
                    if (
                        store_of(previous.data) != BILKA_ID
                        or previous.data.get(CONF_PRICE_STORE, "1653") != location["sid"]
                    ):
                        data["bilka_rematch"] = True
                    if self._taken(_store_unique_id(BILKA_ID), BILKA_ID):
                        return self.async_abort(reason="already_configured")
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        title=f"Middagsro – {location['name']}",
                        data=data,
                    )
                await self.async_set_unique_id(_store_unique_id(BILKA_ID))
                self._abort_if_unique_id_configured()
                if any(store_of(e.data) == BILKA_ID for e in self._async_current_entries()):
                    return self.async_abort(reason="already_configured")
                return self.async_create_entry(title=f"Middagsro – {location['name']}", data=data)
            errors["base"] = "invalid_pickup"
        schema = vol.Schema(
            {
                vol.Required(CONF_PICKUP): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=a["id"], label=a["name"])
                            for a in sorted(self._bilka_locations, key=lambda a: a["name"])
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        if self._bilka_reconfigure:
            schema = self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_PICKUP: self._get_reconfigure_entry().data.get(CONF_PICKUP),
                },
            )
        return self.async_show_form(step_id="bilka_pickup", data_schema=schema, errors=errors)

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
            if self._store == BILKA_ID:
                return await self.async_step_bilka()
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
            if store_of(entry.data) == BILKA_ID:
                uid, _locations, errors = await self._async_validate_bilka(
                    entry.data[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
                if not errors:
                    if uid != entry.data.get("bilka_user_id"):
                        return self.async_abort(reason="wrong_account")
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                    )
                return self.async_show_form(
                    step_id="reauth_confirm",
                    data_schema=REAUTH_SCHEMA,
                    description_placeholders={"email": entry.data[CONF_EMAIL]},
                    errors=errors,
                )
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
            if self._store == BILKA_ID:
                return await self.async_step_reconfigure_bilka()
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
