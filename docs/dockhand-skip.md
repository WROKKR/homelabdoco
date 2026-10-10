# Dockhand visibility for Skip

User-confirmed on 2026-10-03:

- Dockhand v1.0.50, Free edition, authentication disabled.
- Runs on dockerhost26, published TCP 3002 to container 3000.
- Compose directory `/opt/containers/dockhand`; file `docker-compose.yml`.
- Named Docker volume `dockhand_dockhand_data` mounted at `/app/data`.
- Host Docker socket mounted at `/var/run/docker.sock`.
- Environments named `Dockerhost26` (ID 1) and `Minecraft DMZ` (ID 2), confirmed through projected API output.

## Proposed integration

Prepared a narrow stdio MCP bridge in [`../services/skip-dockhand/server.py`](../services/skip-dockhand/server.py). Hermes launches it locally on ollama2: there is no new network listener, shared token, Docker socket mount or additional container. It exposes two argument-free status tools for fixed environment IDs 1 and 2, calling GET `http://192.168.0.160:3002/api/containers?env=<fixed-id>`, disables redirects and proxy inheritance, bounds response size/time, and projects only container names/state/status. It does not accept tool arguments, alternate environments, URLs, logs, full inspect, lifecycle mutation, or filesystem operations. Minecraft DMZ is included for read-only visibility per the user; every result labels its environment. The existing unauthenticated Dockhand HTTP endpoint remains unchanged.

Seven local unit tests passed for output projection, argument rejection, mutation rejection, fixed scope/tool inventory, and malformed response rejection. Live API shape and Hermes MCP integration are pending. This bridge restriction does not prevent the Linux account or other enabled tools from reaching Dockhand independently.

## Transfer and validate

From Windows PowerShell, copy the prepared script to ollama2:

```powershell
scp C:\Users\WROKKR\Documents\Codex\homelab\services\skip-dockhand\server.py wwbb-admin@192.168.0.167:skip-dockhand.py
```

On ollama2:

```bash
python3 ~/skip-dockhand.py --check
```

Review the projected live output before adding the MCP server. If valid, the intended Hermes command is `hermes mcp add dockhand_status --command python3 --args /home/wwbb-admin/skip-dockhand.py`. Installed CLI support and platform MCP opt-in/filtering must be verified before connecting Discord. Keep terminal/file tools disabled.

The reviewed community craibo/dockhand-mcp adapter documents a read-only toggle but still exposes logs and full inspect, requires a Dockhand API token, and does not document an environment allowlist. Its default read-only mode alone is insufficient for this scope. No adapter has been deployed.

Live projected check passed on 2026-10-03 at 09:16 Brisbane time (2026-10-02 23:16 UTC), supplied by the user: 32 containers in Dockerhost26, all running, with `evertonw` reporting unhealthy; Minecraft DMZ returned three running containers (`hawser-hawser-1`, `minecraft-minecraft-1`, `minecraft-notifier-notifier-1`), with Hawser and Minecraft reporting healthy. These are point-in-time container summaries, not application functionality tests. Next: register the local MCP subprocess and validate calls from Discord. Do not publish raw API responses that could contain connection credentials. Dockhand itself remains unauthenticated and existing network controls have not been inventoried.

References: [Dockhand manual](https://dockhand.pro/manual/), [reviewed community adapter](https://github.com/craibo/dockhand-mcp).

## Hermes integration result — 2026-10-03

The user registered the MCP subprocess and reported Discord tool discovery and a Dockerhost26 tool call. Skip's first combined summary invented `evertonw-frontend-1` instead of `evertonw` and incorrectly generalized running containers as healthy. The supplied activity did not establish a second-environment call. A subsequent request for exact names/status strings produced a correct report for Homepage, its proxy, evertonw, its database, Open WebUI, Minecraft and its notifier. It correctly used "health status not reported" where status lacked a healthcheck marker. Minecraft uptime advanced from the earlier snapshot, consistent with refreshed data, but raw activity for both calls was not supplied. Broad unconstrained summarization is not yet validated; request exact fields and distinguish running state from reported health.
