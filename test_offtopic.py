"""python3 test_offtopic.py: 2026-10-23 owner report. POST Wrestling's streaming-industry / world-news items ('Netflix faces
plenty of questions and unrest going into Q3 earnings', 'Netflix's chief content officer Bela Bejaria gone from streaming
service', 'Report: Riyadh International Airport remains highly restricted following Houthi attacks') passed the 0c7eb28 guard,
which only knew combat sports. A story must be about wrestling; corporate news is fine only when the headline clearly is.
Also: Max Caster's 'TNA Deal' story got the AEW card from a stale hand roster list."""
import unittest, combat, vision, editorial
def A(raw, title=None, link="https://www.postwrestling.com/2026/10/20/x/", ss=""):
    return {"id": "c1", "raw_title": raw, "title": title or raw, "link": link, "summary": ss, "src_summary": ss, "categories": ["WWE"]}
class OffTopic(unittest.TestCase):
    def test_dropped(self):
        for raw, title in [("Netflix faces plenty of questions and unrest going into Q3 earnings", "Netflix Reports Q3 Earnings Amid Layoffs"),
                           ("Netflix’s chief content officer Bela Bejaria gone from streaming service", "Netflix Ousts Chief Content Officer Bela Bajaria"),
                           ("Report: Riyadh International Airport remains highly restricted following Houthi attacks", "Riyadh Airport Stays Closed After Houthi Strikes"),
                           ("Paramount stock jumps after merger news", None), ("10 MLB Stars Known For Their Fiery Temper On the Field", None)]:
            a = A(raw, title, ss="WWE's largest broadcast partner, Netflix, heads into its earnings release. Saudi Arabia hosts WWE next month.")
            self.assertTrue(combat.offtopic(a), raw)
            self.assertTrue(combat.nonwrestling(a), raw)   # the ingest + pubgate guard
    def test_kept(self):
        for raw in ["WWE Raw on Netflix Draws 4.5M Global Hours", "Meltzer Shares Raw on Netflix Subscriber Numbers",
                    "CM Punk Appears In First Trailer For Netflix Movie Guarding Stars", "Dave Meltzer: WWE Gets $150M For Riyadh WrestleMania",
                    "TKO Earnings: WWE Revenue Up 20 Percent", "TNA Apologizes For Max Caster's Riyadh Comments",
                    "Tyrese Haliburton Sports Triple H Jacket For Opening Night", "Kidd survives bloody war to keep Global Heavyweight Gold - NEW JAPAN PRO-WRESTLING",
                    "Why Roman's Reign of Terror Is Worse Than Triple H's", "Jim Ross back home and on the mend after recent hospital visit",
                    "Syko Stu Looks Back On Infamous Raja Jackson Incident", "Vince McMahon court case stemming from car crash charges dismissed",
                    "AEW Signs New Media Rights Deal With Warner Bros. Discovery", "Zach Bryan Uses Dusty Rhodes' Hard Times Promo"]:
            self.assertIsNone(combat.offtopic(A(raw)), raw)
            self.assertIsNone(combat.nonwrestling(A(raw)), raw)
class CasterCard(unittest.TestCase):
    def test_tna_deal_story_gets_tna_card(self):
        c = {"id": "c289bac580ffb", "title": "Contract News: Inside Word On Max Caster's TNA Deal & Circumstances Surrounding His Departure",
             "raw_title": "Backstage News On Max Caster's TNA Deal", "summary": "TNA President Carlos Silva decided to terminate Max Caster."}
        self.assertEqual(vision.promotion("Max Caster", c), "tna")
        self.assertEqual(editorial.categories({"raw_title": c["raw_title"], "summary_src": c["summary"]}), ["TNA"])
    def test_not_on_aew_hand_list(self):   # left AEW 2025; TNA ended his deal Oct 2026: free agent
        self.assertNotRegex(editorial.ROSTER["AEW"], r"Max Caster")
if __name__ == "__main__":
    unittest.main()
