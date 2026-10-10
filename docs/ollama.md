# Ollama instances

Inventory supplied by the user on 2026-10-02 from commands executed inside two KVM guests. Both instances run as VMs on Proxmox. On 2026-10-03 the user confirmed ollama2 is VM 118; ollama01 VM ID and exact host placement remain pending.

The user describes one existing instance used by Home Assistant and n8n workflows and a second, better-resourced instance that is currently unused. The hostname-to-role mapping below follows the order of the supplied results and remains to be explicitly confirmed.

| Property | `ollama01` | `ollama2` |
|---|---|---|
| Role | Existing Home Assistant and n8n inference | Dedicated to Hermes for now, per user; deployment pending |
| Address | `192.168.0.166` | `192.168.0.167` |
| OS | Ubuntu 22.04.5 LTS | Ubuntu 26.04.1 LTS |
| Kernel at observation | `5.15.0-191-generic` | `7.0.0-34-generic` |
| Architecture / virtualization | x86-64 / KVM | x86-64 / KVM |
| Guest CPU allocation | 8 vCPUs, one socket, 8 cores reported | 8 vCPUs, one socket, 8 cores reported |
| Guest CPU model | AMD Ryzen 9 3950X 16-Core Processor | QEMU Virtual CPU version 2.5+ |
| Guest RAM reported | 31 GiB | 30 GiB |
| Swap | 8 GiB | 8 GiB |
| Root filesystem capacity | 98 GiB | 96 GiB |
| GPU visible in guest | Virtual display adapter only; `nvidia-smi` unavailable | NVIDIA TU116 / GeForce GTX 1660 Ti |
| NVIDIA VRAM | Not established | 6144 MiB (6 GiB) |
| NVIDIA driver | Not established | `595.91.07` |

The RAM values are rounded guest observations, not verified Proxmox configuration values. The CPU model on `ollama2` is a virtual model and does not establish its physical host CPU. GPU visibility and a working NVIDIA driver do not yet prove Ollama is using GPU acceleration.

Subsequent Proxmox API output on 2026-10-03 confirmed VM 118 (`ollama2`) runs on node `Yggdrasil` with 8 vCPUs and 32 GiB configured RAM (`maxmem=34359738368`). Earlier 30 GiB was guest-reported usable memory, not the configured allocation.

## Pending inventory

- Confirm hostname-to-role mapping, ollama01 Proxmox VM ID, and physical host placement.
- Confirm `ollama2` service unit and currently loaded models; versions and installed-model lists are recorded below.
- Remaining startup configuration, model storage, and network reachability from clients.
- Effective context length, concurrency, and GPU offload during inference.
- Actual endpoint URLs and models configured in Home Assistant, n8n, and Open WebUI.
- Hermes deployment location and validation. Initial scope is documentation assistance and read-only health reporting, with an eventual Discord bot interface. The user has allocated `ollama2` solely to Hermes for now; deployment is pending. See [`hermes.md`](hermes.md).

New models may be installed as needed, per the user. No model or resource configuration has been changed as part of this inventory.

## Ollama service and model inventory

The user initially supplied two identical API/service blocks on 2026-10-02. Subsequent hostname-labelled output established that the detailed inventory below belongs to `ollama01`, and supplied a separate version and model list for `ollama2`.

Both instances report the systemd environment setting `OLLAMA_HOST=0.0.0.0:11434`. No other variables from the requested Ollama settings filter appeared. This does not establish effective defaults, per-request overrides, firewall rules, or client reachability.

### `ollama01`

- Server version: `0.32.3`.
- `/api/ps`: no models loaded at observation time; this does not establish whether clients use the instance.
- Native systemd service `ollama`: active, running `/usr/local/bin/ollama serve`.
- Unit: `/etc/systemd/system/ollama.service`.
- Drop-in: `/etc/systemd/system/ollama.service.d/override.conf`; contents pending.

| Installed model | Quantization | Reported maximum context | Reported capabilities |
|---|---|---:|---|
| `qwen3:14b` | Q4_K_M | 40960 | completion, tools, thinking |
| `qwen3:8b` | Q4_K_M | 40960 | completion, tools, thinking |
| `qwen3.5:9b` | Q4_K_M | 262144 | vision, completion, tools, thinking |
| `qwen3.5:35b` | Q4_K_M | 262144 | vision, completion, tools, thinking |
| `nomic-embed-text:latest` | F16 | 2048 | embedding |
| `gemma2:9b` | Q4_0 | 8192 | completion |
| `qwen2.5-coder:7b` | Q4_K_M | 32768 | completion, tools, insert |
| `llama3.1:8b` | Q4_K_M | 131072 | completion, tools |
| `llama3.2:3b` | Q4_K_M | 131072 | completion, tools |

Reported maximum context is model metadata, not evidence of the effective runtime context setting or successful execution at that size. GPU offload and performance remain untested.

### `ollama2`

- Server version: `0.34.2`.
- Hostname-labelled `ollama list` supplied on 2026-10-02:

| Installed model | Model ID prefix | Reported disk size |
|---|---|---|
| `qwen3:14b` | `bdbd181c33f2` | 9.3 GB |
| `qwen3:8b` | `500a1f067a9f` | 5.2 GB |
| `llama3.2:3b` | `a80c4f17acd5` | 2.0 GB |

These IDs match models in the detailed `ollama01` API inventory, but `ollama2` runtime context, GPU offload, and inference performance have not been measured. Its service unit details and `/api/ps` response remain pending; the earlier duplicate output is not evidence for them.
