"""python3 test_img_promo.py -- a story's photo may not show another promotion's branding (2026-10-22: NXT logo on
'AEW Blood And Guts 2026 Match Set' from a head-to-head ratings article's split graphic). No network, no AI calls."""
import unittest, os
os.environ.pop("AI_API_KEY", None)
import enrich, vision, pubgate
RS = "https://www.ringsidenews.com/wp-content/uploads/2026/10/wwe-nxt-expected-to-go-head-to-head-with-aew-blood-amp-guts-on-november-4-00.jpg"
M411 = "https://411mania.com/wp-content/uploads/2026/09/aew-blood-guts-26-e1789269474892.jpg"
NEUTRAL = "https://cdn.example/IMG_4411.jpg"
H2H = "WWE NXT Expected to Go Head-to-Head With AEW Blood & Guts on November 4"
AEW = frozenset({"aew"})
class Foreign(unittest.TestCase):
    def test_split_file_name_is_strong(self):
        f, strong = enrich.foreign_promo(RS, AEW)
        self.assertEqual(f, {"wwe"}); self.assertTrue(strong)
    def test_own_promotion_poster_ok_even_from_h2h_article(self):
        self.assertEqual(enrich.foreign_promo(M411, AEW, src="WWE NXT Reportedly Set to Go Head-to-Head With AEW Blood & Guts 2026")[0], frozenset())
    def test_unlabelled_photo_from_h2h_article_is_weak(self):
        f, strong = enrich.foreign_promo(NEUTRAL, AEW, src=H2H)
        self.assertEqual(f, {"wwe"}); self.assertFalse(strong)
    def test_unlabelled_photo_from_plain_article_ok(self):
        self.assertEqual(enrich.foreign_promo(NEUTRAL, AEW, src="AEW Blood And Guts 2026 Will Feature")[0], frozenset())
    def test_story_naming_both_allows_split(self):
        self.assertEqual(enrich.foreign_promo(RS, frozenset({"aew", "wwe"}))[0], frozenset())
    def test_alt_text_counts(self):
        self.assertTrue(enrich.foreign_promo(NEUTRAL, AEW, label="TNA Knockouts title belt")[0])
    def test_no_story_promotion_no_verdict(self):
        self.assertEqual(enrich.foreign_promo(RS, frozenset())[0], frozenset())
    def test_combat_crossover_ok(self):
        u = "https://cdn.example/wwe-star-boxing-debut.jpg"
        self.assertEqual(enrich.foreign_promo(u, frozenset({"wwe"}), story_text="WWE Star Set For Boxing Debut")[0], frozenset())
    def test_img_clash_needs_every_promotion(self):
        self.assertTrue(enrich.img_clash(RS, frozenset(), AEW))
        self.assertFalse(enrich.img_clash(M411, frozenset(), AEW))
        self.assertTrue(enrich.img_clash("https://f/WWE-Logo-2026.jpg", frozenset(), frozenset({"tna"})))
    def test_former_promotion_mention_allows_old_photo(self):   # Max Caster's Dynamite photo on a 'former AEW champion' story
        u = "https://w/Screenshot-max-caster-entrance-dynamite.jpg"
        self.assertEqual(enrich.foreign_promo(u, frozenset({"tna"}), story_text="The former AEW World Tag Team Champion appeared at TNA's Bound for Glory")[0], frozenset())
        self.assertTrue(enrich.foreign_promo(u, frozenset({"tna"}), story_text="Caster appeared at TNA's Bound for Glory")[0])
class Choose(unittest.TestCase):
    def setUp(self):
        vision._C = {}; vision._PAGES.clear()
        vision.save = lambda: None
    def card(self, image, members, src=None):
        return {"id": "t-bg", "title": "AEW Blood and Guts 2026 Match Set", "raw_title": "AEW Blood And Guts 2026 Will Feature....",
                "summary": "The November 4 Blood and Guts event in Jacksonville will be headlined by a WarGames-style match.",
                "link": "https://e.org/bg", "image": image, "member_src": src or {}, "updates": [], "ts": 0}
    def test_split_graphic_skipped_for_next_report(self):
        c = self.card(RS, [RS, M411], {RS: H2H, M411: "WWE NXT Reportedly Set to Go Head-to-Head With AEW Blood & Guts 2026"})
        img, _, st = vision.choose(c, [RS, M411], fetch=False)
        self.assertEqual(img, M411)
    def test_split_graphic_only_falls_back_to_promo_card(self):
        img, _, st = vision.choose(self.card(RS, [RS], {RS: H2H}), [RS], fetch=False)
        self.assertEqual(img, vision.PROMO_CARD.format("aew")); self.assertIn("promo", st)
    def test_weak_signal_without_vision_budget_is_skipped(self):
        img, _, _ = vision.choose(self.card(NEUTRAL, [NEUTRAL], {NEUTRAL: H2H}), [NEUTRAL], fetch=False)
        self.assertEqual(img, vision.PROMO_CARD.format("aew"))
    def test_weak_signal_vision_says_clean_keeps_photo(self):
        vision._C = {"b1|" + NEUTRAL + "|WWE or NXT": {"ok": False}}
        img, _, _ = vision.choose(self.card(NEUTRAL, [NEUTRAL], {NEUTRAL: H2H}), [NEUTRAL], fetch=False)
        self.assertEqual(img, NEUTRAL)
    def test_no_key_story_takes_next_report_photo(self):
        c = self.card(RS, [RS, M411], {RS: H2H}); c["title"] = c["raw_title"] = "AEW Sets Two Cage Matches"
        img, _, st = vision.choose(c, [RS, M411], fetch=False)
        self.assertEqual((img, st), (M411, "no-names"))
class Cluster(unittest.TestCase):
    def test_cluster_never_picks_split_graphic(self):
        arts = [{"id": "a1", "raw_title": "AEW Blood And Guts 2026 Will Feature....", "title": "AEW Blood And Guts 2026 Will Feature",
                 "summary": "AEW Blood and Guts match set.", "link": "https://e.org/1", "source": "PWInsider", "ts": 100, "image": None, "categories": ["AEW"]}]
        arts.append({**arts[0], "id": "a2", "link": "https://e.org/2", "source": "Ringside News", "raw_title": H2H, "title": H2H, "image": RS, "ts": 90})
        cs = [c for c in enrich.cluster(arts) if c["link"] == "https://e.org/1"]
        self.assertTrue(cs)
        for c in cs:
            self.assertNotIn(RS, c.get("member_images", [])); self.assertNotEqual(c.get("image"), RS)
if __name__ == "__main__": unittest.main()
