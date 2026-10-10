"""Run on PC3; fixed Prometheus reads. Supports a forced-command SSH key."""
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = "http://10.43.239.132:9090/api/v1/"
MODES = ("targets", "probes", "alerts")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get(path):
    with urllib.request.build_opener(NoRedirect, urllib.request.ProxyHandler({})).open(BASE + path, timeout=15) as response:
        raw = response.read(2000001)
    if len(raw) > 2000000:
        raise ValueError("Response too large")
    data = json.loads(raw)
    if data.get("status") != "success":
        raise ValueError("Prometheus query failed")
    return data["data"]


def labels(value):
    allowed = ("job", "instance", "target", "namespace", "service", "endpoint", "alertname", "severity")
    return {key: "".join(c for c in value[key] if c.isprintable())[:256] for key in allowed if isinstance(value.get(key), str)}


def collect(mode):
    if mode not in MODES:
        raise ValueError("Unsupported mode")
    result = {"collected_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "source": "Prometheus on PC3", "scope": "Existing Prometheus coverage only; absent metrics do not establish healthy systems."}
    if mode == "targets":
        data = get("targets?state=active")
        result["targets"] = [{"labels": labels(t.get("labels", {})), "scrape_health": t.get("health") if t.get("health") in ("up", "down", "unknown") else "unknown", "last_scrape": t.get("lastScrape")} for t in data.get("activeTargets", [])]
        result["note"] = "Scrape health is not blackbox probe success. Repeated jobs may represent different endpoints."
    elif mode == "alerts":
        data = get("alerts")
        result["alerts"] = [{"labels": labels(a.get("labels", {})), "state": a.get("state") if a.get("state") in ("pending", "firing", "inactive") else "unknown", "active_at": a.get("activeAt"), "expected_heartbeat": a.get("labels", {}).get("alertname") == "Watchdog"} for a in data.get("alerts", [])]
        result["note"] = "Watchdog is an expected heartbeat, not an outage. Empty active alerts do not establish complete monitoring coverage. Alertmanager delivery not checked."
    else:
        result["probe_metrics"] = {}
        for query in ("probe_success", "probe_http_status_code"):
            data = get("query?" + urllib.parse.urlencode({"query": query}))
            if data.get("resultType") != "vector":
                raise ValueError("Unexpected result type")
            result["probe_metrics"][query] = [{"labels": labels(row.get("metric", {})), "sample_epoch": row["value"][0], "value": float(row["value"][1])} for row in data.get("result", [])]
        result["note"] = "probe_success 1 means configured probe succeeded; 0 means it failed. Match labels and sample time. HTTPS :443 is not Homepage :3001. No result is unknown coverage, not success."
    return result


def main():
    if sys.argv[1:] == ["--ssh"]:
        # Original SSH command is a single mode token, never executed as a shell command.
        mode = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    elif len(sys.argv) == 2:
        mode = sys.argv[1]
    else:
        raise SystemExit("Use targets, probes or alerts.")
    if mode not in MODES:
        raise SystemExit("Unsupported request; no command executed.")
    try:
        print(json.dumps(collect(mode)))
    except Exception:
        raise SystemExit("Prometheus collection failed; raw response withheld.")


if __name__ == "__main__":
    main()
