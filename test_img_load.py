"""python3 test_img_load.py -- top stories never show an empty frame (2026-10-22: homepage TOP STORY 'Shayna Baszler Signs With
TNA' rendered a dark box: its photo failed to load in the reader's browser and the card's onerror handler then removed the
TNA placeholder under it). Broken photos are detected and replaced (next report's photo -> promotion card), the hero prefers a
real photo that loads, and every <img> falls back to the placeholder. No network, no AI calls."""
import unittest, os, re, json, io, subprocess, shutil, urllib.error, urllib.request
os.environ.pop("AI_API_KEY", None)
import imgmeta, vision, toppick, pages, extras
ROOT = os.path.dirname(os.path.abspath(__file__))
class _Resp(io.BytesIO):
    def __init__(self, status=200, ct="image/jpeg", body=b"\xff\xd8\xff\xe0", hdr=None):
        super().__init__(body); self.status = status; self.headers = {"Content-Type": ct, **(hdr or {})}
def _fake(*answers):
    seq = list(answers); calls = []
    def f(req, timeout=None):
        calls.append(req); a = seq.pop(0) if len(seq) > 1 else seq[0]
        if isinstance(a, Exception): raise a
        return a
    f.calls = calls; return f
class LoadState(unittest.TestCase):
    def setUp(self): self._u = urllib.request.urlopen
    def tearDown(self): urllib.request.urlopen = self._u
    def st(self, *a):
        urllib.request.urlopen = _fake(*a); return imgmeta.load_state("https://pub.example/a.jpg")
    def test_ok(self): self.assertEqual(self.st(_Resp()), "ok")
    def test_siteground_challenge(self):   # wp.bodyslam.net 2026-10-22: 202 text/html + sg-captcha: challenge
        self.assertEqual(self.st(_Resp(202, "text/html", b"<html>", {"sg-captcha": "challenge"})), "broken:challenge")
    def test_cloudflare_challenge(self):
        self.assertEqual(self.st(_Resp(200, "text/html", b"<html>", {"cf-mitigated": "challenge"})), "broken:challenge")
    def test_html_instead_of_image(self): self.assertEqual(self.st(_Resp(200, "text/html", b"<!doctype html>")), "broken:not-image")
    def test_404(self): self.assertEqual(self.st(urllib.error.HTTPError("u", 404, "nf", {}, None)), "broken:http-404")
    def test_403_with_range_retries_without(self):
        self.assertEqual(self.st(urllib.error.HTTPError("u", 403, "x", {}, None), _Resp()), "ok")
    def test_ip_blocks_are_unknown(self):   # i0.wp.com refused the Actions runner 2026-10-22 while readers loaded the photos
        e403 = urllib.error.HTTPError("u", 403, "x", {}, None)
        self.assertIsNone(self.st(e403, e403)); self.assertIsNone(self.st(urllib.error.HTTPError("u", 429, "x", {}, None)))
        self.assertEqual(self.st(urllib.error.HTTPError("u", 410, "x", {}, None)), "broken:http-410")
    def test_transient_is_unknown(self):
        self.assertIsNone(self.st(urllib.error.HTTPError("u", 503, "x", {}, None)))
        self.assertIsNone(self.st(TimeoutError()))
    def test_non_ascii_url_is_encoded(self):   # curly quote / × in WordPress file names used to raise before any request
        q = imgmeta.qurl("https://d.example/up/WWE-‘Ring-Boys-1800-×-1200.png")
        self.assertTrue(q.isascii()); self.assertIn("%E2%80%98", q)
    def test_own_site_never_probed(self):
        self.assertEqual(imgmeta.load_state("https://wrestlingcentralnews.com/img/promo/tna.jpg"), "ok")
class Broken(unittest.TestCase):
    def setUp(self):
        self._probe, self._ls, self._pi = imgmeta.probe, imgmeta.load_state, imgmeta.page_images
        imgmeta.page_images = lambda *a: []
    def tearDown(self):
        imgmeta.probe, imgmeta.load_state, imgmeta.page_images = self._probe, self._ls, self._pi; imgmeta._C = None
    def test_find_marks_broken(self):
        imgmeta.probe = lambda u: None; imgmeta.load_state = lambda u: "broken:challenge"
        self.assertEqual(imgmeta.find("https://wp.bodyslam.net/x/dynamite.jpeg", "https://l"), ("https://wp.bodyslam.net/x/dynamite.jpeg", None, None, "broken"))
        self.assertEqual(imgmeta._WHY.pop("https://wp.bodyslam.net/x/dynamite.jpeg"), "broken:challenge")
    def test_unknown_is_not_broken(self):
        imgmeta.probe = lambda u: None; imgmeta.load_state = lambda u: None
        self.assertEqual(len(imgmeta.find("https://a/x.jpg")), 3)
    def test_apply_turns_broken_into_placeholder_not_empty_string(self):
        imgmeta._C = {"https://a/x.jpg": {"best": ["https://a/x.jpg", None, None, "broken"], "v": 4}}
        cl = [{"image": "https://a/x.jpg", "img_w": 1, "img_h": 1}, {"image": "https://a/x.jpg", "image_status": "override"}]
        imgmeta.apply(cl)
        self.assertIsNone(cl[0]["image"]); self.assertEqual(cl[0]["image_status"], "broken"); self.assertNotIn("img_w", cl[0])
        self.assertEqual(cl[1]["image"], "https://a/x.jpg")
    def test_broken_rechecked_later_and_unmeasured_once(self):
        import time
        now = time.time(); seen = []
        imgmeta._C = {"https://a/old-broken.jpg": {"best": ["https://a/old-broken.jpg", None, None, "broken"], "v": 5, "at": now - 7 * 3600},
                      "https://a/new-broken.jpg": {"best": ["https://a/new-broken.jpg", None, None, "broken"], "v": 5, "at": now},
                      "https://a/v4-broken.jpg": {"best": ["https://a/v4-broken.jpg", None, None, "broken"], "v": 4, "at": now},
                      "https://a/v3-unmeasured.jpg": {"best": ["https://a/v3-unmeasured.jpg", None, None], "v": 3, "at": now},
                      "https://a/v3-measured.jpg": {"best": ["https://a/v3-measured.jpg", 800, 450], "v": 3, "at": now}}
        imgmeta.find = (lambda f: (lambda u, l=None: (seen.append(u), (u, 900, 500))[1]))(imgmeta.find)
        import tempfile; imgmeta.CACHE = os.path.join(tempfile.mkdtemp(), "image_sizes.json")
        try:
            imgmeta.run([{"image": u, "ts": now, "first_ts": now, "link": "l"} for u in imgmeta._C])
        finally:
            import importlib; importlib.reload(imgmeta)
        self.assertEqual(sorted(seen), ["https://a/old-broken.jpg", "https://a/v3-unmeasured.jpg", "https://a/v4-broken.jpg"])
class ChooseSkipsBroken(unittest.TestCase):
    BAD = "https://wp.bodyslam.net/wp-content/uploads/2026/10/drew-mcintyre-insight-01.jpg"
    GOOD = "https://cdn.example/drew-mcintyre-raw.jpg"
    def setUp(self):
        vision._C = {}; vision._PAGES.clear(); vision.save = lambda: None
        imgmeta._C = {self.BAD: {"best": [self.BAD, None, None, "broken"], "v": 4}}
    def tearDown(self): imgmeta._C = None
    def card(self, image):
        return {"id": "t-dm", "title": "Drew McIntyre Says He's In Best Shape Of His Life", "raw_title": "Drew McIntyre Says He's In Best Shape Of His Life",
                "summary": "WWE star Drew McIntyre discussed his training.", "link": "https://e.org/dm", "image": image, "updates": [], "ts": 0, "categories": ["WWE"]}
    def test_next_report_photo(self):
        img, _, _ = vision.choose(self.card(self.BAD), [self.BAD, self.GOOD], fetch=False)
        self.assertEqual(img, self.GOOD)
    def test_only_broken_never_returned(self):
        img, _, _ = vision.choose(self.card(self.BAD), [self.BAD], fetch=False)
        self.assertNotEqual(img, self.BAD)
class Hero(unittest.TestCase):
    def items(self, lead_img, lead_w):
        import time
        now = time.time(); L = []
        for k in range(10):
            L.append({"id": f"s{k}", "title": f"Story {k}", "ts": now - 60 * k, "first_ts": now - 60 * k, "imp": 40 - k, "categories": ["WWE"],
                      "image": f"https://cdn.example/p{k}.jpg", "img_w": 1200, "img_h": 675})
        L[0].update(image=lead_img, img_w=lead_w); return L
    def test_measured_photo_beats_promo_card_and_none(self):
        for img, w in ((None, None), ("", None), ("https://wrestlingcentralnews.com/img/promo/tna.jpg", 1200), ("https://x/unmeasured.jpg", None)):
            lead, sec = toppick.pick(self.items(img, w))
            self.assertEqual(lead["id"], "s1", (img, w))
    def test_real_photo_lead_kept(self):
        self.assertEqual(toppick.pick(self.items("https://cdn.example/real.jpg", 1920))[0]["id"], "s0")
    def test_photo_tiers(self):
        self.assertEqual([toppick.photo(c) for c in ({"image": None}, {"image": " "}, {"image": "https://w/img/promo/aew.jpg", "img_w": 1200},
                                                      {"image": "https://x/a.jpg"}, {"image": "https://x/a.jpg", "img_w": 900})], [0, 0, 1, 1, 2])
    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_app_js_top_pick_mirrors_python(self):
        js = open(os.path.join(ROOT, "public", "app.js")).read()
        need = [re.search(r"function pic\(i\)\{.*?\n", js).group(0), re.search(r"function photo\(i\)\{.*?\n", js).group(0),
                re.search(r"const TP=\{.*?\n", js).group(0), re.search(r"function topPick\(L\)\{.*?return\[lead,\.\.\.sec\]\}\n", js, re.S).group(0)]
        for img, w, want in ((None, None, "s1"), ("https://wrestlingcentralnews.com/img/promo/tna.jpg", 1200, "s1"), ("https://cdn.example/real.jpg", 1920, "s0")):
            L = self.items(img, w)
            out = subprocess.run(["node", "-e", "".join(need) + f"console.log(topPick({json.dumps(L)})[0].id)"], capture_output=True, text=True, timeout=20)
            self.assertEqual(out.stdout.strip(), want, out.stderr)
class NeverEmptyFrame(unittest.TestCase):
    def test_no_handler_removes_its_previous_sibling(self):
        # fg's old handler removed previousElementSibling: once the blurred copy had removed itself, that was the .ph placeholder
        for f in ("public/app.js", "extras.py", "pages.py"):
            self.assertNotIn("previousElementSibling", open(os.path.join(ROOT, f)).read(), f)
    def test_app_js_every_img_has_onerror_and_empty_maps_to_placeholder(self):
        js = open(os.path.join(ROOT, "public", "app.js")).read()
        imgs = [l for l in js.split("<img ")[1:] if l.startswith(('class="bg', 'class="fg'))]
        self.assertGreaterEqual(len(imgs), 3)
        for t in imgs: self.assertRegex(re.split(r"<(?:img|div|/div)|`", t)[0], r'onerror="[^"]+"')
        self.assertIn('<div class="ph">', js); self.assertIn("function pic(i)", js); self.assertNotIn("const img=i.image?", js)
    def test_spanish_home_cards_have_fallback(self):
        L = {"url": "es/noticias/x.html", "t": "Shayna Baszler firma con TNA", "s": "x"}
        h = extras.card_html({"categories": ["TNA"], "source": "PWInsider", "image": "https://a/x.jpg", "img_w": 1920, "img_h": 1080}, L, 0, hero=True)
        self.assertIn('<div class="ph">TNA</div>', h); self.assertEqual(h.count("onerror="), 2)
        self.assertIn("querySelector(&#x27;img.bg&#x27;)", h.replace("'", "&#x27;"))
    def test_story_hero_falls_back_to_placeholder(self):
        src = open(os.path.join(ROOT, "pages.py")).read()
        self.assertIn('onerror="{e(HERO_ERR)}"', src); self.assertIn("ph-h", pages.HERO_ERR); self.assertIn('data-cat="{e(c["categories"][0])}"', src)
class ShaynaOverride(unittest.TestCase):
    def test_override(self):
        ov = json.load(open(os.path.join(ROOT, "image_overrides.json")))
        it = [o for o in ov["items"] if "cb913ddea1d55" in o.get("ids", [])]
        self.assertEqual(len(it), 1)
        self.assertEqual(it[0]["image"], "https://djnvkc60dme4l.cloudfront.net/articles/featured/56329a99da472915e539cba193be9d69-1-1.jpg")
        self.assertIn("https://www.pwinsider.com/article/212996/shayna-baszler-signs-with-tna.html", it[0]["links"])
if __name__ == "__main__": unittest.main()
