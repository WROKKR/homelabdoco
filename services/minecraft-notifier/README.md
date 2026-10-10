# Minecraft log watcher → n8n → Discord

Prepared for friendsminecraft, vanilla Java 26.1.2 and 26.3 English server logs. Minecraft 26.3's `System chat:` prefix and retained login line are supported without duplicate join events.

The watcher posts join, leave, death, advancement/challenge/goal and solo public chat events. Chat is forwarded only when the reconstructed online set contains exactly the message's author. Private messages, console broadcasts, and ordinary chat with multiple players are ignored. Inform players that solo public chat is forwarded to Discord.

No Minecraft API credential or Docker socket is needed. Log access is read-only. English death patterns are generated from 101 Mojang 26.1.2 translation entries, including fall deaths. Regenerate with `python extract_templates.py` when changing the supported version (update its version first).

## n8n workflow

1. Add a Webhook trigger: POST, path `minecraft-events`, Header Auth.
2. Create a header credential named `X-Minecraft-Token` with value `Bearer YOUR_RANDOM_TOKEN`. Store only the token in the VM secret below. A dedicated header avoids authentication middleware or reverse proxies consuming the standard `Authorization` header. Use HTTPS when available; HTTP sends this token and event contents unencrypted on the LAN.
3. Set response mode to **When Last Node Finishes**. Do not acknowledge immediately: the watcher must receive an error if delivery fails. Do not enable Continue On Fail on the Discord delivery node.
4. Add an HTTP Request node to your Discord webhook, method POST, JSON body expression `{{ $json.body.discord }}`. Add query parameter `wait=true`. Keep the webhook URL private in n8n. This body explicitly disables mentions and link previews. Alternatively map the message into a Discord node, ensuring mentions remain disabled.
5. Activate/publish the workflow and use its **Production URL** in the VM configuration. n8n's test URL is only available while listening.
6. For retry deduplication, persist `body.event_id` in a database with a unique constraint and record successful sends. Stable IDs let you identify duplicate deliveries. The sample wiring alone does not implement deduplication.

Example event (values illustrative):

```json
{
  "schema_version": 1,
  "event_id": "installation-uuid:42",
  "server": "friendsminecraft-test",
  "type": "death",
  "message": "WROKKR drowned",
  "observed_at_unix": 1790000000,
  "solo_chat": false,
  "discord": {
    "content": "WROKKR drowned",
    "allowed_mentions": {"parse": []},
    "flags": 4
  }
}
```

Types: `join`, `leave`, `death`, `advancement`, `chat`. `observed_at_unix` is collection time, not a reconstructed historical Minecraft timestamp. The chat message identifies its author and marks them as playing solo.

## Install on the home VM

Copy this directory to `/opt/minecraft/notifier` (it is a separate Compose project and does not restart Minecraft).

```bash
sudo install -d -m 700 /opt/minecraft/secrets /srv/minecraft/notifier-state
sudo python3 -c "import getpass,json,os; from pathlib import Path; url=input('n8n production webhook URL: ').strip(); token=getpass.getpass('n8n header token (without Bearer prefix): '); path=Path('/opt/minecraft/secrets/webhook.json'); fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600); out=os.fdopen(fd,'w'); json.dump({'url':url,'token':token},out); out.close(); path.chmod(0o600)"
cd /opt/minecraft/notifier
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose logs --tail=30 -f
```

Never paste the secret file into chat or commit it. The root process inside this restricted container is needed to read the existing root-only secret; it has no Linux capabilities, a read-only root filesystem, and no host control socket. Its only writable bind is its state directory.

## Behaviour and limitations

- First launch scans existing latest.log for presence without sending historical notifications. Normal restart resumes at the committed offset. Position and queued event are committed in one SQLite transaction.
- Rotation recovers the unprocessed tail from a matching gzip archive, then follows the new latest.log. If the watcher is down across multiple Minecraft rotations, intervening logs are not replayed. If the prior archive has been removed, its unread tail cannot be recovered. An operational warning records unmatched rotation. Run continuously; this is not a full archival log ingester.
- Player count becomes authoritative after the normal server start/Done marker. If history is incomplete, solo chat remains suppressed until a new startup. Duplicate join/leave lines do not inflate the online set.
- A persistent FIFO queue retries transport failures and HTTP 429/5xx. 401/403/404 retain events for retry after credential/workflow repair. Other 4xx retain a dead-letter row for inspection; they are not discarded. Queue growth must be monitored during long outages.
- Delivery is at-least-once: a connection failure after successful Discord posting can cause a duplicate on retry. Discord does not provide an idempotency key for incoming webhooks. A stable event ID supports n8n-side deduplication but cannot eliminate every ambiguous-send case.
- Minecraft only supplies log events it announces. Disabled death/advancement announcements, non-English messages, custom plugins or altered log formats need corresponding adjustments. Unknown lines are ignored, not guessed to be deaths.
- All test activity and watcher state are disposable. Before final world replacement, stop this notifier, archive its state directory, and start with a new empty state directory to avoid mixing histories. Keep the cloud server migration separate.

## Validation

Run `python -m unittest -v` in this directory. Tests cover solo/multiplayer transitions, unknown presence, common deaths, all advancement categories, chat/console spoof avoidance, partial writes, restart deduplication, gzip rotation, HTTP rate-limit retries, unique event IDs and mention suppression. These tests use mocks and send nothing to Discord.

After deployment, test joins/leaves and solo chat, then a second online player suppressing chat. Check n8n executions and the Discord channel. Test retry recovery by temporarily stopping the workflow and confirming queued events arrive when it is reactivated. Stop the watcher using `sudo docker compose stop` from this directory.
