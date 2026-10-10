# Skip health reports

Priority correction — 2026-10-04: Dockerhost26, infrastructure hosts and Home Assistant are the disruptive-outage priorities. Homepage is a frequently edited application, not the centerpiece of availability monitoring. Existing tools give container status and Proxmox host/VM snapshots; Dockerhost26 guest CPU/RAM/disk trends and Home Assistant application health are not established. Confirm broader physical-host scope before adding checks. Prometheus currently has Turing Pi node metrics, plus configured HTTPS/DNS probes; it does not yet establish host-history coverage for Dockerhost26 or Yggdrasil.

First stage: manually collected endpoint reports from `ollama2`, explained in Discord by Skip. No scheduled collection, live agent tools or remote administrative access is configured by this stage.

Use [`skip-health-check.sh`](skip-health-check.sh). Homepage's host binding is confirmed by Docker inventory. Home Assistant TCP 8123 and Proxmox TCP 8006 are initial assumed direct web endpoints, pending user confirmation. These probes use no credentials and discard response bodies. HTTPS certificate verification is skipped only for the fixed private Proxmox URL because its certificate configuration is not inventoried; this check does not validate TLS trust.

HTTP responses show endpoint reachability from the collector, not application correctness, all VM health, Homepage widget health, Home Assistant automation success, or backup success. Authentication failures and redirects must not be automatically classified as outages. Collection errors are reported separately through curl exit status.

Paste the timestamped report into Skip's Discord conversation with: "Explain this report briefly. Separate responding endpoints, failed checks, and unknowns. Do not infer VM, automation, widget, or backup health. Do not propose changes or commands."

After initial results, add curated local checks on dockerhost26 and yggdrasil as needed. Do not give Skip Docker socket access, Proxmox administrative credentials or arbitrary shell execution as part of this reporting stage.

## First observed result — 2026-10-03

User-supplied collection at `2026-10-02T22:43:13+00:00` (2026-10-03 08:43:13 Australia/Brisbane) from `ollama2`: Homepage, Home Assistant and Proxmox each returned HTTP 200. Proxmox TLS verification was skipped. This confirms endpoint reachability at that time only.

Skip initially misclassified the results as public accessibility on port 80. After explicit source, address and port information was supplied, it correctly described LAN reachability and limits. The maintained collector now includes the probed URL in each result to reduce ambiguity. Uncorrected report interpretation has not yet passed an independent fresh-session check.

## Combined report configuration

Prepared `services/skip-proxmox/update_reporting_prompt.py` to append a marked reporting block to the existing Skip prompt without replacing personality or inventory. It backs up the prior prompt privately and is repeatable without duplicating rules. User execution and fresh-session combined-report validation are pending. No scheduler or alert automation has been configured.

Combined scope: two Dockhand status calls and three Proxmox calls, with exact names, healthcheck versus running distinctions, calculated units, sampled-load caveats and explicit untested coverage. It cannot establish Homepage widget behavior, Home Assistant automation success, client availability or backup integrity.

The first combined LLM-assembled report failed: Skip overstated health, invented n8n usage of ollama2 and a 7B model, and recommended a restart without diagnosis. Prepared `services/skip-proxmox/combined_report.py` to compose the report deterministically from the existing collectors. User live check passed at 10:10 Brisbane on 2026-10-03, and the registered `homelab_report` MCP tool `homelab_health_report` returned a factually preserved Discord report at 10:14. Skip added formatting only. Updated the persistent reporting-rule installer to select this combined tool by default; application of that updated installer is pending. Individual tools remain for targeted questions. No schedule configured.

## Change-only notifications (prepared)

User requested notifications only when something changes. Prepared `services/skip-proxmox/change_monitor.py` for a five-minute user timer on ollama2, with a silent initial baseline and two consecutive matching polls before notification. Tracks container running/health state, addition/removal, VM state and collection failure/recovery. Ignores uptime and numeric CPU/RAM fluctuations. Notifications use deterministic text through `hermes send`, with no model invocation. Target must be an explicit numeric Discord channel. Delivery failures retain changes for retry; multi-message partial delivery may cause duplicates on retry. Monitor state is private and atomically saved. Concurrent polls are locked. Baseline is retained across restarts; corruption fails rather than silently resetting. Initial existing problems are baselined without an alert.

Syntax and pure transition checks passed locally for two-poll confirmation, transient recovery and removal. Linux execution, delivery and timer remain pending. This monitor runs on ollama2 and cannot notify if that VM, host, network or Discord delivery fails; no external dead-man monitor exists.

## Homepage container state (manual collection)

Run manually on `dockerhost26`. Restrict inspection to state fields; do not dump full container configuration, environment, or logs.

```bash
printf 'Homepage container report\nCollected: %s\nCollector: %s\n' "$(date -Is)" "$(hostname)"
sudo docker inspect --format '{{.Name}} status={{.State.Status}} running={{.State.Running}} restarting={{.State.Restarting}} oom_killed={{.State.OOMKilled}} restart_count={{.RestartCount}} started={{.State.StartedAt}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}not_configured{{end}}' homepage homepage-dockerproxy
```

Container running state and Docker healthcheck status do not establish Homepage widget correctness or proxy permission configuration. Restart count is cumulative for the container and does not identify a cause.
