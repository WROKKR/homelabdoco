# Monitoring on the Turing Pi cluster

## Status and boundary

An experimental Prometheus/Grafana/Alertmanager stack runs on the Turing Pi 2 K3s cluster. It is part of the learning environment and is not a highly available production dependency. It currently observes the cluster itself; monitoring of Proxmox, `dockerhost26`, VMs, or UniFi is not documented.

Facts below were observed from user-provided `kubectl` output on 2026-09-30 unless marked otherwise.

## Deployment

Both charts are installed declaratively through K3s `HelmChart` resources in `kube-system`, targeting namespace `monitoring`. Chart values live in those resources' `valuesContent`, not in this repository yet.

| HelmChart | Chart | Version | Repository |
|---|---|---|---|
| `monitoring` | `kube-prometheus-stack` | `88.3.0` | `https://prometheus-community.github.io/helm-charts` |
| `blackbox` | `prometheus-blackbox-exporter` | `11.17.1` | same |

The `monitoring` namespace is about 25 days old (created early September 2026).

## Components and placement

| Component | Node | Persistent storage |
|---|---|---|
| Prometheus (`prometheus-monitoring-kube-prometheus-prometheus-0`) | `pc3` | 20 GiB `local-path` PVC |
| Grafana (`monitoring-grafana`) | `tr4` | 5 GiB `local-path` PVC |
| Alertmanager (`alertmanager-monitoring-kube-prometheus-alertmanager-0`) | `pc2` | None observed |
| Prometheus Operator | `tr4` | None |
| kube-state-metrics | `tr4` | None |
| node-exporter DaemonSet | `pc1`, `pc2`, `pc3`, `tr4` (host network, port 9100) | None |
| Blackbox exporter | **No pod or Service observed** | — |

All pods were Running. Restart counts are uniform (four per container, last eight days before observation), consistent with whole-cluster restarts rather than crash loops.

`local-path` volumes are node-local and pin their pods to that node. Prometheus is therefore tied to `pc3` and Grafana to `tr4`. Neither volume is replicated.

## Access

| Service | Type | Port | Access |
|---|---|---|---|
| Grafana | NodePort | `30300` → 80 | `http://<any node IP>:30300`, e.g. `http://192.168.0.183:30300` (plain HTTP) |
| Prometheus | ClusterIP | 9090 | `kubectl port-forward` only |
| Alertmanager | ClusterIP | 9093 | `kubectl port-forward` only |

No Ingress for the monitoring stack was observed. Grafana admin credentials are stored in a Kubernetes Secret; never record them here.

```bash
# From PC3
sudo k3s kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090
sudo k3s kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-alertmanager 9093:9093
```

## Alerting

Alertmanager delivers to Discord (documented previously; receiver configuration, routes, channel, and custom rules have not been captured). The Discord webhook URL is a secret and must stay in a Kubernetes Secret or redacted chart values. Frigate camera events do not use this path.

## Open discrepancies

1. **Blackbox exporter:** its HelmChart exists and reports `FAILED=False`, but no matching pod or Service appeared in filtered output. Confirm whether it is running under a name without `prom`, or whether the install never produced a workload.
2. **Grafana volume on `tr4`:** [`edge-cluster-troubleshooting.md`](edge-cluster-troubleshooting.md) records `local-path` as restricted to `pc3`, but Grafana's bound `local-path` volume runs on `tr4`. Either the provisioner's `nodePathMap` was later extended to TR4's NVMe or the placement needs explaining. Verify before relying on either document.

## Not yet documented

## Discovery update — 2026-10-04

User-supplied Kubernetes inventory confirms `blackbox-exporter` is running on pc1, with ClusterIP Service `10.43.225.237:9115`. This resolves the earlier missing-pod/Service discrepancy. Prometheus runs on pc3 and its main Service is `monitoring-kube-prometheus-prometheus`, ClusterIP `10.43.239.132`, ports 9090/8080. Alertmanager remains ClusterIP `10.43.224.234:9093`; Grafana remains NodePort 30300. No Ingress appeared in the supplied listing.

ServiceMonitors include blackbox probes named `blackbox-exporter-monitoring-wwbb-casa` and `blackbox-exporter-technitium-internal-dns`. Custom PrometheusRules include `blackbox-alerts` and `technitium-dns-alerts`. Names establish configuration presence, not successful target scraping, probe behavior, or alert delivery. Active targets and firing/pending alerts remain to be queried.

The user attempted loopback Prometheus API access on PC3 and received connection refused, followed by a JSON parse error due to empty curl output. This establishes no listener on loopback TCP 9090 at that time; it does not establish a Prometheus outage. The service name in the proposed port-forward matches the inventory. Temporary forwarding requires the process to remain running in another terminal; alternatively the observed ClusterIP can be tested directly from PC3. Do not expose an unauthenticated NodePort for Skip as part of discovery. Notification timer remains unconfigured while monitoring coverage is investigated.

## Remaining inventory

User-supplied API discovery at 2026-10-04 approximately 11:50 Brisbane time showed 27 active targets, all scrape health `up`: two blackbox exporter targets, Grafana, Alertmanager, apiserver, CoreDNS, kubelets, operator, Prometheus, kube-state-metrics and node exporters on 192.168.0.181–184. Duplicate kubelet/monitoring targets correspond to separate scrape endpoints; do not classify duplicates as an error without endpoint metadata. Both blackbox target instances were exporter pod address `10.42.1.23:9115`; actual probe destinations/results have not been established. `probe_success` is still needed: scrape `up` is not probe success.

Only active Prometheus alert returned was `Watchdog`, firing with severity `none`. This always-firing heartbeat should not be narrated as an outage. No Proxmox, Dockerhost26, HAOS or ollama2 host-metric targets appeared in this snapshot. This does not rule out blackbox probing of their services; current exporter inventory provides no evidence of resource-history coverage for those hosts. Broad host monitoring remains incomplete.

Subsequent fixed metric queries returned `probe_success=1` for target `monitoring-wwbb-casa` (instance `https://192.168.0.160`) and `technitium-internal-dns` (instance `192.168.0.160:53`). HTTPS probe status was 200. Neither establishes Homepage port 3001, Home Assistant or Proxmox probe coverage. DNS module query name/expected answer and HTTPS host-header/TLS policy remain unknown; success means the configured probe passed, not that all DNS/application behavior works.

Prepared `services/skip-prometheus/collector.py` for PC3, restricted to targets, active alerts and fixed probe metric reads with projected fields. Prepared a stdio SSH wrapper `services/skip-prometheus/server.py` for ollama2 with three argument-free tools. Proposed dedicated forced-command SSH key restricted by source IP 192.168.0.167, no forwarding/PTY, and only three exact command tokens. No Kubernetes admin credentials will be given to Skip, no new service exposure, and no arbitrary PromQL or shell command tool. Local projection, heartbeat and tool-argument checks passed. Transfer, forced-key installation, live validation and Hermes registration remain pending. The user's existing wwbb-admin account is assumed for SSH execution, not a claim of dedicated OS-level least privilege.

- Chart `valuesContent` (sanitized) for both HelmCharts.
- Prometheus retention time/size (chart default is 10 days; volume is 20 GiB).
- Scrape targets beyond chart defaults, including any blackbox probes.
- Alertmanager routes and receivers, custom `PrometheusRule` resources, Grafana dashboards and data sources.
- Backup and recovery of Grafana state and chart values.
- A dead-man's-switch: if `pc3` or the cluster fails, Prometheus and Alertmanager fail with it and nothing alerts. The chart's always-firing `Watchdog` alert can feed an external heartbeat service.

## Checks

```bash
sudo k3s kubectl get pods -n monitoring -o wide
sudo k3s kubectl get helmchart -n kube-system monitoring blackbox
sudo k3s kubectl get prometheus -n monitoring -o jsonpath='{.items[0].spec.retention}{" "}{.items[0].spec.retentionSize}{"\n"}'
sudo k3s kubectl get pv $(sudo k3s kubectl get pvc -n monitoring monitoring-grafana -o jsonpath='{.spec.volumeName}') -o jsonpath='{.spec.nodeAffinity}{"\n"}'
sudo k3s kubectl get cm -n kube-system local-path-config -o jsonpath='{.data.config\.json}{"\n"}'
```

Export chart values for version control only after removing webhook URLs, passwords, and tokens:

```bash
sudo k3s kubectl get helmchart -n kube-system monitoring -o jsonpath='{.spec.valuesContent}'
```
