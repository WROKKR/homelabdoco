"""Add/update Skip's Home Assistant tool rules without changing identity, inventory or other rule blocks.

Run on ollama2 as the Hermes user. Backs up the previous prompt privately. Repeatable.
"""
import datetime
import json
import os
from pathlib import Path
import subprocess

START = "<!-- SKIP_HOMEASSISTANT_RULES_START -->"
END = "<!-- SKIP_HOMEASSISTANT_RULES_END -->"
RULES = """Home Assistant tools (read-only; they cannot control devices, run automations or change anything):
- home_status_now: solar generation today, home battery charge, current feed-in price, Backrest backup plans, and Frigate's last completed review.
- daily_totals_7d: solar generation per day for the last 7 days.
- recent_changes_24h: Frigate reviews in the last 24 hours.

Backups: for any backup question, call home_status_now. This live tool data supersedes the static backup notes in the inventory above. There are six Backrest plans: dockerhost26 to local, dockerhost26 to Wasabi, HexOS backups to Wasabi, Immich photos to Wasabi, restic appliance to local, restic appliance to Wasabi. Each has a last result and a last backup time. Quote each plan's display line, including hours ago, exactly; do not recalculate ages. Plan schedules are unknown, so report ages without calling a plan overdue unless WROKKR says what is expected. A success result means Backrest reported success; it does not prove the backup is restorable. Name any plan whose result is not success, or whose value is unavailable or not found.

Energy: quote display lines and units exactly; do not convert units or estimate values. In daily totals, today is partial and a null total means no data (unknown), not zero.

Frigate: review times are when the activity started. Object labels come from a general detector and can be wrong (a wallaby may be labelled dog). No review in 24 hours means none was recorded, not that nothing happened.

Unavailable or not-found sensors are unknown, not failed. If a Home Assistant tool call fails, say so; do not reuse older values as current. homelab_health_report does not include backups or energy; when WROKKR asks about these alongside overall health, also call home_status_now and add its results as a separate section."""


def merge(prompt, rules=RULES):
    if not prompt.startswith("You are Skip,"):
        raise ValueError("Expected Skip prompt not found")
    block = START + "\n" + rules + "\n" + END
    if START in prompt:
        start = prompt.index(START)
        if END not in prompt[start:]:
            raise ValueError("Incomplete Home Assistant rule block")
        finish = prompt.index(END, start) + len(END)
        return prompt[:start] + block + prompt[finish:]
    return prompt + "\n\n" + block


def main():
    result = subprocess.run(["hermes", "config", "get", "agent.system_prompt"], check=True, capture_output=True, text=True)
    prompt = result.stdout.strip()
    try:
        decoded = json.loads(prompt)
        if isinstance(decoded, str):
            prompt = decoded
    except json.JSONDecodeError:
        pass
    try:
        updated = merge(prompt)
    except ValueError as error:
        raise SystemExit(f"{error}; no changes made.")
    if updated == prompt:
        print("Home Assistant rules already current; no changes made.")
        return
    directory = Path.home() / ".config/skip-homeassistant"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = directory / ("prompt-before-ha-rules-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f") + ".txt")
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(prompt)
    subprocess.run(["hermes", "config", "set", "agent.system_prompt", json.dumps(updated)], check=True)
    print(f"Home Assistant rules saved. Previous prompt backed up to {backup}")
    print("Restart the Hermes gateway, then start a fresh Discord conversation to test.")


if __name__ == "__main__":
    main()
