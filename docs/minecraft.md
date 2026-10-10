# Minecraft migration and notifications

## Confirmed from user-provided output

- Cloud source: `minecraft@minecraft.whitewolfbrownbear.com:/home/minecraft`, vanilla 26.1.2, approximately 3.3 GiB total. World `whitewolfbrownbear`, survival/easy, authenticated users and enforced whitelist, maximum 20 players.
- Home test host: `friendsminecraft`, Debian 13, `192.168.0.171`, approximately 16 GiB RAM. VM ID has not been confirmed.
- System disk: 32 GiB. Separate 100 GiB ext4 virtual disk mounted by UUID at `/srv/minecraft`.
- Docker and Compose installed; Docker service has `RequiresMountsFor=/srv/minecraft` and `ConditionPathIsMountPoint=/srv/minecraft` override.
- Compose project `/opt/minecraft`: `itzg/minecraft-server:java25`, vanilla version pinned to 26.1.2, 3–7 GiB heap, data mounted from `/srv/minecraft/data`. Current deployment is a disposable live-copy test, not a completed migration.
- Imported staging copy: `/srv/minecraft/import`. Version 26.1.2 uses `dimensions/minecraft/{overworld,the_nether,the_end}` and `players/{stats,advancements,data}` below the world.
- Management protocol schema reports 2.0.0, with no advertised death or advancement notifications. Private container-loopback API tested successfully for join/leave. Its secret is only on the VM; never record it here.

## Notification implementation — prepared, not deployed

See [watcher deployment instructions](../services/minecraft-notifier/README.md). The agreed direction is log events → authenticated n8n webhook → Discord. Joins, leaves, deaths, advancements/challenges/goals and public chat when exactly one player is online are in scope. Player-count reconstruction uses logs; notifier needs no management credential. n8n already runs on dockerhost26; the actual webhook URL and credential remain to be configured privately.

Local unit tests pass. Container startup, actual n8n workflow, and end-to-end Discord delivery remain unverified. New Minecraft backups and a restore test are still pending; the existing NAS read/checksum instability documented in operations has not been resolved. Cloud cutover/DNS/ingress and a clean final world sync have not occurred.
