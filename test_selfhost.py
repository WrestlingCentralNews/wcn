"""python3 test_selfhost.py -- story photos are copied to our own site (public/img/s) and the page, og:image and JSON-LD use the
copy; never upscaled, capped at 1600px, non-images / panoramas keep the old hotlink, unused files are pruned; imgmeta finds
X 'name=orig' originals and checks the photo's own report page. No network, no AI calls."""
import unittest, os, io, json, tempfile, time, re
os.environ.pop("AI_API_KEY", None)
from PIL import Image
import selfhost, imgmeta, pages
def jpg(w, h, mode="RGB"):
    b = io.BytesIO(); Image.new(mode, (w, h), (200, 30, 30) if mode == "RGB" else (200, 30, 30, 120)).save(b, "PNG" if mode == "RGBA" else "JPEG"); return b.getvalue()
SRC = {"https://a.com/big.jpg": jpg(2400, 1350), "https://a.com/mid.jpg": jpg(900, 506), "https://a.com/alpha.png": jpg(1300, 731, "RGBA"),
       "https://a.com/page.jpg": b"<html>captcha</html>", "https://a.com/tiny.jpg": jpg(200, 120),
       "https://a.com/pano.jpg": jpg(1600, 900)[:20] + b'GPano:ProjectionType="equirectangular"' + jpg(1600, 900)[20:]}
class SelfHost(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); selfhost.DIR = os.path.join(self.d, "img"); selfhost.MAN = os.path.join(self.d, "m.json")
        self.calls = []
        def get(u, timeout=20, ref=None):
            self.calls.append(u)
            if u.startswith(selfhost.SITE): raise OSError("not on live site")
            return SRC[u]
        selfhost._get = get
    def cl(self, *urls): return [{"id": f"c{i}", "image": u, "ts": 1000 - i, "link": "https://a.com/story", "title": "T", "summary": "S"} for i, u in enumerate(urls)]
    def test_copy_sizes(self):
        cl = self.cl(*SRC); selfhost.run(cl)
        by = {c["image"]: c for c in cl}
        b = by["https://a.com/big.jpg"]; self.assertTrue(b["image_local"].startswith("https://wrestlingcentralnews.com/img/s/"))
        self.assertEqual((b["local_w"], b["local_h"]), (1600, 900))                       # capped
        self.assertEqual((by["https://a.com/mid.jpg"]["local_w"]), 900)                   # never upscaled
        f = os.path.join(selfhost.DIR, by["https://a.com/alpha.png"]["image_local"].rsplit("/", 1)[1])
        self.assertEqual(open(f, "rb").read()[:3], b"\xff\xd8\xff"); self.assertEqual(Image.open(f).mode, "RGB")
        for u in ("https://a.com/page.jpg", "https://a.com/tiny.jpg", "https://a.com/pano.jpg"):
            self.assertNotIn("image_local", by[u], u)                                      # stays a hotlink
        self.assertEqual(sorted(os.listdir(selfhost.DIR)), sorted(selfhost.fname(u) for u in SRC if u in ("https://a.com/big.jpg", "https://a.com/mid.jpg", "https://a.com/alpha.png")))
    def test_cached_and_failed_not_refetched(self):
        selfhost.run(self.cl(*SRC)); n = len(self.calls); cl = self.cl(*SRC); selfhost.run(cl)
        self.assertEqual(len(self.calls), n); self.assertEqual(sum(1 for c in cl if c.get("image_local")), 3)
    def test_own_and_none_skipped(self):
        cl = self.cl("https://wrestlingcentralnews.com/img/promo/wwe.jpg", None, "http://a.com/x.jpg"); selfhost.run(cl)
        self.assertEqual(self.calls, []); self.assertFalse(any(c.get("image_local") for c in cl))
    def test_prune_and_restore_from_site(self):
        selfhost.run(self.cl("https://a.com/big.jpg", "https://a.com/mid.jpg"))
        M = json.load(open(selfhost.MAN)); M["https://a.com/mid.jpg"]["used"] = int(time.time()) - 5 * 86400; json.dump(M, open(selfhost.MAN, "w"))
        selfhost.run(self.cl("https://a.com/big.jpg"))                                     # mid.jpg's story is gone (past 60 days)
        self.assertEqual(os.listdir(selfhost.DIR), [selfhost.fname("https://a.com/big.jpg")])
        self.assertNotIn("https://a.com/mid.jpg", json.load(open(selfhost.MAN)))
        os.remove(os.path.join(selfhost.DIR, selfhost.fname("https://a.com/big.jpg")))  # Actions cache miss -> live site first, then source
        self.calls.clear(); cl = self.cl("https://a.com/big.jpg"); selfhost.run(cl)
        self.assertTrue(self.calls[0].startswith(selfhost.SITE + "img/s/")); self.assertTrue(cl[0].get("image_local"))
    def test_swap_and_page(self):
        cl = self.cl("https://a.com/big.jpg"); c = cl[0]
        c.update(url="story/t-c0.html", source="A", trusted=1, imp=5, kind={"type": "news"}, categories=["WWE"], first_ts=time.time(), sources=1, updates=[], img_w=2400, img_h=1350, image_credit=None)
        selfhost.run(cl); loc = c["image_local"]
        with selfhost.swap(cl):
            self.assertEqual((c["image"], c["img_w"]), (loc, 1600))
            h = pages.page(c, [])
        self.assertEqual((c["image"], c["img_w"]), ("https://a.com/big.jpg", 2400)); self.assertNotIn("_hot", c)
        og = re.search(r'property="og:image" content="([^"]+)"', h).group(1); self.assertEqual(og, loc)
        self.assertIn(f'"url": "{loc}"'.replace(" ", ""), h.replace(" ", "")) if '"ImageObject"' in h else None
        ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
        imgs = json.dumps(ld); self.assertIn(loc, imgs); self.assertNotIn("a.com/big.jpg", imgs)
        self.assertNotIn('src="https://a.com/big.jpg"', h); self.assertIn(f'src="{loc}"', h)
    def test_photon_origin(self):
        SRC["https://a.com/w/p.jpg"] = jpg(1300, 731)
        cl = self.cl("https://i0.wp.com/a.com/w/p.jpg?fit=1200%2C675&ssl=1"); selfhost.run(cl)   # i0.wp.com not in SRC -> KeyError, origin works
        self.assertEqual(cl[0]["local_w"], 1300); self.assertEqual(selfhost.photon_origin("https://a.com/x.jpg"), None)
class ImgMeta(unittest.TestCase):
    def test_x_orig(self):
        for u in ("https://pbs.twimg.com/media/G4abcdEFGHijk12?format=jpg&name=small", "https://pbs.twimg.com/media/G4abcdEFGHijk12.jpg", "https://pbs.twimg.com/media/G4abcdEFGHijk12?format=jpg&name=900x900"):
            self.assertIn("https://pbs.twimg.com/media/G4abcdEFGHijk12?format=jpg&name=orig", imgmeta.variants(u), u)
    def test_photo_report_page_first(self):
        seen = []; P = {"https://a.com/p-300x169.jpg": (300, 169), "https://a.com/p.jpg": None, "https://b.com/p-big.jpg": (1600, 900)}
        imgmeta.probe = lambda u: P.get(u); imgmeta.padded = lambda u: False; imgmeta.load_state = lambda u: None
        imgmeta.page_images = lambda link, img: (seen.append(link), ["https://b.com/p-big.jpg"] if link == "https://b.com/report" else [])[1]
        r = imgmeta.find("https://a.com/p-300x169.jpg", "https://b.com/report", "https://lead.com/x")
        self.assertEqual(r[:3], ("https://b.com/p-big.jpg", 1600, 900)); self.assertEqual(seen, ["https://b.com/report"])
if __name__ == "__main__": unittest.main()
