"""Config flow: the one-screen set-up form (Crafty URL, API token, SSL check)."""

from __future__ import annotations

from aiohttp import ClientResponseError
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import request
from .const import DOMAIN, ERRORS


class CraftyFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the details, prove they work by listing servers, then save them."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Show the form, tidy what was typed, and only save it once listing servers works."""
        errors: dict[str, str] = {}

        if user_input:
            # Tidy what was typed: trim spaces, drop a trailing "/", assume https.
            url = user_input[CONF_URL].strip().rstrip("/")
            if "://" not in url:
                url = "https://" + url
            token = user_input[CONF_TOKEN].strip()

            # One Crafty instance should only be added once.
            self._async_abort_entries_match({CONF_URL: url})

            session = async_get_clientsession(self.hass, user_input[CONF_VERIFY_SSL])
            try:
                # Listing servers proves the URL, the token and the API all work.
                await request(session, "GET", f"{url}/api/v2/servers", token)
            except ClientResponseError as err:
                # 401/403 = Crafty rejected the token; any other HTTP error = trouble reaching it.
                errors["base"] = "invalid_auth" if err.status in (401, 403) else "cannot_connect"
            except ERRORS:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Crafty Controller",
                    data={
                        CONF_URL: url,
                        CONF_TOKEN: token,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_TOKEN): str,
                    # Off by default: Crafty ships with a self-signed certificate.
                    vol.Required(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
        )
