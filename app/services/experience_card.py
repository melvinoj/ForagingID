"""Small first-party website card made only from an already gated public export."""
from __future__ import annotations
import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from PIL import Image, ImageOps


def public_recipe_titles(data, db_file):
    """Use the app's existing title rule, limited to already-public recipe IDs."""
    import sqlite3
    from app.models.species import recipe_list_title
    titles = {}
    with sqlite3.connect(f'file:{Path(db_file).resolve()}?mode=ro', uri=True) as db:
        for recipe in data.get('recipes') or []:
            row = db.execute('SELECT title, body FROM species_recipes WHERE id=?',
                             (recipe['recipe_id'],)).fetchone()
            titles[recipe['recipe_id']] = recipe_list_title(*row) if row else ''
    return titles


def normalized_route(walk):
    stops = walk.get('stops') or []
    points = walk.get('line') or [[s['lng'], s['lat']] for s in stops]
    if not points:
        raise ValueError('The walk has no route or positioned stops')
    k = math.cos(math.radians(sum(p[1] for p in points) / len(points)))
    all_points = points + [[s['lng'], s['lat']] for s in stops]
    xs, ys = [p[0]*k for p in all_points], [p[1] for p in all_points]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    scale = 84 / (max(hi_x-lo_x, hi_y-lo_y) or 1e-9)
    ox, oy = (100-(hi_x-lo_x)*scale)/2, (100-(hi_y-lo_y)*scale)/2
    def xy(lng, lat):
        return [round(ox+(lng*k-lo_x)*scale, 2), round(oy+(hi_y-lat)*scale, 2)]
    return [xy(*p) for p in points], {str(s['n']): xy(s['lng'], s['lat']) for s in stops}


def stop_key(lat, lng):
    return f'{lat:.6f},{lng:.6f}'


def card_candidates(data, page_dir, recipe_titles=None):
    recipes = {}
    for r in data.get('recipes') or []:
        recipes.setdefault(r['species_id'], recipe_titles.get(r['recipe_id']) if recipe_titles is not None else r.get('dish'))
    plants = {p['id']: p for p in data.get('species') or []}
    candidates = []
    for index, stop in enumerate(data['walk'].get('stops') or []):
        choices = []
        for sid in stop.get('species') or []:
            plant = plants.get(sid)
            if not plant or plant.get('toxic') or plant.get('deadly'):
                continue
            photo = plant.get('photo') or plant.get('thumb')
            if not photo or not (Path(page_dir)/photo).is_file():
                continue
            resolved = (Path(page_dir)/photo).resolve()
            if Path(page_dir).resolve() not in resolved.parents:
                raise ValueError('Photo outside the public walk')
            choices.append({'stop': str(stop['n']), 'order': index,
                            'key': stop_key(stop['lat'], stop['lng']), 'species_id': sid, 'common_name': plant.get('en') or plant['sci'],
                            'photo_source': str(resolved), 'dish': recipes.get(sid)})
        if choices:
            choices.sort(key=lambda c: (not bool(c['dish']), c['species_id']))
            candidates.append(choices[0])
    return candidates


def select_stops(candidates, overrides=None):
    overrides = overrides or {}
    forced = [c for c in candidates if overrides.get(c['key']) is True]
    if len(forced) > 6:
        raise ValueError('Choose at most six stops to feature on the card')
    missing = set(k for k,v in overrides.items() if v is True) - {c['key'] for c in candidates}
    if missing:
        raise ValueError('A selected card stop no longer has an eligible public photo; review the card choices')
    selected = list(forced)
    available = [c for c in candidates if overrides.get(c['key']) is not False and c not in selected]
    def add_spread(pool, target):
        while pool and len(selected) < target:
            unused = [c for c in pool if c['species_id'] not in {s['species_id'] for s in selected}]
            if not unused:
                break
            if selected:
                chosen = max(unused, key=lambda c: min(abs(c['order']-s['order']) for s in selected))
            else:
                chosen = unused[len(unused)//2]
            selected.append(chosen)
            pool.remove(chosen)
    add_spread([c for c in available if c['dish']], 6)
    add_spread([c for c in available if c not in selected], 4)
    return sorted(selected, key=lambda c: c['order'])


def build_bundle(data, page_dir, slug, destination, overrides=None, recipe_titles=None, cover_photo=None, cover_species=None):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError('Invalid walk slug')
    route, positions = normalized_route(data['walk'])
    candidates = card_candidates(data, page_dir, recipe_titles)
    selected = select_stops(candidates, overrides)
    if not selected:
        raise ValueError('No public stop photos are available for the card')
    dest = Path(destination)
    (dest/'photos').mkdir(parents=True, exist_ok=True)
    plants = {p['id']: p for p in data.get('species') or []}
    if cover_species is not None:
        plant = plants.get(cover_species)
        if not plant or not plant.get('photo'):
            raise ValueError('The selected cover photo is no longer available on this walk')
        cover_photo = plant['photo']
    if not cover_photo:
        cover_photo = selected[0]['photo_source']
    cover_path = (Path(page_dir)/cover_photo).resolve()
    if Path(page_dir).resolve() not in cover_path.parents:
        raise ValueError('Cover must be a photo from the public walk')
    with Image.open(cover_path) as source:
        cover = ImageOps.exif_transpose(source).convert('RGB')
        cover.thumbnail((1200,1200), Image.Resampling.LANCZOS)
        import io
        encoded = io.BytesIO(); cover.save(encoded, 'WEBP', quality=80, method=6)
    body = encoded.getvalue()
    cover_name = 'cover-'+hashlib.sha256(body).hexdigest()[:12]+'.webp'
    (dest/'photos'/cover_name).write_bytes(body)
    cover_plant = next((p for p in plants.values() if p.get('photo') == str(cover_path.relative_to(Path(page_dir).resolve()))), None)
    cover_info = {'photo': cover_name, 'alt': (cover_plant.get('en') or cover_plant['sci']) if cover_plant else data['title']}
    featured = []
    for c in selected:
        with Image.open(c['photo_source']) as source:
            photo = ImageOps.fit(ImageOps.exif_transpose(source).convert('RGB'), (300,300),
                                 method=Image.Resampling.LANCZOS)
            import io
            encoded = io.BytesIO()
            photo.save(encoded, 'WEBP', quality=78, method=6)
        body = encoded.getvalue()
        name = f"{c['species_id']}-{hashlib.sha256(body).hexdigest()[:12]}.webp"
        (dest/'photos'/name).write_bytes(body)
        featured.append({'stop': c['stop'], 'position': positions[c['stop']],
                         'common_name': c['common_name'], 'photo': name, 'dish': c['dish']})
    bundle = {'version': 1, 'slug': slug, 'title': data['title'],
              'url': f'https://melvinoj.github.io/foraging-experience/w/{slug}/',
              'species': len(data.get('species') or []), 'stops': len(data['walk'].get('stops') or []),
              'distance_km': round((data['walk'].get('distance_m') or 0)/1000, 1),
              'route': route, 'straight_ranges': data['walk'].get('straight_ranges') or [],
              'featured_stops': featured, 'cover': cover_info}
    (dest/'featured.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2)+'\n')
    return bundle


async def publish_website_card(public_clone, overrides=None, website_clone=None, override_slug=None, cover_species=None):
    """Separate commit after GitHub Pages publication. Failure is reported by caller."""
    import os
    import tempfile
    from app.services import experience_publish as xp
    website = Path(website_clone or os.environ.get('LAND_MEMORY_WEBSITE_CLONE',
                   str(Path.home()/'Documents/ChatGPT/website/source')))
    manifest = json.loads((Path(public_clone)/'walks.json').read_text())
    slug = manifest.get('featured')
    if not slug:
        raise ValueError('There is no featured published walk')
    if override_slug and slug != override_slug:
        from sqlalchemy import select
        from app.models.experience import ExperiencePublication
        async with xp.database.AsyncSessionLocal() as db:
            row = await db.scalar(select(ExperiencePublication).where(ExperiencePublication.slug == slug))
            saved = json.loads(row.overrides_json or '{}') if row else {}
            overrides = saved.get('card_stops', {})
            cover_species = saved.get('card_cover_species')
    from app.services.experience_catalogue import data_from_page
    page = Path(public_clone)/'w'/slug
    data = data_from_page((page/'index.html').read_text())
    if not data:
        raise ValueError('The featured walk has no public data')
    remote = (await xp.git(website, 'remote', 'get-url', 'origin'))[1].strip()
    if remote not in ('https://github.com/melvinoj/melvin-jarman-website.git',
                      'git@github.com:melvinoj/melvin-jarman-website.git'):
        raise ValueError('Website clone must point to melvinoj/melvin-jarman-website')
    await xp._git_ok(website, 'fetch', 'origin', what='Fetching the website')
    with tempfile.TemporaryDirectory(prefix='walk_card_') as tmp:
        temp = Path(tmp)
        bundle_dir = temp/'bundle'
        cover_photo = next((w.get('image') for w in manifest['walks'] if w['slug'] == slug), None)
        if cover_photo:
            cover_photo = str((Path(public_clone)/cover_photo).relative_to(page))
        bundle = build_bundle(data, page, slug, bundle_dir, overrides, public_recipe_titles(data, xp._db_file()), cover_photo, cover_species)
        wt = temp/'website'
        await xp._git_ok(website, 'worktree', 'add', '--detach', str(wt), 'origin/main',
                         what='Preparing the website card')
        try:
            target = wt/'assets/walk'
            target.mkdir(parents=True, exist_ok=True)
            # Retain older hashed photos for clients with a cached manifest.
            shutil.copytree(bundle_dir/'photos', target/'photos', dirs_exist_ok=True)
            shutil.copy2(bundle_dir/'featured.json', target/'featured.json')
            await xp._git_ok(wt, 'add', '--', 'assets/walk/featured.json', 'assets/walk/photos',
                             what='Staging only the card bundle')
            paths = (await xp._git_ok(wt, 'diff', '--cached', '--name-only', what='Checking card paths')).splitlines()
            if any(p != 'assets/walk/featured.json' and not p.startswith('assets/walk/photos/') for p in paths):
                raise ValueError('Unexpected file in website card commit')
            if paths:
                await xp._git_ok(wt, 'commit', '-m', f'Update featured walk card: {bundle["title"]}', what='Saving card')
                await xp._git_ok(wt, 'push', 'origin', 'HEAD:refs/heads/main', what='Pushing website card')
            sha = (await xp._git_ok(wt, 'rev-parse', 'HEAD', what='Reading card commit')).strip()
            return {'ok': True, 'commit': sha, 'slug': slug,
                    'message': 'Website card bundle saved to GitHub.'}
        finally:
            await xp.git(website, 'worktree', 'remove', '--force', str(wt))
