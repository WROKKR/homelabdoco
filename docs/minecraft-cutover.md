# Minecraft production cutover guide

## Purpose

Move the authoritative Minecraft 26.1.2 world from the cloud server to home VM 119 without losing world or player data, while preserving the home-only Docker, RCON, management API, notifier, DMZ, and backup configuration.

This guide starts from the validated state on 2026-09-30:

- Cloud source: `minecraft@minecraft.whitewolfbrownbear.com:/home/minecraft/`; public A record last observed as `170.64.246.2` with TTL 300.
- Home VM: `friendsminecraft`, Proxmox VM 119, DMZ VLAN 90, reserved address `192.168.90.171`.
- Home data: `/srv/minecraft/data/`; staging: `/srv/minecraft/import-final/`.
- Minecraft container: `/opt/minecraft/compose.yaml` and `minecraft-minecraft-1`.
- Notifier: `/opt/minecraft/notifier`, with state under `/srv/minecraft/notifier-state`.
- The home VM has passed reboot, client-login, Discord-delivery, stopped-backup, archive-verification, and isolated-restore tests.

## Safety rules

1. Do not run the final source sync while the cloud Minecraft Java process is running.
2. Do not sync the cloud tree directly over `/srv/minecraft/data`. Sync to staging, inspect it, then merge only authoritative game data.
3. Preserve the home copy of `server.properties`. It contains the settings needed for graceful Docker shutdown and private management integration.
4. Never copy or print RCON, management API, n8n, Discord, SSH, or other secret values into this repository or terminal output shared for troubleshooting.
5. Do not change public DNS until WAN TCP 25565 has been tested from a genuinely external network and the final migrated home world has been backed up.
6. Keep the cloud server stopped but intact during the rollback window. Do not let both copies accept gameplay after the final sync; that creates divergent worlds.
7. Commands in the Proxmox sections run as `root` on `Yggdrasil` and do not use `sudo`. Commands on `friendsminecraft` use `sudo` where shown.

## Phase 1 — Close pre-cutover gates

### Backup automation

On `Yggdrasil`, verify that VM 119 has a scheduled job and that a recent archive exists:

```bash
pvesh get /cluster/backup --output-format yaml
ls -lhtr /mnt/pve/backups/dump/vzdump-qemu-119-*.vma.zst | tail
```

The manually verified restore proves recovery, but scheduled execution and failure notification must also be checked. The local `backups` disk is not an off-host copy.

### Notification security

- Confirm the Discord webhook disclosed during setup was deleted and replaced.
- In Nginx Proxy Manager, prefer `192.168.90.171/32` in the n8n source allowlist. Do not allow the entire DMZ unless that is intentional.
- Confirm a fresh join/leave event reaches Discord after a reboot.

### Firewall policy

Required UniFi policy:

- External to Minecraft DMZ: no access yet.
- Trusted LAN/Teleport to VM 119: TCP 22 and 25565 as required.
- VM 119 to `192.168.0.160`: TCP/UDP 53 for Technitium.
- VM 119 to `192.168.0.160`: TCP 443 for n8n through Nginx Proxy Manager.
- VM 119 to the internet: TCP 80/443 and required time synchronization.
- DMZ to other private networks: deny by default.
- Never forward SSH 22, RCON 25575, query, or management API 25585.

## Phase 2 — Test WAN ingress without moving DNS

Confirm that the public IPv4 reported from home matches the UDM WAN IPv4. A mismatch may indicate upstream NAT or CGNAT.

```bash
curl -4fsS https://api.ipify.org
echo
```

Create exactly one UDM port forward:

```text
Protocol: TCP
WAN port: 25565
Destination: 192.168.90.171
Destination port: 25565
```

Do not change `minecraft.whitewolfbrownbear.com` yet. From a phone hotspot or other external network, test `<home-public-ip>:25565`. A same-LAN test may exercise NAT reflection instead of real WAN ingress.

If a public AAAA record exists, either validate equivalent IPv6 firewalling and service reachability or remove the AAAA record before cutover. IPv6 does not rely on the IPv4 port forward.

## Phase 3 — Freeze the cloud source

Announce the maintenance window and confirm no players are online.

The cloud server was last observed in screen session `1257.pts-0.WWBBMinecraft`. On the cloud host, attach to the actual current session, issue Minecraft's `stop` command, and wait for the server to finish saving:

```bash
screen -ls
screen -r 1257.pts-0.WWBBMinecraft
```

Inside the Minecraft console:

```text
list
stop
```

After screen exits, confirm no Minecraft Java process remains:

```bash
pgrep -af java
```

Stop here if Java is still running. Do not use a forced kill unless graceful shutdown has failed and the recovery implications are accepted.

## Phase 4 — Sync the stopped source into staging

Run these commands on `friendsminecraft`.

Create the staging directory:

```bash
sudo install -d -o wwbb-admin -g wwbb-admin -m 0750 \
  /srv/minecraft/import-final
```

Dry-run the cloud-to-staging sync:

```bash
rsync -aHh \
  --no-owner \
  --no-group \
  --delete-delay \
  --partial \
  --info=progress2 \
  --itemize-changes \
  --dry-run \
  minecraft@minecraft.whitewolfbrownbear.com:/home/minecraft/ \
  /srv/minecraft/import-final/
```

Verify that the command shows the cloud directory as the source and `import-final` as the destination. Then run the real staging sync by removing `--dry-run`:

```bash
rsync -aHh \
  --no-owner \
  --no-group \
  --delete-delay \
  --partial \
  --info=progress2 \
  minecraft@minecraft.whitewolfbrownbear.com:/home/minecraft/ \
  /srv/minecraft/import-final/
```

Perform a checksum dry-run. No file changes should be listed:

```bash
rsync -aH \
  --no-owner \
  --no-group \
  --delete \
  --checksum \
  --itemize-changes \
  --dry-run \
  minecraft@minecraft.whitewolfbrownbear.com:/home/minecraft/ \
  /srv/minecraft/import-final/
```

Inspect the top-level staging tree:

```bash
find /srv/minecraft/import-final \
  -mindepth 1 \
  -maxdepth 1 \
  -printf '%f\n' | sort
```

Expected authoritative content includes the `whitewolfbrownbear` world directory plus applicable `whitelist.json`, `ops.json`, ban lists, and player cache. Stop and reconcile unexpected paths before merging.

### Rsync gotchas

- The trailing slash on `/home/minecraft/` means “copy the contents of this directory.” Removing it changes nesting.
- `--delete` is safe only against the staging directory in this phase. Do not point it at `/srv/minecraft/data`.
- The checksum verification reads every source and destination file and may take several minutes.
- DNS must still point the source hostname at the cloud host during this phase. If DNS has already changed, use the confirmed cloud IP or an SSH host alias that explicitly targets it.

## Phase 5 — Merge authoritative game state at home

Confirm staging contains the expected world directory:

```bash
test -d /srv/minecraft/import-final/whitewolfbrownbear \
  && echo 'world present' \
  || echo 'STOP: expected world directory missing'
```

Confirm the home server is empty, then stop its Compose service cleanly:

```bash
cd /opt/minecraft
sudo docker compose exec minecraft rcon-cli --host 127.0.0.1 list
sudo docker compose stop --timeout 120 minecraft
sudo docker compose ps -a
```

Back up the home-only server properties:

```bash
sudo cp -a \
  /srv/minecraft/data/server.properties \
  /srv/minecraft/data/server.properties.pre-production-cutover
```

Replace the disposable world with the stopped cloud world:

```bash
sudo rsync -aH --delete --chown=1000:1000 \
  /srv/minecraft/import-final/whitewolfbrownbear/ \
  /srv/minecraft/data/whitewolfbrownbear/
```

Copy the authoritative vanilla access-control files when present:

```bash
for file in whitelist.json ops.json banned-ips.json banned-players.json usercache.json; do
  if test -f "/srv/minecraft/import-final/$file"; then
    sudo install -o 1000 -g 1000 -m 0644 \
      "/srv/minecraft/import-final/$file" \
      "/srv/minecraft/data/$file"
  fi
done
```

Do not copy these cloud runtime/configuration paths over the home installation:

- `server.properties`
- `eula.txt`
- server JARs, libraries, versions, caches, or launch scripts
- `logs/` or `crash-reports/`
- RCON, management API, webhook, Discord, or Docker secrets

Check ownership and world size without printing secret configuration:

```bash
sudo du -sh /srv/minecraft/data/whitewolfbrownbear
sudo find /srv/minecraft/data/whitewolfbrownbear \
  \! -user 1000 -o \! -group 1000 | head
```

The final command should print nothing. If it prints paths, correct ownership before starting Minecraft.

## Phase 6 — Start and validate the migrated home server

```bash
cd /opt/minecraft
sudo docker compose up -d --wait --wait-timeout 180
sudo docker compose ps
sudo docker compose exec minecraft rcon-cli --host 127.0.0.1 list
sudo docker compose logs --tail=80 minecraft
```

Validate with a real client before DNS cutover:

- Correct world position and builds.
- Inventory and Ender Chest.
- Advancements and statistics.
- Overworld, Nether, and End dimensions.
- Whitelist and operator status.
- Join, leave, solo chat, advancement, and death notifications as practical.
- No new webhook 403, DNS, forced-stop, or world-save errors.

## Phase 7 — Create a post-migration recovery point

On `Yggdrasil`, run a stopped-mode backup before changing public DNS:

```bash
vzdump 119 \
  --storage backups \
  --mode stop \
  --compress zstd \
  --notes-template 'Minecraft post-migration pre-DNS-cutover {{guestname}}'
```

Identify and verify the new archive:

```bash
backup_archive=$(find /mnt/pve/backups/dump -maxdepth 1 \
  -type f -name 'vzdump-qemu-119-*.vma.zst' \
  -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)

printf 'Testing: %s\n' "$backup_archive"
zstd -t "$backup_archive"
zstd -dc "$backup_archive" | vma verify -
sha256sum "$backup_archive"
qm status 119
```

Proceed only if both verification commands succeed and VM 119 is running again. This local backup does not replace an off-host copy.

## Phase 8 — DNS cutover

Reconfirm external access to the home WAN IP on TCP 25565. Then change only the public A record for `minecraft.whitewolfbrownbear.com` from the cloud IP to the home WAN IPv4 address. Keep the record DNS-only if the DNS provider offers an HTTP proxy; normal HTTP reverse proxies do not carry Minecraft Java traffic.

At the standard port 25565, no SRV record is required. If an old AAAA or SRV record exists, verify or remove it deliberately.

Check public DNS from independent resolvers and then test from an external Minecraft client:

```powershell
Resolve-DnsName minecraft.whitewolfbrownbear.com -Type A -Server 1.1.1.1
Resolve-DnsName minecraft.whitewolfbrownbear.com -Type AAAA -Server 1.1.1.1
```

The A record should return the home WAN address. DNS propagation may exceed the nominal 300-second TTL for some cached clients.

## Phase 9 — Observation and rollback

Keep the cloud server stopped and intact during the observation window. Monitor:

- External joins and gameplay.
- Discord notification delivery and notifier queue growth.
- Minecraft and notifier container health after restart.
- CPU, memory, disk space, and world-save logs.
- Scheduled backup completion and alert delivery.

Quick notifier queue check:

```bash
cd /opt/minecraft/notifier
sudo docker compose exec notifier python -c \
"import sqlite3; db=sqlite3.connect('/state/watcher.sqlite'); print(db.execute('SELECT id,kind,attempts,dead FROM outbox ORDER BY id').fetchall())"
```

### Rollback warning

Changing DNS back to the cloud and starting its old world loses any gameplay that occurred at home after cutover. If post-cutover home progress must be retained, stop the home server and perform a deliberate reverse migration before starting cloud. Never allow both copies to accept players independently.

Basic rollback without preserving new home progress:

1. Stop home Minecraft cleanly.
2. Change the public A record back to the recorded cloud IP.
3. Start the still-intact cloud server.
4. Verify externally by hostname.

## Phase 10 — Cleanup only after explicit approval

After the agreed observation window:

- Retire the cloud server only after confirming rollback is no longer required.
- Delete temporary restore-test VM 103 only after confirming its identity and receiving explicit approval.
- Remove the known-corrupt VM 119 archive only after explicit approval.
- Remove `/srv/minecraft/import-final` only after confirming the production world and post-migration backup.
- Reconcile scheduled retention and failure notifications.
- Continue migrating old `192.168.x.x` Docker networks on `dockerhost26` into its reserved `10.240.0.0/16` pool one stack at a time.
- Disable the private management API if it is no longer wanted; do not expose it publicly.

## Known operational gotchas

- VM 119's Compose port binding and Docker wait rule both contain the reserved address `192.168.90.171`; an address change requires updating both.
- Docker on `dockerhost26` previously allocated `192.168.80.0/20`, overlapping the DMZ. New automatic networks use `10.240.0.0/16` in `/24` slices, but old networks remain until recreated.
- Nginx Proxy Manager must allow the Minecraft VM source to reach the authenticated n8n webhook. A proxy-level 403 prevents notifier delivery even when DNS and TCP 443 work.
- The notifier is at-least-once: duplicates are possible after ambiguous delivery. Do not clear its SQLite queue during an outage.
- A `sudo` prompt can look like a hung command, particularly after preceding output. Authenticate with `sudo -v` before long diagnostic blocks.
- UFW does not reliably control Docker-published ports in the expected way. The intended external boundary is the UDM TCP-only forward and zone policy.
- Public DNS still identifies the cloud server until Phase 8. LAN testing by hostname may also be affected by split DNS or cached answers.
- A local Proxmox archive protects against VM corruption but not loss of the entire host or backup disk.

## Ongoing upgrades

After the production cutover and observation window, use [`minecraft-upgrades.md`](minecraft-upgrades.md) for future Minecraft or container-image upgrades. Do not perform a version upgrade as part of the cutover itself.
