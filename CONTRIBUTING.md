# Contributing / maintaining

Thanks for helping out. This file is the map for anyone taking over the code.

## Project layout

```
custom_components/crafty_controller/
├── __init__.py       Set-up/unload: creates the coordinator, forwards to the platforms
├── const.py          DOMAIN, PLATFORMS, poll interval, request timeout, the ERRORS tuple
├── api.py            The one function that calls Crafty (auth, timeout, response checks)
├── coordinator.py    Polls Crafty every 30 s and holds the data for all servers
├── entity.py         Base entity (device, unique ID, availability) + entity creation helper
├── switch.py         On/off switch per server (start_server / stop_server)
├── binary_sensor.py  Online/offline status sensor per server
├── config_flow.py    Set-up form: URL, API token, SSL check
├── manifest.json     Integration metadata (bump "version" on every release)
├── translations/     UI strings for the config flow (en.json)
└── brand/            Icons (icon.png 256 px, icon@2x.png 512 px)
tests/
├── stubs.py          Stand-ins for aiohttp, voluptuous and Home Assistant
└── test_integration.py  Dependency-free simulation against a mock Crafty server
```

## How data flows

1. `CraftyCoordinator` calls `GET /servers`, then `GET /servers/{id}/stats` for each server in parallel.
2. `_parse_server()` boils each reply down to `{name, port, running, online}`, stored in `coordinator.data[server_id]`.
3. Entities only read `coordinator.data`. A server missing from `data` is shown as unavailable.
4. Turning the switch on or off calls `POST /servers/{id}/action/start_server` or `stop_server`, then updates the state optimistically; the next poll confirms it.

Crafty API endpoints used (API v2, [spec](https://docs.craftycontrol.com/pages/developer-guide/api-reference/v2/)):

| Call | Used for |
| --- | --- |
| `GET /api/v2/servers` | List servers (name, port); also validates the token in the config flow |
| `GET /api/v2/servers/{id}/stats` | `running` and `int_ping_results` |
| `POST /api/v2/servers/{id}/action/{start_server\|stop_server}` | The switch |

## Conventions

- **Unique IDs are permanent.** `_key` on each entity class (`power`, `status`) feeds the unique ID. Changing it orphans users' existing entities.
- **One error path.** Network and API problems all surface as the `ERRORS` tuple in `const.py`. Catch that tuple, not individual exceptions.
- **Keep it minimal.** The goal is a small integration: on/off, status, port, name. Think twice before adding more.
- Keep comments and docstrings current; the code is meant to be readable by someone new.

## Running the simulation

```
python3 tests/test_integration.py
```

Needs Python 3.12+ and nothing else. It loads the real integration files against stand-ins for Home Assistant, aiohttp and voluptuous, and a mock Crafty server that returns messy data (missing fields, 403s, HTML pages, hangs, removed and added servers, failed actions) and checks the entities and config flow behave. It exits non-zero if any check fails.

It does **not** test real Home Assistant, real HTTP/TLS, or a real Crafty. Always try changes on a real instance too.

## Standards for every change

- **Readable over clever.** Write code a newcomer can follow on the first read. Prefer a few plain lines with a named
  variable to a dense one-liner, a nested conditional expression, or a trick that needs a comment to decode.
- **Comment the why.** Every function and class has a docstring. Comments explain why the code does something
  non-obvious (a quirk of the device or service, a Home Assistant rule, a deliberate trade-off), not what each line
  does.
- **Keep names consistent.** Follow the names already used in the integration: the same words for
  the same things, Home Assistant's conventions for entities and config entries, `snake_case` for Python names and
  `camelCase` for JavaScript.
- **Keep the docs in step.** When you change a function, class or behaviour, update its docstring, its comments and the
  pages under `docs/` (and the README) that describe it in the same commit.
- **Keep the tests green.** Every change keeps existing behaviour and passes all of the tests. When you
  fix a bug, add the situation that caused it to the tests so it stays fixed.
- **No new dependencies without approval.** Don't add a third-party library (to a `manifest.json`, a
  `requirements.txt` or CI) without asking in an issue first. This page says what it already depends on and why.

### Test layout

The tests use these names:

```
tests/
  stubs.py                stand-ins for Home Assistant and the libraries the integration uses
  test_integration.py     the real integration against the stand-ins and a fake device or service
  test_<subject>.py       any other checks (test_engine.py, test_blueprint.py, test_live_proxy.py)
  test_<subject>_soak.py  a long simulation: it takes a length as an argument, and CI runs a short one
  fake_<service>.py       a fake device or service, when it's too big to live inside the test
  requirements.txt        what the tests need beyond Python, if they need anything
```

Every `test_*.py` is a plain script, not a pytest suite: run it with `python3` from the repository root, and it
exits non-zero if any check fails.

### The Marketplace

`hacs.json` at the root is the Marketplace's file: the name it lists and the oldest Home Assistant version the
integration works with. Keep that version in step with the README's requirements.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/): a type, an optional scope, then a short summary in
the imperative.

```
feat: add a diagnostics download
fix: keep the last value when the service is briefly unreachable
refactor: split the coordinator's update into steps
docs: explain the safety settings
test: cover a reply with a missing field
chore: update the CI actions
```

## Releasing

1. Update `CHANGELOG.md` and bump `version` in `manifest.json`.
2. Run the simulation and make sure the GitHub *CI* workflow is green.
3. Publish it: push the tag (`git tag vX.Y.Z && git push origin vX.Y.Z`), or open **Actions → Release → Run
   workflow** and enter the version. The [Release workflow](.github/workflows/release.yml) checks the manifest
   and `CHANGELOG.md` are at that version, then publishes the GitHub release the Marketplace installs from.

## Known limitations / ideas

- No reconfigure or re-auth flow: to change the URL or token, remove and re-add the integration.
- A server renamed in Crafty keeps its old device name in Home Assistant until the device is renamed there.
- The smallest set of Crafty API-key permissions that works has not been pinned down; see the [Configuration](docs/Configuration.md) page.

## Reporting bugs

[Open an issue](https://github.com/soullink9/HA-Marketplace-Crafty-Controller/issues/new/choose) with your Home Assistant version, the integration's
version, what you did and what you expected.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).
