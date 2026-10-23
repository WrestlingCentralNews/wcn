"""python3 test_photo_reuse.py -- owner rule 2026-10-23: a photo confirmed on ANOTHER story is reused only when the published
headline is about exactly that one person (first-named subject, nobody else named, not results/event/vs/roundup), and only
photos of that person alone (no posters / group shots / screenshots / 'vs' / other names in the file name). The d4ecbc1 swaps
put Penta on 'Cyndi Lauper Announces Las Vegas Residency', PAC on 'CMLL Title Change Ends 931-Day Reign' (key taken from the
SOURCE headline 'CMLL Roundup: ... Kemalito honors PAC, & more!') and Liv Morgan on 'WWE Honolulu House Show Results'.
No network, no AI."""
import unittest, os
os.environ.pop("AI_API_KEY", None)
import vision, pubgate, imgmeta
PAC_IMG = "https://example.com/wp-content/uploads/2026/10/pac-aew-entrance.jpg"
def card(t, raw=None, typ="news", cid="cnew0000001"):
    return {"id": cid, "title": t, "raw_title": raw or t, "summary": "", "kind": {"type": typ}, "link": "https://example.com/a",
            "updates": [], "categories": []}
class Base(unittest.TestCase):
    def setUp(self):
        vision._C = {"choice3|cother000001|PAC|abcd1234": {"image": PAC_IMG, "credit": None, "st": "key-labelled", "key": "PAC"}}
        vision._PAGES.clear(); vision._PIX = None; vision.save = lambda: None
        vision.CARD_TITLES = {"cother000001": "PAC Signs New AEW Contract"}
        self._un = imgmeta.unusable; imgmeta.unusable = lambda u: False
    def tearDown(self): imgmeta.unusable = self._un
class Headline(Base):
    def ok(self, t, key, **kw): return vision.solo_subject(card(t, **kw), key)
    def test_single_subject_allowed(self):
        self.assertTrue(self.ok("Will Ospreay Would Run Underground Wrestling If Banned", "Will Ospreay"))
        self.assertTrue(self.ok("Cody Rhodes Calls Haku Toughest Yet Sweetest Wrestler", "Cody Rhodes"))
        self.assertTrue(self.ok("Ilja Dragunov Praises AEW For Serving Wrestling Fans", "Ilja Dragunov"))
        self.assertTrue(self.ok("AEW Star PAC Returns To Training", "PAC"))
    def test_key_only_in_source_headline(self):
        self.assertFalse(self.ok("CMLL Title Change Ends 931-Day Reign", "PAC",
                                 raw="CMLL Roundup: Tom Cruise respects lucha libre, Kemalito honors PAC, & more!"))
        self.assertFalse(self.ok("Cyndi Lauper Announces Las Vegas Residency", "Penta",
                                 raw="Cyndi Lauper Hitting Vegas, Bischoff Documentary, Hawaii Vlog, Penta And More WWE Notes"))
    def test_results_event_roundup(self):
        self.assertFalse(self.ok("WWE Honolulu House Show Results", "Liv Morgan", typ="results"))
        self.assertFalse(self.ok("WrestleDream 2026 features new Clockwork Carnage title match", "Tony Khan"))
        self.assertFalse(self.ok("TNA Impact Recaps Bound For Glory Title Changes", "Hardys"))
        self.assertFalse(self.ok("FTR vs MCMG Series Continues On AEW Collision", "Swerve Strickland"))
    def test_multi_person(self):
        self.assertFalse(self.ok("Sami Zayn Retains WWE Title In Dark Match Vs Cody Rhodes", "Sami Zayn"))
        self.assertFalse(self.ok("Jay White and David Finlay unite in AEW mega-faction", "Jay White"))
        self.assertFalse(self.ok("Bandido Shares Final Talk With PAC", "Bandido"))
        self.assertFalse(self.ok("Penta Recalls Stress Before Roman Reigns Bout", "Penta"))
    def test_not_primary_subject(self):
        self.assertFalse(self.ok("Raquel Discusses Liv Morgan, Top Stars Billed For WWE MSG Return", "Liv Morgan"))
        self.assertFalse(self.ok("Ospreay warns MJF over AEW title claim", "MJF"))
        self.assertFalse(self.ok("AEW Updates Full Gear 2026 Poster Honoring Pac", "PAC"))
        self.assertFalse(self.ok("Mojo Brookzz Aligns With New Level On Dynamite", "New Level"))
        self.assertFalse(self.ok("First Trailer Drops for CM Punk Netflix Rom-Com", "CM Punk"))
class Photo(Base):
    def test_solo_photo(self):
        self.assertTrue(vision.solo_photo("https://x.com/uploads/2026/10/AEW-WrestleDream-Will-Ospreay.jpg", "Will Ospreay"))
        self.assertFalse(vision.solo_photo("https://x.com/uploads/2026/10/NicNemethvsLeonSlaterTNABoundforGlory2026.jpg", "Leon Slater"))
        self.assertFalse(vision.solo_photo("https://x.com/uploads/2026/10/Screenshot-334.png", "PAC"))
        self.assertFalse(vision.solo_photo("https://x.com/2026/10/dominik-mysterio-explains-why-seth-rollins-is-a-significant-figure.jpg", "Dominik Mysterio"))
        # hand-blocked (reuse_block.json): Jericho / Nick Wayne match graphic
        self.assertFalse(vision.solo_photo("https://d1fcaprh3kb5t7.cloudfront.net/wp-content/uploads/2026/10/06065959/HT75eXxXsAA69Aa-scaled.jpeg?v=1", "Chris Jericho"))
    def test_source_card_must_be_about_them_alone(self):
        self.assertFalse(vision.solo_source("Queen Aminata earns TBS title shot vs Persephone", "Persephone"))
        self.assertFalse(vision.solo_source("Damian Priest Dismisses R-Truth's Injury Post", "Damian Priest"))
        self.assertFalse(vision.solo_source(None, "PAC"))
        self.assertTrue(vision.solo_source("Dominik Mysterio Skips NXT Training For Main Roster", "Dominik Mysterio"))
class Choose(Base):
    def test_cmll_story_never_gets_pac(self):
        c = card("CMLL Title Change Ends 931-Day Reign", raw="CMLL Roundup: Tom Cruise respects lucha libre, Kemalito honors PAC, & more!")
        img, cr, st = vision.choose(c, [], budget_ok=False, fetch=False)
        self.assertNotEqual(img, PAC_IMG)
        self.assertEqual(st, "promo-logo:cmll")
    def test_stale_cached_reuse_dropped(self):
        c = card("CMLL Title Change Ends 931-Day Reign", raw="CMLL Roundup: Tom Cruise respects lucha libre, Kemalito honors PAC, & more!")
        k = "choice3|" + c["id"] + "|PAC|" + vision.hashlib.md5(b"").hexdigest()[:8]
        vision._C[k] = {"image": PAC_IMG, "credit": None, "st": "key-other-story", "key": "PAC"}
        self.assertNotEqual(vision.choose(c, [], budget_ok=False, fetch=False)[0], PAC_IMG)
    def test_single_subject_story_reuses(self):
        c = card("PAC Returns To Training After Injury")
        self.assertEqual(vision.choose(c, [], budget_ok=False, fetch=False)[:3:2], (PAC_IMG, "key-other-story"))
    def test_source_gone_no_reuse(self):
        vision.CARD_TITLES = {}
        self.assertNotEqual(vision.choose(card("PAC Returns To Training After Injury"), [], budget_ok=False, fetch=False)[0], PAC_IMG)
    def test_source_multi_person_no_reuse(self):
        vision.CARD_TITLES = {"cother000001": "PAC vs Will Ospreay Set For Dynamite"}
        self.assertNotEqual(vision.choose(card("PAC Returns To Training After Injury"), [], budget_ok=False, fetch=False)[0], PAC_IMG)
class Roundup(unittest.TestCase):
    def test_nonwrestling_lead_falls_back(self):
        c = card("Cyndi Lauper Announces Las Vegas Residency",
                 raw="Cyndi Lauper Hitting Vegas, Bischoff Documentary, Hawaii Vlog, Penta And More WWE Notes")
        c.update(source="PWInsider", summary="Singer Cyndi Lauper has revealed a 2027 residency. Penta notes.")
        pubgate.gate(c, {})
        self.assertIn("WWE", c["title"])
if __name__ == "__main__": unittest.main()
