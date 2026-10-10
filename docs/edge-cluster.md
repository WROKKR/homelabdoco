# Edge cluster and Raspberry Pi inventory

## Purpose and status

The Turing Pi 2 cluster is currently a learning and experimentation environment. Its likely future purpose is to run monitoring services after the hardware and software configuration has been tested and considered stable.

K3s has been adopted for the current experimental cluster. Ceph remains an exploratory future interest only: it might partially use this cluster or might not use it at all.

See [`edge-cluster-troubleshooting.md`](edge-cluster-troubleshooting.md) for the running record of commissioning problems, resolutions, and lessons.

## Confirmed current hardware

All three CM4 nodes:

- are installed or available for the Turing Pi 2 cluster;
- run 64-bit Raspberry Pi OS;
- have DHCP reservations on the existing LAN;
- remain non-production while experimentation continues.

| Quantity | Module | Memory | Boot storage | Current state |
|---:|---|---:|---|---|
| 2 | Raspberry Pi Compute Module 4 Lite | 8 GB each | 64 GB microSD each, installed in the Turing Pi CM4 adapter | Available and running Raspberry Pi OS |
| 1 | Raspberry Pi Compute Module 4 with eMMC | 4 GB | 16 GB onboard eMMC | Available and running Raspberry Pi OS |

The Turing Pi is hardware revision v2.4. The confirmed node layout is:

| Physical slot | Host | Address | Module | Boot storage | Additional storage | Current K3s role |
|---:|---|---|---|---|---|---|
| 1 | `PC1` | `192.168.0.181` | CM4, 4 GB | 16 GB eMMC | None | Agent |
| 2 | `PC2` | `192.168.0.182` | CM4 Lite, 8 GB | 64 GB microSD | None | Agent |
| 3 | `PC3` | `192.168.0.183` | CM4 Lite, 8 GB | 64 GB microSD | Samsung 860 EVO 500 GB SATA SSD | Server, embedded etcd, agent |
| 4 | `TR4` | `192.168.0.184` | Turing RK1, 8 GB | 32 GB eMMC | Samsung MZVLB256HAHQ 256 GB NVMe | Agent |

PC3's SATA SSD is formatted as ext4, mounted at `/mnt/k3s-storage`, configured in `fstab`, and covered by the periodic TRIM timer. TR4 boots Ubuntu from eMMC and mounts its ext4 NVMe at `/mnt/k3s-storage`; its K3s agent data is under `/mnt/k3s-storage/k3s`.

The CM4 wireless variants and cooling arrangement are not yet documented.

## Other Raspberry Pi plans

- `PS1` (`192.168.0.186`) is a standalone Raspberry Pi 4 with 8 GB RAM and microSD boot storage, joined as K3s worker `ps1` on 2026-10-11. The user-supplied node output confirms `Ready`, K3s `v1.36.3+k3s1`, Debian 13 (64-bit Raspberry Pi OS), kernel `6.18.50+rpt-rpi-v8`, and containerd `2.3.2-k3s2`. No dedicated workload is assigned. Memory cgroups were enabled and rpi-swap disabled before joining; the supplied checks confirm `memory` is available and no active swap remains. Workload networking validation is pending. PC3 remains the sole server/etcd member; PC3-local persistent volumes remain tied to PC3.

- Two Raspberry Pi 4 systems are future purchases rather than current inventory.
  - One is intended to host a second Technitium DNS server.
  - One is intended to drive a smart dashboard.
- One reclaimed Raspberry Pi 3B is currently available.
  - It is not intended to join the Turing Pi cluster initially.
  - Its standalone recreational use has not been decided.

## Intended and exploratory software

### Monitoring

The cluster now runs an experimental Prometheus/Grafana monitoring stack and a Frigate workload. See [`monitoring.md`](monitoring.md) for the stack's deployment and access details. These deployments are still part of the learning environment and must not be treated as highly available production dependencies. PC3 remains the sole K3s server and embedded-etcd member.

Frigate is pinned to the RK1 node `TR4` to use its RK3588 media and NPU acceleration. UniFi Protect remains the authoritative NVR; see [`frigate.md`](frigate.md) for the deployment, storage, camera policy, and operational checks.

### Kubernetes

The cluster currently runs K3s `v1.36.3+k3s1`. PC1, PC2, and PC3 use 64-bit Raspberry Pi OS based on Debian 13 with the Raspberry Pi 6.18 kernel. TR4 uses Ubuntu 22.04.5 with the Turing/Rockchip BSP 5.10 kernel. PC3 is the sole server and embedded-etcd member; PC1, PC2, and TR4 are agents. All four nodes are schedulable.

K3s uses its packaged Flannel networking, CoreDNS, Traefik ingress, ServiceLB, Metrics Server, and Local Path Provisioner. K3s state is stored under `/mnt/k3s-storage/k3s` on PC3's SATA SSD. Dynamically provisioned local volumes use `/mnt/k3s-storage/local-path` and are explicitly restricted to PC3; they are not replicated or highly available.

The CM4 and RK1 are ARM64 systems, so mixing them does not create a mixed CPU-architecture cluster. TR4 is labelled `homelab.local/module=rk1`, `homelab.local/storage=nvme`, and `homelab.local/platform=turing-pi2`. Hardware capability still differs significantly, particularly processing performance, accelerators, kernel support, and storage interfaces. Workloads should be scheduled by declared capabilities rather than by assuming all nodes are interchangeable.

The `lab/hello-cluster` deployment was scaled to four replicas. A replica ran successfully on TR4, and requests entering Traefik through `192.168.0.184` were routed across the mixed RK1/CM4 cluster.

### Ceph

Ceph is a future learning interest, not a committed part of the homelab architecture. It may use the Turing Pi cluster partially, entirely, or not at all.

If a real multi-host Ceph experiment is later approved, each OSD should normally receive a separate raw data device rather than consuming a node's Raspberry Pi OS boot microSD or eMMC. Any proposed Ceph topology must account for the Turing Pi's node-specific storage connectivity, 1 GbE networking, replication overhead, and the limited endurance and capacity of the current boot media.

## Open discovery items

- Record cooling, power-supply, and case details.
- Record CM4 wireless capability and whether Wi-Fi or Bluetooth is disabled.
- Decide whether the nodes should share a common baseline configuration and automation method.
- Decide whether TR4 should remain an agent or eventually participate in a three-server high-availability topology.
- Finish documenting the deployed monitoring stack's retention, backup, alert-delivery, and availability requirements.
