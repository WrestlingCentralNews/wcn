"""python3 test_retro.py -- look-back / re-published history pieces never publish as news (owner 2026-10-22); results stories whose
wrestlers are mostly off every current roster are held; legit stories about former wrestlers, returns and current results stay."""
import unittest, time, re
import editorial, pubgate
NOW = time.time()
def art(raw, body="", link=None, kind="results", src="PWTorch", summary_src=""):
    return {"raw_title": raw, "title": raw, "link": link or "https://www.example.com/" + re.sub(r"\W+", "-", raw.lower())[:60] + "/",
            "source": src, "body": body, "summary_src": summary_src, "kind": {"type": kind}, "ts": NOW, "pub_ts": NOW}
AMBROSE_BODY = ("The following is a report originally published here 10 years ago this week… (1) Dolph Ziggler defeated Tyler Breeze to retain "
                "the Intercontinental Championship. (2) Bray Wyatt beat Kane. (3) The Usos defeated The Vaudevillains. (4) Baron Corbin pinned Jack Swagger. "
                "(5) Naomi beat Alexa Bliss. (6) AJ Styles defeated Dean Ambrose to retain the WWE Title.")
TOKYO_BODY = ("The following is a report originally published here 20 years ago this week… (1) Tommy Dreamer pinned Kevin Thorne at 7:43. "
              "(2) The Highlanders beat The Spirit Squad. (3) Sabu defeated Rob Van Dam. (4) Edge beat Ric Flair. (5) CM Punk pinned Matt Striker. "
              "(6) DX (Triple H & Shawn Michaels) beat Randy Orton & Mr. Kennedy.")
class Retro(unittest.TestCase):
    def test_pwtorch_years_ago_column(self):
        for raw, body, url in (("10 YEARS AGO – WWE LIVE EVENT REPORT: AJ Styles vs. Dean Ambrose for WWE Title", AMBROSE_BODY,
                                "https://www.pwtorch.com/site/2026/10/22/10-years-ago-wwe-live-event-report-aj-styles/"),
                               ("20 YEARS AGO – WWE LIVE EVENT REPORT IN TOKYO, JAPAN: CM Punk, Randy Orton", TOKYO_BODY,
                                "https://www.pwtorch.com/site/2026/10/22/20-years-ago-wwe-live-event-report-in-tokyo-japan/")):
            self.assertTrue(editorial.retro(art(raw, body, url)))
            # even with the prefix stripped (an AI rewrite) and an unrelated URL, the body gives it away
            self.assertTrue(editorial.retro(art(re.sub(r"^\d+ YEARS AGO – ", "", raw), body)))
    def test_results_style_past_phrases(self):
        for opening in ("A live event in Tokyo featured several matches two decades ago.", "On this day, WWE ran a house show in Boston.",
                        "Looking back at the Raw results from Toronto.", "Throwback: the full results of the 1998 Survivor Series.",
                        "In 2006, WWE held a live event in Tokyo, Japan."):
            self.assertTrue(editorial.retro(art("WWE Live Event Results From Tokyo", summary_src=opening)), opening)
        self.assertTrue(editorial.retro(art("WWE No Mercy 2003 Results", "Results.")))
        self.assertTrue(editorial.retro(art("Torrie Wilson vs Dawn Marie – WWE No Mercy 2002 | WON Flashback", kind="other")))
        self.assertTrue(editorial.retro(art("WWE celebrates anniversary of Bret Hart's first-ever WWF title win", kind="other")))
        self.assertTrue(editorial.retro(art("Chris Benoit Lost WWE Gold 21 Years Ago — Then Revived a WCW Classic", kind="other")))
    def test_current_news_kept(self):
        for raw, body, kind in (("AEW WrestleDream 2026 Results", "Will Ospreay retained the AEW World Title in 2026's Clockwork Carnage.", "results"),
                                ("WWE Raw Results 10/19", "CM Punk won the title he first held 15 years ago at Money in the Bank 2011.", "results"),
                                ("Bayley Makes Surprise Appearance at Big Time Wrestling's 30th Anniversary Show", "Bayley appeared.", "other"),
                                ("RevPro 14-Year Anniversary Results", "Results from the show.", "results"),
                                ("Willow Nightingale Reacts To Four Year Anniversary Of Her AEW Signing", "Willow posted on X.", "quote"),
                                ("Mick Foley reveals why he left WWE 5 years ago", "Foley said on his podcast...", "quote"),
                                ("TNA Impact Results 10/15/26", "Impact opened with the Hardys' 35th anniversary celebration.", "results"),
                                ("Former WWE star Dolph Ziggler wins title in Japan", "Nic Nemeth won.", "other")):
            self.assertIsNone(editorial.retro(art(raw, body, kind=kind)), raw)
class RosterStale(unittest.TestCase):
    DB = {p: {"ok": True, "fetched": NOW - 3600, "names": {}} for p in ("WWE", "AEW", "TNA")}
    for n in ("cm punk", "randy orton", "naomi", "alexa bliss", "jey uso", "jimmy uso", "seth rollins", "cody rhodes", "sami zayn",
              "roman reigns", "bron breakker", "rhea ripley", "iyo sky", "gunther", "penta", "dominik mysterio", "jacob fatu", "solo sikoa"):
        DB["WWE"]["names"][n] = {"name": n.title(), "first": NOW - 86400, "last": NOW - 3600}
    for n in ("will ospreay", "kenny omega", "jon moxley", "mjf", "darby allin", "kazuchika okada", "swerve strickland", "hangman adam page"):
        DB["AEW"]["names"][n] = {"name": n.title(), "first": NOW - 86400, "last": NOW - 3600}
    for n in ("mike santana", "moose", "matt hardy", "jeff hardy", "frankie kazarian", "joe hendry", "nic nemeth", "ryan nemeth"):
        DB["TNA"]["names"][n] = {"name": n.title(), "first": NOW - 86400, "last": NOW - 3600}
    def setUp(self): self._min = dict(pubgate.roster.MIN); pubgate.roster.MIN.update({"WWE": 5, "AEW": 5, "TNA": 5})
    def tearDown(self): pubgate.roster.MIN.clear(); pubgate.roster.MIN.update(self._min)
    def c(self, raw, body, cats=("WWE",)):
        a = art(raw, body); a.update(categories=list(cats), id="cx", updates=[])
        return a, {a["link"]: a}
    def test_old_card_held(self):
        c, by = self.c("WWE Live Event Report: AJ Styles vs. Dean Ambrose", AMBROSE_BODY.split("… ", 1)[1])
        self.assertIn("aren't on any current roster", pubgate.roster_stale(c, by, self.DB, NOW) or "")
    def test_current_card_kept(self):
        body = ("(1) Seth Rollins defeated Bron Breakker. (2) Rhea Ripley beat Iyo Sky. (3) Jey Uso pinned Solo Sikoa. "
                "(4) Gunther defeated Penta. (5) Cody Rhodes beat Dominik Mysterio. (6) Roman Reigns defeated Jacob Fatu.")
        self.assertIsNone(pubgate.roster_stale(*self.c("WWE Live Event Results From Honolulu", body), self.DB, NOW))
    def test_former_wrestler_and_return_framing_kept(self):
        body = AMBROSE_BODY.split("… ", 1)[1]
        self.assertIsNone(pubgate.roster_stale(*self.c("WWE Legends Return: Results From The Raw Reunion Show", body), self.DB, NOW))
        self.assertIsNone(pubgate.roster_stale(*self.c("Dolph Ziggler Signs With NJPW", body), self.DB, NOW))   # not a results story
        a, by = self.c("WWE Live Event Report: AJ Styles vs. Dean Ambrose", body); a["kind"] = {"type": "other"}; a["raw_title"] = "Dean Ambrose speaks on AJ Styles"
        self.assertIsNone(pubgate.roster_stale(a, by, self.DB, NOW))
    def test_no_snapshot_fails_open(self):
        c, by = self.c("WWE Live Event Report: AJ Styles vs. Dean Ambrose", AMBROSE_BODY)
        self.assertIsNone(pubgate.roster_stale(c, by, {}, NOW))
class ArtImage(unittest.TestCase):
    def test_pwtorch_header_art(self):
        for u in ("https://www.pwtorch.com/site/wp-content/uploads/post/2017/10/CorbinBaronTeschJoel3x2_600.png",
                  "https://www.pwtorch.com/site/wp-content/uploads/2015/12/PunkCM_GG_3x2_600.jpg"):
            self.assertTrue(pubgate.ART_IMG.search(u))
        self.assertFalse(pubgate.ART_IMG.search("https://www.pwtorch.com/site/wp-content/uploads/post/2026/10/Screenshot-2026-10-21-at-2.24.44-PM.png"))
if __name__ == "__main__": unittest.main()
