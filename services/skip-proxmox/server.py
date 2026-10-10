"""Fixed read-only Proxmox status tools over local stdio MCP."""
import datetime
import json
import ssl
import sys
import urllib.request
from pathlib import Path

DIRECTORY = Path.home() / ".config/skip-proxmox"
BASE = "https://192.168.0.50:8006/api2/json/nodes/Yggdrasil"
ROUTES = {
    "yggdrasil_host_status": ("/status", None, "Yggdrasil"),
    "homeassistant_vm_status": ("/qemu/116/status/current", 116, "Home Assistant"),
    "ollama2_vm_status": ("/qemu/118/status/current", 118, "ollama2"),
}
TOOLS = [{
    "name": name,
    "description": f"Read selected Proxmox metrics for {label} only. VM running state does not establish application, automation or backup health. No configuration, logs, credentials or management actions.",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
} for name, (_, _, label) in ROUTES.items()]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def metrics(data, keys):
    return {k: number(data.get(k)) for k in keys}


def gib(value):
    value = number(value)
    return round(value / 1024**3, 2) if value is not None else None


def percentage(used, total):
    used, total = number(used), number(total)
    return round(100 * used / total, 2) if used is not None and total and total > 0 else None


def project(data, name):
    if not isinstance(data, dict) or name not in ROUTES:
        raise ValueError("Unexpected response or tool")
    _, vmid, label = ROUTES[name]
    result = {
        "collected_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "Proxmox", "node": "Yggdrasil", "resource": label,
        "scope": "Selected host/VM metrics only. No application, automation, storage-pool or backup validation. Missing values are unknown.",
        "cpu_fraction": number(data.get("cpu")),
        "cpu_percent": round(100 * data["cpu"], 2) if number(data.get("cpu")) is not None else None,
        "uptime_seconds": number(data.get("uptime")),
    }
    if vmid is None:
        for key in ("memory", "rootfs"):
            value = data.get(key)
            result[key + "_bytes"] = metrics(value, ("total", "used", "free", "available")) if isinstance(value, dict) else None
            result[key + "_gib"] = {k: gib(value.get(k)) for k in ("total", "used", "free", "available")} if isinstance(value, dict) else None
            result[key + "_used_percent"] = percentage(value.get("used"), value.get("total")) if isinstance(value, dict) else None
        result["logical_cpus"] = number(data.get("cpuinfo", {}).get("cpus")) if isinstance(data.get("cpuinfo"), dict) else None
        result["note"] = "Root filesystem metrics are not total capacity of all Proxmox datastores; CPU is a 0–1 fraction."
    else:
        result.update({"vmid": vmid, "memory_bytes": metrics(data, ("mem", "maxmem")), "vcpus": number(data.get("cpus"))})
        result["configured_memory_gib"] = gib(data.get("maxmem"))
        result["proxmox_reported_memory_gib"] = gib(data.get("mem"))
        result["state"] = data.get("status") if data.get("status") in ("running", "stopped", "paused") else "unknown"
        result["note"] = "CPU percentage is Proxmox's normalized VM metric. maxmem is configured memory. mem is Proxmox-reported VM memory usage, not proof of guest OS allocation, available memory, or memory pressure. Quote pre-calculated fields without unit conversion."
    return result


def collect(name):
    if name not in ROUTES:
        raise ValueError("Tool not allowed")
    token = json.loads((DIRECTORY / "token.json").read_text())
    context = ssl.create_default_context(cafile=str(DIRECTORY / "pve-root-ca.pem"))
    request = urllib.request.Request(BASE + ROUTES[name][0], method="GET", headers={
        "Accept": "application/json",
        "Authorization": f"PVEAPIToken={token['id']}={token['secret']}",
    })
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect, urllib.request.HTTPSHandler(context=context))
    with opener.open(request, timeout=15) as response:
        raw = response.read(200001)
    if len(raw) > 200000:
        raise ValueError("Response too large")
    return project(json.loads(raw)["data"], name)


def dispatch(message):
    method, params = message.get("method"), message.get("params") or {}
    if method == "initialize":
        version = params.get("protocolVersion", "2024-11-05")
        if version not in ("2024-11-05", "2025-03-26", "2025-06-18"):
            version = "2025-06-18"
        return {"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": {"name": "skip-proxmox-status", "version": "1.0.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        if params.get("name") not in ROUTES or params.get("arguments", {}) != {}:
            return {"isError": True, "content": [{"type": "text", "text": "Only fixed status tools without arguments are allowed."}]}
        try:
            return {"content": [{"type": "text", "text": json.dumps(collect(params["name"]))}]}
        except Exception:
            return {"isError": True, "content": [{"type": "text", "text": "Proxmox collection failed; verify credentials, TLS, permissions and endpoint manually. No health conclusion available. Raw errors withheld."}]}
    raise ValueError("Unsupported method")


def main():
    for line in sys.stdin:
        message = None
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("Invalid request")
            if "id" not in message:
                continue
            reply = {"jsonrpc": "2.0", "id": message["id"], "result": dispatch(message)}
        except Exception:
            reply = {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None, "error": {"code": -32600, "message": "Invalid or unsupported request"}}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        failed = False
        for name in ROUTES:
            try:
                print(json.dumps(collect(name), indent=2))
            except Exception:
                failed = True
                print(f"{name}: collection failed; check TLS, credentials, permissions and API shape. Raw response withheld.", file=sys.stderr)
        sys.exit(1 if failed else 0)
    elif sys.argv[1:]:
        sys.exit("Unsupported arguments")
    else:
        main()
