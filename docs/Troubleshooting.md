# Troubleshooting

## "Config flow could not be loaded: Invalid handler specified"

Home Assistant can't load the integration's files. Check that the folder is exactly `config/custom_components/crafty_controller/`, that it directly contains `__init__.py` (two underscores each side), `manifest.json`, `config_flow.py` and the other files, and that there are no extra nested folders or `.txt` extensions. Then do a **full restart** of Home Assistant and refresh the browser. The log (**Settings → System → Logs**, search `crafty_controller`) shows the exact error.

## The integration was added but there are no devices

Crafty returned an empty server list for your token. Check from any computer:

```
curl -k -H "Authorization: Bearer YOUR_TOKEN" https://CRAFTY_HOST:8443/api/v2/servers
```

If the reply is `{"status":"ok","data":[]}`, the token can't see any servers: create a key with more permissions (see [Configuration](Configuration.md)). If you get a 403, the token is wrong or lacks API access. Once it lists servers, devices appear within 30 seconds.

## "Cannot reach Crafty at that address"

- Check the URL and port, and that Home Assistant can reach that machine (firewall, Docker networking).
- Use the address Crafty's web interface uses, including `https://` and the port.
- If Crafty uses its default self-signed certificate, turn **Verify SSL certificate** off (see
  [Configuration](Configuration.md#verify-ssl-certificate) for what that means). With it on, the certificate must be
  one Home Assistant trusts and must match the host name in the URL.
- Redirects aren't followed: use the address Crafty ends up on (for example `https://` instead of `http://`).
- The reply must come from Crafty's API; a login page or a reverse-proxy error page is rejected.

## "Crafty rejected the API token"

The token is wrong, revoked, or doesn't have API access. Create a new one in Crafty and enter it. If the integration
is already set up, Home Assistant asks for the new token itself (see
[Configuration](Configuration.md#a-new-api-token)).

## Everything is `unavailable`

Crafty is unreachable or the token no longer works. Check Crafty is running. If the token no longer works, Home
Assistant shows a **Reauthenticate** notice under **Settings → Devices & services**: enter a new token there. The
entities recover on their own once Crafty answers.

## One server is `unavailable`

Crafty returned an error for that server's stats (often a permission problem for that server), or the server was removed in Crafty. Check the token's access to that server.

## The switch is ON but Status is OFF

Normal while a server is starting. If it never becomes ON, the server crashed or isn't answering on its port; check its console in Crafty.

## A server I just created doesn't show up

Wait up to 30 seconds. If it still doesn't appear, the token doesn't have access to the new server.

## Getting more detail

Go to **Settings → Devices & services → Crafty Controller → ⋮ → Enable debug logging**, reproduce the problem, then download the log and look for `crafty_controller`. Attach it (with the token removed) when opening an [issue](https://github.com/soullink9/HA-Marketplace-Crafty-Controller/issues/new/choose).