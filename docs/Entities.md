# Entities

Each Minecraft server in Crafty becomes one Home Assistant **device**, named after the server. Every device has two entities.

| Entity | Type | ON means | OFF means |
| --- | --- | --- | --- |
| Switch (named after the server) | `switch` | The server process is running | The server is stopped |
| Status | `binary_sensor` (connectivity) | The server answers Crafty's ping, so players can connect | Not reachable: stopped, still starting, or not responding |

**Attributes:** both entities carry `port`, the server's Minecraft port as reported by Crafty (empty if Crafty didn't report one).

## Controlling a server

- Turn the switch **on** to start the server, **off** to stop it.
- The switch changes right away, and the next poll (within 30 seconds) confirms the real state.
- If Crafty refuses the action, Home Assistant shows an error and the switch stays where it was.

## Switch vs. Status

They are different on purpose. While a server is starting, the switch is already ON (the process is running) but Status stays OFF until the server answers. So **Status is the one to use to know a server is ready to join.**

## Unavailable

- If Crafty can't be reached (or the token stops working), all entities show `unavailable` until it answers again.
- If a single server's data can't be read, or the server is removed in Crafty, only that server's entities are `unavailable`.

## New servers

Servers created in Crafty later appear automatically within about 30 seconds. No reload needed.