"""python3 test_stale.py -- old articles re-dated by a feed never reach a current event page; hub episode attribution fixes."""
import unittest, datetime as dt, time
import stale, hubs
def ts(s): return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())
ALPHA = {"id": "17861aae1fd3", "title": "American Alpha to defend SmackDown Tag Titles in Turmoil", "raw_title": "American Alpha prepare for tag team turmoil",
         "link": "https://www.wwe.com/shows/eliminationchamber/2017/smackdown-tag-team-title-turmoil-match", "source": "WWE",
         "ts": ts("2026-10-16T07:00:00"), "image": "https://www.wwe.com/f/styles/og_image/public/all/2017/01/20170131_EC_Match_tagteams.jpg",
         "categories": ["WWE"], "kind": {"type": "match"}, "summary": "SmackDown Tag Team Champions American Alpha will defend their titles at WWE Elimination Chamber on February 12.",
         "body": "The match format was the same type of bout that American Alpha won on the November 22, 2016 episode of SmackDown LIVE.", "updates": []}
def cl(title, when, kind="results", cats=("WWE",), link=None, updates=(), first=None, raw=None):
    t = ts(when)
    return {"id": "c" + str(abs(hash(title)))[:12], "title": title, "raw_title": raw or title, "link": link or "https://www.fightful.com/wrestling/x-" + str(abs(hash(title))),
            "source": "Fightful", "ts": t, "first_ts": first or t, "lead_ts": t, "categories": list(cats), "kind": {"type": kind}, "updates": list(updates)}
class Stale(unittest.TestCase):
    def test_american_alpha_is_stale(self):
        self.assertIn("URL dated 2017", stale.reason(ALPHA))
    def test_official_old_photo_and_years(self):
        a = dict(ALPHA, link="https://www.wwe.com/article/american-alpha-turmoil")   # no date in the URL: photo 2017 + text only 2016
        self.assertTrue(stale.reason(a))
        b = dict(a, body=a["body"] + " He returns at Crown Jewel 2026.")   # mentions the current year -> fresh
        self.assertIsNone(stale.reason(b))
        c = dict(a, source="Wrestling Observer")   # outlets reuse old file photos for interviews: rule is official sites only
        self.assertIsNone(stale.reason(c))
    def test_url_dates(self):
        self.assertEqual(stale.url_date("https://www.postwrestling.com/2026/09/30/mlw-returning/"), dt.date(2026, 9, 30))
        self.assertEqual(stale.url_date("https://www.ticketnews.com/2026/07/mattel-aaa/"), dt.date(2026, 7, 31))
        self.assertIsNone(stale.url_date("https://www.wwe.com/shows/smackdown/x"))
        self.assertIsNone(stale.url_date("https://www.fightful.com/wrestling/334110-tony-khan-jon-moxley/"))
        fresh = dict(ALPHA, link="https://www.postwrestling.com/2026/10/15/smackdown-preview/", body="", image=None)
        self.assertIsNone(stale.reason(fresh))
        self.assertIsNotNone(stale.reason(dict(fresh, link="https://www.ticketnews.com/2026/07/mattel-aaa/")))
    def test_never_on_event_page(self):
        good = cl("Cody Rhodes Punts Baron Corbin On SmackDown", "2026-10-17T02:20:00")
        a = dict(ALPHA, first_ts=ALPHA["ts"])
        hubs.tag([a, good])
        self.assertNotIn("hub", a)
        self.assertEqual(good["hub"]["date"], "2026-10-16")
class Episodes(unittest.TestCase):
    def test_early_member_doesnt_drag_to_last_week(self):
        c = cl("R-Truth Injury Update After SmackDown Match", "2026-10-18T16:57:00", kind="news", first=ts("2026-10-14T22:37:00"),
               updates=[{"ts": ts("2026-10-17T02:06:00"), "title": "SmackDown Match Halted After R-Truth Injury"},
                        {"ts": ts("2026-10-14T22:37:00"), "title": "Paige clashes with Nikki Bella"}])
        hubs.tag([c]); self.assertEqual(c["hub"]["date"], "2026-10-16")
    def test_named_date_not_an_airing(self):
        c = cl("Mystery Wrestling Direct Set For November 5", "2026-10-15T19:03:00", kind="news", cats=("AEW",),
               raw="Mystery Wrestling Direct Set For 11/5, AEW Dynamite Highlights, More")
        hubs.tag([c]); self.assertNotIn("hub", c)
    def test_named_airing_outside_window(self):
        c = cl("Tony Khan Reveals Original Plan For 9/30 Dynamite", "2026-10-18T06:58:00", kind="news", cats=("AEW",))
        hubs.tag([c]); self.assertEqual(c["hub"]["date"], "2026-09-30")
    def test_forward_looking_dark_match(self):
        c = cl("AAA Trios Title Dark Match Set For Raw", "2026-10-16T04:00:00", kind="match", raw="Dark match AAA trios title defense announced for Monday's WWE Raw")
        hubs.tag([c]); self.assertEqual(c["hub"]["date"], "2026-10-19")
    def test_manual_exclude(self):
        c = cl("Cody Rhodes Punts Baron Corbin On SmackDown", "2026-10-17T02:20:00")
        old = hubs._excluded; hubs._excluded = lambda: {c["link"]}
        try: hubs.tag([c]); self.assertNotIn("hub", c)
        finally: hubs._excluded = old
if __name__ == "__main__": unittest.main()
