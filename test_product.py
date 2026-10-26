"""python3 test_product.py  -- product-story photos (owner rule 2026-10-26): detection, store-first lookup order, filters, fallback.
No network, no paid calls: fetches and vision are stubbed."""
import unittest, time, product, vision
vision.CACHE_F = "/tmp/wcn_test_product_cache.json"; vision._C = {}
POS = ["WWE Xavier Woods and Ilja Dragunov Action Figures Up for Pre-Order", "Ringside Collectibles Launches Exclusive Natural Disasters WWE Figures",
       "WWE 2K26 Adds Street Fighter Elite Pack", "HOMAGE Launches Knicks-WWE Championship Shirt", "STARDOM Offers Venue Merchandise at Korakuen Hall",
       "Mattel Reveals WWE Elite 131 Lineup", "Jazwares Unveils New AEW Unrivaled Figures", "Mick Foley Announces New Book", "Topps Releases 2026 WWE Trading Cards",
       "WrestleMania 42 Blu-ray Release Date Revealed", "New Cody Rhodes Replica Title Available", "AEW Fight Forever DLC Pack Released"]
NEG = ["Hardys Book Tables Match For TNA iMPACT", "Hardys Book Special iMPACT! Following BFG", "Myles Borne Unfazed By Grayson Waller's Stephanie Vaquer Shirt",
       "Grayson Waller Made Vaquer T-Shirt That Didn't Air", "Nikki Bella Earns WWE Praise For Social Media And Merch", "WWE Sets Loaded NXT and Live Event Schedule",
       "Gunther Retains At Crown Jewel", "AEW Dynamite Viewership Figures Down", "Ilja Dragunov Debuts As All Elite At WrestleDream", "Booker T Books Reality of Wrestling Show"]
def card(t, raw="", cat=("WWE",), cid="cx", summary=""):
    return {"id": cid, "title": t, "raw_title": raw, "summary": summary, "categories": list(cat), "link": "https://www.pwinsider.com/article/1/x.html",
            "source": "PWInsider", "ts": time.time(), "first_ts": time.time()}
class Detect(unittest.TestCase):
    def test_pos(self):
        for t in POS: self.assertTrue(product.is_product(card(t)), t)
    def test_neg(self):
        for t in NEG: self.assertFalse(product.is_product(card(t)), t)
    def test_roundup_raw_ignored(self):
        c = card("WWE Sets Loaded NXT and Live Event Schedule", "WWE Action Figure Sale, Trick Williams' First WWE Championship Shot, Punk Vs. Gable & More")
        self.assertFalse(product.is_product(c))
    def test_kinds(self):
        self.assertEqual(product.kinds("WWE 2K26 Adds Street Fighter Elite Pack"), ["game"])
        self.assertIn("figure", product.kinds("Xavier Woods Action Figures"))
        self.assertTrue(product.kind_ok(["figure"], "WWE Elite Collection Xavier Woods Action Figure"))
        self.assertFalse(product.kind_ok(["figure"], "Ilja Dragunov - Unbesiegbar T-Shirt"))
    def test_stores(self):
        self.assertEqual(product.stores_for(card("New AEW Unrivaled Figures", cat=("AEW",)))[0], "https://shopaew.com/en-us")
        self.assertIn("https://creations.mattel.com", product.stores_for(card("WWE Xavier Woods Action Figures")))
        self.assertIn("https://tnamerch.com", product.stores_for(card("TNA Launches New Hardys T-Shirt", cat=("TNA",))))
        self.assertNotIn("https://creations.mattel.com", product.stores_for(card("WWE 2K26 Adds Street Fighter Elite Pack")))
    def test_unwrap_and_bad(self):
        self.assertEqual(product.unwrap("https://ci3.googleusercontent.com/meips/AB=s0-d-e1-ft#https://x.stripocdn.email/i/elite130_xavier1.jpg"),
                         "https://x.stripocdn.email/i/elite130_xavier1.jpg")
        for u in ["https://www.pwinsider.com/advertisement/a.jpg", "https://x.com/img/logo.png", "https://x.com/i/elite130_instagram.jpg", "https://x.com/a/spin.gif"]:
            self.assertTrue(product.BAD_IMG.search(u), u)
    def test_fresh_series_locale(self):
        now = 1793000000
        self.assertFalse(product.fresh("https://cdn.shopify.com/a.jpg?v=1742322129", now))
        self.assertTrue(product.fresh("https://cdn.shopify.com/a.jpg?v=1792000000", now))
        self.assertTrue(product.fresh("https://x.com/a.jpg", now))
        self.assertEqual(product.series("Mattel WWE Elite 130 figures"), {("elite", "130")})
        self.assertTrue(product.LOCALE.search("https://shop.mattel.com/products/wwe-figura-de-accion-elite-ilja-dragunov-jch96-es-mx"))
class Lookup(unittest.TestCase):
    def setUp(self):
        self.saved = {k: getattr(product, k) for k in ("store_links", "page_image", "shopify_search", "article_images", "is_product_photo", "usable", "_lead")}
        product._lead = lambda c: c["link"]; product.usable = lambda u, c: not product.BAD_IMG.search(u)
        product.store_links = lambda u: []; product.shopify_search = lambda b, q, n=10: []; product.article_images = lambda u: []
        product.is_product_photo = lambda u, w: None; vision._C = {}
        self.c = card("WWE Xavier Woods and Ilja Dragunov Action Figures Up for Pre-Order", cid="c8798825cbab4",
                      summary="New WWE action figures featuring Xavier Woods and Ilja Dragunov are now available for pre-order through Ringside Collectibles.")
    def tearDown(self):
        for k, v in self.saved.items(): setattr(product, k, v)
    def test_linked_store_page_first(self):
        product.store_links = lambda u: ["https://www.ringsidecollectibles.com/wwe-elite-130-toy-figures-xavier-elite130-04.html"]
        product.page_image = lambda u: ("https://www.ringsidecollectibles.com//mm5/graphics/00000001/33/elite130_xavier1.jpg", "Xavier Woods - WWE Elite 130")
        product.shopify_search = lambda b, q, n=10: [("WWE Elite Xavier Woods Action Figure", "https://creations.mattel.com/products/x", "https://cdn.shopify.com/x.jpg")]
        product.article_images = lambda u: [("https://x.stripocdn.email/i/sdcc2026_mattel_wwe_elite130_xavier1.jpg", "Action figure")]
        img, cr, st = product.find(self.c)
        self.assertEqual(st, "product:store-link"); self.assertIn("ringsidecollectibles.com", img); self.assertEqual(cr["text"], "Photo: Ringside Collectibles")
    def test_store_search_before_article(self):
        product.shopify_search = lambda b, q, n=10: [("Ilja Dragunov - Unbesiegbar T-Shirt", "https://shopaew.com/en-us/products/t", "https://cdn.shopify.com/t.png"),
                                                    ("WWE Elite Collection Ilja Dragunov Action Figure", "https://creations.mattel.com/products/i", "https://cdn.shopify.com/i.jpg")]
        product.article_images = lambda u: [("https://x.stripocdn.email/i/sdcc2026_mattel_wwe_elite130_ilja1.jpg", "")]
        img, cr, st = product.find(self.c)
        self.assertEqual((img, st), ("https://cdn.shopify.com/i.jpg", "product:store"))   # the figure, never the t-shirt
    def test_old_store_product_skipped(self):
        product.shopify_search = lambda b, q, n=10: [("WWE Figura de Acción Elite Ilja Dragunov", "https://shop.mattel.com/products/wwe-figura-de-accion-elite-ilja-dragunov-jch96-es-mx",
                                                     "https://cdn.shopify.com/a.jpg?v=1742322129")]
        product.article_images = lambda u: [("https://x.stripocdn.email/i/elite130_instagram.jpg", ""), ("https://www.pwinsider.com/advertisement/ad.jpg", ""),
                                            ("https://x.stripocdn.email/i/sdcc2026_mattel_wwe_elite130_xavier1.jpg", "Action figure of wrestler"),
                                            ("https://x.stripocdn.email/i/sdcc2026_mattel_wwe_elite130_ilja1.jpg", "Wrestling action figure")]
        img, cr, st = product.find(self.c)
        self.assertEqual(st, "product:article"); self.assertIn("elite130_xavier1", img)   # a named figure photo in article order, never the social banner or the ad
        self.assertEqual(cr["text"], "Photo: Ringside Collectibles via PWInsider")
    def test_vision_rejects_unlabelled(self):
        product.article_images = lambda u: [("https://www.pwinsider.com/images/IMG_0001.jpg", "")]
        product.is_product_photo = lambda u, w: False
        self.assertIsNone(product.find(self.c))
        product.is_product_photo = lambda u, w: True
        self.assertEqual(product.find(self.c)[2], "product:article")
        product.is_product_photo = lambda u, w: None   # no budget: unlabelled photo is not trusted
        self.assertIsNone(product.find(self.c))
    def test_other_wrestler_file_skipped(self):
        product.article_images = lambda u: [("https://x.com/i/cody-rhodes-action-figure.jpg", "")]
        self.assertIsNone(product.find(self.c))
    def test_pick_non_product_and_cache(self):
        self.assertIsNone(product.pick(card("Gunther Retains At Crown Jewel")))
        n = [0]
        def ai(u): n[0] += 1; return [("https://x.stripocdn.email/i/sdcc2026_mattel_wwe_elite130_xavier1.jpg", "")]
        product.article_images = ai
        a = product.pick(self.c); b = product.pick(self.c)
        self.assertEqual(a[0], b[0]); self.assertEqual(b[2], "cached:product:article"); self.assertEqual(n[0], 1)
    def test_miss_cached_then_fallback(self):
        self.assertIsNone(product.pick(self.c))
        product.article_images = lambda u: [("https://x.stripocdn.email/i/sdcc2026_mattel_wwe_elite130_xavier1.jpg", "")]
        self.assertIsNone(product.pick(self.c))   # miss remembered for 12 h: the normal rules pick (no refetch every run)
class Wiring(unittest.TestCase):
    def test_tag_untouched_and_x_ok(self):
        import x_poster
        self.assertTrue(x_poster.PHOTO_OK.match("product:store")); self.assertTrue(x_poster.PHOTO_OK.match("cached:product:article"))
        c = card("WWE Xavier Woods and Ilja Dragunov Action Figures Up for Pre-Order"); before = list(c["categories"])
        product.is_product(c); product.stores_for(c); self.assertEqual(c["categories"], before)
    def test_own_photo_probe(self):
        import imgmeta
        self.assertEqual(imgmeta.probe("https://wrestlingcentralnews.com/img/p/woods-dragunov-elite-figures.jpg"), (1600, 900))
    def test_override_present(self):
        import json
        o = [x for x in json.loads(open("image_overrides.json").read())["items"] if "c8798825cbab4" in x.get("ids", [])]
        self.assertEqual(o[0]["image"], "https://wrestlingcentralnews.com/img/p/woods-dragunov-elite-figures.jpg")
if __name__ == "__main__": unittest.main()
