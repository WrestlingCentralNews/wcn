"""Index tier classifier (owner 2026-11-05): flag off by default, results/title changes/top-star big news indexed, rumors/quotes not."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_tier, pages

def s(title, cats=("WWE",), k="news", **kw):
    return dict({"id": "x", "title": title, "raw_title": title, "categories": list(cats), "kind": {"type": k}, "source": "Fightful",
                 "link": "https://e/x", "updates": [], "imp": 12, "summary": " ".join(["w"] * 120)}, **kw)
T = lambda c: index_tier.tier(c)[0]
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
        finally: index_tier.ENABLED = False
    def test_index(self):
        self.assertEqual(T(s("WWE SmackDown Results For November 6", k="results")), "index")
        self.assertEqual(T(s("Queen Aminata Wins AEW TBS Title on Dynamite", ("AEW",))), "index")
        self.assertEqual(T(s("Will Ospreay vs Callum Newman Set For Wrestle Kingdom 21", ("Global",), "match")), "index")
        self.assertEqual(T(s("Cody Rhodes Suffers Torn Pec, Out Of Action")), "index")
        self.assertEqual(T(s("Analysis", original=True)), "index")
    def test_noindex(self):
        self.assertEqual(T(s("Sami Zayn Never Aimed To Win WWE Title", k="quote")), "noindex")
        self.assertEqual(T(s("Could Cody Rhodes Return Soon?")), "noindex")
        self.assertEqual(T(s("Sami Zayn Delivers Strong Promo on Raw", k="results")), "noindex")
        self.assertEqual(T(s("Local Star Wins Indie Show Opener", ("Indie",))), "noindex")
    def test_pure_no_url_change(self):
        c = s("Roman Opens Raw", k="results", url="story/a.html"); index_tier.tier(c); self.assertEqual(c["url"], "story/a.html")

if __name__ == "__main__": unittest.main()
