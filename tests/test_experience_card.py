"""Card selection and bundle tests; photos and repositories are temporary."""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from app.services.experience_card import build_bundle, card_candidates, select_stops


def test_card_bundle_and_overrides():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); page = root/'public'; (page/'photos').mkdir(parents=True)
        species, stops, recipes = [], [], []
        for i in range(1,9):
            Image.new('RGB',(1600,1000),(i*25,70,90)).save(page/'photos'/f'{i}.jpg')
            species.append({'id':i,'en':f'Plant {i}','sci':f'Plantus {i}', 'photo':f'photos/{i}.jpg'})
            stops.append({'n':str(i),'lat':47+i*.001,'lng':7+i*.0005,'species':[i]})
            if i%2: recipes.append({'recipe_id':i,'species_id':i,'dish':f'Dish {i}'})
        data = {'title':'A walk','walk':{'stops':stops,'distance_m':7600,
                'line':[[s['lng'],s['lat']] for s in stops]},'species':species,'recipes':recipes}
        candidates = card_candidates(data,page)
        automatic = select_stops(candidates)
        assert len(automatic)==4 and all(c['dish'] for c in automatic)
        override = {candidates[0]['key']:False,candidates[1]['key']:True}
        selected = select_stops(candidates,override)
        assert '1' not in [c['stop'] for c in selected] and '2' in [c['stop'] for c in selected]
        out = root/'bundle'
        result = build_bundle(data,page,'a-walk',out,override,cover_photo='photos/3.jpg')
        assert result['url'].endswith('/w/a-walk/') and result['distance_km']==7.6
        assert result['cover']['alt']=='Plant 3'
        assert all(0<=v<=100 for p in result['route'] for v in p)
        photos = list((out/'photos').glob('*.webp'))
        assert len(photos)==len(selected)+1
        for p in photos:
            with Image.open(p) as image:
                assert not image.getexif()
                assert image.width<=1200
                if not p.name.startswith('cover-'):assert image.size==(300,300)
        assert not list(out.rglob('*.jpg'))
        assert json.loads((out/'featured.json').read_text())==result
        try:select_stops(candidates,{c['key']:True for c in candidates})
        except ValueError:pass
        else:raise AssertionError('More than six forced stops accepted')
        # No invented recipe title: the app title helper can withhold an untitled recipe.
        assert not card_candidates(data,page,{r['recipe_id']:'' for r in recipes})[0]['dish']
        data['species'][0]['photo']='../../private.jpg'
        (root/'private.jpg').write_bytes(b'private')
        # Unavailable photos are ignored, never copied from outside the published walk.
        assert not any(c['species_id']==1 for c in card_candidates(data,page))


def test_export_does_not_receive_card_only_settings():
    import asyncio
    from types import SimpleNamespace
    from app.services import experience_publish as xp
    original = xp._run
    async def fake_run(cmd, cwd, timeout, env=None):
        saved = json.loads(Path(cmd[cmd.index('--overrides')+1]).read_text())
        assert saved == {'slug':'a-walk','title_en':'A walk'}
        return 0, '{}', ''
    pub = SimpleNamespace(saved_walk_id=1,slug='a-walk',is_default=False,
        overrides_json=json.dumps({'title_en':'A walk','card_stops':{'47.001000,7.001000':True},'card_cover_species':2}))
    xp._run = fake_run
    try:asyncio.run(xp._export(pub,['--plan-json'],30))
    finally:xp._run = original


if __name__=='__main__':
    test_card_bundle_and_overrides()
    test_export_does_not_receive_card_only_settings()
    print('PASS card selection, exclusions, forced stops, cover, coordinates, small photos, metadata and title handling')
