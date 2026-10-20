"""python3 test_evergreen.py -- explainer / history / 'what is' / anniversary pieces never publish or post to X (owner rule 2026-10-20);
real news (incl. news with a background paragraph, quotes, 'who is X? ... signs') stays."""
import unittest, json, os, tempfile, time, io, contextlib
import editorial as E, x_poster as XP
CROWN_JEWEL = {"raw_title": "What is the Crown Jewel Championship? How the champion-vs-champion match works and every past winner",
               "source": "Wrestling Observer", "summary_src": "The WWE men's and women's Crown Jewel Championships were introduced in 2024 ...", "body": ""}
DROP = [   # last-7-day titles (2026-10-13..20) + the owner's list of patterns
    CROWN_JEWEL["raw_title"], "WWE Crown Jewel Championship explained", "AEW's New Clockwork Carnage Match, Explained",
    "Tommy Dreamer's Mysterious Midnight Dreamer Character Explained", "CM Punk and Samoa Joe go 60 minutes – ROH Joe vs Punk II | WON Flashback",
    "What Happened to Chris Benoit's Surviving Son - 19 Years After Double-Murder Incident", "What is bronchial asthma? The disease that killed AEW star Pac",
    "Title Changes On This Day in Wrestling (October 16th)", "Renegade Rick Wilson born on this day in 1965",
    "Everything you need to know about WWE Crown Jewel 2026", "How does the Elimination Chamber match work?", "How the WarGames match works",
    "A look back at Bret Hart's career", "Timeline of the CM Punk and Seth Rollins feud", "Who is Penta? Meet WWE's masked star",
    "Why Survivor Series matters for WWE", "The 10 greatest WrestleMania matches of all time", "Best WWE PLEs ever ranked",
    "Where are they now: the Spirit Squad", "Remembering the 20th anniversary of the Montreal Screwjob", "AEW Dynamite: a brief history",
    "The complete list of past King of the Ring winners", "How old is Rey Mysterio? Age, height and real name",
]
KEEP = [
    "Who Is Necro Butcher? Hardcore Wrestling Legend Signs WWE Deal at 53", "Tony Khan Claims AEW's Biggest Pay-Per-View Numbers Ever Have Come in 2026",
    "Sheamus Looks Back On WWE Debut, Says He Never Had A 'Great Story' In The Company", "Cody Rhodes Explains Why He Punted Baron Corbin",
    "Kevin Owens explained why he attacked Sami Zayn", "Sami Zayn vs Roman Reigns set for the Men's Crown Jewel Championship",
    "Liv Morgan becomes first woman in the history of WWE to hold three titles", "WWE announces Raw 35th anniversary show for January",
    "Medical Examiner Rules PAC Died of Bronchial Asthma", "Dave Meltzer Speculates On The Status Of WWE Crown Jewel 2026 In Saudi Arabia".replace("Speculates On", "Reports On"),
    "Crown Jewel 2026 moved out of Saudi Arabia", "Ilja Dragunov Debuts As All Elite At WrestleDream", "WWE Raw results: Cody Rhodes vs Sami Zayn",
]
class Rule(unittest.TestCase):
    def test_drops(self):
        for t in DROP: self.assertTrue(E.evergreen(t), t)
    def test_keeps(self):
        for t in KEEP: self.assertFalse(E.evergreen(t), t)
        for t in KEEP[:9]: self.assertIsNone(E.verdict({"raw_title": t}), t)
    def test_crown_jewel_verdict(self):
        self.assertEqual(E.verdict(CROWN_JEWEL), "evergreen/explainer")
    def test_news_with_background_paragraph_stays(self):
        a = {"raw_title": "Sami Zayn to confront Roman Reigns on Raw", "summary_src": "",
             "body": "The Crown Jewel Championships were introduced in 2024. Here is everything you need to know: the history of the title explained."}
        self.assertIsNone(E.verdict(a))
class XNever(unittest.TestCase):
    def test_explainer_never_posted(self):
        now = time.time()
        c = {"id": "cd918db8ae042", "title": "WWE Crown Jewel Championship explained", "raw_title": CROWN_JEWEL["raw_title"], "link": "https://example.org/cj",
             "ts": now - 60, "first_ts": now - 60, "categories": ["WWE"], "kind": {"type": "news"}, "sources": 4, "trusted": 2, "image": None, "updates": []}
        d = tempfile.mkdtemp(); XP.NEWS = os.path.join(d, "news.json"); XP.STATE = os.path.join(d, "posted_x.json")
        json.dump({"items": [c]}, open(XP.NEWS, "w")); json.dump({"posted": {}, "links": [], "log": []}, open(XP.STATE, "w"))
        XP.live_posted = lambda: {}
        for k in ("X_API_KEY", "X_POST_ENABLED"): os.environ.pop(k, None)
        f = io.StringIO()
        with contextlib.redirect_stdout(f): XP.run()
        self.assertNotIn("DRY RUN", f.getvalue())
        c2 = dict(c, id="c2", title="Sami Zayn vs Roman Reigns Set For Crown Jewel Championship", raw_title="Sami Zayn vs Roman Reigns Set For Crown Jewel Championship", link="https://example.org/2")
        json.dump({"items": [c2]}, open(XP.NEWS, "w"))
        f = io.StringIO()
        with contextlib.redirect_stdout(f): XP.run()
        self.assertIn("DRY RUN", f.getvalue())   # real news still posts
if __name__ == "__main__": unittest.main()
