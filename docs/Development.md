# Development

The maintainer notes live in the repository so they stay in sync with the code:

- [CONTRIBUTING.md](../CONTRIBUTING.md): project layout, how data flows, the Crafty API calls used, conventions, checking a change, release steps and known limitations.
- [CHANGELOG.md](../CHANGELOG.md): what changed in each version.

The Crafty API reference is at [docs.craftycontrol.com](https://docs.craftycontrol.com/pages/developer-guide/api-reference/v2/).

## Tests and releases: the files

Gitea is the main copy of this repository; it push-mirrors to GitHub, the public copy people install from.

| File | What it does |
|---|---|
| `.gitea/workflows/test.yml` | Runs every check on each push to Gitea (lint, the tests and building the zip, on Python 3.14), with no actions downloaded from GitHub |
| `.gitea/workflows/release.yml` | Publishes a release on Gitea (Run workflow button, or a pushed version tag); its tag then reaches GitHub through the push mirror |
| `.github/workflows/release.yml` | After any push from Gitea's mirror (or from its Run workflow button), publishes every version tag GitHub has no release for yet, with the same files, title and notes as Gitea's: the copy the Marketplace installs from |
| `.github/workflows/ci.yml` | GitHub's checks on every push: lint, the tests and Home Assistant's `hassfest` (which comes from GitHub, so it runs only there) |
| `.github/workflows/validate.yml` | The Marketplace's own checks (the HACS action), which its catalog requires; GitHub only, for the same reason |
| `scripts/release_notes.py` | Shared by both release workflows: checks the version, gives the release's title, writes the notes (install steps with the zip's address on GitHub, then the changelog section) |
| `scripts/build_package.py` | Builds `dist/crafty_controller.zip`, the same bytes every time, and checks it with `check_package.py` |
| `scripts/check_package.py` | Checks the zip the way it gets installed: one `crafty_controller/` folder, a manifest for that domain at the repository's version, the icon, exactly the integration's files |
| `scripts/publish_gitea_release.py` | Creates or updates the Gitea release and uploads its files, through Gitea's API (standard library only) |
| `scripts/plan_github_releases.py` | Used by the GitHub release workflow: lists the version tags GitHub has no published release for yet, oldest first, and which one becomes "Latest" (standard library only) |
| `tests/test_release.py` | Tests all five scripts, publishing against a fake Gitea server |
