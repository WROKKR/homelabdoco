# Edge cluster troubleshooting log

## Purpose

This is a running record of problems encountered while commissioning the Turing Pi 2 and its K3s cluster. It records symptoms, causes, resolutions, and lessons that should survive beyond terminal history.

Do not record passwords, K3s join tokens, private keys, or hardware identifiers here.

## Turing Pi CLI installation on WSL

### Debian repository syntax was copied as Markdown

- **Symptom:** `apt update` reported that a repository resembling `[https://firmware.turingpi.com/tpi/debian](https://...)` had no Release file, and `apt` could not locate the `tpi` package.
- **Cause:** Markdown link syntax was pasted literally into `/etc/apt/sources.list` instead of using the raw repository URL.
- **Resolution:** Correct the repository entry to use the plain URL or install the CLI by another supported method.
- **Lesson:** Commands copied from rendered documentation must not include Markdown link wrappers.

### Distribution Cargo was too old to compile `tpi`

- **Symptom:** `cargo install tpi` failed while parsing `rand_pcg 0.10.2`, reporting that Cargo 1.75.0 did not support the `edition2024` feature.
- **Cause:** The Rust/Cargo version supplied by the WSL distribution was older than the dependency graph required by `tpi 1.0.7`.
- **Resolution:** Install or use a sufficiently current Rust toolchain, then install `tpi`. The resulting `tpi 1.0.7` binary was installed under the invoking user's Cargo bin directory.
- **Lesson:** Check `cargo --version` and which user owns the Rust toolchain before compiling current Rust applications. A toolchain installed for one user will not appear under another user's home directory.

### Shell prompt characters were treated as commands

- **Symptom:** Entering `$ tpi power on` produced `$: command not found`.
- **Cause:** The documentation's `$` shell-prompt marker was copied as part of the command.
- **Resolution:** Run `tpi power on` without the leading prompt character.

### `tpi` CLI syntax differed from older documentation

- **Symptom:** `tpi -u device -n 1` failed with `unexpected argument '-u'` under `tpi 1.0.7`.
- **Cause:** The documentation used syntax from an older CLI generation.
- **Resolution:** Consult `tpi --help` for the installed version and use its current command hierarchy, or use the BMC web interface for the equivalent USB-mode operation.
- **Lesson:** Record the CLI version alongside examples; do not assume older short options remain compatible.

### `turingpi.local` was not usable from WSL

- **Symptom:** `tpi power on` failed while requesting the BMC authentication endpoint at `turingpi.local`.
- **Cause:** WSL could not resolve or reach the `.local` mDNS name reliably.
- **Resolution:** Address the BMC by its reserved IPv4 address with `tpi --host <address> ...`.
- **Lesson:** Prefer the BMC's reserved address for automation; treat `.local` as a convenience name.

## CM4 provisioning and boot media

### CM4 Lite was incorrectly approached as an eMMC flashing target

- **Symptom:** Windows reported an unrecognized USB device while `rpiboot` remained at `Waiting for BCM2835/6/7/2711/2712...`.
- **Cause:** The target was a CM4 Lite. It has no eMMC, so there is nothing for `rpiboot` to expose as mass storage; it boots from the microSD slot on the Turing Pi CM4 adapter.
- **Resolution:** Write Raspberry Pi OS directly to the adapter's microSD card with Raspberry Pi Imager, including SSH customization, then boot the node normally.
- **Lesson:** Confirm whether a CM4 is Lite or eMMC before selecting a flashing workflow.

### CM4 modules do not use the Turing Pi rear NVMe slots

- **Symptom:** Initial storage planning assumed a CM4 could use its slot-associated M.2 NVMe connector.
- **Cause:** The Turing Pi carrier routes the CM4's single PCIe lane to a slot-specific peripheral instead. CM4 storage access is mini-PCIe on Nodes 1 and 2, onboard SATA on Node 3, and USB 3 on Node 4. The rear M.2 NVMe slots are not available to CM4 modules.
- **Resolution:** Place the Lite CM4 intended for SATA storage in physical Node 3. Reserve NVMe use for a compatible module such as the future RK1.

## Host identity and physical placement

### Hostnames followed modules after a physical swap

- **Symptom:** Moving the eMMC and Lite CM4s caused hostnames and reserved addresses to no longer align intuitively with physical Turing Pi slots.
- **Cause:** Hostnames live on each module's boot media, and DHCP reservations follow network identity rather than the carrier slot.
- **Resolution:** Rename the hosts so `PC1`, `PC2`, and `PC3` correspond to physical Nodes 1, 2, and 3 respectively, and update the associated DHCP reservations.

### `/etc/hosts` retained both old and new names

- **Symptom:** A host contained `127.0.1.1 PC1 PC3` after renaming.
- **Cause:** The old local hostname was retained as an alias during the rename.
- **Resolution:** Keep only the host's current name on its `127.0.1.1` entry and verify `/etc/hostname`, `hostname`, and local resolution agree.

## Node 3 SATA commissioning

### SATA disk was initially absent

- **Symptom:** `lsblk` on PC3 showed only the microSD card and swap devices; no SATA disk appeared.
- **Cause:** The CM4 PCIe controller was not initially enabled in Raspberry Pi OS.
- **Resolution:** Add `dtparam=pciex1` under a CM4 configuration section in the active boot `config.txt`, then cold-start the node.

### PCIe remained `link down`

- **Symptom:** The kernel initialized the BCM2711 PCIe root port, but `lspci` showed no endpoint and `dmesg` reported `brcm-pcie ... link down`.
- **Context:** The carrier is a Turing Pi 2 v2.4, whose Node 3 SATA design has a known unconnected `CLKREQ` limitation addressed in v2.5.
- **Investigation:** The OS configuration was valid and memory/storage drivers were not the issue because the onboard ASM1061 controller itself was absent from PCI enumeration.
- **Resolution:** After physical reseating and cold-start troubleshooting, PCIe linked at 5.0 GT/s x1. The ASM1061 SATA controller enumerated, and the Samsung 860 EVO linked at 6.0 Gbps.
- **Lesson:** A CM4 can boot and network while one of its two board-to-board connectors is not fully seated. When the root port exists but the endpoint does not, check the CM4-to-adapter connection, the adapter-to-slot connection, physical slot identity, and board revision before changing storage drivers or filesystems.

### Newly partitioned SSD reported an old VFAT signature

- **Symptom:** `mkfs.ext4` warned that the new partition contained a VFAT filesystem even though the disk initially showed no partition table or mounted filesystem.
- **Cause:** A stale filesystem signature remained at an offset exposed by the newly created partition.
- **Resolution:** After reconfirming the correct blank SSD target, overwrite the stale signature by proceeding with the intended ext4 format.

## K3s host preparation

### Raspberry Pi OS disabled the memory cgroup

- **Symptom:** The systems used cgroup v2, but `/proc/cmdline` contained `cgroup_disable=memory`.
- **Impact:** K3s requires the memory controller for normal kubelet/container accounting.
- **Resolution:** Append `cgroup_enable=memory cgroup_memory=1` to the active Raspberry Pi boot command line and reboot. The earlier disable argument remains in the effective command line, but the later enable arguments take effect; `memory` appears in `/sys/fs/cgroup/cgroup.controllers`.
- **Validation:** All three nodes report `cpuset cpu io memory pids` and K3s starts successfully.

### Raspberry Pi OS Trixie enabled zram swap

- **Symptom:** `swapon --show` reported a 2 GiB `/dev/zram0` device on every node.
- **Cause:** Raspberry Pi OS Trixie uses `rpi-swap` and zram by default.
- **Resolution:** Configure an `rpi-swap` drop-in with `Mechanism=none`, reboot, and verify `swapon --show` is empty.
- **Decision:** Use the conventional no-swap Kubernetes configuration for the initial cluster rather than enabling kubelet swap support.

## K3s cluster and storage

### Initial server placement changed after SSD commissioning

- **Initial idea:** Use the 4 GB eMMC CM4 as the first K3s server because eMMC was more durable than microSD.
- **Change:** Once Node 3's SATA SSD was working, PC3 became the stronger server because it has 8 GB RAM and SSD-backed state.
- **Current result:** PC3 runs the control plane, embedded etcd, and workloads. PC1 and PC2 are agents. K3s state and local persistent volumes are stored on the SATA SSD.

### Default local-path configuration could have used boot media on agents

- **Symptom:** The generated local-path configuration mapped `DEFAULT_PATH_FOR_NON_LISTED_NODES` to `/mnt/k3s-storage/local-path`.
- **Risk:** On PC1 or PC2, that path could be created on the root eMMC/SD filesystem even though the intended SSD exists only on PC3.
- **Resolution:** Configure the provisioner's `nodePathMap` so only `pc3` uses `/mnt/k3s-storage/local-path`, with an empty path list for all unlisted nodes.
- **Trade-off:** These volumes are fast and SSD-backed but local to PC3. They are not replicated and become unavailable when PC3 is offline.

### Storage validation

- **Test:** Create a temporary namespace, a 1 GiB `local-path` persistent-volume claim, and a BusyBox pod constrained to PC3.
- **Result:** The claim bound, the pod ran, and a file written inside the container appeared in the corresponding directory on the SATA SSD.
- **Cleanup:** Deleting the namespace removed the disposable workload and its dynamically provisioned volume according to the `Delete` reclaim policy.

## Current follow-up concerns

- The cluster has one control-plane/etcd member. PC3 failure removes cluster management and scheduling until it returns, although already-running workloads on agents may continue.
- PC3-local persistent volumes are not replicated or highly available.
- The Turing Pi 2 v2.4 Node 3 PCIe/SATA path should be watched for link failures after cold boots.
- The monitoring stack is deployed (see [`monitoring.md`](monitoring.md)); its retention, backup destination, and recovery procedure remain undecided.
- TR4 has been commissioned as an agent but still requires burn-in testing before it is trusted as a K3s server or etcd voter.
- Ceph remains an exploratory future project and is not part of the current storage design.

## RK1 commissioning

### BMC UI falsely reported that flashing failed

- **Symptom:** After flashing the RK1 through the BMC UI, the UI displayed `install failed: undefined`.
- **Observed result:** The image had actually been written successfully. The RK1 booted Ubuntu 22.04.5 from eMMC and completed package updates normally.
- **Resolution:** Verify actual node boot, Ethernet link, DHCP presence, and SSH access before assuming that this generic UI error represents a failed write.
- **Lesson:** The BMC UI result can be a false negative. Do not immediately repeat a long or destructive flash solely because the frontend reports an undefined error.

### RK1 image booted with a hybrid cgroup hierarchy

- **Symptom:** `stat -fc %T /sys/fs/cgroup` returned `tmpfs`; cgroup v1 controllers were mounted separately, with an additional cgroup v2 mount at `/sys/fs/cgroup/unified`.
- **Cause:** `/boot/firmware/ubuntuEnv.txt` contained `systemd.unified_cgroup_hierarchy=0`. The memory controller worked, but Kubernetes 1.36 defaults to rejecting cgroup v1 nodes.
- **Resolution:** Back up `ubuntuEnv.txt`, change the argument to `systemd.unified_cgroup_hierarchy=1`, reboot, and validate that `/sys/fs/cgroup` reports `cgroup2fs` with the expected controllers.
- **Lesson:** A functioning memory controller is not sufficient evidence of compatibility with a current kubelet. Check the hierarchy version as well as controller availability.

### RK1 local preparation and validation

- TR4 was installed in physical Node 4 and assigned the matching logical identity `TR4` and address `192.168.0.184`.
- The default 1 GiB swapfile was disabled and its `fstab` entry commented out.
- Persistent IPv4 forwarding was enabled through `/etc/sysctl.d/90-k3s.conf`.
- The blank 256 GB NVMe was formatted as ext4 and mounted at `/mnt/k3s-storage`.
- K3s `v1.36.3+k3s1` was installed as an agent with `/mnt/k3s-storage/k3s` as its data directory.
- The node joined as `tr4`, reached `Ready`, and successfully participated in scheduling, Flannel routing, Services, ServiceLB, and Traefik ingress.
