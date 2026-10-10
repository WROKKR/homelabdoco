"""Poll fixed collectors; notify only confirmed status changes, without LLM calls."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from importlib.util import module_from_spec, spec_from_file_location

STATE = Path.home() / ".config/skip-proxmox/change-monitor.json"


def load(filename):
    spec = spec_from_file_location(filename.replace("-", "_"), Path.home() / filename)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(docker, proxmox, previous):
    values = {}
    for env_id, label in docker.ENVIRONMENTS.items():
        prefix = label + "/"
        try:
            data = docker.collect(env_id)
            values[prefix + "collection"] = "available"
            for row in data["containers"]:
                names = ", ".join(n for n in row["names"] if n) or "unknown name"
                text = row["status"] or ""
                health = "unhealthy" if "(unhealthy)" in text else "healthy" if "(healthy)" in text else "starting" if "(health: starting)" in text else "not reported"
                values[prefix + names] = f"state={row['state'] or 'unknown'}, health={health}"
        except Exception:
            # Failure to collect is not evidence that containers disappeared.
            values.update({k: v for k, v in previous.items() if k.startswith(prefix)})
            values[prefix + "collection"] = "failed"
    for tool in proxmox.ROUTES:
        prefix = "Proxmox/" + proxmox.ROUTES[tool][2] + "/"
        try:
            data = proxmox.collect(tool)
            values[prefix + "collection"] = "available"
            if "state" in data:
                values[prefix + "VM state"] = data["state"]
        except Exception:
            values.update({k: v for k, v in previous.items() if k.startswith(prefix)})
            values[prefix + "collection"] = "failed"
    return values


def transitions(baseline, current, pending):
    next_pending, confirmed = {}, []
    for key in sorted(set(baseline) | set(current)):
        before, after = baseline.get(key, "absent"), current.get(key, "absent")
        if before == after:
            continue
        old = pending.get(key, {})
        count = old.get("count", 0) + 1 if old.get("value") == after else 1
        next_pending[key] = {"value": after, "count": count}
        if count >= 2:
            confirmed.append((key, before, after))
    return next_pending, confirmed


def save(data):
    temp = STATE.with_suffix(".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(data, handle)
    os.replace(temp, STATE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="Explicit Discord delivery target, e.g. discord:CHANNEL_ID")
    parser.add_argument("--hermes", default=shutil.which("hermes"))
    parser.add_argument("--dry-run", action="store_true", help="Collect and preview; never send or modify baseline")
    args = parser.parse_args()
    if not args.target.startswith("discord:") or not args.target[8:].isdigit():
        raise SystemExit("Use an explicit numeric Discord channel target.")
    if not args.hermes:
        raise SystemExit("Hermes executable not found; use --hermes /absolute/path.")
    STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(STATE.with_suffix(".lock"), "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        stored = json.loads(STATE.read_text()) if STATE.exists() else None
        if stored and stored.get("target") != args.target:
            raise SystemExit("Target changed; preserve or reset baseline manually before proceeding.")
        baseline = stored["baseline"] if stored else {}
        current = snapshot(load("skip-dockhand.py"), load("skip-proxmox.py"), baseline)
        if args.dry_run:
            print(json.dumps({"current": current, "changes": transitions(baseline, current, stored.get("pending", {}) if stored else {})[1] if stored else [], "baseline_exists": stored is not None}, indent=2))
            return
        if stored is None:
            save({"target": args.target, "baseline": current, "pending": {}})
            print("Silent baseline established.")
            return
        pending, confirmed = transitions(baseline, current, stored.get("pending", {}))
        if confirmed:
            stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=10))).isoformat(timespec="minutes")
            lines = [f"Skip status changes — {stamp}", "Confirmed on two consecutive polls:"]
            lines += [f"- {key}: {before} → {after}" for key, before, after in confirmed]
            lines.append("Container/VM status only; failed collection is not proof of an outage. No changes made.")
            # Keep each message below Discord's limit. Retry unacknowledged changes next poll.
            chunks, chunk = [], ""
            for line in lines:
                if len(chunk) + len(line) + 1 > 1800:
                    chunks.append(chunk)
                    chunk = ""
                chunk += line + "\n"
            if chunk:
                chunks.append(chunk)
            for chunk in chunks:
                result = subprocess.run([args.hermes, "send", "--to", args.target, "--file", "-"], input=chunk, text=True, capture_output=True, timeout=120)
                if result.returncode:
                    save({"target": args.target, "baseline": baseline, "pending": pending})
                    raise SystemExit("Delivery failed; changes retained for retry. Credential-bearing output withheld.")
            for key, _, after in confirmed:
                if after == "absent":
                    baseline.pop(key, None)
                else:
                    baseline[key] = after
                pending.pop(key, None)
        save({"target": args.target, "baseline": baseline, "pending": pending})
        print(f"Confirmed changes delivered: {len(confirmed)}; unchanged state remains silent.")


if __name__ == "__main__":
    main()
