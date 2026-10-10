# Homelab project

This repository documents and manages the homelab.

## Authoritative context

- Read `docs/homelab-overview.md` for goals, architecture, hosts, and platforms.
- Read `docs/network-map.md` for networks, VLANs, DNS, ingress, and trust boundaries.
- Read `docs/services.md` for deployed services and their dependencies.
- Read `docs/operations.md` before deployment, maintenance, backup, or recovery work.
- Read `docs/edge-cluster.md` for the Turing Pi, Raspberry Pi, Kubernetes, monitoring, and exploratory Ceph context.
- Read `docs/monitoring.md` before changing or diagnosing Prometheus, Grafana, Alertmanager, or the blackbox exporter.
- Read `docs/frigate.md` before changing or diagnosing Frigate, its Reolink camera streams, RK3588 acceleration, or its TR4 storage.
- Read `docs/edge-cluster-troubleshooting.md` before diagnosing or changing the Turing Pi/K3s cluster.
- Read `docs/hermes.md` and `docs/skip-mcp.md` before changing Hermes/Skip, its MCP tools or its system prompt.
- Read `docs/tpi-cli-wsl-installation.md` when installing or troubleshooting the Turing Pi CLI from WSL.

## Git workflow

This repository is shared by several agents and machines through a private GitHub remote.

- Run `git pull --rebase` before starting work, and commit and push when a coherent change is done, so other agents see it.
- Keep commits focused, with messages that say what changed and why.
- Never commit secrets, live credential files, `.env` files or raw command dumps; `.gitignore` covers the common cases, but check `git status` before committing.
- Files are stored with LF line endings (`.gitattributes`) so scripts copied to Linux hosts run unchanged.

## Working agreements

- Never store, print, or commit passwords, tokens, private keys, recovery codes, or other secrets.
- Refer to secret locations and environment-variable names, not secret values.
- Inspect the relevant documentation and configuration before proposing changes.
- Ask for confirmation before destructive or service-disrupting operations.
- Prefer declarative, version-controlled configuration and repeatable commands.
- Validate changes with the documented checks.
- Update the relevant documentation when topology or operational behavior changes.
- Clearly distinguish observed state, documented state, and assumptions.

## Initial discovery

The homelab inventory is not documented yet. Ask focused questions and update the files under `docs/` as facts are established.
