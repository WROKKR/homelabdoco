"""Deterministic report from existing restricted collectors; no inference."""
import datetime
import importlib.util
import json
from pathlib import Path
import sys


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path.home() / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report(docker, proxmox):
    lines = ["Homelab status — " + datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=10))).isoformat(timespec="seconds"), "Source: Dockhand and Proxmox API observations."]
    for env_id in (1, 2):
        try:
            result = docker.collect(env_id)
            rows = result["containers"]
            running = sum(r["state"] == "running" for r in rows)
            healthy = sum("(healthy)" in (r["status"] or "") for r in rows)
            unhealthy = [r for r in rows if "(unhealthy)" in (r["status"] or "")]
            starting = sum("(health: starting)" in (r["status"] or "") for r in rows)
            missing = len(rows) - healthy - len(unhealthy) - starting
            lines.append(f"\n{result['host']}: {running}/{len(rows)} containers running; health reported healthy={healthy}, unhealthy={len(unhealthy)}, starting={starting}, not reported={missing}.")
            for row in rows:
                names = ", ".join(n for n in row["names"] if n) or "unknown name"
                if row["state"] != "running" or row in unhealthy or any(n in ("homepage", "homepage-dockerproxy", "minecraft-minecraft-1", "minecraft-notifier-notifier-1") for n in row["names"]):
                    lines.append(f"- {names}: state={row['state'] or 'unknown'}; status={row['status'] or 'not reported'}")
        except Exception:
            lines.append(f"\n{docker.ENVIRONMENTS[env_id]}: collection failed; current status unknown.")
    for name in proxmox.ROUTES:
        try:
            data = proxmox.collect(name)
            if name == "yggdrasil_host_status":
                mem = data["memory_gib"] or {}
                lines.append(f"\nYggdrasil: CPU={data['cpu_percent']}%; RAM used={mem.get('used')} / {mem.get('total')} GiB; root FS used={data['rootfs_used_percent']}% (not all datastores).")
            else:
                lines.append(f"{data['resource']} VM {data['vmid']}: state={data['state']}; CPU={data['cpu_percent']}%; configured RAM={data['configured_memory_gib']} GiB; Proxmox-reported RAM usage={data['proxmox_reported_memory_gib']} GiB.")
        except Exception:
            lines.append(f"{proxmox.ROUTES[name][2]}: collection failed; current status unknown.")
    lines.extend(["\nLimits: running is not application health. Unreported health is not a failure. CPU is sampled; load cause and guest memory pressure are unknown. Skip's own inference may affect ollama2 load.", "Untested: Homepage widgets, Home Assistant automations, application/client availability, backups and other Proxmox datastores. No restart recommendation or changes made."])
    return "\n".join(lines)


def main():
    docker = load("skip_docker_collector", "skip-dockhand.py")
    proxmox = load("skip_proxmox_collector", "skip-proxmox.py")
    if sys.argv[1:] == ["--check"]:
        print(report(docker, proxmox))
        return
    if sys.argv[1:]:
        raise SystemExit("Unsupported arguments")
    tool = {"name": "homelab_health_report", "description": "Collect both Dockhand and three Proxmox status checks and return a deterministic report. Quote it verbatim; do not invent names, causes or actions.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}, "annotations": {"readOnlyHint": True, "destructiveHint": False}}
    for line in sys.stdin:
        msg = None
        try:
            msg = json.loads(line)
            if "id" not in msg:
                continue
            method, params = msg.get("method"), msg.get("params") or {}
            if method == "initialize":
                version = params.get("protocolVersion", "2024-11-05")
                if version not in ("2024-11-05", "2025-03-26", "2025-06-18"):
                    version = "2025-06-18"
                result = {"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": {"name": "skip-homelab-report", "version": "1.0.0"}}
            elif method == "tools/list":
                result = {"tools": [tool]}
            elif method == "ping":
                result = {}
            elif method == "tools/call" and params.get("name") == tool["name"] and params.get("arguments", {}) == {}:
                result = {"content": [{"type": "text", "text": report(docker, proxmox)}]}
            else:
                raise ValueError("Unsupported request")
            reply = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        except Exception:
            reply = {"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) else None, "error": {"code": -32600, "message": "Unsupported or invalid request"}}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main()
