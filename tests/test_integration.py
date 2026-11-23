"""Simulation test for the Crafty Controller integration.

Run:  python3 tests/test_integration.py      (Python 3.14, no other dependencies)

The real integration files are loaded and run against a mock Crafty server that
returns messy data: missing fields, odd types, invalid server IDs, 403s, HTML
pages, redirects, oversized replies, hangs, servers that are removed or added,
and failing start/stop actions. It prints PASS/FAIL per check
and exits non-zero if any check fails.

aiohttp, probatio and the Home Assistant base classes are thin stand-ins
(stubs.py), so this checks the integration's own logic only. It does NOT test
real Home Assistant, real HTTP/TLS or a real Crafty. Keep the stand-ins in sync
if the integration starts using more of the Home Assistant API.
"""

import asyncio
import importlib
import json
import os
from pathlib import Path
import sys
import types

sys.dont_write_bytecode = True  # keep __pycache__ out of the repository
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for stubs.py
from stubs import ClientTimeout, ConfigEntry, HomeAssistantError, PKG, render  # noqa: E402,I001  (registers the stand-ins first)

# ───────────────────────── mock Crafty ─────────────────────────
# The mock Crafty's state. Each *_mode switches a reply into one of the failure shapes the tests cover.
CRAFTY = {
    "servers": {},
    "list_mode": "ok",
    "stats_mode": {},
    "action_mode": "ok",
    "delay": 0.3,  # how long a server takes to start or stop after the action
    "stats_delay": 0,  # how long each stats reply takes
    "calls": [],
    "stats_in_flight": 0,
    "stats_max_in_flight": 0,
}


def json_reply(payload, status=200):
    """Build a (status, content type, body) reply with a JSON body."""
    return status, "application/json", json.dumps(payload).encode()


def server_record(server_id, server):
    """Crafty's record for one server, leaving out the name and port when they're None (sparse data)."""
    record = {"server_id": server_id, "type": "minecraft-java"}
    if server["name"] is not None:
        record["server_name"] = server["name"]
    if server["port"] is not None:
        record["server_port"] = server["port"]
    return record


def server_list():
    """Crafty's reply to GET /servers."""
    return json_reply(
        {"status": "ok", "data": [server_record(server_id, server) for server_id, server in CRAFTY["servers"].items()]}
    )


async def route(method, path, headers):
    """Answer one request like Crafty's API v2: /servers, /servers/<id>/stats or /servers/<id>/action/<action>."""
    if headers.get("authorization") != "Bearer GOOD":
        return json_reply({"status": "error", "error": "NOT_AUTHORIZED"}, 403)
    if path == "/api/v2/elsewhere":  # where the "redirect" mode points: a client that follows it gets a good list
        return server_list()
    if path == "/api/v2/servers":
        mode = CRAFTY["list_mode"]
        if mode == "redirect":
            return 302, "text/plain", b"", {"Location": "/api/v2/elsewhere"}
        if mode == "huge":
            return json_reply({"status": "ok", "data": [], "padding": "x" * (1024 * 1024)})
        if mode == "deep":
            return 200, "application/json", b'{"a":' * 100_000 + b"1" + b"}" * 100_000
        if mode == "data_not_list":
            return json_reply({"status": "ok", "data": {"server_id": "s1"}})
        if mode == "html":
            return 200, "text/html", b"<html>login</html>"
        if mode == "error_status":
            return json_reply({"status": "error", "error": "X"})
        if mode == "500":
            return json_reply({"status": "error"}, 500)
        if mode == "wrong_shape":
            return json_reply([])
        if mode == "hang":
            await asyncio.sleep(2)
        return server_list()
    parts = path.split("/")
    server_id = parts[4]
    if server_id not in CRAFTY["servers"]:
        return json_reply({"status": "error", "error": "SERVER_NOT_FOUND"}, 404)
    server = CRAFTY["servers"][server_id]
    if parts[5] == "stats":
        CRAFTY["stats_in_flight"] += 1
        CRAFTY["stats_max_in_flight"] = max(CRAFTY["stats_max_in_flight"], CRAFTY["stats_in_flight"])
        await asyncio.sleep(CRAFTY["stats_delay"])
        CRAFTY["stats_in_flight"] -= 1
        mode = CRAFTY["stats_mode"].get(server_id, "top")
        if mode == "403":
            return json_reply({"status": "error"}, 403)
        if mode == "html":
            return 200, "text/html", b"<html/>"
        if mode == "nulls":
            return json_reply({"status": "ok", "data": None, "running": None, "int_ping_results": None})
        if mode == "odd_types":
            return json_reply({"status": "ok", "running": "yes", "int_ping_results": 1, "server_port": "abc"})
        ping = server["ping"]
        if mode == "nested":
            return json_reply(
                {
                    "status": "ok",
                    "data": {"running": server["running"], "int_ping_results": ping, "server_port": server["port"]},
                }
            )
        return json_reply(
            {
                "status": "ok",
                "data": {"server_id": server_record(server_id, server)},
                "running": server["running"],
                "int_ping_results": "True" if ping else "False",
                "server_port": server["port"],
            }
        )
    if parts[5] == "action":
        mode = CRAFTY["action_mode"]
        if mode == "403":
            return json_reply({"status": "error"}, 403)
        if mode == "error_status":
            return json_reply({"status": "error", "error": "NOPE"})
        start = parts[6] == "start_server"
        asyncio.get_running_loop().call_later(CRAFTY["delay"], lambda: server.update(running=start, ping=start))
        return json_reply({"status": "ok"})


async def handle(reader, writer):
    """Serve one HTTP connection. Errors are swallowed: a test that hangs up mid-request must not crash the server."""
    try:
        head = (await reader.readuntil(b"\r\n\r\n")).decode().split("\r\n")
        method, path, _ = head[0].split(" ")
        headers = {line.split(":", 1)[0].lower(): line.split(":", 1)[1].strip() for line in head[1:] if ":" in line}
        CRAFTY["calls"].append((method, path))
        status, content_type, body, *extra = await route(method, path, headers)
        extra_headers = "".join(f"{k}: {v}\r\n" for k, v in (extra[0] if extra else {}).items())
        writer.write(
            f"HTTP/1.1 {status} X\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\n{extra_headers}Connection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()
        writer.close()
    except Exception:
        pass


# ───────────────────────── harness ─────────────────────────
RESULTS = []


def check(name, cond, detail=""):
    """Record one check and print PASS or FAIL (with the detail on failure)."""
    RESULTS.append(cond)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   <- {detail}"))


class Hass:
    """A stand-in Home Assistant that sets up the integration's platforms and collects the entities they add."""

    def __init__(self):
        self.entities = []
        self.config_entries = types.SimpleNamespace(
            async_forward_entry_setups=self._fwd, async_unload_platforms=self._unl
        )

    async def _fwd(self, entry, platforms):
        for platform in platforms:
            await importlib.import_module(f"crafty_controller.{platform.value}").async_setup_entry(
                self, entry, lambda entities: self.entities.extend(entities)
            )

    async def _unl(self, entry, platforms):
        return True


def find_entity(hass, class_name, server_id):
    """The entity of this class for this server."""
    return next(
        entity for entity in hass.entities if type(entity).__name__ == class_name and entity.server_id == server_id
    )


def state_of(hass, class_name, server_id):
    """(state, attributes) of the entity of this class for this server."""
    return render(find_entity(hass, class_name, server_id))


async def main():
    """Start the mock Crafty, then run every scenario against the real integration."""
    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}"

    # --- file layout / metadata ---
    required_files = [
        "__init__.py",
        "const.py",
        "api.py",
        "coordinator.py",
        "entity.py",
        "config_flow.py",
        "switch.py",
        "binary_sensor.py",
        "manifest.json",
        "translations/en.json",
        "brand/icon.png",
        "brand/icon@2x.png",
    ]
    missing = [file_name for file_name in required_files if not os.path.isfile(f"{PKG}/{file_name}")]
    check("layout: all required files present with exact names", not missing, missing)
    try:
        for file_name in required_files:
            if file_name.endswith(".py"):
                compile(Path(PKG, file_name).read_text(), file_name, "exec")  # syntax check only
        manifest = json.loads(Path(PKG, "manifest.json").read_text())
        translations = json.loads(Path(PKG, "translations/en.json").read_text())
        manifest_ok = (
            manifest["domain"] == "crafty_controller" and manifest["config_flow"] is True and "version" in manifest
        )
        steps = translations["config"]["step"]
        translations_ok = (
            set(steps["user"]["data"]) == {"url", "token", "verify_ssl"}
            and set(steps["reconfigure"]["data"]) == {"url", "verify_ssl"}
            and set(steps["reauth_confirm"]["data"]) == {"token"}
            and {"cannot_connect", "invalid_auth"} <= set(translations["config"]["error"])
            and {"already_configured", "reauth_successful", "reconfigure_successful"}
            <= set(translations["config"]["abort"])
        )
        check("layout: py compiles, manifest + translations valid and match flow keys", manifest_ok and translations_ok)

        def strings(node):
            """Every string in the translations, however deep."""
            if isinstance(node, dict):
                for value in node.values():
                    yield from strings(value)
            else:
                yield node

        with_urls = [text for text in strings(translations) if "://" in text]
        check("layout: no URLs in translation strings (hassfest refuses them)", not with_urls, with_urls)
    except Exception as err:
        check("layout: compile/json", False, repr(err))

    integration = importlib.import_module("crafty_controller")
    importlib.import_module("crafty_controller.api").TIMEOUT = ClientTimeout(total=0.5)  # make hang scenarios fast
    from crafty_controller.config_flow import CraftyFlow

    CRAFTY["servers"] = {
        "s1": {"name": "Survival", "port": 25565, "running": True, "ping": True},
        "s2": {"name": "Creative", "port": 25566, "running": False, "ping": False},
        "s3": {"name": None, "port": None, "running": False, "ping": False},  # sparse data
    }
    CRAFTY["stats_mode"] = {"s2": "nested", "s3": "nulls"}
    hass = Hass()
    entry = ConfigEntry({"url": url, "token": "GOOD", "verify_ssl": False})
    await integration.async_setup_entry(hass, entry)
    coordinator = entry.runtime_data
    SWITCH, STATUS = "CraftySwitch", "CraftyStatus"

    # --- S1 baseline + both response shapes + null/missing fields ---
    check("S1 six entities created (3 servers x switch+status)", len(hass.entities) == 6, len(hass.entities))
    check(
        "S1 s1 running+online, port attr",
        state_of(hass, SWITCH, "s1") == ("on", {"port": 25565}) and state_of(hass, STATUS, "s1")[0] == "on",
        (state_of(hass, SWITCH, "s1"), state_of(hass, STATUS, "s1")),
    )
    check(
        "S1 s2 (nested shape, bool ping) off/off, port 25566",
        state_of(hass, SWITCH, "s2") == ("off", {"port": 25566}) and state_of(hass, STATUS, "s2")[0] == "off",
    )
    check(
        "S1 s3 (no name/port, null stats) survives: off/off, port None",
        state_of(hass, SWITCH, "s3") == ("off", {"port": None}) and state_of(hass, STATUS, "s3")[0] == "off",
    )
    check(
        "S1 s3 device name falls back to server_id", find_entity(hass, SWITCH, "s3")._attr_device_info["name"] == "s3"
    )
    check("S1 unique_ids unique", len({err._attr_unique_id for err in hass.entities}) == 6)

    # --- S2 one server's stats fail -> only that server unavailable ---
    CRAFTY["stats_mode"]["s2"] = "403"
    await coordinator.async_refresh()
    check(
        "S2 s2 403 -> s2 unavailable, no crash",
        state_of(hass, SWITCH, "s2") == ("unavailable", {"port": None})
        and state_of(hass, STATUS, "s2")[0] == "unavailable",
    )
    check(
        "S2 s1/s3 unaffected",
        state_of(hass, SWITCH, "s1")[0] == "on"
        and state_of(hass, SWITCH, "s3")[0] == "off"
        and coordinator.last_update_success,
    )
    CRAFTY["stats_mode"]["s2"] = "html"
    await coordinator.async_refresh()
    check(
        "S2 s2 HTML body -> unavailable, still no crash",
        state_of(hass, SWITCH, "s2")[0] == "unavailable" and state_of(hass, SWITCH, "s1")[0] == "on",
    )
    CRAFTY["stats_mode"]["s2"] = "nested"
    await coordinator.async_refresh()
    check("S2 s2 recovers", state_of(hass, SWITCH, "s2")[0] == "off")

    # --- S2b odd field types fall back to safe values; long names are cut ---
    CRAFTY["stats_mode"]["s3"] = "odd_types"
    CRAFTY["servers"]["s3"]["name"] = 12345
    await coordinator.async_refresh()
    check(
        "S2b odd types (running 'yes', ping 1, port 'abc', numeric name) -> off/off, port None, name = ID",
        coordinator.data["s3"] == {"name": "s3", "port": None, "running": False, "online": False},
        coordinator.data.get("s3"),
    )
    CRAFTY["servers"]["s3"]["name"] = "  " + "N" * 300
    await coordinator.async_refresh()
    check("S2b a 300-character name is cut to 100", coordinator.data["s3"]["name"] == "N" * 100)
    CRAFTY["stats_mode"]["s3"] = "nulls"
    CRAFTY["servers"]["s3"]["name"] = None

    # --- S2c server IDs that could change an API path are skipped, never requested ---
    CRAFTY["calls"].clear()
    for bad_id in ("../../servers", "a b", "s1/action/stop_server", "x" * 65):
        CRAFTY["servers"][bad_id] = {"name": "Bad", "port": 1, "running": True, "ping": True}
    await coordinator.async_refresh()
    requested = [path for _, path in CRAFTY["calls"]]
    check(
        "S2c invalid server IDs skipped: no entities, no requests, others fine",
        len(hass.entities) == 6
        and set(coordinator.data) == {"s1", "s2", "s3"}
        and requested == ["/api/v2/servers"] + [f"/api/v2/servers/{sid}/stats" for sid in ("s1", "s2", "s3")],
        requested,
    )
    for bad_id in ("../../servers", "a b", "s1/action/stop_server", "x" * 65):
        del CRAFTY["servers"][bad_id]

    # --- S2d stats requests run a few at a time, not all at once ---
    for n in range(10):
        CRAFTY["servers"][f"extra{n}"] = {"name": f"Extra {n}", "port": 30000 + n, "running": False, "ping": False}
    coordinator_module = importlib.import_module("crafty_controller.coordinator")
    coordinator_module.MAX_SERVERS = 8
    CRAFTY["stats_delay"], CRAFTY["stats_max_in_flight"] = 0.05, 0
    await coordinator.async_refresh()
    check(
        "S2d at most 4 stats requests at once",
        0 < CRAFTY["stats_max_in_flight"] <= 4,
        CRAFTY["stats_max_in_flight"],
    )
    check("S2d only the first MAX_SERVERS servers are taken", len(coordinator.data) == 8, len(coordinator.data))
    coordinator_module.MAX_SERVERS = 200
    CRAFTY["stats_delay"] = 0
    for n in range(10):
        del CRAFTY["servers"][f"extra{n}"]
    hass.entities[:] = [entity for entity in hass.entities if not entity.server_id.startswith("extra")]
    await coordinator.async_refresh()

    # --- S3 server removed in Crafty, then returns ---
    gone = CRAFTY["servers"].pop("s3")
    await coordinator.async_refresh()
    check(
        "S3 removed server -> unavailable, no KeyError",
        state_of(hass, SWITCH, "s3")[0] == "unavailable" and state_of(hass, STATUS, "s3")[0] == "unavailable",
    )
    CRAFTY["servers"]["s3"] = gone
    await coordinator.async_refresh()
    check(
        "S3 returns -> available again, no duplicate entities",
        state_of(hass, SWITCH, "s3")[0] == "off" and len(hass.entities) == 6,
        len(hass.entities),
    )

    # --- S4 server added later ---
    CRAFTY["servers"]["s4"] = {"name": "Modded", "port": 25570, "running": True, "ping": True}
    await coordinator.async_refresh()
    check(
        "S4 new server gets entities without reload",
        len(hass.entities) == 8 and state_of(hass, SWITCH, "s4") == ("on", {"port": 25570}),
        len(hass.entities),
    )
    check("S4 unique_ids still unique", len({err._attr_unique_id for err in hass.entities}) == 8)

    # --- S5 whole-API failure modes, then recovery ---
    for mode in ("html", "error_status", "500", "wrong_shape", "redirect", "huge", "deep", "data_not_list", "hang"):
        CRAFTY["list_mode"] = mode
        await coordinator.async_refresh()
        all_unavailable = all(render(err)[0] == "unavailable" for err in hass.entities)
        check(
            f"S5 list={mode}: UpdateFailed, all unavailable, no unexpected exception",
            (not coordinator.last_update_success) and all_unavailable and not coordinator.unexpected,
            (coordinator.unexpected[-1:] if coordinator.unexpected else ""),
        )
    CRAFTY["list_mode"] = "ok"
    await coordinator.async_refresh()
    check(
        "S5 recovers after outage",
        coordinator.last_update_success and all(render(err)[0] != "unavailable" for err in hass.entities),
    )
    coordinator._token = "BAD"
    await coordinator.async_refresh()
    check(
        "S5 revoked token -> unavailable and Home Assistant asks for a new token (reauth)",
        (not coordinator.last_update_success) and entry.reauth_started == 1 and not coordinator.unexpected,
        entry.reauth_started,
    )
    coordinator._token = "GOOD"
    await coordinator.async_refresh()

    # --- S6 switch actions ---
    CRAFTY["calls"].clear()
    creative_switch = find_entity(hass, SWITCH, "s2")
    await creative_switch.async_turn_on()
    check("S6 turn_on: POST start_server sent", ("POST", "/api/v2/servers/s2/action/start_server") in CRAFTY["calls"])
    check(
        "S6 turn_on: refresh from Crafty requested, coordinator data left as Crafty reported it",
        coordinator.refresh_requests == 1 and coordinator.data["s2"]["running"] is False,
        (coordinator.refresh_requests, coordinator.data["s2"]),
    )
    check("S6 turn_on: switch shows ON while Crafty catches up (no flicker)", state_of(hass, SWITCH, "s2")[0] == "on")
    await asyncio.sleep(0.5)
    await coordinator.async_refresh()
    check(
        "S6 after server actually starts, poll confirms ON + status online",
        state_of(hass, SWITCH, "s2")[0] == "on" and state_of(hass, STATUS, "s2")[0] == "on",
    )
    await creative_switch.async_turn_off()
    check("S6 turn_off: OFF immediately", state_of(hass, SWITCH, "s2")[0] == "off")
    await asyncio.sleep(0.5)
    await coordinator.async_refresh()
    check("S6 poll confirms OFF", state_of(hass, SWITCH, "s2")[0] == "off" and state_of(hass, STATUS, "s2")[0] == "off")
    for mode in ("403", "error_status"):
        CRAFTY["action_mode"] = mode
        try:
            await creative_switch.async_turn_on()
            raised = False
        except HomeAssistantError:
            raised = True
        check(
            f"S6 action {mode}: HomeAssistantError raised, state NOT flipped",
            raised and state_of(hass, SWITCH, "s2")[0] == "off",
        )
    CRAFTY["action_mode"] = "ok"
    # A server that never starts: once the pending time is over, the switch shows what Crafty reports.
    switch_module = importlib.import_module("crafty_controller.switch")
    switch_module.const.PENDING_STATE_SECONDS = 0.2
    CRAFTY["delay"] = 60
    await creative_switch.async_turn_on()
    check("S6 start that hasn't happened yet: ON", state_of(hass, SWITCH, "s2")[0] == "on")
    await asyncio.sleep(0.3)
    await coordinator.async_refresh()
    check("S6 server never started: back to OFF after the pending time", state_of(hass, SWITCH, "s2")[0] == "off")
    switch_module.const.PENDING_STATE_SECONDS = 60
    CRAFTY["delay"] = 0.3
    creative_switch.server_id = "../s1"
    try:
        await creative_switch.async_turn_off()
        refused = False
    except HomeAssistantError:
        refused = True
    check("S6 action for an invalid server ID is refused before any request", refused)
    creative_switch.server_id = "s2"

    # --- S7 config flow ---
    def new_flow(source="user", flow_entry=None, entries=()):
        config_flow = CraftyFlow()
        config_flow.hass, config_flow.source, config_flow.entry, config_flow.entries = None, source, flow_entry, entries
        return config_flow

    async def flow(url, token, verify=False):
        return await new_flow().async_step_user({"url": url, "token": token, "verify_ssl": verify})

    form = await new_flow().async_step_user()
    defaults = {field.schema: field.default for field in form["schema"].schema}
    check("S7 form: Verify SSL certificate is on by default", defaults.get("verify_ssl") is True, defaults)
    check(
        "S7 form: the example URL is given as a placeholder",
        form["placeholders"] == {"example_url": "https://crafty.example.com:8443"},
        form["placeholders"],
    )

    result = await flow(f"  {url}/  ", " GOOD ")
    check(
        "S7 flow ok: entry created, URL + token normalised",
        result["type"] == "create_entry" and result["data"]["url"] == url and result["data"]["token"] == "GOOD",
        result,
    )
    result = await flow(url, "BAD")
    check("S7 flow bad token -> invalid_auth", result["errors"] == {"base": "invalid_auth"}, result)
    result = await flow("http://127.0.0.1:1", "GOOD")
    check("S7 flow unreachable -> cannot_connect", result["errors"] == {"base": "cannot_connect"}, result)
    result = await flow(f"127.0.0.1:{port}", "GOOD")
    check(
        "S7 flow no-scheme/TLS mismatch -> cannot_connect, no crash",
        result["errors"] == {"base": "cannot_connect"},
        result,
    )
    for mode in ("html", "500", "wrong_shape", "redirect", "huge", "hang"):
        CRAFTY["list_mode"] = mode
        result = await flow(url, "GOOD")
        check(
            f"S7 flow list={mode} -> cannot_connect (not a false 'success')",
            result["errors"] == {"base": "cannot_connect"},
            result,
        )
    CRAFTY["list_mode"] = "ok"

    # --- S7a reauth: a new token is checked, then saved ---
    old_entry = ConfigEntry({"url": url, "token": "OLD", "verify_ssl": False})
    reauth = new_flow("reauth", old_entry)
    result = await reauth.async_step_reauth(old_entry.data)
    check("S7a reauth asks for a token", result["type"] == "form" and result["step_id"] == "reauth_confirm", result)
    result = await reauth.async_step_reauth_confirm({"token": "BAD"})
    check(
        "S7a reauth with a token Crafty rejects -> invalid_auth, entry unchanged",
        result["errors"] == {"base": "invalid_auth"} and old_entry.data["token"] == "OLD",
        result,
    )
    result = await reauth.async_step_reauth_confirm({"token": " GOOD "})
    check(
        "S7a reauth with a working token -> saved (trimmed), entry reloaded",
        result == {"type": "abort", "reason": "reauth_successful"} and old_entry.data["token"] == "GOOD",
        (result, old_entry.data),
    )

    # --- S7c reconfigure: a new URL / SSL setting is checked with the stored token, then saved ---
    moved_entry = ConfigEntry({"url": "http://127.0.0.1:1", "token": "GOOD", "verify_ssl": True}, entry_id="moved")
    other_entry = ConfigEntry({"url": "http://other:8443", "token": "GOOD", "verify_ssl": True}, entry_id="other")
    reconfigure = new_flow("reconfigure", moved_entry, (moved_entry, other_entry))
    result = await reconfigure.async_step_reconfigure()
    defaults = {field.schema: field.default for field in result["schema"].schema}
    check(
        "S7c reconfigure form is filled in with the current URL and SSL setting, and has no token field",
        defaults == {"url": "http://127.0.0.1:1", "verify_ssl": True},
        defaults,
    )
    check("S7c reconfigure form gets the example URL placeholder", "example_url" in result["placeholders"])
    result = await reconfigure.async_step_reconfigure({"url": "http://other:8443/", "verify_ssl": True})
    check("S7c reconfigure to another entry's URL -> already_configured", result["reason"] == "already_configured")
    result = await reconfigure.async_step_reconfigure({"url": "http://127.0.0.1:2", "verify_ssl": False})
    check(
        "S7c reconfigure to an unreachable URL -> cannot_connect, entry unchanged",
        result["errors"] == {"base": "cannot_connect"} and moved_entry.data["url"] == "http://127.0.0.1:1",
        result,
    )
    result = await reconfigure.async_step_reconfigure({"url": f" {url}/ ", "verify_ssl": False})
    check(
        "S7c reconfigure to a working URL -> saved (tidied), token kept",
        result == {"type": "abort", "reason": "reconfigure_successful"}
        and moved_entry.data == {"url": url, "token": "GOOD", "verify_ssl": False},
        (result, moved_entry.data),
    )

    # --- S7b entity ID renamed: every entity opts in to staying in place (Home Assistant 2026.11) ---
    # The hook has to be the integration's own (defining it is the opt-in), and it has to call Home Assistant's.
    base_class = importlib.import_module("crafty_controller.entity").CraftyEntity
    check("S7b the base entity defines async_entity_id_changed", "async_entity_id_changed" in vars(base_class))
    renamed = []
    for entity in hass.entities:
        entity.async_entity_id_changed("switch.old_name")
        renamed.append(getattr(entity, "entity_id_changes", 0) == 1)
    check("S7b every entity passes an entity ID rename on to Home Assistant", bool(renamed) and all(renamed), renamed)

    # --- S8 unload ---
    for unload in entry._un:
        unload()
    check("S8 unload removes coordinator listeners (no leak)", len(coordinator._l) == 0, len(coordinator._l))
    check(
        "overall: no unexpected (non-UpdateFailed) exceptions anywhere",
        not coordinator.unexpected,
        coordinator.unexpected,
    )
    server.close()


asyncio.run(asyncio.wait_for(main(), 90))
print(f"\n{sum(RESULTS)}/{len(RESULTS)} checks passed")
sys.exit(0 if all(RESULTS) else 1)
