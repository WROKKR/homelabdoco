# Backup strategy

## Objective

Obtain the most recovery value from the Wasabi account without deploying another VM or uploading replaceable bulk data.

Wasabi has one S3-compatible storage class, called Hot Cloud Storage. It can be used as an archive target, but it is not a separate cold or deep-archive tier. Pay-Go has a 1 TB monthly billing minimum and a 90-day minimum storage duration for each object.

## Architecture

```text
Proxmox VM backups ──> /mnt/pve/backups on yggdrasil
                              │
High-value exports ──> encrypted Restic repository ──> Wasabi
                              │
Future local copy ──> HexOS/TrueNAS
```

There is no hosted or additional local backup VM in this design.

- Proxmox `vzdump` provides local whole-VM recovery on the existing 3.6 TB disk.
- Restic sends a small, encrypted, file-level recovery set directly to Wasabi.
- The future HexOS/TrueNAS server becomes the second local destination.
- Restic is officially documented as compatible with Wasabi.

## What goes to Wasabi

### Tier 0: recovery bootstrap

- Proxmox configuration export, including `/etc/pve`, with volatile and unnecessary files excluded.
- A VM-ID-to-service inventory and concise rebuild order.
- Docker Compose project definitions from `/opt` on `dockerhost26`.
- Encrypted copies of required Docker environment files.
- UniFi configuration export.
- Technitium DNS configuration/export.
- Restore instructions and references to credentials stored elsewhere.

### Tier 1: irreplaceable application state

- Home Assistant backup archives.
- PostgreSQL dumps for n8n and Vocodex.
- MariaDB dump for BookStack.
- Stateful data for Mealie, Memos, Vikunja, the home web server, and original Vocodex work.
- Other original personal data that cannot simply be downloaded or regenerated.

### Excluded by default

- Plex media.
- Download staging and completed downloads.
- Container images and build caches.
- Ollama model weights.
- Package caches, logs, temporary files, and reproducible operating-system data.
- Whole VM backup archives. These remain local because regularly uploading large changing VM images is poor value for the Wasabi minimum-cost objective.

## Local whole-VM protection

Use scheduled Proxmox `vzdump` jobs targeting `/mnt/pve/backups` for:

1. Home Assistant.
2. `dockerhost26`.
3. Plex configuration disks, excluding media mounts.
4. Other small VMs that are difficult to rebuild.

Initial local retention: 7 daily, 4 weekly, and 3 monthly copies, adjusted after measuring capacity. Install and enable QEMU guest agents where supported. Local backups on a disk in `yggdrasil` do not protect against loss of the entire host and are an interim recovery layer only.

## Direct Wasabi backup method

Run Restic on `dockerhost26`, because most high-value application state is already there. Mount or copy the other small exports into a restricted staging tree, for example:

```text
/var/lib/homelab-backup/
├── databases/
├── home-assistant/
├── proxmox/
├── technitium/
└── unifi/
```

Back up the staging tree plus the required `/opt` project directories. Generate database dumps before Restic runs. Do not copy secrets into logs or this Git repository.

Use one dedicated Restic repository in one dedicated Wasabi bucket. Restic performs client-side encryption and deduplication; the repository password is essential for recovery and must be stored offline in at least two recoverable locations.

## Wasabi security model

- Create a dedicated Wasabi user and bucket for this repository.
- Enable MFA on the Wasabi account owner.
- Use a dedicated automated key that can list, read, and add repository objects. Restrict deletion to Restic's lock objects if testing confirms that policy works; normal backup runs need to remove their locks but should not be able to delete packs, snapshots, indexes, or keys.
- Keep a separate maintenance credential with delete permission offline. Use it only for planned `forget --prune` maintenance.
- Enable bucket versioning for another recovery layer against accidental overwrites or deletion. Add lifecycle cleanup only after the pilot confirms how Restic and Wasabi versioning interact.
- Do not enable Object Lock initially. Restic is documented as compatible with Wasabi, but Wasabi does not document Restic as an Object Lock integration; retention locks can also prevent normal repository pruning.
- Never commit Wasabi keys or the Restic repository password. Load them from root-readable files or a secret manager at runtime.

## Schedule and retention

- Database and application exports: nightly.
- Restic backup to Wasabi: nightly after exports complete.
- Restic snapshot retention: 14 daily, 8 weekly, and 12 monthly snapshots.
- Repository metadata check: weekly.
- Full data sampling/check: monthly, sized to avoid unnecessary bandwidth.
- Planned prune: monthly or quarterly using the offline maintenance credential.
- File-level restore test: monthly.
- Full service recovery exercise: quarterly, rotating between Home Assistant and a Docker application.

Because Wasabi bills deleted objects for the remainder of their 90-day minimum duration, avoid aggressive pruning. Review active storage, timed-deleted storage, and repository growth after 30 and 90 days.

## Restore order

1. Recover the Restic repository password and Wasabi credentials from offline storage.
2. Restore the Tier 0 bootstrap set to an isolated machine.
3. Rebuild Proxmox networking and storage configuration if required.
4. Restore local whole-VM backups when available.
5. Recreate `dockerhost26` from Compose definitions and restore databases/application data.
6. Restore Home Assistant from its native backup archive.
7. Validate DNS, reverse proxy, authentication, and application health before restoring public ingress.

## Implementation gates

1. Confirm the PVE VM IDs and configure local `vzdump` jobs.
2. Create the Wasabi bucket, restricted users, and credentials.
3. Install Restic on `dockerhost26` and initialize an encrypted repository.
4. Back up a small non-critical test directory and restore it elsewhere.
5. Add database export scripts and the staging tree.
6. Restore one database into a disposable container.
7. Add Home Assistant and infrastructure exports.
8. Review Wasabi billing and storage growth before widening scope.

## References

- [Wasabi storage classes](https://docs.wasabi.com/apidocs/operations-on-objects)
- [Wasabi product terms and minimums](https://wasabi.com/product-terms)
- [Wasabi pricing](https://docs.wasabi.com/docs/may-2026-wasabi-pricing)
- [Restic with Wasabi](https://docs.wasabi.com/docs/how-do-i-use-restic-with-wasabi)
- [Restic S3/Wasabi repository setup](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html#wasabi)
