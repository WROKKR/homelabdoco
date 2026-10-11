# Backup troubleshooting

## Incident reported 2026-10-11

User-supplied Backrest output for `dockerhost26-local` reports that
`/usr/local/sbin/check-dockerhost26-staging` exited with status 1 in
`plan/dockerhost26-local/hook/0`.

- Recorded staging pull: `2026-10-02T02:31:20+10:00`.
- Reported age at the check: 780,220 seconds (9 days, 43 minutes, 40 seconds).
- Maximum permitted age: 10,800 seconds (3 hours).
- Task log time: `03:15:00.015Z`; the supplied line has no date.

The observed failure is the staging freshness hook. The supplied excerpt does
not establish the hook condition/timing, whether Restic started, why refresh
stopped, or whether the timestamp correctly represents complete staging data.
Do not bypass the check, increase the threshold, or touch its timestamp to make
an old dataset appear fresh.

The user also identified `dockerhost26-wasabi`, but provided no separate error
for that plan. Shared staging is a hypothesis until both plan definitions and
logs are inspected. No Wasabi connectivity or credential failure is established.

## Refresh service evidence — 2026-10-11

User-supplied filename discovery identifies these files on `restic`:

- `/usr/local/sbin/pull-dockerhost26-backup`
- `/usr/local/sbin/check-dockerhost26-staging`
- `/etc/systemd/system/pull-dockerhost26-backup.service`
- `/etc/systemd/system/pull-dockerhost26-backup.timer`
- Timer enablement link under `/etc/systemd/system/timers.target.wants/`.

The supplied timer listing records a trigger at 02:30 on October 11 and the next
trigger at 02:30 on October 12. The subsequently supplied timer definition uses `OnCalendar=*-*-* 02:30:00` with no explicit timezone; observed service timestamps use AEST. Host timezone confirmation remains outstanding.
Service status and journal show the pull script exiting with status 1 on both
October 10 and 11, at the initial 02:30 attempt and subsequent five-minute retries
through 02:55. Each attempt exits within approximately one second. At about 03:00,
the next restart request is refused with `Start request repeated too quickly`.
The service is failed; its `ExecStart` is `/usr/local/sbin/pull-dockerhost26-backup`.
The supplied service timestamps use AEST.

This confirms the timer fires and the refresh service repeatedly fails. The
restart limit is reached after earlier script failures; it does not explain the
initial exit. No script-level diagnostic appears in the supplied journal, so
source availability, exports, permissions, transfer and marker handling remain
unresolved. The October 10–11 excerpt does not date the first failed refresh.

The subsequently supplied service definition establishes:

- Execution user/group: `backrest:backrest`; `Type=oneshot`.
- Network ordering: `After=network-online.target` and `Wants=network-online.target`.
- Retry policy: `Restart=on-failure`, `RestartSec=5min`.
- Start limit: six starts within 3,600 seconds.
- Start timeout: one hour.
- Timer: nightly 02:30, `Persistent=true`, activating the pull service.

The pasted timer stops at `[Install]`; its install settings were not supplied.
An enablement link was discovered earlier. No working directory, environment or
output redirection is shown in the supplied service excerpt. The scripts remain
uninspected. Inspect source access and staging permissions in the actual
`backrest` execution context once their paths and mechanisms are established;
a successful command as an administrator would not prove this service can run it.

Next inspect the pull script and freshness script without executing them. Identify any redirected output or separate log path,
early exit conditions, execution user and transfer/export dependencies. Review
all output for embedded credentials before sharing. Do not use `bash -x`, which
can expose expanded secrets, or manually restart the service until the pull
script's effects have been reviewed.

## Supplied script behavior — 2026-10-11

The user supplied both scripts. They establish this pull pipeline:

- Source: `restic-pull@192.168.0.160:/var/lib/homelab-export/`.
- SSH identity file reference: `/opt/backrest/ssh/dockerhost26_ed25519` (never store its contents).
- Destination: `/srv/backups/staging/dockerhost26/`.
- Advisory lock: `/run/lock/pull-dockerhost26-backup.lock`.
- Remote readiness requires no `files/.incomplete` and a nonempty
  `files/COMPLETED_AT` under the source tree.
- Source timestamp must be no more than six hours old or five minutes ahead.
- After readiness and age checks, the script creates destination `.incomplete`,
  then uses `rsync -a --delete-delay --partial` to mirror the export tree.
- After transfer it rechecks readiness and requires the source timestamp to be
  unchanged. It writes `SOURCE_COMPLETED_AT` and `PULLED_AT`, then removes the
  destination incomplete marker.
- The Backrest freshness check requires the destination directory, no incomplete
  marker, and nonempty source/pull timestamp files. It validates the pull timestamp
  against the three-hour limit; it does not parse the recorded source timestamp.

The first `remote_ready` runs before the ERR trap and returns SSH's remote `test`
status. Missing/empty remote completion metadata or an incomplete export can
therefore cause exit 1 without a diagnostic. This is consistent with the journal,
but remains a hypothesis until the remote paths are checked as the service user.
Other pre-transfer failures include opening the local lock, SSH/key access and
timestamp parsing. A stale-source branch prints a specific diagnostic; none was
present in the supplied journal. Local lock/key/staging permissions and remote
path access still require verification.

Inspect source completion metadata through SSH as local `backrest`, using the
same identity as the script. Report directory accessibility, incomplete-marker
presence, completion-file size/readability and its timestamp. If SSH itself
fails, diagnose authentication/host-key/network access before inferring source
state. Inspect the exporter on dockerhost26 only after these results: its job
name, schedule, latest failure and required database exports remain unknown.
Do not delete either incomplete marker or manually write completion timestamps.
Do not invoke the pull script yet: its rsync deletion option mutates staging.

The pasted pull begins `!/bin/bash`; confirm the actual first line is
`#!/bin/bash` before changing anything. The supplied text alone does not establish
a malformed installed shebang.

## Confirmed source readiness failure — 2026-10-11

The user ran the read-only SSH probe as local `backrest` with the pull script's
identity and remote account. It successfully entered the export `files`
directory and reported `Export incomplete marker PRESENT` and
`COMPLETED_AT missing or empty`.

This confirms both source readiness conditions fail, explaining the pull's
silent early exit 1. SSH authentication and access to that directory worked for
this probe. The source export is not marked complete; whether its exporter is
currently running, failed or abandoned remains unknown. Do not remove markers
or fabricate timestamps. Identify the exporter scheduler and script on
dockerhost26 (`192.168.0.160`), then inspect its status, logs and database export
steps before deciding on a repair. This does not establish the Wasabi plan's
own error or complete staging/repository permissions.

## Source export failure identified — 2026-10-11

User-supplied dockerhost26 discovery identifies the enabled
`homelab-backup-export.timer`, triggering `homelab-backup-export.service` at
02:00 AEST (October 11 last trigger; October 12 next trigger). Export scripts
are `/usr/local/sbin/homelab-backup-export`, `homelab-files-export`, and
`homelab-db-export`. Service `ExecStart` runs the main script.

The October 10 and 11 journals both report successful logical dumps for Vocodex
PostgreSQL, n8n PostgreSQL and BookStack MariaDB, then stop 36 running containers
and begin copying `/opt/containers` and named volumes. After copying
`vocodex_pgdata` and `technitium_config`, Docker reports:
`get portainer_portainer_data: no such volume`.
The exporter then reports starting Technitium first, pia-vpn afterward, ordinary
containers next and VPN dependents after VPN health. It reports all previously
running containers restarted, then the service exits 1. These are script reports,
not independent application-health or dump-integrity checks.

The missing Portainer volume is the observed failure point explaining the
unfinished source export. An obsolete required-volume entry is the leading
hypothesis: the October service inventory did not list running Portainer, but
retirement has not been confirmed. Inspect the file exporter and actual volumes/
container mounts before changing the recovery set. Never create an empty volume
to satisfy the exporter or skip missing required volumes indiscriminately.
If Portainer was intentionally retired, remove its obsolete entry from the
reviewed export inventory; if still needed, locate its actual data or recover
it before considering backups complete.

This exporter is service-disrupting: it stops Docker workloads, including DNS
and the VPN stack, for the file copy. A manual export retry needs confirmation
under the repository working agreement after the concrete fix is reviewed.
Do read-only inventory/script inspection first. Keep incomplete markers intact.
Remaining coverage questions include whether all required named volumes and
bind mounts are covered, and how newer Shlink, Ghost and Firefly databases are
protected. Three logical dump success messages do not prove coverage of all
current databases; a reviewed stopped-file export may provide other protection.

## Documented backup estate

Existing October records describe Backrest on `restic` (`192.168.0.249`) and six
plans: dockerhost26 to local and Wasabi; HexOS backups to Wasabi; Immich photos
to Wasabi; and the restic appliance to local and Wasabi. Home Assistant exposes
last-result and last-backup sensors; see [skip-homeassistant.md](skip-homeassistant.md).
This inventory is not a live verification of configuration or recoverability.
The original [backup-strategy.md](backup-strategy.md) contains proposed schedules
and architecture, not confirmed settings for these deployed plans.

## Read-only discovery

Start on the backup VM, in its normal administrative shell. These commands
identify candidate units and files without running a refresh or backup:

```sh
hostname
systemctl list-timers --all --no-pager
systemctl list-unit-files --no-pager | rg -i 'backup|staging|dockerhost|backrest|restic|pull|sync'
sudo stat /usr/local/sbin/check-dockerhost26-staging
sudo rg -l 'dockerhost26|staging' /usr/local/sbin /etc/systemd/system /etc/cron.d /etc/crontab
```

If `rg` is unavailable on the VM, use `grep -Ei` for the unit list and
`grep -RlE` for the filename search. Missing paths are useful evidence, not a
reason to invent the job name. If nothing appears, inspect the relevant user's
cron and Backrest hooks locally; refresh may be scheduled there or on dockerhost26.

Inspect the check script locally to identify the staging path, timestamp file,
age calculation and success criteria. Share only a reviewed, redacted copy;
scripts, unit files and logs can embed credentials. Do not paste Backrest's
complete configuration, environment files, or credential-bearing command lines.

Once the exact refresh unit name is found, inspect its timer/service definition
locally and obtain a redacted status and journal covering the last successful
pull and subsequent failure. Record the execution user, working directory,
source/destination, schedule/timezone, last trigger/result and next trigger.
Check free space/inodes, expected mounts and path ownership on the staging host.
Check source exports, SSH/rsync access and clock state only after learning which
mechanisms the script actually uses. Never run an unknown refresh script before
reviewing whether it stops containers, overwrites files or deletes data.

In Backrest, inspect each plan's paths, exclusions, schedule/timezone, hooks,
hook failure policy and last operation separately. Record the latest successful
snapshot time as well as the most recent attempt/result. Obtain the Wasabi
plan's own failing operation and redacted log; do not infer it from local status.

## Required data still missing

| Area | Required facts/evidence | Status |
|---|---|---|
| Execution context | Backrest version, native/container deployment, hook host/user and path mappings | Unknown |
| Freshness check | Reviewed script, actual staging and marker paths, timestamp semantics and clock state | Scripts supplied; paths and marker rules established; live metadata/clock checks missing |
| Refresh pipeline | Export/pull scripts, scheduler, dependencies, trigger history and first error after last success | Pull script and unit definitions supplied; nightly 02:30; repeated exit 1 on October 10–11; remote readiness and source exporter state missing |
| Source coverage | Per-application data paths, named volumes, databases/dump method, export validation and exclusions | Unknown |
| Both dockerhost26 plans | Exact source paths, hook conditions/failure policy, schedules/timezone, retention and repository mapping | Names only; local hook error supplied |
| Local repository | Actual repository path, mount/capacity, latest successful snapshot and check result | Staging path established; appliance disk documented; repository/plan mapping unknown |
| Wasabi repository | Endpoint/region, bucket/prefix, secret references, access policy, latest snapshot/check | Unknown; never record secret values |
| Alerting | Failure and stale-staging alerts, recipient reference, retry policy and delivery test | HA status sensors documented; notification behavior unknown |
| Recovery | Recovery objectives, offline credential recovery locations, application/database restore tests | Local smoke test and isolated Minecraft restore documented only |

## Recovery gate

After identifying the root cause, repair the refresh mechanism with confirmation
if the operation is destructive or service-disrupting. Validate source exports
and a complete staging pull, then run the freshness check in its actual Backrest
execution context. Verify the marker advances only after all required exports
and transfers succeed. Retry both plans separately, confirm new snapshots include
the intended data, and perform an isolated file/database restore. Record results
and remaining coverage gaps; a green job alone does not establish restorability.
