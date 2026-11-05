"""Index tier classifier (owner 2026-11-05): flag off by default; results/title changes/business/weekly matches/newsworthy+controversy quotes indexed."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_tier, pages

def s(title, cats=("WWE",), k="news", **kw):
    return dict({"id": "x", "title": title, "raw_title": title, "categories": list(cats), "kind": {"type": k}, "source": "Fightful",
                 "link": "https://e/x", "updates": [], "imp": 12, "summary": " ".join(["w"] * 120)}, **kw)
T = lambda c: index_tier.tier(c)[0]
R = lambda c: index_tier.tier(c)[1]
class Tier(unittest.TestCase):
    def test_off_by_default(self):
        self.assertFalse(index_tier.ENABLED)
        c = s("Old LA Knight Video Resurfaces"); self.assertEqual(T(c), "noindex")
        self.assertFalse(index_tier.noindex(c)); self.assertFalse(pages.noindex(c))
    def test_enabled_hooks_pages(self):
        index_tier.ENABLED = True
        try:
            self.assertTrue(pages.noindex(s("Old LA Knight Video Resurfaces")))
            self.assertFalse(pages.noindex(s("WWE Raw Results For November 2", k="results")))
            self.assertFalse(pages.noindex(s("WWE SmackDown Viewership Rises On October 30")))
        finally: index_tier.ENABLED = False
    def test_index(self):
        self.assertEqual(T(s("WWE SmackDown Results For November 6", k="results")), "index")
        self.assertEqual(T(s("Queen Aminata Wins AEW TBS Title on Dynamite", ("AEW",))), "index")
        self.assertEqual(T(s("Will Ospreay vs Callum Newman Set For Wrestle Kingdom 21", ("Global",), "match")), "index")
        self.assertEqual(T(s("Cody Rhodes Suffers Torn Pec, Out Of Action")), "index")
        self.assertEqual(T(s("Analysis", original=True)), "index")
    def test_business_ratings(self):
        self.assertEqual(T(s("WWE Q3 Revenue Hits $399.3 Million")), "index")
        self.assertEqual(R(s("WWE Q3 Revenue Hits $399.3 Million")), "business/ratings")
        self.assertEqual(T(s("TKO Raises 2026 Guidance After Strong Q3")), "index")
        self.assertEqual(T(s("WWE SmackDown Viewership Rises On October 30")), "index")
        self.assertEqual(T(s("SmackDown Halloween Episode Draws Higher TV Ratings", k="results")), "index")
        self.assertEqual(T(s("WWE and Netflix Expand Partnership on Rights Deal")), "index")
        self.assertEqual(T(s("TKO Updates WWE Legal Proceedings")), "noindex")  # legal, not earnings/ratings/deals
    def test_weekly_ple_match(self):
        self.assertEqual(T(s("Six-Woman Tag Match Added to Raw", k="match")), "index")
        self.assertEqual(R(s("Six-Woman Tag Match Added to Raw", k="match")), "weekly/PLE match announced")
        self.assertEqual(T(s("FTR vs MCMG IV, Persephone vs Shirakawa Set For AEW Collision", ("AEW",), "match")), "index")
        self.assertEqual(T(s("FTR, MCMG Booked for Match 4 on Jericho Cruise Collision", ("AEW",), "match")), "index")
        self.assertEqual(T(s("Main Roster Stars Set For NXT On CW")), "noindex")  # appearance, not a match
    def test_newsworthy_quote(self):
        # earnings also matches business/ratings (either reason is fine; must be indexed)
        self.assertEqual(T(s("Undertaker Reveals Peak Yearly Earnings", k="quote")), "index")
        self.assertIn(R(s("Undertaker Reveals Peak Yearly Earnings", k="quote")).split(" (")[0],
                      ("business/ratings", "newsworthy quote"))
        self.assertEqual(T(s("Steven Borden Discusses Concussion From AEW All Out", ("AEW",), "quote")), "index")
        self.assertIn("newsworthy quote", R(s("Steven Borden Discusses Concussion From AEW All Out", ("AEW",), "quote")))
        self.assertEqual(T(s("Cody Rhodes Rules Out WrestleMania Return This Year", k="quote")), "index")
        self.assertEqual(T(s("Sami Zayn Calls Self-Awareness A Gift And Curse", k="quote")), "noindex")  # filler
        self.assertEqual(T(s("Paul Heyman Explains His Signature Suit And Tie Look", k="quote")), "noindex")
    def test_controversy_quote(self):
        c = s("RVD Calls AEW Creative 'Inmates Running the Asylum'", ("AEW", "TNA"), "quote", imp=14)
        self.assertEqual(T(c), "index")
        self.assertIn("controversy quote", R(c))
        # same words but single-outlet / low imp -> stay noindex
        self.assertEqual(T(s("RVD Calls AEW Creative 'Inmates Running the Asylum'", ("AEW",), "quote", imp=10)), "noindex")
        # top star + controversy + multi-outlet
        self.assertEqual(T(s("Drew McIntyre Blasts WWE Creative After Raw", k="quote", imp=16)), "index")
        # praise / soft = not controversy
        self.assertEqual(T(s("Booker T Praises CM Punk's Second WWE Run", k="quote", imp=20)), "noindex")
        # Meltzer / Cornette industry figures
        self.assertEqual(T(s("Dave Meltzer Slams AEW Booking Of World Title Scene", ("AEW",), "quote", imp=18)), "index")
        self.assertEqual(T(s("Jim Cornette Rips Modern WWE Product", k="quote", imp=15)), "index")
    def test_noindex(self):
        self.assertEqual(T(s("Sami Zayn Never Aimed To Win WWE Title", k="quote")), "noindex")
        self.assertEqual(T(s("Could Cody Rhodes Return Soon?")), "noindex")
        self.assertEqual(T(s("Sami Zayn Delivers Strong Promo on Raw", k="results")), "noindex")
        self.assertEqual(T(s("Local Star Wins Indie Show Opener", ("Indie",))), "noindex")
    def test_pure_no_url_change(self):
        c = s("Roman Opens Raw", k="results", url="story/a.html"); index_tier.tier(c); self.assertEqual(c["url"], "story/a.html")

if __name__ == "__main__": unittest.main()
