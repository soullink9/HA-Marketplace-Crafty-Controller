# Installation

You need Home Assistant 2026.9 or newer and a Crafty Controller 4 that Home Assistant can reach over the network.

## From the Marketplace

In Home Assistant 2026.11 and newer, open **Settings → Marketplace**, search for **Crafty Controller** and install it, then
restart Home Assistant. Updates then show up under **Settings → Updates**.

If it isn't listed yet, add it from its link instead: this repository's address,
`https://github.com/soullink9/HA-Marketplace-Crafty-Controller`. Adding from a link needs Home Assistant to be connected to GitHub.

To install by hand instead, follow the steps below.

## Download

1. Copy the [`custom_components/crafty_controller`](../custom_components/crafty_controller) folder from this repository into `/config/custom_components/`. The result must be:

   ```
   config/custom_components/crafty_controller/__init__.py
   config/custom_components/crafty_controller/manifest.json
   ...
   ```

2. **Restart Home Assistant.** A full restart is needed the first time. Reloading is not enough for a brand-new integration.

## Add the integration

1. Go to **Settings → Devices & services → Add integration** and search for **Crafty Controller**.
2. Fill in the form (see [Configuration](Configuration.md)):
   - **URL** of your Crafty, for example `https://192.168.1.10:8443`
   - **API token**
   - **Verify SSL certificate**
3. When it connects, every Minecraft server in Crafty appears as a device.

Nothing showing up, or an error on the form? See [Troubleshooting](Troubleshooting.md).