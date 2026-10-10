"""Stdio MCP wrapper on ollama2; only three fixed forced-command SSH reads."""
import json
from pathlib import Path
import subprocess
import sys

MODES = {"prometheus_scrape_status": "targets", "prometheus_probe_results": "probes", "prometheus_active_alerts": "alerts"}
TOOLS = [{"name": name, "description": f"Read fixed {mode} snapshot from PC3 Prometheus. No arbitrary queries, shell, mutation or raw configuration. Coverage is limited to configured monitoring.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}, "annotations": {"readOnlyHint": True, "destructiveHint": False}} for name, mode in MODES.items()]


def collect(name):
    if name not in MODES:
        raise ValueError("Unsupported tool")
    cmd = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10", "-i", str(Path.home() / ".ssh/skip-prometheus"), "wwbb-admin@192.168.0.183", MODES[name]]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=55)
    if len(result.stdout) > 2000000:
        raise ValueError("Response too large")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError("Unexpected output")
    return data


def dispatch(msg):
    method, params = msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        version = params.get("protocolVersion", "2024-11-05")
        if version not in ("2024-11-05", "2025-03-26", "2025-06-18"):
            version = "2025-06-18"
        return {"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": {"name": "skip-prometheus", "version": "1.0.0"}}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "ping":
        return {}
    if method == "tools/call":
        if params.get("name") not in MODES or params.get("arguments", {}) != {}:
            return {"isError": True, "content": [{"type": "text", "text": "Only fixed argument-free monitoring tools are allowed."}]}
        try:
            return {"content": [{"type": "text", "text": json.dumps(collect(params["name"]))}]}
        except Exception:
            return {"isError": True, "content": [{"type": "text", "text": "Monitoring collection failed. Check restricted SSH and PC3 API access; no health conclusion available."}]}
    raise ValueError("Unsupported method")


def main():
    if sys.argv[1:] == ["--check"]:
        for name in MODES:
            print(json.dumps(collect(name), indent=2))
        return
    for line in sys.stdin:
        msg = None
        try:
            msg = json.loads(line)
            if "id" not in msg:
                continue
            reply = {"jsonrpc": "2.0", "id": msg["id"], "result": dispatch(msg)}
        except Exception:
            reply = {"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) else None, "error": {"code": -32600, "message": "Unsupported request"}}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main()
