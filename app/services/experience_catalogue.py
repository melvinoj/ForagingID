"""Catalogue only already-published experience exports; never reads the app DB.

Root index = all walks, root preview = newest published walk. The walk pages
retain their data/safety content. Publishing must update and verify all three
root documents plus walks.json in the same commit as the walk.
"""
from __future__ import annotations
import html
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT_FILES = ('index.html', 'preview.html', 'tree.html', 'walks.json')
PRIVACY = 'https://melvinjarman.co.uk/datenschutzerklarung/'

def data_from_page(text):
    marker = 'window.DATA = '
    if marker not in text:
        return None
    try:
        return json.JSONDecoder().raw_decode(text, text.index(marker) + len(marker))[0]
    except ValueError:
        return None

def slugify(title):
    import unicodedata
    value = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-') or 'published-walk'

def fix_privacy_links(text):
    return re.sub(r'https://melvinjarman\.co\.uk/datenschutz(?![a-z])/?', PRIVACY, text)

def preserve_root_walk(root):
    """Give a legacy root walk its own URL before replacing root with a list."""
    index = root / 'index.html'
    d = data_from_page(index.read_text()) if index.exists() else None
    if not d:
        return None
    slug = d.get('slug') or slugify(d.get('title') or 'published-walk')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError('Invalid published walk slug; catalogue was not changed')
    dest = root / 'w' / slug
    if dest.exists():
        return None
    if not all((root / name).is_file() for name in ('index.html', 'preview.html', 'tree.html')):
        raise ValueError('Legacy walk is incomplete; catalogue was not changed')
    dest.mkdir(parents=True)
    for name in ('index.html', 'preview.html', 'tree.html'):
        shutil.copy2(root / name, dest / name)
    if (root / 'photos').exists():
        shutil.copytree(root / 'photos', dest / 'photos')
    return slug

def _rebase_card(text, prefix):
    def replace(match):
        attr, quote, url = match.groups()
        if not url or url.startswith(('#', '/', 'data:')) or urlsplit(url).scheme:
            return match.group(0)
        return f'{attr}={quote}{html.escape(urljoin(prefix, url), quote=True)}{quote}'
    return re.sub(r'\b(href|src)=(\"|\x27)(.*?)\2', replace, text)

def rebuild_catalogue(root, *, published_slug=None, published_at=None, seed_dates=None):
    root = Path(root)
    preserve_root_walk(root)
    path = root / 'walks.json'
    previous = json.loads(path.read_text()) if path.exists() else {}
    known = {w['slug']: w for w in previous.get('walks', [])}
    seed_dates = seed_dates or {}
    walks = []
    for index in sorted((root / 'w').glob('*/index.html')):
        slug = index.parent.name
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
            raise ValueError('Invalid walk directory in published site')
        d = data_from_page(index.read_text())
        if not d:
            raise ValueError(f'{slug}: published page data missing')
        if not all((index.parent / n).is_file() for n in ('preview.html', 'tree.html')):
            raise ValueError(f'{slug}: preview or tree missing; nothing may be published')
        # Existing public exports only. No new species, recipes, routes or photos.
        for name in ('index.html', 'preview.html', 'tree.html'):
            p = index.parent / name
            text = fix_privacy_links(p.read_text())
            if name == 'index.html':
                if 'id="walk-collection-link"' not in text:
                    nav = '<nav id="walk-collection-link" aria-label="Walk collection" style="padding:12px 16px;background:#1e2b28;color:#d8e4d8"><a href="../../" style="color:inherit">← All walks</a></nav>'
                    text = re.sub(r'(<body[^>]*>)', lambda m: m.group(1)+nav, text, count=1)
                text = re.sub(r'<link rel="canonical" href="[^"]+">',
                              f'<link rel="canonical" href="https://melvinoj.github.io/foraging-experience/w/{slug}/">', text)
            p.write_text(text)
        stamp = known.get(slug, {}).get('published_at') or seed_dates.get(slug) or '1970-01-01T00:00:00+00:00'
        digest = hashlib.sha256((index.read_text() + (index.parent / 'preview.html').read_text()).encode()).hexdigest()
        if slug == published_slug and digest != known.get(slug, {}).get('content_digest'):
            stamp = published_at or datetime.now(timezone.utc).isoformat()
        preview = (index.parent / 'preview.html').read_text()
        match = re.search(r'<img[^>]+src=[\"\x27](photos/[^\"\x27]+)', preview)
        walk = d.get('walk') or {}
        walks.append({'slug': slug, 'title': d.get('title') or walk.get('name') or slug,
                      'url': f'w/{slug}/', 'published_at': stamp, 'content_digest': digest,
                      'species': len(d.get('species') or []), 'stops': len(walk.get('stops') or []),
                      'distance_km': round((walk.get('distance_m') or 0)/1000, 1),
                      'image': f'w/{slug}/{match.group(1)}' if match else None})
    walks.sort(key=lambda w: (w['published_at'], w['slug']), reverse=True)
    featured = walks[0] if walks else None
    manifest = {'version': 1, 'featured': featured['slug'] if featured else None, 'walks': walks}
    (root / 'walks.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    cards = []
    for pos, walk in enumerate(walks):
        esc = html.escape
        image = f'<img src="{esc(walk["image"],quote=True)}" alt="" loading="lazy">' if walk['image'] else ''
        label = 'Latest published walk' if pos == 0 else 'Published walk'
        date = datetime.fromisoformat(walk['published_at'].replace('Z','+00:00')).strftime('%d %B %Y') if not walk['published_at'].startswith('1970-') else ''
        label += ' · '+date if date else ''
        cards.append(f'<a class="walk" href="{esc(walk["url"],quote=True)}">{image}<div><span>{label}</span><h2>{esc(walk["title"])}</h2><p>{walk["species"]} species · {walk["stops"]} stops · {walk["distance_km"]} km</p><b>Explore this walk →</b></div></a>')
    css = '''*{box-sizing:border-box}body{margin:0;background:#1e2b28;color:#d8e4d8;font:17px/1.6 system-ui}main,footer{max-width:1100px;margin:auto;padding:40px 6%}h1,h2{font-family:Georgia;font-weight:400;line-height:1.15}h1{font-size:clamp(38px,7vw,68px)}h2{font-size:30px}a{color:inherit}a:focus-visible{outline:3px solid #c89b3c;outline-offset:4px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px}.walk{background:#2a3330;text-decoration:none;border:1px solid #4a5e5a;border-radius:8px;overflow:hidden}.walk img{display:block;width:100%;height:auto;aspect-ratio:1.7;object-fit:cover}.walk>div{padding:24px}.walk span{font-size:12px;color:#a8c88a}.walk b{font-size:15px}footer{font-size:14px}footer a{margin-right:20px}@media(max-width:650px){.grid{grid-template-columns:1fr}}'''
    (root / 'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Foraging walks | Melvin Jarman</title><link rel="canonical" href="https://melvinoj.github.io/foraging-experience/"><style>'+css+'</style><main><p>FROM THE WALK TO THE PLATE</p><h1>Foraging walks</h1><p>Walks, plants and recipes from time outside. Explore the latest walk or return to an earlier one.</p><div class="grid">'+(''.join(cards) or '<p>There are no published walks at the moment.</p>')+'</div></main><footer><a href="https://melvinjarman.co.uk/">Melvin Jarman</a><a href="https://melvinjarman.co.uk/impressum/">Impressum</a><a href="'+PRIVACY+'">Privacy</a></footer></html>')
    if featured:
        prefix = featured['url']
        preview = (root / prefix / 'preview.html').read_text()
        preview = _rebase_card(preview, prefix)
        preview = preview.replace('</body>', '<!-- catalogue-featured: '+featured['slug']+' --></body>')
        (root / 'preview.html').write_text(preview)
        target = prefix+'tree.html'
        (root / 'tree.html').write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={target}"><title>Foraging tree</title><a href="{target}">Open the latest walk’s tree</a></html>')
        if featured['slug'] not in (root/'preview.html').read_text():
            raise ValueError('Latest-walk preview was not updated; publishing must stop')
    else:
        (root / 'preview.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="robots" content="noindex"><p>No walks are currently published.</p></html>')
        (root / 'tree.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><a href="index.html">Browse the walks</a></html>')
    return {name: (root / name).read_bytes() for name in ROOT_FILES}
