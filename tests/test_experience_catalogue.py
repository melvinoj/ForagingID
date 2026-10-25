"""Catalogue tests use only temporary copies of already-public HTML; no live DB."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('catalogue',Path(__file__).parents[1]/'app/services/experience_catalogue.py')
c=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(c)

class CatalogueTests(unittest.TestCase):
    def walk(self,root,slug,title):
        d=root/'w'/slug;d.mkdir(parents=True)
        data={'slug':slug,'title':title,'species':[{}],'walk':{'distance_m':1234,'stops':[{},{}]}}
        (d/'index.html').write_text('<html><script>window.DATA = '+json.dumps(data)+';</script>https://melvinjarman.co.uk/datenschutz</html>')
        (d/'preview.html').write_text('<html><body><a href="index.html"><img src="photos/1.jpg">'+title+'</a></body></html>')
        (d/'tree.html').write_text('tree');(d/'photos').mkdir();(d/'photos/1.jpg').write_bytes(b'public-photo')
        return d
    def test_latest_preview_list_and_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);self.walk(r,'old','Old walk');self.walk(r,'new','New walk')
            result=c.rebuild_catalogue(r,seed_dates={'old':'2026-10-21','new':'2026-10-22'})
            self.assertEqual(list(result),list(c.ROOT_FILES))
            self.assertEqual(json.loads((r/'walks.json').read_text())['featured'],'new')
            self.assertIn('w/new/index.html',(r/'preview.html').read_text())
            self.assertIn('w/new/photos/1.jpg',(r/'preview.html').read_text())
            self.assertLess((r/'index.html').read_text().index('New walk'),(r/'index.html').read_text().index('Old walk'))
            self.assertIn(c.PRIVACY,(r/'w/new/index.html').read_text())
            before={n:(r/n).read_bytes() for n in c.ROOT_FILES}
            c.rebuild_catalogue(r,published_slug='new',published_at='2026-10-25')
            self.assertEqual(before,{n:(r/n).read_bytes() for n in c.ROOT_FILES})
    def test_missing_preview_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);d=self.walk(r,'new','New');(d/'preview.html').unlink()
            with self.assertRaisesRegex(ValueError,'preview or tree missing'):c.rebuild_catalogue(r)
    def test_unpublished_walk_removed_and_previous_featured(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);self.walk(r,'old','Old');self.walk(r,'new','New')
            c.rebuild_catalogue(r,seed_dates={'old':'2026-10-21','new':'2026-10-22'})
            shutil.rmtree(r/'w/new');c.rebuild_catalogue(r)
            self.assertEqual(json.loads((r/'walks.json').read_text())['featured'],'old')
            self.assertNotIn('w/new/',(r/'index.html').read_text())
    def test_legacy_root_preserved(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);d=self.walk(r,'rummelsbuhl-foray','Rümmelsbühl foray')
            for n in ['index.html','preview.html','tree.html']:shutil.copy2(d/n,r/n)
            shutil.copytree(d/'photos',r/'photos');shutil.rmtree(r/'w')
            c.preserve_root_walk(r);self.assertTrue((r/'w/rummelsbuhl-foray/index.html').exists())
            c.rebuild_catalogue(r);self.assertIn('Rümmelsbühl',(r/'index.html').read_text())
if __name__=='__main__':unittest.main()
