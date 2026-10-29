"""Exercise real card commits and override republishing against a local bare remote."""
import asyncio,json,sqlite3,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from app.services import experience_card as card, experience_publish as xp

def git(cwd,*args):
 r=subprocess.run(['git',*args],cwd=cwd,text=True,capture_output=True)
 assert r.returncode==0,r.stderr
 return r.stdout.strip()

async def exercise():
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp); remote=root/'remote.git'; website=root/'website'; public=root/'public'; page=public/'w/test-walk';(page/'photos').mkdir(parents=True)
  git(root,'init','--bare','-b','main',str(remote));git(root,'clone',str(remote),str(website))
  git(website,'config','user.name','Test');git(website,'config','user.email','test@example.test')
  (website/'unrelated.txt').write_text('preserve me');git(website,'add','.');git(website,'commit','-m','Initial');git(website,'push','origin','main')
  dbfile=root/'test.db';db=sqlite3.connect(dbfile);db.execute('create table species_recipes(id integer,title text,body text)')
  plants=[];stops=[];recipes=[]
  for i in range(1,7):
   Image.new('RGB',(1400,900),(i*30,80,100)).save(page/'photos'/f'{i}.jpg')
   plants.append({'id':i,'en':f'Plant {i}','sci':f'Plantus {i}','photo':f'photos/{i}.jpg'})
   stops.append({'n':str(i),'lat':47+i*.001,'lng':7+i*.001,'species':[i]})
   recipes.append({'recipe_id':i,'species_id':i,'dish':f'Dish {i}'})
   db.execute('insert into species_recipes values(?,?,?)',(i,f'Dish {i}','body'))
  db.commit();db.close()
  data={'title':'Test walk','species':plants,'recipes':recipes,'walk':{'stops':stops,'distance_m':1200,'line':[[s['lng'],s['lat']] for s in stops]}}
  (page/'index.html').write_text('<script>window.DATA = '+json.dumps(data)+';</script>')
  (public/'walks.json').write_text(json.dumps({'featured':'test-walk','walks':[{'slug':'test-walk','image':'w/test-walk/photos/3.jpg'}]}))
  real_git,real_db=xp.git,xp._db_file
  async def controlled_git(cwd,*args,**kwargs):
   if args==('remote','get-url','origin'):return 0,'https://github.com/melvinoj/melvin-jarman-website.git\n',''
   return await real_git(cwd,*args,**kwargs)
  xp.git=controlled_git;xp._db_file=lambda:str(dbfile)
  try:
   first=await card.publish_website_card(public,website_clone=website)
   assert first['ok']
   paths=git(remote,'diff-tree','--no-commit-id','--name-only','-r','main').splitlines()
   assert paths and all(p=='assets/walk/featured.json' or p.startswith('assets/walk/photos/') for p in paths)
   bundle=json.loads(git(remote,'show','main:assets/walk/featured.json'))
   assert bundle['cover']['alt']=='Plant 3' and len(bundle['featured_stops'])==6
   first_photos={bundle['cover']['photo']} | {s['photo'] for s in bundle['featured_stops']}
   second=await card.publish_website_card(public,{card.stop_key(stops[0]['lat'],stops[0]['lng']):False},website_clone=website,cover_species=2)
   bundle=json.loads(git(remote,'show','main:assets/walk/featured.json'))
   assert second['commit']!=first['commit']
   assert '1' not in [s['stop'] for s in bundle['featured_stops']]
   assert bundle['cover']['alt']=='Plant 2'
   expected={bundle['cover']['photo']} | {s['photo'] for s in bundle['featured_stops']}
   actual=set(git(remote,'ls-tree','--name-only','main:assets/walk/photos').splitlines())
   assert actual==expected, (actual,expected)
   deleted=set(git(remote,'diff-tree','--no-commit-id','--name-only','--diff-filter=D','-r','main').splitlines())
   assert deleted=={'assets/walk/photos/'+name for name in first_photos-expected}
   paths=git(remote,'diff-tree','--no-commit-id','--name-only','-r','main').splitlines()
   assert all(p=='assets/walk/featured.json' or p.startswith('assets/walk/photos/') for p in paths)
   third=await card.publish_website_card(public,{card.stop_key(stops[0]['lat'],stops[0]['lng']):False},website_clone=website,cover_species=2)
   assert third['commit']==second['commit'], 'Identical republish must be a no-op'
   assert git(remote,'show','main:unrelated.txt')=='preserve me'
   print('PASS scoped website commits; stop and cover override republish; orphan photos deleted atomically; identical republish unchanged; unrelated file preserved')
  finally:xp.git=real_git;xp._db_file=real_db

if __name__=='__main__':asyncio.run(exercise())
