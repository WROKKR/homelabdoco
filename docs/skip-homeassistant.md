# Home Assistant visibility for Skip

Prepared on 2026-10-03. The user reported installing it on `ollama2` at about 19:14 Brisbane time on 2026-10-03, using `services/skip-homeassistant/install.sh`. `--check` output and Hermes registration have not been reviewed here. On 2026-10-04 the user reported Skip did not know backup status lives in these tools; the prompt rules below address that. See [`skip-mcp.md`](skip-mcp.md) for all of Skip's tools. Gives Skip read-only access to a small allowlist of Home Assistant sensors: solar generation, home battery charge, current feed-in price, last result and last backup time for each of the six Backrest plans, and Frigate's last completed review (once the HA sensor below exists).

## Design

Home Assistant is the hub: solar (GoSungrow), Mosquitto/Zigbee2MQTT and Backrest data already arrive there as entities, so one bridge covers them. Skip receives no MQTT broker credential and no Backrest login.

[`../services/skip-homeassistant/server.py`](../services/skip-homeassistant/server.py) is a local stdio MCP launched by Hermes on `ollama2`, matching the Proxmox and Dockhand bridges. It opens no listener and only sends GET requests to fixed `/api/` paths on `http://192.168.0.161:8123`, with redirects and proxies disabled and response sizes bounded.

| Tool | Returns |
|---|---|
| `home_status_now` | Each allowlisted sensor's label, value, unit, a pre-formatted `display` line, last reported time and "value unchanged since" (Brisbane time) |
| `daily_totals_7d` | For entries marked `daily_total`: highest reading per Brisbane date for the last 7 days. Today is partial; missing days are unknown, not zero |
| `recent_changes_24h` | For entries marked `recent_changes`: value changes in the last 24 hours with Brisbane times, at most 30 per sensor, with a count of older ones omitted |

Sensors with HA device class `timestamp` (such as Backrest `..._last_backup`) are shown as a Brisbane time plus a calculated `hours_ago`, so Skip quotes the age instead of computing it.

All tools take no arguments. Entities come only from `~/.config/skip-homeassistant/entities.json`; entries are validated (`sensor.`/`binary_sensor.` only, fixed categories, at most 40). Attributes are dropped unless listed per entity, and HA's friendly names are not passed through.

**Home Assistant tokens cannot be read-only.** The bridge code is the read-only boundary. The token could still control devices if used another way, which is why Skip's terminal and file tools must stay disabled and the token must stay on `ollama2` only.

## Known limitations

- Each Backrest plan has two entries: `..._last_backup_status` (last result) and `..._last_backup` (timestamp, shown with `hours_ago`). The status sensor's "value unchanged since" is not the last backup time; use the timestamp entry for staleness. The `wasabi_restic_appliance` status entity ID follows the naming pattern but was not confirmed; `--check` shows "entity not found" if it differs.
- A backup status is what Backrest reported; it does not prove the snapshot is restorable.
- Daily totals assume the GoSungrow sensor resets at local midnight. Verify against the Sungrow app for one or two days.
- HA is reached over plain HTTP, so the token crosses the LAN unencrypted (same as other LAN clients of 8123).
- Whether a non-admin user's token can read `/api/history` should be confirmed by `--check`.

## Setup

1. In Home Assistant, **Settings → People → Users → Add user** `skip-readonly`. Leave **Administrator** off. Optionally enable "Can only log in from the local network".
2. Log in as that user, open **Profile → Security → Long-lived access tokens**, create a token named `skip-hermes`. Do not paste it into chat or Git.
3. On `ollama2`:

```bash
install -d -m 700 ~/.config/skip-homeassistant
python3 -c "import getpass,json,os; p=os.path.expanduser('~/.config/skip-homeassistant/token.json'); fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600); f=os.fdopen(fd,'w'); json.dump({'token':getpass.getpass('HA token: ')},f); f.close()"
```

4. From Windows PowerShell:

```powershell
scp C:\Users\WROKKR\Documents\Codex\homelab\services\skip-homeassistant\server.py wwbb-admin@192.168.0.167:skip-homeassistant.py
scp C:\Users\WROKKR\Documents\Codex\homelab\services\skip-homeassistant\entities.example.json wwbb-admin@192.168.0.167:.config/skip-homeassistant/entities.json
```

5. On `ollama2`, validate before registering:

```bash
chmod 600 ~/.config/skip-homeassistant/entities.json
python3 ~/skip-homeassistant.py --attributes   # attribute NAMES only, no values
python3 ~/skip-homeassistant.py --check        # both tools' exact output
```

If `--attributes` shows a useful non-secret field on the Backrest sensors (for example a last-run time), add it to that entry's `"attributes"` list in `entities.json` and re-run `--check`.

6. Register with Hermes, then restart the gateway (see [Restarting the gateway](#restarting-the-gateway)):

```bash
hermes mcp add homeassistant_status --command python3 --args /home/wwbb-admin/skip-homeassistant.py
```

## System prompt rules

Skip needs to know which questions these tools answer. [`../services/skip-homeassistant/update_prompt.py`](../services/skip-homeassistant/update_prompt.py) appends a marked `SKIP_HOMEASSISTANT_RULES` block to Hermes's `agent.system_prompt`, leaving the persona, inventory and reporting-rule block unchanged. It is repeatable (re-running replaces only its own block), refuses to run if the prompt does not start with Skip's persona, and backs up the previous prompt to `~/.config/skip-homeassistant/`.

The block tells Skip to use `home_status_now` for backup questions (superseding the static backup notes in the inventory), names the six plans, has it quote display lines and ages exactly, not call a plan overdue without a known schedule, treat `success` as reported rather than proven restorable, and add a separate backup/energy section when asked alongside the overall health report. It also covers energy units, partial days, and Frigate label limitations.

```powershell
scp C:\Users\WROKKR\Documents\Codex\homelab\services\skip-homeassistant\update_prompt.py wwbb-admin@192.168.0.167:skip-ha-update-prompt.py
```

```bash
python3 ~/skip-ha-update-prompt.py
```

Restart the Hermes gateway and test in a fresh Discord conversation.

## Restarting the gateway

How the gateway runs on `ollama2` has not been recorded. Per the Hermes docs: `hermes gateway status` shows whether it is an installed service; if so, `hermes gateway stop` then `hermes gateway start` (add `--system` to status if installed as a system service), and logs are in `journalctl --user -u hermes-gateway`. If it was started in the foreground with `hermes gateway` (for example in tmux or screen), stop it with Ctrl-C and start it again. Record which applies here once confirmed.

## Validation

- `--check` values match HA's **Developer Tools → States** for each entity.
- Ask "How are the backups?" without naming any tool. Skip should call `home_status_now` and list all six plans with result and age, without inventing schedules or calling them verified.
- In a fresh Discord conversation: "What did the solar generate today, and what's the status of each backup plan? Quote the tool output." Check labels, values and units are unchanged and nothing is added.
- "Show solar for the last 7 days." Compare two or three days with the Sungrow app.
- Ask Skip to turn something on. It must say it cannot; confirm in HA's logbook that nothing happened.

## Adding sensors

Add an entry to `~/.config/skip-homeassistant/entities.json` (and to `entities.example.json` here, without secrets). No code change or re-registration is needed; new values appear on the next tool call. Prefer pre-calculated HA sensors (Utility Meter daily totals, template sensors) over raw readings so Skip quotes numbers rather than calculating them.

## Minecraft and Frigate (MQTT events)

Both publish events over MQTT to the Home Assistant Mosquitto broker. Skip sees them through HA entities, not by subscribing to the broker: HA Mosquitto users have no topic ACLs, and raw MQTT is an unfiltered stream. As of 2026-10-03 neither has HA entities and the Frigate integration is not installed.

### Frigate

[`../services/skip-homeassistant/homeassistant-frigate.yaml`](../services/skip-homeassistant/homeassistant-frigate.yaml) defines a trigger-based template sensor `sensor.frigate_last_review` from Frigate's `frigate/reviews` topic. It updates only when a review ends, with a state such as `10:00 front_yard: person, dog (alert)`. The start time is part of the state so consecutive similar reviews still appear as separate changes in `recent_changes_24h`.

1. Merge the `template:` block into Home Assistant's `configuration.yaml` (File editor or Studio Code Server add-on).
2. **Developer Tools → YAML → Check configuration**, then reload **Template entities**.
3. After the next detection, confirm the sensor in **Developer Tools → States**.

Assumes the default `frigate` topic prefix and that Frigate is publishing to this broker. No snapshot, clip or Frigate URL is passed to Skip.

### Minecraft

Pending: the topic(s) and a sample payload the notifier path publishes. Then define HA MQTT sensors (for example "last event" and "players online") and add them with `"category": "minecraft", "recent_changes": true`. Keep player chat out of the event sensor unless deliberately wanted.

`recent_changes_24h` only sees changes HA's recorder kept; identical consecutive values appear once.
