# Changelog

## Unreleased

### Repository

- Gitea is the main copy: its runner checks every push and publishes releases (`.gitea/workflows/`), with nothing
  downloaded from GitHub, so it keeps working when GitHub can't be reached. Gitea push-mirrors to GitHub, and every
  push from it publishes on GitHub the releases GitHub doesn't have yet, with the same files and notes, where the
  Marketplace installs from.
- The release helpers live in `scripts/` and are used by both: the version check and notes, building the zip, and
  publishing on Gitea. Every release's notes now start with how to install it.
- The release's zip is now always `crafty_controller.zip` (it had the version in its name), so
  `.../releases/latest/download/crafty_controller.zip` always gets the newest. Each zip is checked before it's published.

## 1.2.0 (2026-11-04)

- Moved to its own repository, [HA-Marketplace-Crafty-Controller](https://github.com/soullink9/HA-Marketplace-Crafty-Controller), so it can be installed and updated
  from the Home Assistant Marketplace (Home Assistant 2026.11 and newer). Installing by hand works as before.
- Lists its categories, so it shows up in the right place when browsing the Marketplace. No other changes to how
  the integration works.

## 1.1.1 (2026-11-02)

- No changes to the integration.

## 1.1.0 (2026-11-01)

- No changes to the integration.

## 1.0.2 (2026-11-01)

- No changes to the integration.

## 1.0.0 (2026-11-01)

Initial release.

- One Home Assistant device per Crafty server.
- Switch to start and stop a server.
- Status sensor showing whether the server is online (answering) or offline.
- Server name (device name) and port (`port` attribute) on each entity.
- Config flow asking for the Crafty URL, API token and SSL verification.
- Servers added in Crafty later appear without reloading the integration.
- Per-server error isolation: one unreadable server does not affect the others.
- Request timeouts and clear errors when Crafty is unreachable or replies unexpectedly.
- Brand icons and a simulation test.
