# Minecraft server upgrade guide

## Scope

This runbook upgrades the production Minecraft server on VM 119 after the home cutover is complete. The current deployment is vanilla Minecraft in Docker Compose:

- Compose project: `/opt/minecraft/compose.yaml`
- Persistent data: `/srv/minecraft/data`
- Image: `itzg/minecraft-server:java25`
- Minecraft version is explicitly pinned with `VERSION`
- Proxmox VM: `119` on `Yggdrasil`

There is no zero-downtime upgrade for this single-server design. Schedule a maintenance window and keep players disconnected until validation is complete.

## Understand the two upgrade types

Treat these as separate changes whenever possible:

1. **Minecraft upgrade:** change the Compose `VERSION` value. Starting the recreated container downloads and runs that server release against the persistent world.
2. **Container-image upgrade:** run `docker compose pull` to replace the `itzg/minecraft-server` image. This updates the entrypoint and supporting tools, but does not by itself intentionally change the pinned Minecraft version.

If the target Minecraft release requires a different Java version, the image tag must also change deliberately. Do not switch to `latest`, and do not remove the `VERSION` pin.

## Important gotchas

- A newer Minecraft release may irreversibly convert world data. **Changing `VERSION` back is not a safe rollback.** Restore the complete pre-upgrade backup instead.
- Never open an upgraded world with an older server release.
- Confirm the target is a stable server release and read its official release notes. Check world-format, Java, command, whitelist, datapack, and networking changes.
- Back up all dimensions and player data together. Copying only the Overworld is not sufficient.
- The first start may spend longer than usual upgrading chunks or generating data. Do not interrupt it merely because startup is slow; watch the logs.
- Do not set `OVERRIDE_SERVER_PROPERTIES=true`. The current home `server.properties` contains required RCON and operational settings.
- Do not rotate or expose RCON, management API, n8n, Discord, or webhook credentials as part of a routine upgrade.
- Vanilla currently has no mods or plugins to reconcile. If that changes, every mod/plugin and loader must be checked before a Minecraft upgrade.
- A local Proxmox archive is a rollback point, but it is not protection from loss of the Proxmox host or backup disk.

## Phase 1 — Research and record the target

Choose an explicit target release; do not use a floating value such as `LATEST`.

On `friendsminecraft`, record the current deployment without printing secrets:

```bash
cd /opt/minecraft
sudo docker compose config --services
sudo docker compose images
sudo grep -E '^[[:space:]]*(image:|VERSION:|TYPE:|OVERRIDE_SERVER_PROPERTIES:)' compose.yaml
sudo docker compose exec minecraft rcon-cli --host 127.0.0.1 version
```

Before proceeding, determine:

- the exact target Minecraft version;
- whether it requires a different Java major version;
- whether the release changes the world/data format;
- whether current clients can connect to it;
- whether the target remains compatible with the notifier's log parsing.

The notifier recognizes text log events rather than depending on the Minecraft protocol. Join/leave and chat are usually stable, but death and advancement wording can change and must be tested after an upgrade.

## Phase 2 — Confirm the recovery point

Use a recently verified backup or create a fresh stopped-mode backup. A routine scheduled backup is not sufficient evidence unless its archive has actually passed verification.

First confirm no players are online:

```bash
cd /opt/minecraft
sudo docker compose exec minecraft rcon-cli --host 127.0.0.1 list
```

Stop Minecraft cleanly:

```bash
sudo docker compose stop --timeout 120 minecraft
sudo docker compose ps -a
```

On `Yggdrasil`, create the known-good backup type:

```bash
vzdump 119 \
  --storage backups \
  --mode stop \
  --compress zstd \
  --notes-template 'Minecraft pre-upgrade {{guestname}}'
```

VM 119 normally starts again after `vzdump --mode stop`, which can also restart Minecraft through Docker. Identify and verify the new archive before changing anything:

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

Stop if either verification command fails. Preserve the archive path and SHA-256 in the maintenance record; do not store any credentials with it.

After VM 119 is available again, stop the Minecraft service once more before editing its version:

```bash
cd /opt/minecraft
sudo docker compose stop --timeout 120 minecraft
sudo docker compose ps -a
```

## Phase 3 — Prepare the Compose change

Save the current Compose file locally:

```bash
cd /opt/minecraft
sudo cp -a compose.yaml "compose.yaml.pre-upgrade-$(date +%Y%m%d-%H%M%S)"
```

Edit the Compose file:

```bash
sudoedit /opt/minecraft/compose.yaml
```

Change only the required values:

```yaml
services:
  minecraft:
    image: itzg/minecraft-server:java25  # change only if target requires another Java major
    environment:
      VERSION: "EXACT_TARGET_VERSION"
```

`EXACT_TARGET_VERSION` is a placeholder, not a value to paste literally. Preserve the rest of the deployment, including the fixed DMZ port binding, volume, memory, secret mount, RCON settings, `OVERRIDE_SERVER_PROPERTIES`, health check, TTY/stdin, logging, and stop grace period.

Validate the rendered configuration before starting anything:

```bash
cd /opt/minecraft
sudo docker compose config --quiet
sudo docker compose config | grep -E 'image:|VERSION:|source: /srv/minecraft|target: /data|25565'
```

Stop and correct the file if Compose validation fails or the `/srv/minecraft/data` mount is absent.

## Phase 4 — Start the upgrade

### Minecraft version only

When the existing image supports the target Java and server release, recreate without pulling a new image:

```bash
cd /opt/minecraft
sudo docker compose up -d --force-recreate minecraft
sudo docker compose logs -f --tail=100 minecraft
```

### Deliberate container-image update

If the image tag changed, or an image update is intentionally included:

```bash
cd /opt/minecraft
sudo docker compose pull minecraft
sudo docker compose up -d --force-recreate minecraft
sudo docker compose logs -f --tail=100 minecraft
```

Follow the logs until Minecraft reports `Done`. Exit log following with `Ctrl-C`; that does not stop the container. Investigate rather than repeatedly restarting if startup reports world, Java, download, permissions, or configuration errors.

## Phase 5 — Validate before reopening access

Run the local checks:

```bash
cd /opt/minecraft
sudo docker compose ps
sudo docker compose exec minecraft rcon-cli --host 127.0.0.1 version
sudo docker compose exec minecraft rcon-cli --host 127.0.0.1 list
sudo docker compose logs --tail=150 minecraft | \
  grep -E 'Done|WARN|ERROR|Exception|Failed|Preparing spawn|Preparing level'
```

Then use a real client and validate:

- target version is shown and the client can connect;
- correct world, location, inventory, Ender Chest, advancements, and statistics;
- Overworld, Nether, and End load correctly;
- whitelist and operator access remain correct;
- block changes persist after disconnect/reconnect;
- join, leave, solo chat, advancement, and death events reach Discord;
- no notifier queue growth, webhook 403, DNS, RCON, forced-stop, or repeated world-save errors appear.

Check the notifier after generating test events:

```bash
cd /opt/minecraft/notifier
sudo docker compose ps
sudo docker compose logs --since=15m
sudo docker compose exec notifier python -c \
"import sqlite3; db=sqlite3.connect('/state/watcher.sqlite'); print(db.execute('SELECT id,kind,attempts,dead FROM outbox ORDER BY id').fetchall())"
```

## Phase 6 — Establish the new recovery point

Once validation passes, allow the server to save and take another verified backup labelled as the post-upgrade recovery point. The same stopped-mode and verification procedure from Phase 2 is preferred.

Keep both the pre-upgrade and post-upgrade verified archives through the observation window. Confirm the next scheduled backup also completes successfully before allowing retention to remove the pre-upgrade copy.

Record in the handover:

- old and new Minecraft versions;
- old and new image tags or image IDs;
- upgrade date and observed downtime;
- pre- and post-upgrade archive names and verification result;
- any changed behavior in logs or notifier events.

## Rollback

If the upgraded server has opened or saved the world, do not merely restore the old `VERSION` value.

1. Prevent player access and stop the upgraded Minecraft service cleanly if possible.
2. Preserve diagnostic logs and the upgraded state; do not delete it during troubleshooting.
3. Restore the verified **pre-upgrade VM archive**. A Proxmox restore that replaces production is destructive and requires explicit approval.
4. Keep the restored VM network-disconnected or otherwise isolated until its identity, disks, world, and version are confirmed.
5. Ensure the upgraded and restored servers can never accept players simultaneously.
6. Reattach networking/start production only after confirming the restored server is authoritative.
7. Test client login and Discord notifications again.

If failure occurred before the server opened or wrote the world, reverting only the Compose file may sometimes work, but the full verified backup remains the safer rollback. Treat any uncertain startup as a potentially modified world.

## Suggested routine

- Do not auto-upgrade Minecraft versions or the Minecraft image with Watchtower.
- Review stable releases manually and upgrade deliberately during a maintenance window.
- Avoid upgrading on release day unless a security issue makes delay riskier.
- Keep `VERSION` and the Java image tag pinned.
- Perform one material change at a time: Minecraft version, Java/image, then unrelated configuration on separate maintenance events.

## Worked example — 26.1.2 to 26.3

Minecraft Java Edition 26.3 is a stable release. For this vanilla deployment, retain the existing `itzg/minecraft-server:java25` image selection and change only the pinned Minecraft version first. This avoids combining a Minecraft world upgrade with an unrelated container-image update.

The 26.3 release notes specifically state that some server log lines were removed. The notifier reads logs, so join, leave, solo chat, death, and advancement delivery all require explicit post-upgrade testing. New terrain features appear in newly generated chunks; existing explored terrain is not regenerated.

### On `friendsminecraft` — confirm empty and stop

```bash
cd /opt/minecraft
sudo docker compose exec minecraft rcon-cli --host 127.0.0.1 version
sudo docker compose exec minecraft rcon-cli --host 127.0.0.1 list
sudo docker compose stop --timeout 120 minecraft
sudo docker compose ps -a
```

Expected starting version: `26.1.2`. Do not continue if players are present or the container does not stop cleanly.

### On `Yggdrasil` — create and verify the pre-upgrade archive

```bash
vzdump 119 \
  --storage backups \
  --mode stop \
  --compress zstd \
  --notes-template 'Minecraft 26.1.2 before 26.3 upgrade {{guestname}}'

backup_archive=$(find /mnt/pve/backups/dump -maxdepth 1 \
  -type f -name 'vzdump-qemu-119-*.vma.zst' \
  -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)

printf 'Testing: %s\n' "$backup_archive"
zstd -t "$backup_archive"
zstd -dc "$backup_archive" | vma verify -
sha256sum "$backup_archive"
qm status 119
```

Continue only if both `zstd` and `vma verify` succeed. Wait for VM 119 and SSH to return.

### On `friendsminecraft` — change the pin

Stop Minecraft again in case it restarted during the VM backup, and preserve the Compose file:

```bash
cd /opt/minecraft
sudo docker compose stop --timeout 120 minecraft
sudo cp -a compose.yaml compose.yaml.pre-26.3
sudo sed -i 's/VERSION: "26\.1\.2"/VERSION: "26.3"/' compose.yaml
sudo grep -n 'VERSION:' compose.yaml
sudo docker compose config --quiet
```

The `grep` output must show exactly `VERSION: "26.3"`. If it still shows 26.1.2, edit it with `sudoedit /opt/minecraft/compose.yaml`. Do not change `TYPE`, the `java25` image tag, the volume, secrets, port binding, or server-property behavior.

### Start 26.3 without pulling a different image

```bash
cd /opt/minecraft
sudo docker compose up -d --force-recreate minecraft
sudo docker compose logs -f --tail=150 minecraft
```

Wait for a successful `Done` line. The container should download the 26.3 server assets using the pinned `VERSION`. Use `Ctrl-C` to leave the log view; this does not stop Minecraft.

Then validate locally:

```bash
cd /opt/minecraft
sudo docker compose ps
sudo docker compose exec minecraft java -version
sudo docker compose exec minecraft rcon-cli --host 127.0.0.1 version
sudo docker compose exec minecraft rcon-cli --host 127.0.0.1 list
sudo docker compose logs --tail=200 minecraft | \
  grep -E 'Done|WARN|ERROR|Exception|Failed|upgrade'
```

The RCON version result must identify 26.3. Connect using a 26.3 client and check the world, inventory, Ender Chest, advancements, all dimensions, and persisted block changes.

Generate one of every required notifier event: join, leave, solo chat, death, and advancement. Then check:

```bash
cd /opt/minecraft/notifier
sudo docker compose logs --since=20m
sudo docker compose exec notifier python -c \
"import sqlite3; db=sqlite3.connect('/state/watcher.sqlite'); print(db.execute('SELECT id,kind,attempts,dead FROM outbox ORDER BY id').fetchall())"
```

If Minecraft works but an alert type is absent, retain 26.3 and diagnose the changed log format against the watcher. Do not clear the notifier queue.

Finally, create and verify a second stopped-mode VM backup labelled `Minecraft 26.3 post-upgrade`, using the same procedure. Keep the verified 26.1.2 archive until 26.3 has passed the observation window and a scheduled backup has also succeeded.
