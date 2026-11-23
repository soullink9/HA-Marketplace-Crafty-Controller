# Changelog

## 1.4.1 (2026-11-23)

- Fixes Home Assistant's integration check (hassfest), which failed on 1.4.0 because the set-up forms had an example
  URL in their translations. The example is now passed in as a placeholder and shown under the URL field. No other
  changes.

## 1.4.0 (2026-11-22)

Hardening after a security review.

### Set-up

- **Verify SSL certificate is now on by default** for new set-ups, so the API token only goes to a Crafty whose
  certificate Home Assistant trusts. Turn it off for Crafty's own self-signed certificate; the form now explains what
  that means. Existing set-ups keep their setting.
- **Reconfigure:** change the URL or the SSL setting from **⋮ → Reconfigure**, without removing the integration.
- **Reauthenticate:** when Crafty rejects the token, Home Assistant asks for a new one instead of leaving everything
  unavailable.

### Talking to Crafty

- Redirects are no longer followed, so the token only ever goes to the address that was set up. A redirect shows as
  "Cannot reach Crafty"; enter the address it points to.
- Every reply is checked before use: at most 1 MiB, the server list must be a list (at most 200 servers), and each
  field's type is checked (an odd name, port or state falls back to a safe value instead of reaching an entity).
- Server IDs that aren't valid Crafty IDs are skipped, and IDs are percent-encoded in every request.
- At most four stats requests run at once, instead of one per server all together.
- After a start or stop the integration refreshes from Crafty straight away. The switch shows the requested state
  until Crafty reports it (at most a minute), without changing the polled data.

### Repository

- Every GitHub action is pinned to a commit, the Gitea jobs' image to a digest, and `ruff` to a version.
- Workflows are read-only by default; only the job that publishes a release may write. The Gitea checkout no longer
  puts the token on git's command line, and GitHub's checkouts don't keep theirs.

## 1.3.0 (2026-11-15)

### Home Assistant 2026.11 or newer only

- Needs Home Assistant 2026.11 or newer (it was 2026.9). Only the latest Home Assistant is supported from now on, so
  the Marketplace doesn't offer this version to older installations; they keep 1.2.0.
- The entities stay in place when their entity ID is renamed, instead of being removed and added again (the new
  behaviour in Home Assistant 2026.11).
- The set-up form uses Probatio, Home Assistant's validation library, directly instead of the old `voluptuous` name.
- Dropped `from __future__ import annotations`, which Python 3.14 no longer needs.
- The README's Marketplace button opens the Marketplace link (`marketplace_repository`) instead of the HACS one, and
  the docs say a new install from the Marketplace needs no restart.

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
