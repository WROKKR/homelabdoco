# Services

All VMs run on Proxmox. Unraid supplies shares to the Plex VM and does not host VMs.

## Virtual machines

| Service or VM | Purpose | Platform | Address | Storage or dependencies | Notes |
|---|---|---|---|---|---|
| `dockerhost26` | Docker application host | VM on Proxmox | `192.168.0.160` | Proxmox; mounts not yet documented | Container inventory captured below |
| Plex | Media server | VM on Proxmox | Unknown | Shares on Unraid | Exact VM name and address unknown |
| Home Assistant | Home automation | HAOS full VM 116 on Proxmox | `192.168.0.161` | Zigbee2MQTT uses the Mosquitto broker at `core-mosquitto:1883` internally | VM type/ID confirmed 2026-10-03; address and broker reported 2026-09-26 |
| `ollama01` | Local model serving for Home Assistant and n8n workflows | Ubuntu 22.04.5 LTS VM on Proxmox | `192.168.0.166` | 8 vCPUs; 31 GiB reported RAM; no physical GPU visible in supplied inventory | Existing instance; service configuration and models pending; see [`ollama.md`](ollama.md) |
| `ollama2` | Local model serving dedicated to Hermes for now | Ubuntu 26.04.1 LTS VM 118 on Proxmox | `192.168.0.167` | 8 vCPUs; 30 GiB reported RAM; GTX 1660 Ti with 6 GiB VRAM | Hermes/Skip connected to Discord; read-only Proxmox, Dockhand and Home Assistant status tools (see [`skip-mcp.md`](skip-mcp.md)); see [`ollama.md`](ollama.md) |
| `restic` | Local and offsite backup orchestration | Debian 13 VM on Proxmox | `192.168.0.249` | Backrest under `/opt/backrest`; local repository under `/srv/backups` | Local smoke-test backup, integrity check, and restore passed on 2026-08-08 |

## Docker containers on `dockerhost26`

Observed from `docker ps` on 2026-08-08. Published addresses are host bindings, not necessarily the URLs used by clients.

Docker Compose projects are stored in separate directories under `/opt` on `dockerhost26` and are managed from the command line. Exact directory-to-project mappings are not yet inventoried. Portainer is installed but is not the primary management method.

| Container | Purpose | Image | Published host ports | Dependencies or notes |
|---|---|---|---|---|
| `vocodex-frontend-1` | Vocodex frontend | Local `vocodex-frontend` | `8300 -> 80` | Depends on Vocodex backend |
| `vocodex-backend-1` | Vocodex API | Local `vocodex-backend` | `8800 -> 8000` | Depends on `vocodex-db-1` |
| `vocodex-db-1` | Vocodex database | `postgres:16` | Internal `5432` | Healthy at observation time |
| `n8n` | Workflow automation | `docker.n8n.io/n8nio/n8n:2.31.6` | `192.168.0.160:5678` | Depends on `n8n-postgres` |
| `n8n-postgres` | n8n database | `postgres:16-alpine` | Internal `5432` | Healthy at observation time |
| `deluge` | Download client | `lscr.io/linuxserver/deluge:latest` | Shares network path with VPN container; confirm | Routed through `pia-vpn`/Gluetun |
| `pia-vpn` | VPN gateway for download stack | `qmcgaw/gluetun:latest` | `8112`, `9696`, `58846` on `192.168.0.160`; additional internal ports | Healthy; VPN credentials must never be documented here |
| `open-webui` | Web UI for local AI | `ghcr.io/open-webui/open-webui:main` | `192.168.0.160:3000 -> 8080` | Likely uses Ollama; confirm endpoint |
| `vikunja` | Task management | `vikunja/vikunja:latest` | `192.168.0.160:3456` | Data location unknown |
| `mealie` | Recipe management | `ghcr.io/mealie-recipes/mealie:v3.20.1` | `192.168.0.160:9925 -> 9000` | Healthy at observation time |
| `memos` | Notes service | `neosmemo/memos:stable` | `192.168.0.160:5230` | Data location unknown |
| `bookstack` | Documentation/wiki | `lscr.io/linuxserver/bookstack:latest` | `192.168.0.160:6875 -> 80`; internal `443` | Depends on `bookstack-db` |
| `bookstack-db` | BookStack database | `lscr.io/linuxserver/mariadb:latest` | Internal `3306` | Database for BookStack |
| `heimdall` | Application dashboard | `lscr.io/linuxserver/heimdall:latest` | `192.168.0.160:800 -> 80`, `4433 -> 443` | Data location unknown |
| `sonarr` | TV media automation | `ghcr.io/linuxserver/sonarr:latest` | `192.168.0.160:8989` | Uses download and media storage paths; confirm mounts |
| `flaresolverr` | Web challenge helper | `ghcr.io/flaresolverr/flaresolverr:latest` | `192.168.0.160:8191`; internal `8192` | Used by indexer tooling; exact dependency unknown |
| `radarr` | Movie media automation | `ghcr.io/linuxserver/radarr:latest` | `192.168.0.160:7878` | Uses download and media storage paths; confirm mounts |
| `technitium` | DNS service | `technitium/dns-server:latest` | TCP/UDP `53`, UI `5380` on `192.168.0.160`; other internal service ports | DNS role; DHCP role not yet confirmed |
| `portainer-portainer-1` | Docker management | `portainer/portainer-ce:latest` | `9443`; internal `8000`, `9000` | Management access should remain private |
| `bloggr-bloggr-1` | Home web server | Local `bloggr-bloggr` | Internal `80` | Reached through Nginx Proxy Manager and an external port forward |
| `reverse-proxy-npm-1` | Reverse proxy | `jc21/nginx-proxy-manager:latest` | `80`, `81`, `443` | Routes for exposed/internal services not yet inventoried |
| `shlink` stack (`shlink`, `db`, `web-client`) | Public URL shortener `link.wwbb.dev` | `shlinkio/shlink:5.1.6`, `postgres:16-alpine`, `shlinkio/shlink-web-client:4.8.1` | `192.168.0.160:8085` (Shlink), `:8086` (LAN-only admin UI) | Prepared in `services/shlink/`, not yet deployed. Public through NPM; `/rest/` limited to the LAN |

## Docker inventory update — 2026-10-03

The user supplied a newer `docker ps` snapshot from `dockerhost26`. All listed containers were running at observation time; `evertonw` (Ghost) reported unhealthy. This is a point-in-time status, not current health or proof of application functionality.

Additional running containers compared with the earlier table:

| Container | Image | Published host port or dependency |
|---|---|---|
| `bytestash-bytestash-1` | `ghcr.io/jordan-dalby/bytestash:latest` | All host interfaces, TCP 5000 |
| `dockhand` | `fnsys/dockhand:latest` | All host interfaces, TCP 3002 to container 3000 |
| `homepage` | `ghcr.io/gethomepage/homepage:latest` | All host interfaces, TCP 3001 to container 3000 |
| `homepage-dockerproxy` | `ghcr.io/tecnativa/docker-socket-proxy:latest` | Internal TCP 2375; proxy policy not inventoried |
| `wasabi-dashboard` | `wasabi-dashboard:latest` | All host interfaces, TCP 8880 to container 8080; presence does not prove backups are configured |
| `watchtower` | `nickfedor/watchtower:latest` | Internal TCP 8080; update scope and schedule unknown |
| `evertonw` | `ghost:6-alpine` | All host interfaces, TCP 2368; reported unhealthy |
| `evertonw-db` | `mysql:8.4` | Internal TCP 3306/33060; reported healthy |
| `prowlarr` | `ghcr.io/linuxserver/prowlarr:latest` | No published host port shown; actual network path unknown |

`shlink-shlink-1`, `shlink-db-1`, and `shlink-web-client-1` are now observed running, superseding the earlier prepared/not-deployed note. Shlink and its web client bind `192.168.0.160:8085` and `:8086`; public proxy behavior remains unverified by this snapshot. Portainer did not appear in `docker ps`; retirement versus stopped state is unknown. Homepages, applications, proxy routes and backup arrangements still require confirmation from their configuration.

## UniFi Protect

The UDM Pro SE runs UniFi Protect and uses its installed disk for recordings from Reolink security cameras. Camera models, adoption method, retention, and recording settings are not yet documented.

## Frigate

Frigate runs as an experimental K3s workload pinned to the Turing RK1 node `TR4` (`192.168.0.184`). It uses the RK3588 RKNN NPU for object detection and RKMPP for FFmpeg hardware decoding. Configuration and media are stored on TR4's NVMe under `/mnt/k3s-storage/frigate`.

Frigate provides local object detection and Review items; UniFi Protect remains the full-quality, continuous NVR. The authenticated UI is currently available through NodePort `30971` to Frigate port `8971`. The unauthenticated internal port `5000` must not be exposed. See [`frigate.md`](frigate.md) for the complete deployment and operational record.

## Inventory limitations

- This is a runtime snapshot, not the authoritative deployment configuration.
- Exact `/opt` project directories, volumes, bind mounts, networks, restart policies, environment-variable names, and reverse-proxy routes are not yet documented.
- Container status can change; verify live state before maintenance.
- Six Backrest plans are documented in the October inventory; source coverage, schedules and recovery validation remain incomplete. See [`backup-troubleshooting.md`](backup-troubleshooting.md).

## Docker management and backup update — 2026-10-11

The user confirms Portainer was replaced with Dockhand, superseding the older
Portainer management notes. Supplied mount inspection identifies Dockhand's
`/app/data` as named volume `dockhand_dockhand_data`; the Docker socket is also
bind-mounted. The user replaced the retired
`portainer_portainer_data` export entry with Dockhand's volume. The manual source
export passed at 13:30:57 AEST; staging refresh, backup and restore validation
remain pending. See [backup troubleshooting](backup-troubleshooting.md).
