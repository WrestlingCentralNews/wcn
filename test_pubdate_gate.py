"""python3 test_pubdate_gate.py -- 2026-10-22 Penta / Usos fixes: publish-time verified-date gate (fail closed), junk-paragraph
filter that kept dropping real paragraphs, and headline framing guards (inverted choice, recollection presented as new)."""
import unittest, time, freshness, enrich, framing, pubgate
NOW = 1792710000   # 2026-10-22 ~22:20 UTC
H = 3600
def art(link, src="PWInsider", **k):
    a = {"id": link[-6:], "link": link, "source": src, "raw_title": "Some Story", "title": "Some Story", "ts": NOW - H, "added": NOW - H}
    a.update(k); return a
def story(lead, *others):
    return {"id": "c" + lead["id"], "link": lead["link"], "title": lead["title"], "raw_title": lead["raw_title"], "source": lead["source"],
            "updates": [{"link": o["link"], "source": o["source"], "ts": o["ts"], "title": o["title"]} for o in others]}
class DateGate(unittest.TestCase):
    def test_old_live_report_blocked(self):   # Usos live Raw report (page 2026-10-20 02:20) re-clustered into a new story 2 days later
        a = art("https://www.pwinsider.com/article/212911/the-usos-speak-live-ongoing-wwe-raw-report.html", pub_ts=NOW - 53 * H, ts=NOW - 2 * H)
        r = freshness.publish_check(story(a), {a["link"]: a}, NOW)
        self.assertTrue(r and r.startswith("stale"), r)
    def test_fresh_page_date_passes(self):
        a = art("https://www.wrestlinginc.com/2294871/wwe-aew-penta-family-helped-choose/", "Wrestling Inc", pub_ts=NOW - 2 * H)
        self.assertIsNone(freshness.publish_check(story(a), {a["link"]: a}, NOW))
    def test_feed_date_alone_fails_closed(self):   # fresh feed/Google date but no page date -> held
        a = art("https://www.fightful.com/wrestling-news/some-story", "Fightful", ts=NOW - H)
        r = freshness.publish_check(story(a), {a["link"]: a}, NOW)
        self.assertTrue(r and r.startswith("unverified date"), r)
        self.assertTrue(freshness.needs_recheck(story(a), {a["link"]: a}))
        a["pubchk2"] = 3; self.assertFalse(freshness.needs_recheck(story(a), {a["link"]: a}))
    def test_url_date_counts_as_verified(self):
        a = art("https://www.example.com/2026/10/22/story-name/", "Example")
        self.assertIsNone(freshness.publish_check(story(a), {a["link"]: a}, NOW))
        b = art("https://www.example.com/2026/10/18/old-story/", "Example")
        self.assertTrue(freshness.publish_check(story(b), {b["link"]: b}, NOW).startswith("stale"))
    def test_undated_lead_with_dated_tier1_member(self):
        lead = art("https://www.fightful.com/wrestling-news/x", "Fightful")
        m = art("https://www.pwinsider.com/article/1/x.html", "PWInsider", pub_ts=NOW - 5 * H)
        r = freshness.publish_check(story(lead, m), {lead["link"]: lead, m["link"]: m}, NOW)
        if __import__("editorial").tier("PWInsider") == 1: self.assertIsNone(r)
    def test_gate_skips_live_stories_and_holds_new(self):
        old = art("https://www.pwinsider.com/article/2/old.html", pub_ts=NOW - 60 * H); s = story(old)
        bl = {old["link"]: old}
        orig = pubgate.gate; pubgate.gate = lambda c, b: (True, [], [])
        try:
            self.assertEqual(len(pubgate.run([s], bl, log=lambda *x: None, live_ids={s["id"]}, now=NOW)), 1)   # already on the site
            self.assertEqual(len(pubgate.run([s], bl, log=lambda *x: None, live_ids=set(), now=NOW)), 0)       # new to the site
        finally: pubgate.gate = orig
class Junk(unittest.TestCase):
    def test_real_paragraphs_kept(self):
        for p in ["He said he went through a lot and it was enough for him to decide.",
                  "The commentary team praised the match on his podcast this week.",
                  "He was advertised for Raw next Monday in San Diego, California."]:
            self.assertFalse(enrich.JUNK.search(p), p)
    def test_boilerplate_dropped(self):
        for p in ["Leave a comment below and tell us", "Listen to the full episode below", "Ugh, what a night lol"]:
            self.assertTrue(enrich.JUNK.search(p), p)
    def test_credit_badge_stripped_not_paragraph(self):
        p = ("Ethan Miller/Getty Images Add Wrestling Inc. on Google: Preferred Source Google Discover In 2024, Penta, along with his "
             "brother Rey Fenix, opted to sign with WWE.")
        q = enrich.strip_credit(p)
        self.assertTrue(q.startswith("In 2024, Penta")); self.assertFalse(enrich.JUNK.search(q))
class Framing(unittest.TestCase):
    SRC = "Penta revealed his family helped him decide between staying with AEW or signing with WWE in 2024. Penta opted to sign with WWE."
    def test_inverted_choice(self):
        self.assertTrue(framing.choice_inverted("Penta Chose AEW Over WWE With Family Input", self.SRC))
        self.assertFalse(framing.choice_inverted("Penta Chose WWE Over AEW With Family Input", self.SRC))
        self.assertFalse(framing.choice_inverted("Penta Retains Title On Raw", self.SRC))
    def test_recollection_gets_past_framing(self):
        self.assertEqual(framing.past_framing("Drew McIntyre pitched sword stabbing idea to Vince McMahon",
                                              "Drew McIntyre pitched chopping off someone's arm with sword to Vince McMahon",
                                              "Drew McIntyre recalled a bizarre pitch he made to Vince McMahon"),
                         "Drew McIntyre Recalls Pitching sword stabbing idea to Vince McMahon")
        self.assertTrue(framing.past_framing("Penta Chose WWE Over AEW", "Penta Says His Family Helped Him Choose Between WWE & AEW", "").startswith("Penta Recalls Choosing"))
    def test_current_news_untouched(self):
        for h, raw in [("Sami Zayn Retains WWE Title vs Cody Rhodes on Raw", "Sami Zayn Loses to Cody Rhodes by DQ, Retains WWE Title"),
                       ("Elly Finch Signs Developmental Deal With WWE", "Michigan State Athlete Elly Finch Signs With WWE"),
                       ("Penta Reveals How His Family Helped Him Choose WWE", "Penta Says ..."),
                       ("Drew McIntyre Signed In 2007, Recalls First Day", "Drew McIntyre says")]:
            self.assertIsNone(framing.past_framing(h, raw, "He recalled it"), h)
if __name__ == "__main__": unittest.main()
