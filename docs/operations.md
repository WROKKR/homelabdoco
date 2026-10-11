# Operations

## Deployment

Docker Compose projects live in separate directories under `/opt` on `dockerhost26` and are managed from the command line. Before changing a stack, identify its exact project directory, inspect its Compose and environment files without exposing secrets, and document its normal update and validation commands. Portainer is installed but is not the primary management path.

## Backups

A dedicated Debian 13 backup VM named `restic` runs at `192.168.0.249`. Backrest is installed under `/opt/backrest`; its local Restic repository is on a separate 1 TB HDD-backed virtual disk mounted at `/srv/backups`. A local smoke-test backup, repository integrity check, and file restore were completed successfully on 2026-08-08.

On 2026-09-27, a stopped-mode `vzdump` of Minecraft VM 119 to the local `backups` XFS filesystem completed without a task error but immediately failed both Zstandard checksum testing and VMA verification. Repeated SHA-256 reads of the resulting 8.8 GiB archive were identical, and no contemporaneous local-disk I/O/XFS errors appeared in the filtered kernel log. The preceding VM 119 archive passed both structural checks. The target HDD reported healthy SMART attributes with no reallocated, pending, uncorrectable, CRC, or logged errors; a subsequent short offline self-test also completed without error. The failed archive remains invalid.

A replacement stopped-mode archive, `vzdump-qemu-119-2026_09_27-13_52_26.vma.zst`, subsequently passed both Zstandard checksum testing and streamed VMA verification. It reported an uncompressed size of 13,561,071,104 bytes and SHA-256 `1b2b2aa5910bc2d39e9adb286ac5282ab9e57f412a136726ed65980bfefbe951`. It was restored under a separate VM ID with networking removed; the restored guest booted, mounted `/srv/minecraft`, retained the world files, and started Minecraft locally. This passes the local backup-and-recovery gate for VM 119. Scheduling, retention, and failure notification remain to be configured.

Later October records describe six Backrest plans, including Wasabi destinations. Exact production source coverage, schedules, retention, notifications and broader recovery tests remain unverified. The dockerhost26 staging freshness failure reported on 2026-10-11 and required discovery data are documented in [`backup-troubleshooting.md`](backup-troubleshooting.md). `yggdrasil` also has a 3.6 TB XFS disk mounted at `/mnt/pve/backups`, but its presence must not be treated as evidence of a working backup or recovery process.

The implementation framework is maintained in [`backup-strategy.md`](backup-strategy.md). Its direct-upload architecture and schedules are the original proposal; later records place orchestration on the existing `restic` VM. Reconcile actual plan configuration before treating the proposal as deployed behavior.

## Recovery

A local Restic smoke-test restore and an isolated Minecraft VM 119 restore/boot test are documented; broader application recovery procedures remain untested. Do not assume that VM, container, configuration, Unraid-share, or UniFi Protect data is recoverable until backups and restore tests are implemented.

## Monitoring and alerting

The Turing Pi 2 K3s cluster runs an experimental Prometheus/Grafana monitoring stack with Alertmanager-to-Discord delivery. It also runs Frigate on `TR4`; Frigate camera events are separate from the Alertmanager notification path. The cluster remains a learning and experimentation environment and must not be treated as a highly available production monitoring dependency.

K3s is the current orchestration platform. Ceph is a separate exploratory interest and is not currently selected as storage for the monitoring stack or Kubernetes. See [`edge-cluster.md`](edge-cluster.md) and [`frigate.md`](frigate.md).

## Maintenance

_Patch cadence, planned downtime, and rollback procedures._

### Minecraft VM boot ordering — 2026-09-27

Minecraft VM 119 originally bound TCP 25565 specifically to its LAN address `192.168.0.171`. Docker started before that address existed, so it failed to restore the Minecraft container with `cannot assign requested address`; the early bridge restoration also lacked usable outbound connectivity. The VM has no installed `dhcpcd-wait-online.service`. A Docker systemd drop-in at `/etc/systemd/system/docker.service.d/wait-for-lan.conf` waits up to 120 seconds for the reserved address on `ens18`, and Docker separately has `RequiresMountsFor=/srv/minecraft`. After moving the VM to DMZ VLAN 90, both the Compose host bind and wait rule were updated to `192.168.90.171`. Reboot testing confirmed the data mount, healthy automatic Minecraft startup, Mojang API connectivity, client login, and Discord notifications.

### Docker address-pool policy — 2026-09-28

Docker's built-in allocation exhausted several `172.x` pools and assigned `/20` networks from `192.168.0.0/16`. The Homepage network on `dockerhost26` received `192.168.80.0/20`, which overlapped the new Minecraft DMZ at `192.168.90.0/24` and captured return traffic. `/etc/docker/daemon.json` on `dockerhost26` now reserves `10.240.0.0/16` for automatically allocated `/24` Docker networks. Homepage was recreated successfully on that pool, resolving DMZ routing to Technitium and n8n. Existing Docker networks are unchanged until their Compose stacks are recreated; migrate remaining `192.168.x.x` networks gradually and never use `10.240.0.0/16` for routed LANs, VLANs, or VPNs.

### Legacy VM retirement — 2026-09-26

User-provided Proxmox shell output confirms VMs 103–113 were removed after stopped-mode, Zstandard-compressed `vzdump` backups to `nas-backups`. Their attached disks occupied 634 GiB on `vms`; the final inventory contains VMs 100–102 and 114–118. This was manual retirement work, not a scheduled backup deployment.

- `nas-backups` is an active SMB/CIFS backup destination at `//192.168.0.100/nas`, mounted at `/mnt/pve/nas-backups`. The user identifies the server as Mimisbrunnr, a physical TrueNAS/HexOS host (confirmed 2026-10-04).
- All 11 backup jobs eventually reported success and their archives were listed on the NAS. VM 112 initially failed because its CD drive referenced missing storage `ISOs`; ejecting the ISO allowed the retry to succeed.
- Archive verification passed explicitly for 103–107 and 112. The verification loop reaching 111 implies the replacement 108 and archives 109–110 passed, but their individual output was not supplied.
- The original archive for 108 failed decompression checksum verification and was retained alongside a replacement. Archive 111 failed once, then passed two decompression tests and produced three matching SHA-256 hashes. Archive 113 failed decompression and returned differing SHA-256 hashes across repeated reads. The cause remains unresolved; the filtered Proxmox kernel log showed only the CIFS mount event.
- VM 110 has no persistent EFI-variable disk configured. VM 107 retains a stale `bootdisk: ide0` reference despite its disk being attached as `scsi0`; consider these configuration details during restoration.
- The user explicitly accepted the recovery risk and proceeded with deletion. Archives were retained; recovery has not been proven by a restore/boot test. Do not describe these backups as reliably verified or this NAS path as a validated recovery solution.
- Live storage output reports `vms` as LVM and no storage named `NVMEstorage`. Reconcile the older physical storage inventory before making assumptions about disk mapping.
