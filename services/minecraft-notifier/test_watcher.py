import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock
import watcher as w

PATTERNS = w.death_patterns(json.loads(Path(__file__).with_name('death_templates.json').read_text()))
def line(text):
    return f'[15:06:17] [Server thread/INFO]: {text}\n'

class Tests(unittest.TestCase):
    def test_presence_and_chat(self):
        state = w.empty_state()
        self.assertIsNone(w.parse(line('<WROKKR> unknown'), state, PATTERNS))
        w.parse(line('Starting minecraft server version 26.1.2'), state, PATTERNS)
        w.parse(line('WROKKR joined the game'), state, PATTERNS)
        self.assertEqual(w.parse(line('<WROKKR> hello'), state, PATTERNS)[0], 'chat')
        w.parse(line('Other joined the game'), state, PATTERNS)
        self.assertIsNone(w.parse(line('<WROKKR> private'), state, PATTERNS))
        w.parse(line('Other left the game'), state, PATTERNS)
        self.assertEqual(w.parse(line('<WROKKR> hello'), state, PATTERNS)[0], 'chat')

    def test_events_and_spoofing(self):
        state = w.empty_state()
        for message in ['WROKKR drowned', 'WROKKR was slain by Zombie', 'WROKKR fell from a high place']:
            self.assertEqual(w.parse(line(message), state, PATTERNS)[0], 'death')
        for category in ['made the advancement', 'completed the challenge', 'reached the goal']:
            self.assertEqual(w.parse(line(f'WROKKR has {category} [Country Lode, Take Me Home]'), state, PATTERNS)[0], 'advancement')
        self.assertIsNone(w.parse(line('<Other> WROKKR drowned'), state, PATTERNS))
        self.assertIsNone(w.parse(line('[Server] WROKKR drowned'), state, PATTERNS))
        self.assertIsNone(w.parse('[15:06:17] [Worker/INFO]: WROKKR drowned\n', state, PATTERNS))

    def test_minecraft_26_3_system_chat_and_login(self):
        state = w.empty_state()
        w.parse(line('Starting minecraft server version 26.3'), state, PATTERNS)
        login = 'WROKKR[/192.168.0.190:52817] logged in with entity id 260 at (873.0, 64.0, -1250.0)'
        self.assertEqual(w.parse(line(login), state, PATTERNS), ('join', 'WROKKR joined the game'))
        # 26.3 writes this immediately after the login line; it must not post a duplicate.
        self.assertIsNone(w.parse(line('System chat: WROKKR joined the game'), state, PATTERNS))
        self.assertEqual(
            w.parse(line('System chat: WROKKR has made the advancement [Stone Age]'), state, PATTERNS),
            ('advancement', 'WROKKR has made the advancement [Stone Age]'),
        )
        self.assertEqual(
            w.parse(line('System chat: WROKKR drowned'), state, PATTERNS),
            ('death', 'WROKKR drowned'),
        )
        self.assertEqual(
            w.parse(line('System chat: WROKKR left the game'), state, PATTERNS),
            ('leave', 'WROKKR left the game'),
        )
        self.assertEqual(state['players'], [])

    def test_minecraft_26_3_system_chat_cannot_spoof_player_chat(self):
        state = {'offset': 0, 'prefix': '', 'prefix_len': 0, 'players': ['WROKKR'], 'known': True}
        self.assertIsNone(w.parse(line('System chat: <WROKKR> not player chat'), state, PATTERNS))

    def test_restart_rotation_and_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'latest.log'
            log.write_text(line('Starting minecraft server version 26.1.2') + line('WROKKR joined the game'))
            db = w.database(root / 'state.db')
            watcher = w.Watcher(root, db, PATTERNS)
            watcher.poll()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 0)
            with log.open('a') as f:
                f.write(line('WROKKR drowned')[:-1])
            watcher.poll()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 0)
            with log.open('a') as f:
                f.write('\n')
            watcher.poll()
            w.Watcher(root, db, PATTERNS).poll()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 1)
            with log.open('a') as f:
                f.write(line('WROKKR left the game'))
            with gzip.open(root / '2026-09-27-1.log.gz', 'wb') as f:
                f.write(log.read_bytes())
            log.write_text(line('Starting minecraft server version 26.1.2') + line('Other joined the game'))
            watcher.poll()
            self.assertEqual([r[0] for r in db.execute('SELECT kind FROM outbox')], ['death', 'leave', 'join'])
            db.close()

    def test_recovered_rotation_preserves_solo_presence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'latest.log'
            log.write_text(line('Starting minecraft server version 26.1.2') + line('WROKKR joined the game'))
            db = w.database(root / 'state.db')
            watcher = w.Watcher(root, db, PATTERNS)
            watcher.poll()
            with gzip.open(root / '2026-09-27-1.log.gz', 'wb') as archive:
                archive.write(log.read_bytes())
            log.write_text(line('<WROKKR> after rotation'))
            watcher.poll()
            self.assertEqual(
                db.execute('SELECT kind,content FROM outbox').fetchall(),
                [('chat', 'WROKKR (playing solo): after rotation')],
            )
            db.close()

    def test_retry_and_structured_payload(self):
        db = w.database(':memory:')
        with db:
            db.execute('INSERT INTO outbox(kind,content,created) VALUES(?,?,?)', ('chat', 'WROKKR: @everyone', 123))
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError('hidden', 429, 'rate limit', {}, io.BytesIO(b'{"retry_after":10}'))
        self.assertFalse(w.deliver(db, 'https://example.test', opener, 'n8n'))
        self.assertEqual(db.execute('SELECT attempts FROM outbox').fetchone()[0], 1)
        request = opener.open.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body['type'], 'chat')
        self.assertEqual(body['discord']['allowed_mentions'], {'parse': []})
        first_id = body['event_id']
        with db:
            db.execute('DELETE FROM outbox')
            db.execute('INSERT INTO outbox(kind,content,created) VALUES(?,?,?)', ('join', 'Other joined', 124))
        opener.open.side_effect = None
        opener.open.return_value.__enter__ = Mock(return_value=io.BytesIO(b'{}'))
        opener.open.return_value.__exit__ = Mock(return_value=False)
        self.assertTrue(w.deliver(db, 'https://example.test', opener, 'n8n'))
        self.assertNotEqual(json.loads(opener.open.call_args.args[0].data)['event_id'], first_id)
        db.close()

    def test_n8n_endpoint_uses_dedicated_header(self):
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / 'webhook.json'
            secret.write_text(json.dumps({'url': 'https://example.test/hook', 'token': 'secret-value'}))
            url, headers = w.endpoint(secret, 'n8n')
            self.assertEqual(url, 'https://example.test/hook')
            self.assertEqual(headers, {'X-Minecraft-Token': 'Bearer secret-value'})

if __name__ == '__main__':
    unittest.main()
