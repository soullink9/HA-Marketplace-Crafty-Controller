# Configuration

The integration is set up entirely from the Home Assistant UI. There is nothing to add to `configuration.yaml`.

## URL

The address of Crafty's web interface, including the port. Crafty's default HTTPS port is `8443`, so a typical value is `https://192.168.1.10:8443`. If you leave out `http://` or `https://`, `https://` is assumed. A trailing `/` is removed.

Use the exact address Crafty answers on. The integration doesn't follow redirects, so the API token only ever goes to
the address you entered: if Crafty or a reverse proxy redirects (for example from `http://` to `https://`), the form
says it can't reach Crafty, and the fix is to enter the address it redirects to.

## API token

Create an API key in Crafty (from your user's page) and paste it in. The token decides which servers Home Assistant can see and what it may do, so it needs:

- access to the servers you want in Home Assistant, and
- permission to run server actions (Crafty's **Commands** permission), which the on/off switch needs to start and stop servers.

To keep access limited, consider creating a dedicated Crafty user and API key for Home Assistant instead of using your admin account.

**What is not established:** the smallest set of key permissions that works has not been pinned down. In early testing, a key without enough permissions made Crafty return an empty server list, so the integration was added but showed no devices, while a key with full access listed the servers. If you find a smaller set that works, please share it in an issue.

## Verify SSL certificate

**On by default.** Home Assistant then only talks to a Crafty whose certificate it trusts, for example one from Let's
Encrypt, directly or behind a reverse proxy. Keep it on whenever you can.

Crafty's own default certificate is self-signed, which Home Assistant can't check. To use it, turn this **off**. The
connection is still encrypted, but Home Assistant can no longer tell it's talking to your Crafty: someone able to
intercept traffic on your network could pose as Crafty, take the API token and start or stop your servers. If you
turn it off, keep Crafty on a network you trust, or give it a proper certificate instead.

With an `http://` URL nothing is encrypted and this setting has no effect.

## Changing the URL or settings later

Go to **Settings → Devices & services → Crafty Controller → ⋮ → Reconfigure** to change the URL or the
**Verify SSL certificate** setting. The new details are checked before they're saved, and your devices and entities
stay as they are.

## A new API token

When Crafty rejects the token (it was deleted, or the user lost access), the entities go unavailable and Home
Assistant shows a **Reauthenticate** notice for Crafty Controller under **Settings → Devices & services**. Create a new
API key in Crafty and enter it there; the integration reloads with it.