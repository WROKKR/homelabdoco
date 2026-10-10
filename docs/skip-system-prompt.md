# Skip system prompt

Skip's prompt is Hermes's `agent.system_prompt` on `ollama2`. It has a **base** (persona, priorities, homelab inventory) followed by **marked rule blocks**, each managed by its own script. The repo files below are the source of truth; edit them, then apply.

| Part | Source of truth | Applied with |
|---|---|---|
| Base | [`../services/skip-prompt/base_prompt.txt`](../services/skip-prompt/base_prompt.txt) | `services/skip-prompt/apply_base_prompt.py` (replaces only the text before the first `<!-- SKIP_` marker) |
| `SKIP_REPORTING_RULES` block | `services/skip-proxmox/update_reporting_prompt.py` | That script |
| `SKIP_HOMEASSISTANT_RULES` block | `services/skip-homeassistant/update_prompt.py` | That script |

All three scripts refuse to run unless the prompt starts with `You are Skip,`, are repeatable, and back up the previous prompt under `~/.config/` on `ollama2`.

## Live state

Captured from `ollama2` on 2026-10-04 at about 13:05 Brisbane time: [`skip-prompt-live.txt`](skip-prompt-live.txt), about 1,000 words.

- Both rule blocks were live.
- The base was the 2026-10-03 version with the refined wallaby personality. The later edit to this doc (availability priorities naming dockerhost26, Home Assistant, Yggdrasil, Urdarbrunnr and Mimisbrunnr; Homepage as lower priority) had **not** been applied, and that doc version lacked the personality refinement.
- `base_prompt.txt` merges the two: live personality and guidance, the new priorities, Urdarbrunnr and Mimisbrunnr, the fuller dockerhost26 application list, a note that Skip's tools are read-only and listed in the rule blocks, and backup text that defers to the Home Assistant tools instead of saying Wasabi uploads are unconfigured.
- Applying the merged base is pending. Re-capture after applying and replace the snapshot.

## Applying the base

From Windows PowerShell:

```powershell
scp C:\Users\WROKKR\Documents\Codex\homelab\services\skip-prompt\apply_base_prompt.py C:\Users\WROKKR\Documents\Codex\homelab\services\skip-prompt\base_prompt.txt wwbb-admin@192.168.0.167:
```

On `ollama2`:

```bash
python3 ~/apply_base_prompt.py           # dry run: shows the diff, changes nothing
python3 ~/apply_base_prompt.py --apply   # saves; rule blocks kept verbatim
```

Then restart the Hermes gateway (see [`skip-homeassistant.md`](skip-homeassistant.md#restarting-the-gateway)) and start a fresh Discord conversation. Check that Skip names Mimisbrunnr and Urdarbrunnr when asked about priorities, answers "I'm a wallaby" when asked what it is, and still uses its tools for health and backup questions.

## Capturing the live prompt

```bash
hermes config get agent.system_prompt | python3 -c "import json,sys; t=sys.stdin.read().strip(); print(json.loads(t) if t.startswith('\"') else t)" > ~/skip-prompt-live.txt
```

Copy it to `docs/skip-prompt-live.txt`. It should contain no secrets, but check before committing.
