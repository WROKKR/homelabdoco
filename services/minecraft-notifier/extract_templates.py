"""Extract English death templates from Mojang's version-pinned client assets."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()

if __name__ == '__main__':
    manifest = json.loads(fetch('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'))
    version = next(v for v in manifest['versions'] if v['id'] == '26.1.2')
    metadata = json.loads(fetch(version['url']))
    client = metadata['downloads']['client']
    archive = fetch(client['url'])
    assert hashlib.sha1(archive).hexdigest() == client['sha1'], 'Download checksum mismatch'
    with zipfile.ZipFile(io.BytesIO(archive)) as jar:
        language = json.loads(jar.read('assets/minecraft/lang/en_us.json'))
    templates = {k: v for k, v in language.items() if k.startswith(('death.attack.', 'death.fell.')) and '%1$s' in v}
    Path(__file__).with_name('death_templates.json').write_text(json.dumps(templates, indent=2) + '\n')
    print(f'Extracted {len(templates)} death templates for Minecraft 26.1.2')
