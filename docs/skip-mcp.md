# Skip's MCP tools

Inventory of the local MCP servers Hermes (Skip) can call on `ollama2`. All are stdio subprocesses launched by Hermes: no network listener, fixed scope, read-only by code, argument-free tools. Each server's own doc has setup, validation and limitations.

| Hermes server | Script on `ollama2` | Tools | Reads from | Credential (on `ollama2` only) | Doc |
|---|---|---|---|---|---|
| `proxmox_status` | `~/skip-proxmox.py` | `yggdrasil_host_status`, `homeassistant_vm_status` (VM 116), `ollama2_vm_status` (VM 118) | Proxmox API on `yggdrasil` | `~/.config/skip-proxmox/token.json` (audit-only API token) and `pve-root-ca.pem` | [`skip-proxmox.md`](skip-proxmox.md) |
| `dockhand_status` | `~/skip-dockhand.py` | `dockerhost26_container_status`, `minecraft_dmz_container_status` | Dockhand on `dockerhost26:3002` | None (Dockhand auth is disabled) | [`dockhand-skip.md`](dockhand-skip.md) |
| `homelab_report` | Not recorded | `homelab_health_report` (combines the five tools above into a fixed-format report) | As above | As above | [`skip-health-reports.md`](skip-health-reports.md) |
| `homeassistant_status` | `~/skip-homeassistant.py` | `home_status_now`, `daily_totals_7d`, `recent_changes_24h` | Home Assistant REST API, allowlisted sensors only | `~/.config/skip-homeassistant/token.json` (non-admin `skip-readonly` user) and `entities.json` | [`skip-homeassistant.md`](skip-homeassistant.md) |

Repo sources: `services/skip-proxmox/`, `services/skip-dockhand/`, `services/skip-homeassistant/`.

## System prompt blocks

Skip's prompt is a base (persona and inventory, source `services/skip-prompt/base_prompt.txt`) plus marked rule blocks, each managed by its own repeatable script that backs up the previous prompt. Full details and live state: [`skip-system-prompt.md`](skip-system-prompt.md). Both blocks below were confirmed live on 2026-10-04.

| Block markers | Script | Covers |
|---|---|---|
| (base, before the first marker) | `services/skip-prompt/apply_base_prompt.py` | Persona, priorities, homelab inventory |
| `SKIP_REPORTING_RULES` | `services/skip-proxmox/update_reporting_prompt.py` | Proxmox/Dockhand status wording and the combined health report |
| `SKIP_HOMEASSISTANT_RULES` | `services/skip-homeassistant/update_prompt.py` | Backups, energy and Frigate via the Home Assistant tools |

The scripts are the source of truth for block wording.

## Not yet confirmed

- Exact registration commands and script path for `homelab_report`.
- A post-restart Hermes tool inventory from Discord (`hermes mcp list` and the enabled built-in toolsets), confirming terminal, file, vision and skills are disabled there as well as in the CLI.

## Boundaries

- No tool restarts, edits or controls anything. Tokens for Proxmox and Home Assistant could do more if used outside these scripts; keeping Skip's terminal and file tools disabled is part of the boundary.
- Dockhand itself has authentication disabled while holding the Docker socket on `dockerhost26`, so anything on the LAN that reaches port 3002 can control containers regardless of Skip's read-only bridge.
