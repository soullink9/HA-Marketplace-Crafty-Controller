"""Simulation test for the Crafty Controller integration.

Run:  python3 tests/test_integration.py      (Python 3.12+, no other dependencies)

The real integration files are loaded and run against a mock Crafty server that
returns messy data: missing fields, 403s, HTML pages, hangs, servers that are
removed or added, and failing start/stop actions. It prints PASS/FAIL per check
and exits non-zero if any check fails.

aiohttp, voluptuous and the Home Assistant base classes are thin stand-ins
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
CRAFTY = {"servers": {}, "list_mode": "ok", "stats_mode": {}, "action_mode": "ok", "delay": 0.3, "calls": []}


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


async def route(method, path, headers):
    """Answer one request like Crafty's API v2: /servers, /servers/<id>/stats or /servers/<id>/action/<action>."""
    if headers.get("authorization") != "Bearer GOOD":
        return json_reply({"status": "error", "error": "NOT_AUTHORIZED"}, 403)
    if path == "/api/v2/servers":
        mode = CRAFTY["list_mode"]
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
        return json_reply(
            {
                "status": "ok",
                "data": [server_record(server_id, server) for server_id, server in CRAFTY["servers"].items()],
            }
        )
    parts = path.split("/")
    server_id = parts[4]
    if server_id not in CRAFTY["servers"]:
        return json_reply({"status": "error", "error": "SERVER_NOT_FOUND"}, 404)
    server = CRAFTY["servers"][server_id]
    if parts[5] == "stats":
        mode = CRAFTY["stats_mode"].get(server_id, "top")
        if mode == "403":
            return json_reply({"status": "error"}, 403)
        if mode == "html":
            return 200, "text/html", b"<html/>"
        if mode == "nulls":
            return json_reply({"status": "ok", "data": None, "running": None, "int_ping_results": None})
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
        status, content_type, body = await route(method, path, headers)
        writer.write(
            f"HTTP/1.1 {status} X\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
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
        translations_ok = set(translations["config"]["step"]["user"]["data"]) == {"url", "token", "verify_ssl"} and {
            "cannot_connect",
            "invalid_auth",
        } <= set(translations["config"]["error"])
        check("layout: py compiles, manifest + translations valid and match flow keys", manifest_ok and translations_ok)
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
    for mode in ("html", "error_status", "500", "wrong_shape", "hang"):
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
        "S5 revoked token -> unavailable (no crash)",
        (not coordinator.last_update_success) and not coordinator.unexpected,
    )
    coordinator._token = "GOOD"
    await coordinator.async_refresh()

    # --- S6 switch actions ---
    CRAFTY["calls"].clear()
    creative_switch = find_entity(hass, SWITCH, "s2")
    await creative_switch.async_turn_on()
    check("S6 turn_on: POST start_server sent", ("POST", "/api/v2/servers/s2/action/start_server") in CRAFTY["calls"])
    check("S6 turn_on: switch shows ON immediately (no flicker)", state_of(hass, SWITCH, "s2")[0] == "on")
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

    # --- S7 config flow ---
    async def flow(url, token, verify=False):
        config_flow = CraftyFlow()
        config_flow.hass = None
        return await config_flow.async_step_user({"url": url, "token": token, "verify_ssl": verify})

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
    for mode in ("html", "500", "wrong_shape", "hang"):
        CRAFTY["list_mode"] = mode
        result = await flow(url, "GOOD")
        check(
            f"S7 flow list={mode} -> cannot_connect (not a false 'success')",
            result["errors"] == {"base": "cannot_connect"},
            result,
        )
    CRAFTY["list_mode"] = "ok"

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
