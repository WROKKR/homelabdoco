# Homelab overview

## Goals

- Provide home networking, storage, media, home automation, local AI, web hosting, workflow automation, and security-camera services.
- Support software development from a Windows desktop and a Linux laptop.

## Architecture

The network uses a UniFi stack. A UniFi Dream Machine Pro SE is the router and runs UniFi Protect, with an installed disk used for Reolink security-camera recordings.

Proxmox is the only server virtualization platform. WSL is used as a development tool on the Windows workstation and is not treated as homelab virtualization.

The currently identified server estate consists of:

- An older Proxmox server hosting the homelab VMs.
- A newer Unraid server providing shares used by the Plex VM.
- A physical HexOS/TrueNAS server intended to provide storage for more important content; current operational details remain to be inventoried.
- A Turing Pi 2 development cluster populated by three Raspberry Pi CM4 modules and one Turing RK1. It runs an experimental four-node K3s cluster with monitoring and Frigate workloads, but remains a non-production learning environment.

All VMs run on Proxmox. The Proxmox environment includes a Docker VM named `dockerhost26`, plus VMs for Plex, Home Assistant, two Ollama instances (`ollama01` at `192.168.0.166` and `ollama2` at `192.168.0.167`), and other workloads not yet inventoried. See [`ollama.md`](ollama.md) for the local AI VM inventory. The Docker VM address observed from published container ports is `192.168.0.160`.

## Hosts and platforms

| Name | Role | Platform | Address or DNS | Notes |
|---|---|---|---|---|
| `odin` | Router, network controller, and Protect recorder | UniFi Dream Machine Pro SE / UniFi OS / UniFi Protect | `192.168.0.1` | Contains a disk used for Reolink camera recordings |
| `yggdrasil` | Primary virtualization host | Proxmox VE 9.2 on Debian 13 | `192.168.0.50/24` | Hosts all VMs, including Docker, Plex, Home Assistant, and Ollama |
| `Urdarbrunnr` | Media storage | Unraid 7.3.1, physical host | `192.168.0.150` | Hostname, platform, address and management URL https://192.168.0.150 confirmed by user on 2026-10-04; provides shares to Plex |
| `restic` | Backup appliance | Debian 13 VM on Proxmox | `192.168.0.249/24` | Runs Backrest and Restic; 32 GB SSD-backed system disk plus 1 TB HDD-backed repository disk |
| Turing Pi 2 cluster | Four-node experimental K3s cluster hosting monitoring and Frigate | Turing Pi 2 with three Raspberry Pi CM4 modules and one Turing RK1 | `PC1`-`PC3` and `TR4`; see [`edge-cluster.md`](edge-cluster.md) | Mixed Raspberry Pi OS and Ubuntu/Rockchip BSP; non-production |
| `Mimisbrunnr` | Important-content storage | TrueNAS/HexOS 25.10.7, physical host | `192.168.0.100` | Hostname, platform, address and management URL https://192.168.0.100 confirmed by user on 2026-10-04; current configuration/status pending |
| Windows desktop | Primary workstation and Codex client | Windows with WSL | Unknown | Used for most workstation tasks and development |
| Linux laptop | Mobile workstation | Linux | Unknown | Physical client device |

## `yggdrasil` host profile

- Gigabyte B550 EAGLE WIFI6 motherboard.
- AMD Ryzen 9 3950X: 16 cores and 32 threads with AMD-V.
- 125 GiB usable memory and 8 GiB swap.
- NVIDIA GeForce GTX 970 GPU.
- One Realtek gigabit Ethernet interface used by `vmbr0`; a Realtek Wi-Fi interface exists but was down when inspected.
- Proxmox VE 9.2.0 with manager 9.2.3; Debian 13 and kernel `7.0.12-1-pve` at the time of inspection.
- Default route is through `odin` at `192.168.0.1`.

### Local storage summary

| Device class | Approximate size | Current role |
|---|---:|---|
| SATA system disk | 466 GB | EFI, Proxmox root, swap, and local LVM-thin storage |
| NVMe storage | 1.7 TB | LVM-backed VM disks (`NVMEstorage`) |
| NVMe storage | 1.8 TB | LVM-backed VM disks (`vms`) |
| SATA data disk | 3.6 TB | XFS mounted at `/mnt/pve/backups`; backup workflow not yet implemented |

Transient disk usage, process state, machine identifiers, boot identifiers, UUIDs, and serial numbers are intentionally not maintained as project context.

## Constraints and decisions

- Availability priorities are the three physical hosts (Yggdrasil, Unraid Urdarbrunnr, and TrueNAS/HexOS Mimisbrunnr), dockerhost26, and Home Assistant. Homepage is frequently edited but a lower-priority availability target. The Turing Pi remains experimental monitoring infrastructure.

- Proxmox is the sole server virtualization platform.
- WSL is a workstation development tool, not part of the virtualization estate.
- Unraid currently serves media-related shares.
- The planned HexOS/TrueNAS system is intended for more important content.
- All VMs live on Proxmox; Unraid is used for shares rather than VM hosting.
- Backrest backup plans are documented on the `restic` VM; deployed schedules, source coverage and recovery validation remain incomplete. See [`backup-troubleshooting.md`](backup-troubleshooting.md).
- Hostnames, hardware specifications, full network addressing, storage protection, and availability requirements are not yet documented.
- K3s is the adopted experimental orchestration platform for the current Turing Pi cluster.
- Ceph is an exploratory future interest. It might use some, all, or none of the Turing Pi cluster and must not be treated as a committed storage design.
