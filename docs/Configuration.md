# Configuration

The integration is set up entirely from the Home Assistant UI. There is nothing to add to `configuration.yaml`.

## URL

The address of Crafty's web interface, including the port. Crafty's default HTTPS port is `8443`, so a typical value is `https://192.168.1.10:8443`. If you leave out `http://` or `https://`, `https://` is assumed. A trailing `/` is removed.

## API token

Create an API key in Crafty (from your user's page) and paste it in. The token decides which servers Home Assistant can see and what it may do, so it needs:

- access to the servers you want in Home Assistant, and
- permission to run server actions (Crafty's **Commands** permission), which the on/off switch needs to start and stop servers.

To keep access limited, consider creating a dedicated Crafty user and API key for Home Assistant instead of using your admin account.

**What is not established:** the smallest set of key permissions that works has not been pinned down. In early testing, a key without enough permissions made Crafty return an empty server list, so the integration was added but showed no devices, while a key with full access listed the servers. If you find a smaller set that works, please share it in an issue.

## Verify SSL certificate

Crafty uses a self-signed certificate by default. Leave this **off** in that case. Turn it on only if Crafty has a certificate your Home Assistant trusts (for example one behind a reverse proxy).

## Changing the URL or token later

There is no reconfigure option yet. Remove the integration (**Settings → Devices & services → Crafty Controller → ⋮ → Delete**) and add it again with the new details.