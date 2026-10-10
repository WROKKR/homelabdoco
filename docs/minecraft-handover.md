# Minecraft handover — 2026-09-27

## Immediate objective

Complete the controlled production cutover from the cloud Minecraft server to the validated home VM. Preserve the cloud source until the stopped final sync, local backup, WAN test, DNS change, and observation window are complete.

Follow [`minecraft-cutover.md`](minecraft-cutover.md) for the command-by-command runbook, stop points, rollback procedure, and known gotchas.

After production cutover, follow [`minecraft-upgrades.md`](minecraft-upgrades.md) for version-pinned Minecraft and container-image upgrades, validation, and rollback.

## Token-efficient working agreement

- Read this file and applicable AGENTS.md first. Open only the relevant section/file for the next concrete step; avoid whole-repository scans and repeating completed research.
- Work through short, copy-pasteable command blocks. The user executes Linux commands and returns output. Ask for concise diagnostics, not complete logs/configurations.
- No subagents, broad audits, new frameworks, or optional features. Run focused tests after relevant code changes; do not repeat passing checks without reason.
- Be explicit about prepared versus deployed versus verified. Never print credentials. Do not infer SSH access from known addresses.

## Home test server (confirmed by user output)

- Debian 13 VM: `friendsminecraft`, `192.168.90.171` on DMZ VLAN 90 (original test address was `192.168.0.171`); login `wwbb-admin`, sudo works. Proxmox host `yggdrasil` at `192.168.0.50`. Proxmox VM ID `119` confirmed from `qm list` on 2026-09-27.
- 16 GiB RAM; 32 GiB system disk `/dev/sda`; separate 100 GiB ext4 `/dev/sdb` mounted by UUID at `/srv/minecraft` (about 93 GiB initially free).
- Docker/Compose installed and tested. Docker systemd override requires `/srv/minecraft` to be mounted.
- `/opt/minecraft/compose.yaml` runs `itzg/minecraft-server:java25`, `TYPE=VANILLA`, `VERSION=26.1.2`, initial/max heap 3G/7G, `OVERRIDE_SERVER_PROPERTIES=false`, `/srv/minecraft/data:/data`, DMZ binding `192.168.90.171:25565:25565`. Container `minecraft-minecraft-1` works; user joined successfully.
- Reboot persistence is verified. Docker initially started before DHCP assigned the reserved address, which made the fixed host-port bind fail and also left the restored Minecraft bridge without outbound DNS/egress. `/etc/systemd/system/docker.service.d/wait-for-lan.conf` now adds an `ExecStartPre` check that waits up to 120 seconds for `192.168.90.171` on `ens18`. The existing `minecraft-storage.conf` still requires `/srv/minecraft` before Docker. After rebuilding the Compose network and moving to VLAN 90, repeated reboot testing through 2026-09-30 produced a healthy Minecraft container, successful Mojang API and n8n connectivity, client login, and Discord notifications.
- This is a disposable copy from `/srv/minecraft/import`, originally copied while the cloud server was running. Test progress will be discarded during the later clean migration.
- World: `whitewolfbrownbear`, about 3 GiB. Minecraft 26.1.2 stores dimensions under `dimensions/minecraft/{overworld,the_nether,the_end}` and player stats/advancements under `players/{stats,advancements}`.
- Gameplay: survival/easy, online-mode and enforced whitelist, max 20 players, view/simulation distance 10. Saved stats for eight players tested successfully.

## Cloud source and cutover boundary

- `minecraft@minecraft.whitewolfbrownbear.com:/home/minecraft`, about 3.3 GiB, vanilla 26.1.2. Last observed running in screen `1257.pts-0.WWBBMinecraft` with Java 3G/7G heap. Rsync installed and initial copy completed.
- Public DNS observed on 2026-09-27: `minecraft.whitewolfbrownbear.com` has an A record for the cloud host at `170.64.246.2` with a 300-second TTL. Do not change it until the final stopped sync and explicit cutover.
- No final shutdown/sync, router ingress, or DNS cutover has been performed. Preserve cloud service until a separately agreed cutover. Final sync must replace disposable test state without overwriting desired integration settings blindly.

## Pre-ingress security audit

- VM 119 has only SSH on TCP 22 and the Docker-published Minecraft service on `192.168.90.171:25565` listening on the host. The notifier publishes no ports.
- Minecraft has `online-mode=true`, `white-list=true`, `enforce-whitelist=true`, and `enable-query=false`.
- RCON on 25575 and the management API on 25585 are enabled inside the Minecraft container but are not published to the host. RCON remains required for graceful container shutdown; the notifier does not depend on the management API.
- SSH allows public keys and password authentication for non-root users; root is key-only and X11 forwarding is enabled. Neither nftables nor UFW has an active host-managed input policy. External safety therefore depends initially on creating exactly one UDM TCP forward for 25565 and never forwarding SSH, RCON, query, or the management API. Host firewall/SSH defense-in-depth remains available as a later hardening step.
- On 2026-09-28, the user created UniFi DMZ VLAN 90 (`192.168.90.0/24`, gateway `192.168.90.1`), tagged VM 119 with that VLAN, reserved `192.168.90.171`, changed UniFi to zone-based firewalling, and assigned the network to the DMZ zone. DMZ DNS access to Technitium and HTTPS access to n8n are explicit exceptions to the default isolation policy.
- Initial DMZ-to-Technitium replies failed because `dockerhost26` had automatically allocated `192.168.80.0/20` to the Homepage Docker network, which overlapped the DMZ and captured the return route. `dockerhost26` now uses `10.240.0.0/16` with `/24` allocations in Docker's `default-address-pools`; Homepage was recreated on the new pool. Routing, split DNS, and n8n connectivity then passed. Other existing `192.168.x.x` Docker networks remain candidates for staged migration.
- The Minecraft Compose host-port bind and Docker boot wait were changed from `192.168.0.171` to `192.168.90.171`. Nginx Proxy Manager initially returned HTTP 403 to notifier webhook requests because its source allowlist did not include the DMZ; adding the Minecraft DMZ source allowed queued events to flow immediately. Prefer an NPM allow entry of `192.168.90.171/32` rather than the entire `/24` unless additional DMZ services need the same proxy host.

## Notification decisions and implementation

- User wants join/leave, all death messages, advancement/challenge/goal announcements, and public chat only when exactly one player is online.
- Architecture: **read-only log watcher → authenticated n8n webhook → Discord**. No Discord bot commands. n8n already runs on `dockerhost26` (`192.168.0.160`, port 5678 documented); actual webhook endpoint/credentials not configured or supplied.
- Code: `services/minecraft-notifier/` in this repo. Files: `watcher.py`, `death_templates.json`, `extract_templates.py`, `test_watcher.py`, `Dockerfile`, `compose.yaml`, `README.md`. Transfer bundle: `services/minecraft-notifier.zip`.
- Deployed as a separate Compose project at `/opt/minecraft/notifier` on `friendsminecraft`; state is at `/srv/minecraft/notifier-state`. Six local unittest cases pass. The added regression test verifies that a successfully recovered log rotation preserves authoritative solo-player presence.
- Live join, leave, death, and solo public-chat delivery to Discord have been verified. During troubleshooting, the original standard `Authorization` header was rejected upstream; the working n8n Header Auth credential uses `X-Minecraft-Token: Bearer <token>`. The n8n Discord delivery is an HTTP Request node with a JSON body, `wait=true`, and Webhook response mode **When Last Node Finishes**.
- A rotation-state bug that left `known=False` after a recovered rotation was fixed and deployed. The existing state was repaired after the watcher cursor aligned. Future successfully recovered rotations preserve the reconstructed online set; genuinely unrecoverable gaps still suppress solo chat until state is re-established.
- Minecraft 26.3 prefixes game-generated announcements with `System chat:`. On 2026-10-01 this prevented the 26.1.2 parser from recognizing a live join. The repository watcher now treats the retained `logged in with entity id` line as the authoritative join, suppresses the following duplicate system-chat announcement, and accepts the new prefix for leave, death, and advancement events. Regression tests pass; deployment and live event validation are still required.
- A Discord webhook URL was exposed during troubleshooting. Confirm that webhook was deleted in Discord and that the working workflow uses its replacement; never reuse the disclosed URL.
- Stdlib Python; 101 English death templates extracted from checksum-verified official 26.1.2 client. SQLite cursor/outbox, retries, stable event IDs, mention suppression. First startup skips historical notifications while reconstructing player count. Unknown count suppresses solo chat.
- Known limitation: downtime spanning multiple log rotations can miss intermediate files. Delivery is at-least-once (duplicates possible after ambiguous success); n8n deduplication is not implemented. Non-retryable 4xx rows are retained as dead letters. Do not oversell reliability.
- Watcher Compose is a separate project; install at `/opt/minecraft/notifier`, state at `/srv/minecraft/notifier-state`, private configuration at `/opt/minecraft/secrets/webhook.json` containing `url` and `token`. No secrets have been supplied or confirmed saved.
- n8n: POST webhook path `minecraft-events`, Header Auth `X-Minecraft-Token: Bearer <token>`, response **When Last Node Finishes**. Forward `$json.body.discord` as JSON to Discord webhook with `wait=true`; do not swallow delivery errors. Production URL requires active/published workflow. Detailed instructions in watcher README.

## API findings (do not repeat investigation)

- Actual server schema is management protocol 2.0.0. Join/leave notifications work. No advertised death/advancement events. Schema supports player list, status/heartbeat, saves, settings, allowlist/bans/operators; no TPS/CPU/memory in status.
- Test API enabled on container loopback `127.0.0.1:25585`, TLS disabled only for this private namespace, generated 40-character bearer secret in server.properties. No host port published. Watcher does not need this API or credential.
- Python websocket-client succeeded with bearer header and **without** `minecraft-v1` subprotocol. Adding that subprotocol caused Invalid WebSocket Header. No need to retest.

## Next steps

1. Confirm the disclosed Discord webhook was deleted and the replacement is active. Narrow the NPM source allow entry to `192.168.90.171/32` unless the full DMZ intentionally needs access.
2. Confirm the recurring local VM 119 job and backup-failure notification delivery after their first scheduled run. The isolated restore test has passed; remove temporary restore-test VM 103 only with explicit approval.
3. Create a UDM TCP-only 25565 forward to `192.168.90.171`, verify it from a genuinely external network using the WAN IP, and do not change public DNS yet.
4. Schedule a maintenance window: stop the cloud server cleanly, perform the final rsync into the home data tree while preserving home-only integration configuration, validate ownership/world files, start home Minecraft, and take a fresh verified backup.
5. Change the public A record from the cloud address to the home WAN address, test by hostname externally, observe joins/notifier/backup health, and retain the stopped cloud server for rollback until explicitly retired.
6. Historical statistics collection/dashboard and staged migration of remaining `192.168.x.x` Docker networks remain future work.

## Storage caution already accepted for legacy cleanup

VMs 103–113 were backed up to SMB `nas-backups` at TrueNAS/HexOS `192.168.0.100`, then removed at user's explicit acceptance of unresolved checksum/read instability. Reclaimed 634 GiB; `vms` last reported about 887 GiB free. `NVMEstorage` does not exist in live configuration. Do not treat those archives or the NAS path as a verified backup solution for new Minecraft data. Details are in operations.md only if needed.

On 2026-09-27, a clean stopped-mode backup of VM 119 to local Proxmox storage `backups` (`/dev/sdb1`, XFS) completed according to `vzdump` and produced an 8.8 GiB archive, but `zstd -t` failed with a restored-data checksum mismatch and piped `vma verify` failed with a short extent. Two subsequent SHA-256 reads matched (`3c97cd058dda9d055dcc118c6df8c2f38e811074a2ec58403a4986453f0e26fd`), and the filtered kernel log showed no local SDB/XFS I/O errors. The immediately preceding crash-consistent VM 119 archive passed both Zstandard and VMA verification. `/dev/sdb` SMART reported PASSED with zero reallocated, pending, offline-uncorrectable, CRC, or logged errors; a subsequent short offline self-test completed without error.

A replacement stopped-mode backup, `vzdump-qemu-119-2026_09_27-13_52_26.vma.zst`, was created on the same storage. It passed both `zstd -t` and streamed `vma verify`, reported an uncompressed size of 13,561,071,104 bytes, and had SHA-256 `1b2b2aa5910bc2d39e9adb286ac5282ab9e57f412a136726ed65980bfefbe951`. The archive was then restored under a separate VM ID with its network adapter removed. The isolated guest booted, mounted `/srv/minecraft`, retained the world files, and started Minecraft locally. The local backup-and-recovery gate is therefore passed. Preserve the failed archive for diagnosis until its eventual cleanup is explicitly approved.
