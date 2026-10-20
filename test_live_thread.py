"""python3 test_live_thread.py -- live X thread: promotion handle tagged in the ROOT (pinned) post only, within 280 chars."""
import unittest, live_thread as L
def st(slug, brand, kind, name, tag=None, date="2026-10-26"):
    return {"key": f"{date}-{slug}", "slug": slug, "brand": brand, "kind": kind, "name": name, "tag": tag, "date": date}
SHOWS = [(st("wwe-raw", "WWE", "weekly", "WWE Raw", "#WWERaw"), "@WWE"), (st("wwe-smackdown", "WWE", "weekly", "WWE SmackDown", "#SmackDown"), "@WWE"),
         (st("wwe-crown-jewel", "WWE", "ppv", "WWE Crown Jewel 2026", "#WWECrownJewel"), "@WWE"),
         (st("wwe-nxt", "WWE", "weekly", "WWE NXT", "#WWENXT"), "@WWENXT"), (st("wwe-nxt-halloween-havoc", "WWE", "ppv", "NXT Halloween Havoc 2026"), "@WWENXT"),
         (st("aew-dynamite", "AEW", "weekly", "AEW Dynamite", "#AEWDynamite"), "@AEW"), (st("aew-collision", "AEW", "weekly", "AEW Collision"), "@AEW"),
         (st("aew-wrestledream", "AEW", "ppv", "AEW WrestleDream 2026", "#AEWWrestleDream"), "@AEW"),
         (st("tna-impact", "TNA", "weekly", "TNA iMPACT!", "#TNAiMPACT"), "@ThisIsTNA"), (st("tna-bound-for-glory", "TNA", "ppv", "TNA Bound for Glory 2026"), "@ThisIsTNA"),
         (st("aaa-heroes-inmortales", "Global", "ppv", "AAA Héroes Inmortales 2026"), "@luchalibreaaa")]
UNMAPPED = [st("njpw-power-struggle", "Global", "ppv", "NJPW Power Struggle"), st("roh-final-battle", "Global", "ppv", "ROH Final Battle"),
            st("wwe-evolve", "WWE", "weekly", "WWE Evolve"), st("gcw-fight-club", "Indie", "ppv", "GCW Fight Club")]
class T(unittest.TestCase):
    def test_handles(self):
        for s, h in SHOWS: self.assertEqual(L.promo_handle(s), h, s["slug"])
        for s in UNMAPPED: self.assertIsNone(L.promo_handle(s), s["slug"])
    def test_root_tags_promotion(self):
        for s, h in SHOWS:
            for link in (True, False):
                t = L.root_text(s, link)
                self.assertIn(f"with {h}", t); self.assertEqual(t.count("@"), 1, t); self.assertLessEqual(L.XP.x_len(t), 280)
                self.assertEqual(L.XP.has_url(t), link)
        self.assertIn("Live results thread with @WWE:", L.root_text(SHOWS[0][0], True))
    def test_unmapped_root_has_no_tag(self):
        for s in UNMAPPED: self.assertNotIn("@", L.root_text(s, True))
    def test_long_name_stays_in_limit(self):
        s = st("wwe-crown-jewel", "WWE", "ppv", "WWE Crown Jewel " + "Very Long Name " * 6, "#WWECrownJewel")
        t = L.root_text(s, True); self.assertLessEqual(L.XP.x_len(t), 280); self.assertIn("@WWE", t)
    def test_replies_untagged(self):
        s = SHOWS[0][0]; m = {"en": "Seth Rollins defeated CM Punk", "id": "x"}
        self.assertNotIn("@", L.match_text(s, m)); self.assertNotIn("@", L.match_text(s, dict(m, title="change")))
if __name__ == "__main__": unittest.main()
