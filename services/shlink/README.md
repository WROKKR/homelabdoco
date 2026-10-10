# Shlink URL shortener

Compose project for `dockerhost26` (`192.168.0.160`), installed at `/opt/shlink`.

| Container | Image | Host binding | Purpose |
|---|---|---|---|
| `shlink-shlink-1` | `shlinkio/shlink:5.1.6` | `192.168.0.160:8085` → 8080 | Redirects and REST API |
| `shlink-db-1` | `postgres:16-alpine` | Internal only | Database, data in `/opt/shlink/data/postgres` |
| `shlink-web-client-1` | `shlinkio/shlink-web-client:4.8.1` | `192.168.0.160:8086` → 8080 | LAN-only admin UI |

Secrets live only in `/opt/shlink/.env` (mode 600). The API key lives in the browser running the web client and in any password manager; never in this repo.

## Install

```bash
sudo ss -ltnp | grep -E ':(8085|8086)\b'      # expect no output; otherwise change ports in .env
sudo install -d -m 755 /opt/shlink
# copy compose.yaml and .env.example from this repo into /opt/shlink, then:
cd /opt/shlink
sudo cp .env.example .env && sudo chmod 600 .env
sudo sed -i "s|^DB_PASSWORD=.*|DB_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=')|" .env
sudo nano .env                                # set DEFAULT_DOMAIN and optional values
sudo docker compose config --quiet
sudo docker compose up -d
sudo docker compose logs --tail=50 shlink    # wait for migrations to finish
curl -s http://192.168.0.160:8085/rest/health
```

Create an API key (shown once; store it in your password manager):

```bash
sudo docker compose exec shlink shlink api-key:generate --name=web-client
```

Then open `http://192.168.0.160:8086`, add a server with URL `https://link.wwbb.dev` and the key.

## DNS and Nginx Proxy Manager

Short domain: `link.wwbb.dev`, public. `.dev` is HSTS-preloaded, so browsers only ever use HTTPS; a valid certificate is mandatory.

1. **Port forwards:** confirm the UDM forwards both TCP 80 and 443 to NPM on `192.168.0.160`. Port 80 is needed for Let's Encrypt HTTP-01 issuance and renewal.
2. **Public DNS:** at the `wwbb.dev` DNS provider, create `link` as an A record to the home WAN address (or a CNAME to an existing dynamic-DNS name if the WAN address changes).
3. **Split DNS:** in Technitium, create a zone for `link.wwbb.dev` (not all of `wwbb.dev`, unless it should be internal too) with an A record to `192.168.0.160`. LAN clients then reach NPM directly with their real source address, which the `/rest/` allow rule depends on; hairpin NAT through the UDM would not preserve it.
4. **NPM proxy host:** `link.wwbb.dev` → `http://192.168.0.160:8085`; request a Let's Encrypt certificate; enable Force SSL, HTTP/2 and HSTS. Leave "Block common exploits" on.
5. **Restrict the API.** In the proxy host's **Advanced** tab:

```nginx
location /rest/ {
    allow 192.168.0.0/24;
    deny all;
    proxy_pass http://192.168.0.160:8085;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Redirects stay public; link creation and statistics are LAN or Teleport only.

## Validation

- `curl -sI https://link.wwbb.dev/<short-code>` returns 302 to the long URL.
- Visits appear in the web client.
- From outside the LAN (phone on mobile data): a short link redirects and `https://link.wwbb.dev/rest/health` returns 403.
- `sudo docker compose restart` and a VM reboot leave all three containers running.

## Backup

Add a nightly logical dump to the backup staging tree (see `docs/backup-strategy.md`, Tier 1):

```bash
sudo docker compose -f /opt/shlink/compose.yaml exec -T db pg_dump -U shlink -d shlink | gzip > /var/lib/homelab-backup/databases/shlink.sql.gz
```

Restore test: load that dump into a disposable `postgres:16-alpine` container and check the `short_urls` table row count.

## Upgrade

Change the pinned tags in `compose.yaml`, read the Shlink release notes for the versions in between, take a dump, then `docker compose pull && docker compose up -d`. Shlink runs database migrations at startup.
