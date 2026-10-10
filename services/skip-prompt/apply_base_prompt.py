"""Replace the base part of Skip's live prompt with base_prompt.txt, keeping every marked rule block.

Run on ollama2 as the Hermes user, with base_prompt.txt beside this script.
Default is a dry run that prints a diff; pass --apply to save (the previous prompt is backed up).
"""
import datetime
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys

MARKER = "<!-- SKIP_"


def merge(live, base):
    base = base.strip()
    if not base.startswith("You are Skip,") or MARKER in base:
        raise ValueError("base_prompt.txt must start with Skip's persona and contain no rule blocks")
    if not live.startswith("You are Skip,"):
        raise ValueError("Live prompt does not start with Skip's persona")
    index = live.find(MARKER)
    return base if index < 0 else base + "\n\n\n" + live[index:]


def read_live():
    result = subprocess.run(["hermes", "config", "get", "agent.system_prompt"], check=True, capture_output=True, text=True)
    prompt = result.stdout.strip()
    try:
        decoded = json.loads(prompt)
        if isinstance(decoded, str):
            return decoded
    except json.JSONDecodeError:
        pass
    return prompt


def main():
    if sys.argv[1:] not in ([], ["--apply"]):
        raise SystemExit("Usage: apply_base_prompt.py [--apply]")
    base = (Path(__file__).resolve().parent / "base_prompt.txt").read_text()
    live = read_live()
    try:
        updated = merge(live, base)
    except ValueError as error:
        raise SystemExit(f"{error}; no changes made.")
    if updated == live:
        print("Live base prompt already matches base_prompt.txt; no changes.")
        return
    sys.stdout.writelines(difflib.unified_diff(live.splitlines(True), updated.splitlines(True), "live", "updated"))
    print()
    if sys.argv[1:] != ["--apply"]:
        print("Dry run only. Review the diff, then re-run with --apply.")
        return
    directory = Path.home() / ".config/skip-prompt"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = directory / ("prompt-before-base-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f") + ".txt")
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(live)
    subprocess.run(["hermes", "config", "set", "agent.system_prompt", json.dumps(updated)], check=True)
    print(f"Base prompt saved; rule blocks kept. Previous prompt backed up to {backup}")
    print("Restart the Hermes gateway, then start a fresh Discord conversation.")


if __name__ == "__main__":
    main()
