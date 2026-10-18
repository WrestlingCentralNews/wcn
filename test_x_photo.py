"""python3 test_x_photo.py -- every X post carries the site's (story-matched) photo; 30 s budget; text-only fallback, never skipped."""
import unittest, json, os, tempfile, time, io, contextlib
import x_poster as XP, xspend, live_x
PROMO = "https://wrestlingcentralnews.com/img/promo/{}.jpg"
def card(**k):
    now = time.time()
    c = {"id": "c1", "title": "Ilja Dragunov Debuts For AEW At WrestleDream", "raw_title": "Ilja Dragunov Makes AEW Debut At WrestleDream", "link": "https://e.org/1",
         "ts": now - 60, "first_ts": now - 60, "categories": ["AEW"], "kind": {"type": "news"}, "sources": 4, "trusted": 2, "updates": [],
         "image": "https://cdn.example/dragunov.jpg", "image_status": "key-verified"}
    c.update(k); return c
class Cands(unittest.TestCase):
    def test_verified_site_photo_first(self):
        self.assertEqual(XP.photo_candidates(card())[0], ("https://cdn.example/dragunov.jpg", "site:key-verified"))
    def test_cached_and_logo_status(self):
        c = card(image=PROMO.format("aew"), image_status="cached:promo-logo:aew")
        self.assertEqual(XP.photo_candidates(c)[0][0], PROMO.format("aew"))
    def test_unverified_person_photo_never_used(self):   # the Austin Creed/Kofi kind of mix-up
        c = card(title="Austin Creed Joins AEW", raw_title="Austin Creed Joins AEW", image="https://cdn.example/kofi.jpg", image_status="person-photo-unverified")
        urls = [u for u, _ in XP.photo_candidates(c)]
        self.assertNotIn("https://cdn.example/kofi.jpg", urls); self.assertEqual(urls[0], PROMO.format("aew"))
    def test_no_promo_uses_site_default(self):
        c = card(title="Legend Recalls Career", raw_title="Legend Recalls Career", image=None, image_status="wcn-card")
        self.assertEqual(XP.photo_candidates(c), [(XP.SITE_DEFAULT_IMG, "site-default")])
class Attach(unittest.TestCase):
    def setUp(self):
        self.f, self.u = XP.fetch_image, XP.upload_media
        self.d = tempfile.mkdtemp(); xspend.LEDGER = os.path.join(self.d, "x_spend.json")
    def tearDown(self): XP.fetch_image, XP.upload_media = self.f, self.u
    def test_falls_through_failed_download(self):
        def fetch(u, timeout=30):
            if "bad" in u: raise IOError("404")
            return b"\xff\xd8\xff..", "image/jpeg"
        XP.fetch_image = fetch; XP.upload_media = lambda u, src, data, timeout=60: ("m123", None)
        mid, url, why, err = XP.attach_photo([("https://bad/x.jpg", "site:key-verified"), (PROMO.format("aew"), "promo-logo:aew")])
        self.assertEqual((mid, url, why), ("m123", PROMO.format("aew"), "promo-logo:aew"))
    def test_budget_exceeded_text_only(self):
        def slow(u, timeout=30): time.sleep(3); return b"\xff\xd8\xff", "image/jpeg"
        XP.fetch_image = slow; t = time.time()
        mid, url, why, err = XP.attach_photo([("https://x/y.jpg", "site:key-verified")], budget=2)
        self.assertIsNone(mid); self.assertIn("exceeded", err); self.assertLess(time.time() - t, 2.8)
    def test_default_budget_is_30s(self): self.assertEqual(XP.PHOTO_BUDGET_S, 30)
    def test_upload_failure(self):
        XP.fetch_image = lambda u, timeout=30: (b"\xff\xd8\xff", "image/jpeg"); XP.upload_media = lambda u, src, data, timeout=60: (None, "upload HTTP 400")
        mid, url, why, err = XP.attach_photo([("https://x/y.jpg", "site:key-verified")]); self.assertIsNone(mid); self.assertIn("400", err)
class Post(unittest.TestCase):
    """run() with fake keys and a stubbed X: a photo is attached when available, and the post still goes out when it isn't."""
    def go(self, attach):
        d = tempfile.mkdtemp(); XP.NEWS = os.path.join(d, "news.json"); XP.STATE = os.path.join(d, "posted_x.json"); xspend.LEDGER = os.path.join(d, "x_spend.json")
        json.dump({"items": [card()]}, open(XP.NEWS, "w")); json.dump({"posted": {}, "links": [], "log": []}, open(XP.STATE, "w"))
        XP.live_posted = lambda: {}; sent = []
        XP.post_tweet = lambda text, media_ids=None: (sent.append(media_ids) or (201, {"data": {"id": "999"}}, {}))
        XP.attach_photo = attach
        os.environ.update(X_POST_ENABLED="1", X_API_KEY="k", X_API_SECRET="k", X_ACCESS_TOKEN="k", X_ACCESS_TOKEN_SECRET="k")
        try:
            with contextlib.redirect_stdout(io.StringIO()): XP.run()
        finally:
            for k in ("X_POST_ENABLED", "X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"): os.environ.pop(k, None)
        return sent, json.load(open(XP.STATE))
    def test_with_photo(self):
        sent, S = self.go(lambda cands, src="x_poster", budget=None: ("m1", cands[0][0], cands[0][1], None))
        self.assertEqual(sent, [["m1"]]); self.assertEqual(S["log"][-1]["media"], "m1"); self.assertEqual(S["first_photo_post"]["tweet"], "999")
    def test_photo_fails_still_posts(self):
        sent, S = self.go(lambda cands, src="x_poster", budget=None: (None, None, None, "exceeded 30s"))
        self.assertEqual(sent, [None]); self.assertTrue(S["log"][-1]["ok"])
class Live(unittest.TestCase):
    def test_live_uses_matching_verified_card(self):
        st = {"name": "AEW WrestleDream 2026", "brand": "AEW"}
        cards = [{"id": "cX", "title": "Kofi Kingston Wins At WrestleDream", "image": "https://cdn/kofi.jpg", "image_status": "key-verified"},
                 {"id": "cY", "title": "Will Ospreay Retains AEW World Title At WrestleDream", "image": "https://cdn/ospreay.jpg", "image_status": "cached:key-labelled"}]
        c = live_x.photo_candidates(st, {"winner": "Will Ospreay"}, cards)
        self.assertEqual(c[0], ("https://cdn/ospreay.jpg", "site-card:cY")); self.assertEqual(c[1][0], PROMO.format("aew"))
    def test_live_unverified_or_other_show_falls_back_to_logo(self):
        st = {"name": "AEW WrestleDream 2026", "brand": "AEW"}
        cards = [{"id": "c1", "title": "Will Ospreay Retains At WrestleDream", "image": "https://cdn/x.jpg", "image_status": "person-photo-unverified"},
                 {"id": "c2", "title": "Will Ospreay Wins At Wrestle Kingdom", "image": "https://cdn/y.jpg", "image_status": "key-verified"}]
        self.assertEqual(live_x.photo_candidates(st, {"winner": "Will Ospreay"}, cards)[0][0], PROMO.format("aew"))
if __name__ == "__main__": unittest.main()
