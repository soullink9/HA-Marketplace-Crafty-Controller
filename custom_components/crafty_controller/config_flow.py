"""Config flow: the set-up form (Crafty URL, API token, SSL check), plus reconfigure and reauth.

- user:        add Crafty Controller (URL, token, SSL check)
- reconfigure: change the URL or the SSL check of an existing entry (⋮ → Reconfigure)
- reauth:      Home Assistant starts this when Crafty rejects the token; asks for a new one
Every path proves the details work by listing the servers before anything is saved.
"""

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientResponseError
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import probatio

from .api import request
from .const import DOMAIN, ERRORS


def _tidy_url(url: str) -> str:
    """Tidy a typed URL: trim spaces, drop a trailing "/", assume https."""
    url = url.strip().rstrip("/")
    if "://" not in url:
        url = "https://" + url
    return url


class CraftyFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the details, prove they work by listing servers, then save them."""

    VERSION = 1

    async def _check(self, url: str, token: str, verify_ssl: bool) -> dict[str, str]:
        """List the servers with these details. Returns the form errors: {} when they work."""
        session = async_get_clientsession(self.hass, verify_ssl)
        try:
            # Listing servers proves the URL, the token and the API all work.
            await request(session, "GET", f"{url}/api/v2/servers", token)
        except ClientResponseError as err:
            # 401/403 = Crafty rejected the token; any other HTTP error = trouble reaching it.
            return {"base": "invalid_auth" if err.status in (401, 403) else "cannot_connect"}
        except ERRORS:
            return {"base": "cannot_connect"}
        return {}

    async def async_step_user(self, user_input=None):
        """Show the form, tidy what was typed, and only save it once listing servers works."""
        errors: dict[str, str] = {}

        if user_input:
            url = _tidy_url(user_input[CONF_URL])
            token = user_input[CONF_TOKEN].strip()

            # One Crafty instance should only be added once.
            self._async_abort_entries_match({CONF_URL: url})

            errors = await self._check(url, token, user_input[CONF_VERIFY_SSL])
            if not errors:
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
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_URL): str,
                    probatio.Required(CONF_TOKEN): str,
                    # On by default, so the token only goes to a Crafty that proves who it is. Turning it off is
                    # for Crafty's own self-signed certificate.
                    probatio.Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
        )

    async def async_step_reconfigure(self, user_input=None):
        """Change the URL or the SSL check of an existing entry, keeping its token (and its devices)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input:
            url = _tidy_url(user_input[CONF_URL])
            # Moving to an address another entry already uses would add that Crafty twice.
            if any(
                other.entry_id != entry.entry_id and other.data.get(CONF_URL) == url
                for other in self._async_current_entries(include_ignore=False)
            ):
                return self.async_abort(reason="already_configured")

            errors = await self._check(url, entry.data[CONF_TOKEN], user_input[CONF_VERIFY_SSL])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_URL: url, CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL]}
                )

        return self.async_show_form(
            step_id="reconfigure",
            errors=errors,
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_URL, default=entry.data[CONF_URL]): str,
                    probatio.Required(CONF_VERIFY_SSL, default=entry.data[CONF_VERIFY_SSL]): bool,
                }
            ),
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Crafty rejected the stored token: ask for a new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask for a new API token, and save it once listing servers works with it."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input:
            token = user_input[CONF_TOKEN].strip()
            errors = await self._check(entry.data[CONF_URL], token, entry.data[CONF_VERIFY_SSL])
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})

        return self.async_show_form(
            step_id="reauth_confirm",
            errors=errors,
            description_placeholders={"url": entry.data[CONF_URL]},
            data_schema=probatio.Schema({probatio.Required(CONF_TOKEN): str}),
        )
