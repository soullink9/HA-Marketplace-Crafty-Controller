# Disclosure

This project was primarily created for personal use and for my family. While I may provide updates, they are not guaranteed. However, if you've stumbled upon this and find it interesting, feel free to download and use it. I had a great time building this and hope you enjoy it.

Note: Built with the assistance of Claude.ai. I’m putting it here now so you don't have to hunt for it below.

<p align="center">
  <img src="docs/images/logo.png" alt="soullink9 logo" width="200">
</p>

# Crafty Controller for Home Assistant

> Start and stop your Minecraft servers from Home Assistant, and see at a glance which ones are running.

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=soullink9&repository=HA-Marketplace-Crafty-Controller&category=integration)

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=crafty_controller)

A small custom integration for [Crafty Controller](https://craftycontrol.com/). It is deliberately minimal: it does the few things needed to turn a server on and know what is already running, and nothing else.

## What you get

Every Minecraft server in Crafty becomes a Home Assistant device with:

- **A switch**: on while the server is running. Turn it on to start the server, off to stop it.
- **A status sensor**: online when the server is answering and players can connect. It stays off while a server is still starting up.
- **The server's name and port**: the name is the device name, and the port is a `port` attribute on both entities.

Servers added in Crafty later appear on their own. If one server can't be read, only that server goes `unavailable`. Crafty is polled locally every 30 seconds.

## Requirements

- Home Assistant 2026.9 or newer
- Crafty Controller 4 (API v2), reachable from Home Assistant
- A Crafty API token (see [Configuration](docs/Configuration.md))

## Install

Install **Crafty Controller** from the Marketplace (**Settings → Marketplace**, Home Assistant 2026.11 and newer), or copy the [`custom_components/crafty_controller`](custom_components/crafty_controller) folder into `/config/custom_components/`, then restart Home Assistant.

Then go to **Settings → Devices & services → Add integration → Crafty Controller** and enter your Crafty URL (for example `https://192.168.1.10:8443`) and API token. Full steps are in the [Installation](docs/Installation.md) page.

## Documentation

Details live in the other pages here:

| Page | What's in it |
| --- | --- |
| [Installation](docs/Installation.md) | Installing, adding the integration |
| [Configuration](docs/Configuration.md) | Crafty URL, API token and permissions, SSL |
| [Entities](docs/Entities.md) | The switch, the status sensor, attributes and states |
| [Troubleshooting](docs/Troubleshooting.md) | No devices, can't connect, unavailable entities |
| [Development](docs/Development.md) | Pointers for maintainers |

## Privacy

The integration only talks to the Crafty address you enter. There is no cloud service and no telemetry. Your API token is stored by Home Assistant in the integration's config entry, like any other integration credential.

## Contributing

Bug reports and pull requests are welcome, although replies are not guaranteed (see the [Disclosure](#disclosure) above). [CONTRIBUTING.md](CONTRIBUTING.md) explains the code layout, how to run the simulation test, and the release steps.

## Credits

- **[Crafty Controller](https://craftycontrol.com/)** by Arcadia Technology. This integration is a client for Crafty's [v2 API](https://docs.craftycontrol.com/pages/developer-guide/api-reference/v2/), and Crafty does all of the actual server management.
- **[Home Assistant developer documentation](https://developers.home-assistant.io/)**. The integration follows its documented patterns (config flow, `DataUpdateCoordinator`, `runtime_data`).
- **[Claude](https://claude.ai)** by Anthropic, which assisted in building this project.

No code was copied or adapted from other projects. The icon is original artwork made for this project; it is not Crafty's or Minecraft's artwork.

## Disclaimer

This is an unofficial community project. It is not affiliated with or endorsed by Arcadia Technology (Crafty Controller), Mojang or Microsoft. Minecraft is a trademark of its respective owners.

## License

[GNU General Public License v3.0](LICENSE) (GPL-3.0).
