"""Config flow for the IDM integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import IDMClient
from .const import DOMAIN
from .exceptions import BadCredentialsException, IDMServiceException

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
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


class IDMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the IDM config flow."""

    VERSION = 1

    async def _async_validate(self, username: str, password: str) -> dict[str, str]:
        """Try to log in; return a dict of form errors (empty when successful)."""

        def _login() -> Any:
            return IDMClient(email=username, password=password).login()

        try:
            user = await self.hass.async_add_executor_job(_login)
        except BadCredentialsException:
            return {"base": "invalid_auth"}
        except IDMServiceException as err:
            _LOGGER.debug("IDM service error during setup: %s", err)
            return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error while validating IDM credentials")
            return {"base": "unknown"}

        if not user:
            return {"base": "invalid_auth"}
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            errors = await self._async_validate(username, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_create_entry(title=username, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication after the portal rejected our credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user for a fresh password."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            username = entry.data[CONF_USERNAME]
            errors = await self._async_validate(username, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )
