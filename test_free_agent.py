"""python3 test_free_agent.py -- free agents / wrestlers between promotions (owner rule 2026-10-23, Max Caster): photo first,
else the LAST promotion's card if they left within ~6 months, else the WCN card; departure tracking (hand / roster / text)."""
import unittest, json, os, tempfile, time
import departed, vision, current, aggregator
DAY = 86400
class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.s = (departed.SEEN, departed.HAND, current.official)
        departed.SEEN = os.path.join(self.d, "seen.json"); departed.HAND = os.path.join(self.d, "hand.json")
        current.official = lambda name, db=None, now=None: (set(), {"WWE", "AEW", "TNA"})
        self.now = time.time()
    def tearDown(self): departed.SEEN, departed.HAND, current.official = self.s
    def hand(self, **items): json.dump({"items": items}, open(departed.HAND, "w"))
    def c(self, title, summary="", age=0): return {"id": "c1", "title": title, "raw_title": title, "summary": summary, "ts": self.now - age, "first_ts": self.now - age}
class Text(Base):
    def test_patterns(self):
        for t, p in [("TNA Ended Zed Nobody's Deal After Bound For Glory", "TNA"), ("Zed Nobody Released By WWE", "WWE"),
                     ("Zed Nobody Comments On His Departure From AEW", "AEW"), ("WWE Released A Statement On Zed Nobody", None), ("Zed Nobody Left Impact Wrestling In 2024", "TNA"), ("Zed Nobody Parts Ways With TNA", "TNA"),
                     ("Zed Nobody No Longer With AEW", "AEW"), ("Zed Nobody Fired From NXT", "WWE")]:
            r = departed.from_text(self.c(t), "Zed Nobody"); self.assertEqual(r[0] if r else None, p, t)
    def test_summary_and_other_person(self):
        self.assertEqual(departed.from_text(self.c("Zed Nobody Speaks Out", "TNA President ended his pay-per-appearance deal. TNA ended his deal after Bound for Glory."), "Zed Nobody")[0], "TNA")
        self.assertIsNone(departed.from_text(self.c("Someone Else Released By WWE"), "Zed Nobody"))
        self.assertIsNone(departed.from_text(self.c("Zed Nobody Wins TNA Title"), "Zed Nobody"))
    def test_dates(self):
        c = self.c("Zed Nobody Details Injuries After WWE Exit", "He noted his body was in bad shape following his 2021 WWE release.")
        r = departed.from_text(c, "Zed Nobody"); self.assertEqual(r[0], "WWE"); self.assertEqual(time.gmtime(r[1]).tm_year, 2021)
        self.assertEqual(departed.card("Zed Nobody", c), "")   # left 2021 -> WCN card
        c = self.c("Zed Nobody Explains Exit", "Zed Nobody left AEW in 2023 to join WWE. After leaving WWE in September 2025, Zed Nobody returned.")
        r = departed.from_text(c, "Zed Nobody"); self.assertEqual((r[0], time.gmtime(r[1])[:2]), ("WWE", (2025, 9)))
        self.assertIsNone(departed.from_text(self.c("Zed Nobody Recalls Unhappy 2014 WWE Exit"), "Zed Nobody"))
    def test_remembered(self):
        departed.last("Zed Nobody", self.c("Zed Nobody Released By AEW", age=3 * DAY))
        self.assertEqual(departed.last("Zed Nobody")[0], "AEW")   # later story with no departure text
class Window(Base):
    def test_recent_is_last_promo(self):
        self.hand(**{"Zed Nobody": {"promo": "TNA", "date": time.strftime("%Y-%m-%d", time.gmtime(self.now - 11 * DAY))}})
        self.assertEqual(vision.promotion("Zed Nobody", self.c("Zed Nobody Is Now A Free Agent")), "tna")
        self.assertEqual(vision.promotion("Zed Nobody", self.c("WWE Interested In Zed Nobody")), "tna")
    def test_old_is_wcn_card(self):
        self.hand(**{"Zed Nobody": {"promo": "TNA", "date": time.strftime("%Y-%m-%d", time.gmtime(self.now - 200 * DAY))}})
        self.assertEqual(departed.card("Zed Nobody"), "")
        self.assertIsNone(vision.promotion("Zed Nobody", self.c("Zed Nobody Is Now A Free Agent")))
    def test_unknown_and_retired(self):
        self.assertIsNone(vision.promotion("Zed Nobody", self.c("Zed Nobody Is Now A Free Agent")))
        self.hand(**{"Zed Nobody": {"promo": "AEW", "date": time.strftime("%Y-%m-%d", time.gmtime(self.now - DAY))}})
        self.assertIsNone(vision.promotion("Zed Nobody", self.c("Zed Nobody Announces Retirement")))
    def test_newest_source_wins_and_new_signing(self):
        self.hand(**{"Zed Nobody": {"promo": "AEW", "date": time.strftime("%Y-%m-%d", time.gmtime(self.now - 300 * DAY))}})
        self.assertEqual(vision.promotion("Zed Nobody", self.c("Zed Nobody Released By TNA", age=DAY)), "tna")
        self.assertEqual(vision.promotion("Zed Nobody", self.c("Zed Nobody Signs With WWE")), "wwe")   # the new promotion
    def test_still_rostered_unaffected(self):
        current.official = lambda name, db=None, now=None: ({"WWE"}, {"AEW", "TNA"})
        self.hand(**{"Zed Nobody": {"promo": "TNA", "date": time.strftime("%Y-%m-%d", time.gmtime(self.now - DAY))}})
        self.assertIsNone(departed.card("Zed Nobody") and vision.free_agent("Zed Nobody", self.c("Zed Nobody leaves")))
    def test_roster_dropoff(self):
        db = {"AEW": {"fetched": self.now, "count": 100, "names": {"zed nobody": {"name": "Zed Nobody", "first": self.now - 90 * DAY, "last": self.now - 5 * DAY}}}}
        self.assertEqual(departed.from_rosters("Zed Nobody", db)[0], "AEW")
        db["AEW"]["names"]["zed nobody"]["last"] = self.now
        self.assertIsNone(departed.from_rosters("Zed Nobody", db))
class Caster(unittest.TestCase):
    def test_hand_table(self):
        h = json.load(open(departed.HAND))["items"]["Max Caster"]; self.assertEqual(h["promo"], "TNA")
        self.assertLessEqual(time.time() - departed._ts(h["date"]), departed.RECENT)
    def test_photo_override(self):
        c = [{"id": "c289bac580ffb", "title": "Contract News: Inside Word On Max Caster's TNA Deal", "link": "https://sports.yahoo.com/articles/backstage-news-max-casters-tna-181446931.html",
              "image": "https://wrestlingcentralnews.com/img/promo/tna.jpg", "image_status": "promo-logo:tna", "sources": 1, "updates": []}]
        aggregator.image_overrides(c)
        self.assertIn("Untitled-Design-8.jpg", c[0]["image"])
if __name__ == "__main__": unittest.main()
