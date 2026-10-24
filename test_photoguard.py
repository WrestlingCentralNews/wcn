"""python3 test_photoguard.py -- 360 panoramas / unrelated scenery never become a story photo, and 'free live stream' spam
pages are never a source (2026-10-24: a Japanese town's krpano barrel-room panorama on 'WWE SmackDown Preview For October 23').
No network, no AI calls."""
import unittest, os
os.environ.pop("AI_API_KEY", None)
import photoguard, imgmeta, editorial, enrich, vision
PANO = "https://www.town.shodoshima.lg.jp/section/VR_choseiyoran/shodoshima349data/thumbnail.jpg"
SPAM = {"source": "小豆島町", "via": "Google News: WWE", "raw_title": "(LIVESTREAMs)! WWE SmackDown 𝐋𝐈𝐕𝐄 Ｆｒｅｅ 𝐒𝐭𝐑𝐞𝐀𝐦 Wrestling 23 October, 2026",
        "link": "https://www.town.shodoshima.lg.jp/section/VR_choseiyoran/shodoshima349.html?xml=data:video/mp4;base64,PGtycGFubz4=&id=wwe-smackdown-live-espn-gs8a14",
        "image": PANO}
F4W = "https://www.f4wonline.com/wp-content/uploads/2026/05/WWE-SmackDown-Logo-Arena-2026.jpg"
class Pano(unittest.TestCase):
    def test_url_tokens(self):
        self.assertTrue(photoguard.pano_url(PANO))
        for u in ("https://a/b/beach-360.jpg", "https://a/pano/1.jpg", "https://a/equirectangular_hall.jpg", "https://a/vtour/t.jpg", "https://a/krpano/x.jpg", "https://www.uco.es/scai/visita_virtual/SCAI UCOdata/thumbnail.jpg"):
            self.assertTrue(photoguard.pano_url(u), u)
        for u in ("https://cdn/x/wwe-raw-1360x765.jpg", "https://a/b/Orton-300x360.png", "https://a/b/panama-city.jpg", "https://a/b/Varsity.jpg", F4W):
            self.assertFalse(photoguard.pano_url(u), u)
    def test_gpano_xmp(self):
        self.assertTrue(photoguard.pano_bytes(b'\xff\xd8...<x:xmpmeta><rdf:Description GPano:ProjectionType="equirectangular"'))
        self.assertTrue(photoguard.pano_bytes(b"<GPano:ProjectionType>equirectangular</GPano:ProjectionType>"))
        self.assertFalse(photoguard.pano_bytes(b"\xff\xd8\xff\xe0JFIF ordinary photo"))
    def test_shape(self):
        self.assertEqual(photoguard.shape(3000, 800), "extreme-shape")
        self.assertEqual(photoguard.shape(300, 900), "extreme-shape")
        self.assertIsNone(photoguard.shape(1200, 600))               # 2:1 from a wrestling outlet is a normal header
        self.assertEqual(photoguard.shape(400, 200, generic=True), "panorama")
        self.assertIsNone(photoguard.shape(1600, 900, generic=True))
    def test_generic_source_needs_wrestling_words(self):
        self.assertTrue(photoguard.generic_source(SPAM, set()))
        self.assertEqual(photoguard.reject("https://town.example.jp/data/thumbnail.jpg", {**SPAM, "link": "https://town.example.jp/a"}), "off-topic-generic")
        self.assertIsNone(photoguard.reject("https://town.example.jp/data/cody-rhodes-smackdown.jpg", {**SPAM, "link": "https://town.example.jp/a"}))
        self.assertIsNone(photoguard.reject("https://www.f4wonline.com/x/IMG_1234.jpg", {"source": "Wrestling Observer", "link": "https://www.f4wonline.com/a"}))
        self.assertIsNone(photoguard.reject("https://www.ringsidenews.com/x/IMG_1234.jpg", {"source": "Ringside News", "link": "https://www.ringsidenews.com/a"}))
    def test_generic_news_outlet_camera_names_ok(self):   # Tony Khan photo on AOL, Montez Ford on Bleeding Cool (live 2026-10-24)
        self.assertIsNone(photoguard.reject("https://hermes.media.transform.aol.com/00c2b29b/w_1200/h", {"source": "AOL.com", "link": "https://www.aol.com/articles/x"}))
        self.assertIsNone(photoguard.reject("https://bleedingcool.com/wp-content/uploads/2021/05/E2g9CkYXMAI2Eku-2000x1125.jpeg", {"source": "Bleeding Cool News", "link": "https://bleedingcool.com/x"}))
        self.assertEqual(photoguard.reject("https://www.uco.es/x/banner.jpg", {"source": "Universidad de Córdoba (UCO)", "link": "https://www.uco.es/x"}), "off-topic-generic")
    def test_unusable_from_cache(self):
        imgmeta._C = {PANO: {"best": [PANO, 400, 200], "v": 6}, "https://x/banner.jpg": {"best": ["https://x/banner.jpg", 2400, 600], "v": 6},
                      "https://x/ok.jpg": {"best": ["https://x/ok.jpg", 1200, 675], "v": 6}}
        try:
            self.assertEqual(imgmeta.unusable(PANO), "panorama")
            self.assertEqual(imgmeta.unusable("https://x/banner.jpg"), "extreme-shape")
            self.assertIsNone(imgmeta.unusable("https://x/ok.jpg"))
            cl = [{"image": PANO}]; imgmeta.apply(cl)
            self.assertIsNone(cl[0]["image"]); self.assertEqual(cl[0]["image_status"], "panorama")
        finally: imgmeta._C = None
class Choose(unittest.TestCase):
    def setUp(self):
        vision._C = {}; vision._PAGES.clear(); vision.save = lambda: None
    def test_preview_never_gets_the_panorama(self):
        c = {"id": "t-sd", "title": "WWE SmackDown Preview For October 23", "raw_title": "WWE Friday Night Smackdown On USA Network Preview",
             "summary": "WWE SmackDown is scheduled for tonight at the Toyota Arena in Ontario, California.", "link": "https://e.org/sd",
             "image": PANO, "member_src": {PANO: SPAM["raw_title"], F4W: "WWE SmackDown Preview for October 23"}, "updates": [], "ts": 0}
        img, _, st = vision.choose(c, [PANO, F4W], budget_ok=False, fetch=False)
        self.assertNotEqual(img, PANO, st)
class Spam(unittest.TestCase):
    def test_stream_spam(self):
        self.assertEqual(editorial.stream_spam(SPAM), "stream spam")
        for t in ("%*(((LIVESTREAM TV>)))* WWE SmackDown Wrestling Live Stream", "[ＴＶ ＣＨＡＮＮＥＬ] WWE SmackDown Live 𝐒𝐭𝐫𝐞𝐚𝐦 Wrestling",
                  "++[LIVESTREAMS]TV!!AEW WrestleDream Live Streaming Wrestling Free Online 2026"):
            self.assertEqual(editorial.stream_spam({"source": "Universidad de Córdoba (UCO)", "raw_title": t, "link": "https://www.uco.es/x"}), "stream spam", t)
    def test_real_news_kept(self):
        for s, t in (("Sports Illustrated", "WWE SmackDown Preview (10/23/26): Start Time, Match Card, How To Watch & Live Stream"),
                     ("Cageside Seats", "AEW WrestleDream live stream: The Buy In"), ("Fightful", "AEW WrestleDream Buy-In Live Stream"),
                     ("Ringside News", "Key Executive Who Helped Put Together WWE's Netflix Deal Leaving Streaming Giant"),
                     ("| Cord Cutters News", "Prime Video Adds More Wrestling as MLW Expands Streaming Reach")):
            self.assertIsNone(editorial.stream_spam({"source": s, "raw_title": t, "link": "https://e.org/a"}), t)
    def test_cluster_drops_panorama_member_photo(self):
        a = {"id": "a1", "link": "https://e.org/a1", "source": "Wrestling Observer", "raw_title": "WWE SmackDown Preview for October 23", "title": "WWE SmackDown Preview for October 23",
             "summary": "", "image": None, "ts": 2, "categories": ["WWE"], "kind": {"type": "news"}}
        self.assertTrue(enrich._scenery({**SPAM}))
        self.assertFalse(enrich._scenery({**a, "image": F4W}))
class Notice(unittest.TestCase):   # 2026-10-24 'This Week's Gotham Wrestling Now Streaming' (c764129f9ef72)
    def test_streaming_notice(self):
        for t in ("THIS WEEK'S EDITION OF GOTHAM WRESTLING IS NOW STREAMING", "This Week's Edition Of WWE Main Event Is Now Streaming", "This Week's Edition Of TNA Xplosion Is Now Streaming"):
            self.assertEqual(editorial.stream_notice({"raw_title": t}), "streaming notice", t)
        for t in ("WWE Unreal Season 2 Is Now Streaming On Netflix", "WWE Main Event Preview", "This Week's Edition Of Uwn Championship Wrestling Tv", "WWE SmackDown Preview For October 23"):
            self.assertIsNone(editorial.stream_notice({"raw_title": t}), t)
if __name__ == "__main__": unittest.main()
