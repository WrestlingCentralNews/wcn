"""python3 test_current_promo.py -- tags and placeholder follow the subject's CURRENT promotion (official rosters,
data/rosters.json). 2026-10-23: 'Joe Hendry Believes He Can Become Top WWE Draw' was tagged WWE + TNA with the TNA logo
because an old brand list had Hendry under TNA and the summary said he 'rose to prominence in TNA'. No network, no AI."""
import unittest, os, time
os.environ.pop("AI_API_KEY", None)
import current, vision, editorial, roster
NOW = time.time()
def snap(names, n):
    pad = {f"filler {i}": {"name": f"Filler {i}", "first": NOW - 9e6, "last": NOW - 60} for i in range(n)}
    pad.update({roster.key(x): {"name": x, "first": NOW - 9e6, "last": NOW - 60} for x in names})
    return {"names": pad, "fetched": NOW - 60, "count": len(pad), "ok": True, "baseline": NOW - 9e6}
DB = {"WWE": snap(["Joe Hendry", "Cody Rhodes", "Trick Williams"], 120), "AEW": snap(["Chris Sabin", "Adam Copeland"], 80),
      "TNA": snap(["AJ Francis", "Mike Santana"], 40)}
HENDRY = {"id": "cf9396d9a9e3c", "title": "Joe Hendry Believes He Can Become Top WWE Draw",
          "raw_title": "Joe Hendry: I Know In My Heart I Can Be A Top Draw For WWE",
          "summary": "Joe Hendry rose to prominence in TNA Wrestling during 2024-25 before signing with WWE. Speaking to TV Insider, "
                     "Hendry said: \"I know in my heart that I can be a top draw for WWE.\"",
          "categories": ["WWE", "TNA"], "link": "https://www.fightful.com/x", "updates": [], "ts": 0}
class Base(unittest.TestCase):
    def setUp(self):
        self._db = current._db; current._db = lambda: DB
        self._ov = current._OV; current._OV = {}
        vision._C = {}; vision._PAGES.clear(); vision._PIX = None; vision.save = lambda: None
    def tearDown(self): current._db = self._db; current._OV = self._ov
class Official(Base):
    def test_listed_and_absent(self):
        self.assertEqual(current.official("Joe Hendry"), ({"WWE"}, {"AEW", "TNA"}))
    def test_unknown_name(self):
        self.assertEqual(current.official("Nobody Atall")[0], set())
    def test_stale_or_tiny_roster_ignored(self):
        db = {**DB, "TNA": {**DB["TNA"], "fetched": NOW - 30 * 86400}}
        self.assertEqual(current.official("Joe Hendry", db), ({"WWE"}, {"AEW"}))
        db = {"WWE": {**DB["WWE"], "count": 20}}
        self.assertEqual(current.official("Joe Hendry", db), (set(), set()))
    def test_hand_list_no_longer_has_hendry_in_tna(self):
        self.assertNotIn("Joe Hendry", editorial.ROSTER["TNA"].split("|")); self.assertIn("Joe Hendry", editorial.ROSTER["WWE"].split("|"))
class PastOnly(Base):
    def test_history_phrases(self):
        for s in ["He rose to prominence in TNA Wrestling during 2024-25 before signing with WWE.", "The former TNA World Champion spoke.",
                  "During his time in TNA he won the title.", "He left TNA in 2025."]:
            self.assertTrue(current.past_only("TNA", s), s)
    def test_present_or_future_mentions_count(self):
        for s in ["Hendry will appear at TNA Slammiversary.", "He is set to face Mike Santana on TNA Impact next week.",
                  "The former TNA champion returns to TNA tonight as part of the working agreement."]:
            self.assertFalse(current.past_only("TNA", s), s)
class Tags(Base):
    def test_hendry_story(self):
        c = dict(HENDRY); self.assertTrue(current.fix_tags(c)); self.assertEqual(c["categories"], ["WWE"])
    def test_current_promotion_leads(self):
        c = {**HENDRY, "categories": ["TNA", "WWE"]}; current.fix_tags(c); self.assertEqual(c["categories"], ["WWE"])
    def test_tna_only_tag_replaced(self):
        c = {**HENDRY, "categories": ["TNA"]}; current.fix_tags(c); self.assertEqual(c["categories"], ["WWE"])
    def test_crossover_headline_untouched(self):
        c = {**HENDRY, "title": "Joe Hendry To Appear At TNA Bound For Glory", "raw_title": "Joe Hendry Set For TNA Bound For Glory",
             "summary": "WWE's Joe Hendry will appear at TNA Bound for Glory.", "categories": ["TNA", "WWE"]}
        self.assertIsNone(current.fix_tags(c)); self.assertEqual(c["categories"], ["TNA", "WWE"])
    def test_partner_show_in_summary_kept(self):
        c = {**HENDRY, "title": "Joe Hendry Teases Big Return", "raw_title": "Joe Hendry Teases Big Return",
             "summary": "Joe Hendry is set to appear on TNA Impact next week under the working agreement.", "categories": ["TNA", "WWE"]}
        current.fix_tags(c); self.assertEqual(c["categories"], ["WWE", "TNA"])
    def test_look_back_keeps_old_promotion_second(self):
        c = {"id": "x1", "title": "AJ Francis Recalls Getting Heat In WWE Over Expressions Meeting", "raw_title": "AJ Francis recalls WWE heat",
             "summary": "AJ Francis recalled a meeting from his time in WWE.", "categories": ["WWE", "TNA"]}
        current.fix_tags(c); self.assertEqual(c["categories"], ["TNA", "WWE"])
    def test_old_promotion_history_in_summary_dropped(self):
        c = {"id": "x2", "title": "Cody Rhodes Links Neck Tattoo To Career Rise", "raw_title": "WWE's Cody Rhodes Says Career Has Been On Upward Trajectory",
             "summary": "Rhodes debuted the tattoo at AEW Revolution 2020, returned to WWE in 2022.", "categories": ["WWE", "AEW", "Global"]}
        current.fix_tags(c); self.assertEqual(c["categories"], ["WWE", "Global"])
    def test_hand_set_tags_win(self):
        current._OV = {"cf9396d9a9e3c": {"categories": ["TNA"]}}
        c = dict(HENDRY); self.assertIsNone(current.fix_tags(c)); self.assertEqual(c["categories"], ["WWE", "TNA"])
    def test_no_roster_data_no_change(self):
        current._db = lambda: {}
        c = dict(HENDRY); self.assertIsNone(current.fix_tags(c)); self.assertEqual(c["categories"], ["WWE", "TNA"])
    def test_unlisted_subject_untouched(self):
        c = {**HENDRY, "title": "Someone Unknown Talks TNA Past", "raw_title": "Someone Unknown Talks", "summary": "He rose to prominence in TNA."}
        self.assertIsNone(current.fix_tags(c))
class Placeholder(Base):
    def test_hendry_promotion_is_wwe(self):
        self.assertEqual(vision.promotion("Joe Hendry", HENDRY), "wwe")
    def test_look_back_story_uses_current_promotion(self):
        c = {"title": "Chris Sabin Recalls Motor City Machine Guns Helping TNA Sign The Young Bucks", "raw_title": "x", "summary": ""}
        self.assertEqual(vision.promotion("Chris Sabin", c), "aew")
    def test_past_promotion_not_story_promotion(self):
        self.assertEqual(current.past_promos(HENDRY, "Joe Hendry"), {"tna"})
    def test_other_story_photo_before_placeholder(self):
        good = "https://www.wrestlinginc.com/img/gallery/joe-hendry-reveals-favorite-wwe-entrances/l-intro.jpg"
        vision._C = {"choice3|cOTHER|Joe Hendry|abcd": {"image": good, "st": "key-labelled", "key": "Joe Hendry", "credit": None},
                     "choice3|cP|Joe Hendry|abce": {"image": vision.PROMO_CARD.format("wwe"), "st": "promo-logo:wwe", "key": "Joe Hendry"},
                     "choice3|cQ|Joe Hendry|abcf": {"image": "https://x/joe-hendry-and-randy-orton.jpg", "st": "key-labelled", "key": "Joe Hendry"}}
        bad = "https://cdn.example/maxresdefault-182.jpg"
        vision._C["v2|" + bad + "|Joe Hendry"] = {"ok": False, "who": "unknown"}; vision._VI = None
        c = {**HENDRY, "image": bad, "member_src": {bad: HENDRY["raw_title"]}}
        img, _, st = vision.choose(c, [bad], fetch=False)
        self.assertEqual((img, st), (good, "key-other-story"))
    def test_tna_era_photo_not_reused(self):
        old = "https://x/joe-hendry-tna-world-champion.jpg"
        vision._C = {"choice3|cOLD|Joe Hendry|a": {"image": old, "st": "key-labelled", "key": "Joe Hendry"}}
        self.assertIsNone(vision.person_photo("Joe Hendry", ["Joe Hendry"], frozenset({"wwe"}), HENDRY["summary"], "cX"))
    def test_single_subject_report_photo_before_placeholder(self):
        u = "https://cdn.example/IMG_0001.jpg"
        c = {**HENDRY, "image": u, "member_src": {u: "Joe Hendry Says He Can Be A Top Draw"}}
        img, _, st = vision.choose(c, [u], fetch=False)
        self.assertEqual((img, st), (u, "report-photo"))
    def test_match_report_photo_not_used(self):
        u = "https://cdn.example/IMG_0002.jpg"
        self.assertIsNone(vision.report_photo([u], {u: "Joe Hendry vs. JD McDonagh Set For Raw"}, "Joe Hendry"))
    def test_stale_cached_placeholder_rechecked(self):
        vision._C = {}
        c = {**HENDRY, "image": None, "member_src": {}}
        import hashlib
        k = "choice3|" + c["id"] + "|Joe Hendry|" + hashlib.md5(b"").hexdigest()[:8]
        vision._C[k] = {"image": vision.PROMO_CARD.format("tna"), "st": "promo-logo:tna", "key": "Joe Hendry"}
        img, _, st = vision.choose(c, [], fetch=False)
        self.assertEqual((img, st), (vision.PROMO_CARD.format("wwe"), "promo-logo:wwe"))
    def test_cached_placeholder_kept_when_still_right(self):
        c = {**HENDRY, "image": None, "member_src": {}}
        import hashlib
        k = "choice3|" + c["id"] + "|Joe Hendry|" + hashlib.md5(b"").hexdigest()[:8]
        vision._C = {k: {"image": vision.PROMO_CARD.format("wwe"), "st": "promo-logo:wwe", "key": "Joe Hendry"}}
        self.assertEqual(vision.choose(c, [], fetch=False)[2], "cached:promo-logo:wwe")
if __name__ == "__main__": unittest.main()
