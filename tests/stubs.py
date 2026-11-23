"""Stand-ins for aiohttp, probatio and the Home Assistant classes Crafty Controller uses.

Importing this module registers them under the real names and puts custom_components/ on the path, so
`import crafty_controller` loads the real integration. The aiohttp stand-in makes real plain-HTTP requests, which is
how the test's mock Crafty server is reached; anything but http:// fails like a TLS handshake would. Like aiohttp, it
follows redirects unless told not to (allow_redirects=False). Keep the
stand-ins in sync if the integration starts using more of the Home Assistant API.
"""

import asyncio
from enum import Enum
import json
import os
import sys
import types
from typing import Generic, TypeVar
from urllib.parse import urljoin, urlparse

# Locate the integration relative to this file so the script runs from anywhere.
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "custom_components")
PKG = os.path.join(ROOT, "crafty_controller")
sys.path.insert(0, ROOT)
T = TypeVar("T")


# ───────────────────────── aiohttp stand-in ─────────────────────────
class ClientError(Exception):
    pass


class ClientResponseError(ClientError):
    def __init__(self, status):
        super().__init__(status)
        self.status = status


class ClientTimeout:
    def __init__(self, total=None):
        self.total = total


class _Content:
    """resp.content: the body, read in chunks."""

    def __init__(self, body):
        self.body = body

    async def iter_chunked(self, size):
        for start in range(0, len(self.body), size):
            yield self.body[start : start + size]


class _Resp:
    def __init__(self, status, body, headers):
        self.status, self.body, self.headers = status, body, headers
        self.content = _Content(body)

    def raise_for_status(self):
        if self.status >= 400:
            raise ClientResponseError(self.status)

    async def json(self, content_type=None):
        return json.loads(self.body)  # bad JSON -> ValueError, as real


async def _fetch(method, url, headers):
    """Make one plain-HTTP request to the mock Crafty and return its response.

    Anything but http:// fails like a TLS handshake would, which is how the config flow test checks that a
    scheme mismatch is reported as "cannot connect".
    """
    parsed = urlparse(url)
    if parsed.scheme != "http":
        raise ClientError("ssl/handshake failure (stand-in)")
    try:
        reader, writer = await asyncio.open_connection(parsed.hostname, parsed.port)
    except OSError as e:
        raise ClientError(str(e)) from e
    header_lines = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    writer.write(f"{method} {parsed.path} HTTP/1.1\r\nHost: x\r\n{header_lines}Connection: close\r\n\r\n".encode())
    raw = await reader.read()
    writer.close()
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.decode().split("\r\n")
    response_headers = {k.strip().lower(): v.strip() for k, _, v in (line.partition(":") for line in lines[1:])}
    return _Resp(int(lines[0].split(" ", 2)[1]), body, response_headers)


class _Req:
    """What session.request() returns: an async context manager that applies the timeout like aiohttp does."""

    def __init__(self, method, url, headers, timeout, allow_redirects):
        self.args = (method, url, headers)
        self.timeout, self.allow_redirects = timeout, allow_redirects

    async def _run(self):
        method, url, headers = self.args
        for _ in range(10):
            resp = await _fetch(method, url, headers)
            if not (self.allow_redirects and resp.status in (301, 302, 303, 307, 308)):
                return resp
            url = urljoin(url, resp.headers["location"])  # aiohttp's default: follow it
        raise ClientError("too many redirects")

    async def __aenter__(self):
        return await asyncio.wait_for(self._run(), self.timeout.total if self.timeout else None)

    async def __aexit__(self, *exc_info):
        return False


class ClientSession:
    def request(self, method, url, headers=None, timeout=None, allow_redirects=True):
        return _Req(method, url, headers or {}, timeout, allow_redirects)

    def get(self, url, **kw):
        return self.request("GET", url, **kw)


def fake_module(name, **attributes):
    """Register a stand-in module under `name`, so the integration's imports find it instead of the real one."""
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    sys.modules[name] = module
    return module


fake_module(
    "aiohttp",
    ClientError=ClientError,
    ClientResponseError=ClientResponseError,
    ClientTimeout=ClientTimeout,
    ClientSession=ClientSession,
)


class _Required:
    def __init__(self, key, default=None):
        self.schema, self.default = key, default


class _Schema:
    def __init__(self, schema):
        self.schema = schema


fake_module("probatio", Required=_Required, Schema=_Schema)


# ───────────────────────── Home Assistant stand-ins ─────────────────────────
class Platform(str, Enum):
    SWITCH = "switch"
    BINARY_SENSOR = "binary_sensor"


class HomeAssistantError(Exception):
    pass


class UpdateFailed(Exception):
    pass


class ConfigEntryNotReady(Exception):
    pass


class ConfigEntryAuthFailed(Exception):
    pass


class ConfigEntry(Generic[T]):
    def __init__(self, data, entry_id="entry1"):
        self.data, self.runtime_data, self._un, self.entry_id = data, None, [], entry_id
        self.reauth_started = 0

    def async_on_unload(self, fn):
        self._un.append(fn)


class ConfigFlow:
    def __init_subclass__(cls, domain=None, **kw):
        cls.domain = domain

    # Tests set `entry` (the entry being reconfigured or reauthenticated) and `entries` (every entry).
    entry, entries, source = None, (), "user"

    def _async_abort_entries_match(self, match):
        pass

    def _async_current_entries(self, include_ignore=True):
        return list(self.entries)

    def _get_reconfigure_entry(self):
        return self.entry

    def _get_reauth_entry(self):
        return self.entry

    def async_show_form(self, step_id, data_schema, errors=None, description_placeholders=None):
        return {
            "type": "form",
            "step_id": step_id,
            "errors": errors or {},
            "schema": data_schema,
            "placeholders": description_placeholders or {},
        }

    def async_create_entry(self, title, data):
        return {"type": "create_entry", "data": data}

    def async_abort(self, reason):
        return {"type": "abort", "reason": reason}

    def async_update_reload_and_abort(self, entry, data_updates):
        entry.data = {**entry.data, **data_updates}
        reason = "reauth_successful" if self.source == "reauth" else "reconfigure_successful"
        return {"type": "abort", "reason": reason}


class DataUpdateCoordinator(Generic[T]):
    def __init__(self, hass, logger, *, name, config_entry=None, update_interval=None):
        self.data, self.last_update_success, self._l, self.unexpected = None, True, [], []
        self.config_entry, self.refresh_requests = config_entry, 0

    async def async_request_refresh(self):
        self.refresh_requests += 1
        await self.async_refresh()

    async def async_refresh(self):
        try:
            self.data = await self._async_update_data()
            self.last_update_success = True
        except UpdateFailed:
            self.last_update_success = False
        except ConfigEntryAuthFailed:
            self.last_update_success = False
            self.config_entry.reauth_started += 1  # real HA starts the reauth flow
        except Exception as err:
            self.unexpected.append(err)
            self.last_update_success = False  # real HA logs these as bugs
        for listener in list(self._l):
            listener()

    async def async_config_entry_first_refresh(self):
        await self.async_refresh()
        if not self.last_update_success:
            raise ConfigEntryNotReady()

    def async_add_listener(self, listener):
        self._l.append(listener)
        return lambda: self._l.remove(listener)


class CoordinatorEntity(Generic[T]):
    def __init__(self, coordinator):
        self.coordinator = coordinator

    @property
    def available(self):
        return self.coordinator.last_update_success

    def async_write_ha_state(self):
        render(self)

    def async_entity_id_changed(self, old_entity_id):
        self.entity_id_changes = getattr(self, "entity_id_changes", 0) + 1


def render(entity):
    """Return (state, attributes) the way Home Assistant would show the entity."""
    attrs = entity.extra_state_attributes  # HA evaluates attributes even when unavailable
    if not entity.available:
        return "unavailable", attrs
    return ("on" if entity.is_on else "off"), attrs


fake_module("homeassistant")
fake_module("homeassistant.components")
fake_module("homeassistant.helpers")
fake_module("homeassistant.config_entries", ConfigEntry=ConfigEntry, ConfigFlow=ConfigFlow)
fake_module("homeassistant.const", CONF_TOKEN="token", CONF_URL="url", CONF_VERIFY_SSL="verify_ssl", Platform=Platform)
fake_module("homeassistant.core", HomeAssistant=object, callback=lambda f: f)
fake_module(
    "homeassistant.exceptions", HomeAssistantError=HomeAssistantError, ConfigEntryAuthFailed=ConfigEntryAuthFailed
)
fake_module("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda hass, v=True: ClientSession())
fake_module("homeassistant.helpers.device_registry", DeviceInfo=dict)
fake_module(
    "homeassistant.helpers.update_coordinator",
    CoordinatorEntity=CoordinatorEntity,
    DataUpdateCoordinator=DataUpdateCoordinator,
    UpdateFailed=UpdateFailed,
)
fake_module("homeassistant.components.switch", SwitchEntity=type("SwitchEntity", (), {}))
fake_module(
    "homeassistant.components.binary_sensor",
    BinarySensorEntity=type("BinarySensorEntity", (), {}),
    BinarySensorDeviceClass=type("BSDC", (), {"CONNECTIVITY": "connectivity"}),
)
