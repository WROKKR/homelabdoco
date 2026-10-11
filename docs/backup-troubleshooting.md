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
trigger at 02:30 on October 12. The timer definition/timezone is not yet inspected.
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

Next inspect the service/timer definitions, pull script and freshness script
without executing them. Identify any redirected output or separate log path,
early exit conditions, execution user and transfer/export dependencies. Review
all output for embedded credentials before sharing. Do not use `bash -x`, which
can expose expanded secrets, or manually restart the service until the pull
script's effects have been reviewed.

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
| Freshness check | Reviewed script, actual staging and marker paths, timestamp semantics and clock state | Script path and 3-hour limit only |
| Refresh pipeline | Export/pull scripts, scheduler, dependencies, trigger history and first error after last success | Pull script/unit names established; 02:30 triggers and repeated exit 1 on October 10–11; definitions and script diagnostics missing |
| Source coverage | Per-application data paths, named volumes, databases/dump method, export validation and exclusions | Unknown |
| Both dockerhost26 plans | Exact source paths, hook conditions/failure policy, schedules/timezone, retention and repository mapping | Names only; local hook error supplied |
| Local repository | Actual repository path, mount/capacity, latest successful snapshot and check result | Appliance disk documented; plan mapping unknown |
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
