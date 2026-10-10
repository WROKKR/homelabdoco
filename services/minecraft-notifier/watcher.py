"""Vanilla English Minecraft logs -> durable Discord webhook queue (stdlib only)."""
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

LOG = logging.getLogger('minecraft-notifier')
LINE = re.compile(r'^\[\d{2}:\d{2}:\d{2}\] \[(?:Server thread|Async Chat Thread[^/]*)/INFO\]: (.*)$')
PLAYER = r'[A-Za-z0-9_]{1,16}'

def death_patterns(templates):
    patterns = []
    for text in templates.values():
        if not text.startswith('%1$s '):
            continue
        parts = re.split(r'(%\d+\$s)', text)
        patterns.append(re.compile(''.join(
            f'(?P<player>{PLAYER})' if p == '%1$s' else '.+?' if re.fullmatch(r'%\d+\$s', p)
            else re.escape(p) for p in parts)))
    return patterns

def parse(line, state, patterns):
    match = LINE.fullmatch(line.rstrip('\r\n'))
    if not match:
        return None
    text = match[1]
    # Minecraft 26.3 prefixes game-generated chat announcements, including
    # joins, leaves, advancements, and deaths, with "System chat: ". Keep
    # player chat on the unmodified text so a system announcement cannot be
    # mistaken for player-authored public chat.
    system_text = text.removeprefix('System chat: ')
    players = set(state['players'])
    if text.startswith('Starting minecraft server version ') or text.startswith('Done ('):
        players.clear()
        state['known'] = True
    elif text == 'Stopping server':
        players.clear()
        state['known'] = False
    else:
        # The login line remains present in 26.3 and precedes the system-chat
        # join announcement. Treat it as the authoritative join and suppress
        # the later announcement when the player is already known.
        login = re.fullmatch(r'(' + PLAYER + r')\[.*] logged in with entity id \d+ at \(.+\)', text)
        if login:
            player = login[1]
            if player in players:
                return None
            players.add(player)
            state['players'] = sorted(players)
            return 'join', f'{player} joined the game'
        for suffix, kind in [(' joined the game', 'join'), (' left the game', 'leave')]:
            if system_text.endswith(suffix) and re.fullmatch(PLAYER, system_text[:-len(suffix)]):
                player = system_text[:-len(suffix)]
                if kind == 'join':
                    if player in players:
                        return None
                    players.add(player)
                else:
                    players.discard(player)
                state['players'] = sorted(players)
                return kind, f'{player}{suffix}'
        chat = re.fullmatch(r'(?:\[Not Secure\] )?<(' + PLAYER + r')> (.*)', text)
        if chat:
            if state['known'] and players == {chat[1]}:
                return 'chat', f'{chat[1]} (playing solo): {chat[2]}'
            return None
        advancement = re.fullmatch('(' + PLAYER + r') has (?:made the advancement|completed the challenge|reached the goal) \[.+\]', system_text)
        if advancement:
            return 'advancement', system_text
        if any(pattern.fullmatch(system_text) for pattern in patterns):
            return 'death', system_text
    state['players'] = sorted(players)
    return None

def database(path):
    db = sqlite3.connect(path, timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS cursor (id INTEGER PRIMARY KEY, data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, content TEXT NOT NULL,
        created REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        next_try REAL NOT NULL DEFAULT 0, dead INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')
    with db:
        db.execute('INSERT OR IGNORE INTO metadata VALUES(?,?)', ('instance', str(uuid.uuid4())))
    return db

def empty_state():
    return {'offset': 0, 'prefix': '', 'prefix_len': 0, 'players': [], 'known': False}

class Watcher:
    def __init__(self, logs, db, patterns):
        self.logs, self.db, self.patterns = Path(logs), db, patterns
        row = db.execute('SELECT data FROM cursor WHERE id=1').fetchone()
        self.state = json.loads(row[0]) if row else None

    def matches(self, stream):
        s = self.state
        stream.seek(0)
        return hashlib.sha256(stream.read(s['prefix_len'])).hexdigest() == s['prefix']

    def consume(self, stream, historical=False):
        stream.seek(self.state['offset'])
        for _ in range(1000):
            start = stream.tell()
            raw = stream.readline()
            if not raw or not raw.endswith(b'\n'):
                stream.seek(start)
                break
            event = parse(raw.decode('utf-8', errors='replace'), self.state, self.patterns)
            self.state['offset'] = stream.tell()
            position = stream.tell()
            stream.seek(0)
            prefix = stream.read(min(1024, position))
            stream.seek(position)
            self.state.update(prefix=hashlib.sha256(prefix).hexdigest(), prefix_len=len(prefix))
            with self.db:
                if event and not historical:
                    self.db.execute('INSERT INTO outbox(kind,content,created) VALUES(?,?,?)', (*event, time.time()))
                self.db.execute('INSERT OR REPLACE INTO cursor VALUES(1,?)', (json.dumps(self.state),))
        return stream.tell()

    def poll(self):
        try:
            stream = (self.logs / 'latest.log').open('rb')
        except FileNotFoundError:
            return
        with stream:
            if self.state is None:
                self.state = empty_state()
                # Establish presence from retained history, without posting it.
                while True:
                    before = self.state['offset']
                    self.consume(stream, historical=True)
                    if self.state['offset'] == before:
                        break
                LOG.info('Initial log history skipped; player count known=%s', self.state['known'])
                return
            size = os.fstat(stream.fileno()).st_size
            if size < self.state['offset'] or not self.matches(stream):
                recovered = False
                for archive in sorted(self.logs.glob('*.log.gz'), reverse=True):
                    try:
                        with gzip.open(archive, 'rb') as old:
                            if self.matches(old):
                                while True:
                                    before = self.state['offset']
                                    self.consume(old)
                                    if before == self.state['offset']:
                                        break
                                recovered = True
                                break
                    except (OSError, EOFError):
                        LOG.warning('Unreadable rotated log; content omitted')
                LOG.info('Log replaced; previous tail recovered=%s', recovered)
                # A matched archive gives us a continuous event stream, so the
                # reconstructed presence remains authoritative across rotation.
                # Without that continuity, suppress solo chat until a new server
                # startup marker establishes a trustworthy player set.
                players = self.state['players'] if recovered else []
                known = self.state['known'] if recovered else False
                self.state = empty_state()
                self.state.update(players=players, known=known)
            self.consume(stream)

def payload(content):
    # Disable mentions and markdown interpretation of player-supplied text.
    safe = re.sub(r'([\\`*_~|>])', r'\\\1', content)
    return {'content': safe[:1900], 'allowed_mentions': {'parse': []}, 'flags': 4}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def webhook_url(secret):
    url = secret.read_text().strip()
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'discord.com' or not re.fullmatch(r'/api(?:/v\d+)?/webhooks/\d+/[\w.-]+', parsed.path):
        raise ValueError('Expected a discord.com HTTPS webhook URL')
    query = dict(urllib.parse.parse_qsl(parsed.query))
    query['wait'] = 'true'
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))

def endpoint(secret, mode):
    if mode == 'discord':
        return webhook_url(secret), {}
    config = json.loads(secret.read_text())
    url, token = config['url'], config['token']
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or not token or '\n' in token or '\r' in token:
        raise ValueError('Invalid webhook configuration')
    return url, {'X-Minecraft-Token': 'Bearer ' + token}

def deliver(db, url, opener, mode='discord', headers=None):
    # FIFO: a rate-limited event holds later events until its retry time.
    row = db.execute('SELECT id,content,attempts,kind,created,next_try FROM outbox WHERE dead=0 ORDER BY id LIMIT 1').fetchone()
    if row is None:
        return False
    ident, content, attempts, kind, created, next_try = row
    if next_try > time.time():
        return False
    delay = min(300, 2 ** min(attempts + 1, 8))
    dead = 0
    instance = db.execute('SELECT value FROM metadata WHERE key=?', ('instance',)).fetchone()[0]
    body = payload(content) if mode == 'discord' else {
        'schema_version': 1, 'event_id': f'{instance}:{ident}',
        'server': os.getenv('SERVER_NAME', 'friendsminecraft-test'),
        'type': kind, 'message': content, 'observed_at_unix': created,
        'solo_chat': kind == 'chat', 'discord': payload(content),
    }
    request = urllib.request.Request(url, json.dumps(body).encode(),
        {'Content-Type': 'application/json', 'User-Agent': 'MinecraftLogNotifier/1.0', **(headers or {})})
    try:
        with opener.open(request, timeout=15) as response:
            response.read()
        with db:
            db.execute('DELETE FROM outbox WHERE id=?', (ident,))
        return True
    except urllib.error.HTTPError as error:
        if error.code == 429:
            try:
                delay = max(1, float(json.loads(error.read()).get('retry_after', delay)))
            except (ValueError, TypeError):
                pass
        elif error.code in (401, 403, 404):
            delay = 300
        elif 400 <= error.code < 500:
            dead = 1
        LOG.warning('Webhook HTTP %s; event %s retained%s', error.code, ident, ' for inspection' if dead else ' for retry')
    except (OSError, urllib.error.URLError):
        LOG.warning('Webhook connection failed; event %s retained for retry', ident)
    with db:
        db.execute('UPDATE outbox SET attempts=attempts+1,next_try=?,dead=? WHERE id=?', (time.time()+delay, dead, ident))
    return False

def sender(path, secret):
    db = database(path)
    opener = urllib.request.build_opener(NoRedirect)
    while True:
        try:
            mode = os.getenv('DELIVERY_MODE', 'n8n')
            url, headers = endpoint(secret, mode)
            deliver(db, url, opener, mode, headers)
        except (OSError, ValueError, KeyError):
            LOG.warning('Webhook secret unavailable or invalid; delivery paused')
            time.sleep(30)
        time.sleep(1)

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    path = Path(os.getenv('STATE_PATH', '/state/watcher.sqlite'))
    path.parent.mkdir(parents=True, exist_ok=True)
    templates = json.loads(Path(__file__).with_name('death_templates.json').read_text())
    watcher = Watcher(os.getenv('LOG_DIR', '/logs'), database(path), death_patterns(templates))
    secret = Path(os.getenv('WEBHOOK_FILE', '/run/secrets/webhook.json'))
    threading.Thread(target=sender, args=(path, secret), daemon=True).start()
    while True:
        watcher.poll()
        time.sleep(1)

if __name__ == '__main__':
    main()
