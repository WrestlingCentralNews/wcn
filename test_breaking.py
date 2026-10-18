"""python3 test_breaking.py  -- sample headlines for the 'BREAKING🚨🚨🚨' rule (positives must label, negatives must not)."""
import unittest, breaking
POS = {
 "Bandido, Hangman & Brody King regain AEW Trios titles": "title-change",
 "Knockout Brothers & Jeff Cobb Win NEVER Six-Man Titles": "title-change",
 "Alexa Bliss and Tatum Paxley Win Women's Tag Titles": "title-change",
 "Dominik Mysterio Wins The Intercontinental Championship On Raw": "title-change",
 "New AEW TNT Champion Crowned On Collision": "title-change",
 "Jade Cargill Vacates WWE Women's Tag Team Titles Due To Injury": "title-change",
 "Gunther Dethroned At Crown Jewel": "title-change",
 "PJ Vasa Released by WWE NXT": "release",
 "Carmelo Hayes Has Been Released From WWE": "release",
 "WWE Releases Several Wrestlers Following Raw": "release",
 "AEW Star Fired After Incident In Chicago": "release",
 "Ilja Dragunov Debuts As All Elite At WrestleDream": "debut",
 "AAA on FOX Results: La Catalina Debuts in Tag Title Match": "debut",
 "Mike Bailey Makes His NJPW Debut In Korakuen Hall": "debut",
 "Jay White Returns at AEW WrestleDream": "return",
 "Rhea Ripley Returns to WWE Programming": "return",
 "Will Ospreay returns unannounced to NJPW": "return",
 "Stephanie Vaquer returns at WWE Hawaii house show": "return",
 "Mariah May Makes Shocking Return On Dynamite": "return",
}
NEG = ["Moxley Retains Continental Title Over Davis At WrestleDream", "Mercedes Mone Retains AEW Women's Title at WrestleDream",
 "Nikki Bella earns Women's Title shot by beating Paige", "Trey Miguel earns TNA title shot at Destination X", "Jacy Jayne Describes Out-of-Body Title Win",
 "Drew McIntyre Teases Major WWE Return", "Maya World Cleared To Return To AEW Ring", "Backstage News On Naomi's WWE Return", "Kevin Knight Open To NJPW Return",
 "Kaitlyn Rules Out In-Ring Return", "Corey Graves Medically Cleared for Potential Return", "Tony Khan Updates Mercedes Moné Injury Return",
 "Apollo Crews Open To WWE Return", "MLW Returns To Atlanta Center Stage", "MLW Returns To PPV With November SuperFight", "WWE Stars Promote Return to Australia",
 "WWE Releases SmackDown Videos", "TNA Releases Three Hours Of Leon Slater Matches", "Yota Tsuji Set for MLW Debut", "Sheamus Recalls Nervous WWE ECW Debut",
 "Christyan XO Recalls AEW/ROH Debut Path", "Kofi Calls New Level AEW Debut Worst Kept Secret", "AEW Announces Paris Debut For Grand Slam France",
 "Vietnam's Ares set for NJPW debut in Korakuen Hall tag match", "Drake Maverick Reflects On Surprise Indie Return", "Bully Ray Praises Je'Von Evans' Intense Ambulance Return",
 "Kenny Omega Targets Wrestle Kingdom Title Shot", "AEW World Title Set For Clockwork Carnage At WrestleDream", "Kyle Fletcher Feels Ready For AEW World Title",
 "Rumor: Former WWE Champion Could Return At Survivor Series", "Is Brock Lesnar Returning At WrestleMania?", "Randy Orton Expected To Return Soon",
 "CM Punk Reportedly Set To Return Next Month", "Roman Reigns May Return On SmackDown", "Raw Preview: New Champion To Be Crowned?",
 "Wrestler Requests Release From AEW", "Seth Rollins Fires Back At Critics", "Cody Rhodes Fired Up Ahead Of Crown Jewel",
 "Will Ospreay Will Return At Wrestle Kingdom", "Five wrestlers clash in ladder match for title shot", "Sawyer Defends GCW Title vs Cogar on November 7",
 "Ospreay Retains AEW World Title at All Out", "Hotch vs. Ali 2-Out-Of-3 Falls For TNA International Title", "Raw Returns To Madison Square Garden"]
class T(unittest.TestCase):
    def test_pos(self):
        for h, k in POS.items(): self.assertEqual(breaking.kind(h), k, h)
    def test_neg(self):
        for h in NEG: self.assertIsNone(breaking.kind(h), h)
    def test_quote_never(self): self.assertIsNone(breaking.kind("Jay White Returns at AEW WrestleDream", "quote"))
    def test_x_text(self):
        import x_poster as X
        c = {"id": "t1", "title": "Ilja Dragunov Debuts As All Elite At WrestleDream " + "x" * 200, "raw_title": "Ilja Dragunov Makes AEW Debut At WrestleDream", "summary": "A long summary. " * 20, "categories": ["AEW"], "sources": 9, "trusted": 4, "kind": {"type": "news"}}
        t = X.tweet_text(c); self.assertTrue(t.startswith("BREAKING🚨🚨🚨\n")); self.assertEqual(t.count("🚨"), 3); self.assertLessEqual(X.x_len(t), 280)
        c2 = dict(c, title="Moxley Retains Continental Title Over Davis At WrestleDream", id="t2")
        self.assertNotIn("🚨", X.tweet_text(c2))
    def test_live_text(self):
        import live_x
        st = {"name": "AEW WrestleDream 2026", "brand": "AEW", "tag": "#AEWWrestleDream"}
        t = live_x.match_text(st, {"en": "Bandido, Hangman Page and Brody King defeated Swerve Strickland, Austin Creed and Kofi to win the AEW Trios Titles.", "title": "change"})
        self.assertTrue(t.startswith("BREAKING🚨🚨🚨\n")); self.assertEqual(t.count("🚨"), 3)
        t = live_x.match_text(st, {"en": "Moxley defeated Davis to retain.", "title": "retain"}); self.assertNotIn("🚨", t)
# source check (2026-10-18): the AI headline alone never earns the label; the source's own title/summary must state the event
SRC_CASES = [  # (AI headline, source title + summary, expected)
 ("AAA on FOX Results: La Catalina Debuts in Tag Title Match",
  "AAA on FOX Results (10/17): La Catalina Appears, Tag Title Bout\nLucha Libre AAA aired the latest episode of AAA on FOX on October 17. The event aired on Fox Latin America and YouTube. Full results are below.", None),
 ("Ilja Dragunov Debuts As All Elite At WrestleDream", "Ilja Dragunov Makes AEW Debut At WrestleDream", "debut"),
 ("Ilja Dragunov Debuts As All Elite At WrestleDream", "Ilja Dragunov shows up at AEW WrestleDream", None),
 ("Mike Bailey Makes His NJPW Debut In Korakuen Hall", "Speedball makes first appearance for NJPW in Korakuen Hall", "debut"),
 ("Yota Tsuji Debuts In MLW", "NJPW's Yota Tsuji to Make MLW Debut at Saturday Night SuperFight", None),
 ("Bandido, Hangman & Brody King regain AEW Trios titles", "Hangman Adam Page And Brodido Win AEW World Trios Title At AEW WrestleDream", "title-change"),
 ("Wagner Brothers Win AAA Tag Titles", "AAA on FOX Results (10/17): La Catalina Appears, Tag Title Bout", None),
 ("Moose Wins TNA World Title", "Moose Gets TNA World Title Shot At Bound For Glory", None),
 ("PJ Vasa Released by WWE NXT", "ANOTHER WWE NXT RELEASE", "release"),
 ("Max Caster Released By TNA", "Backstage News On Max Caster's TNA Deal", None),
 ("AEW Star Fired After Incident In Chicago", "AEW has fired a wrestler after an incident in Chicago, per Fightful Select.", "release"),
 ("Jay White Returns at AEW WrestleDream", "Jay White returned at AEW WrestleDream to confront Ospreay", "return"),
 ("Jay White Returns at AEW WrestleDream", "Jay White could return at AEW WrestleDream", None),
 ("Rhea Ripley Returns to WWE Programming", "Daily Update: Rhea Ripley, AAA, Lucha Kingdom", None),
]
class S(unittest.TestCase):
    def test_source_check(self):
        for h, src, exp in SRC_CASES: self.assertEqual(breaking.kind(h, None, src), exp, (h, src))
    def test_no_source_given_is_headline_only(self): self.assertEqual(breaking.kind("Jay White Returns at AEW WrestleDream"), "return")
    def test_x_card_la_catalina(self):
        import x_poster as X
        c = {"id": "c11f0df54e806", "title": "AAA on FOX Results: La Catalina Debuts in Tag Title Match", "raw_title": "AAA on FOX Results (10/17): La Catalina Appears, Tag Title Bout",
             "src_summary": "Lucha Libre AAA aired the latest episode of AAA on FOX on October 17. The event aired on Fox Latin America and YouTube. Full results are below.",
             "summary": "x", "categories": ["Global"], "sources": 2, "trusted": 1, "kind": {"type": "results"}}
        self.assertFalse(X.is_breaking(c)); self.assertNotIn("🚨", X.tweet_text(c))
        c2 = dict(c, title="AAA on FOX Results: La Catalina Appears, Wagner Brothers Defend Tag Titles"); self.assertFalse(X.is_breaking(c2))

class Guard(unittest.TestCase):
    def test_la_catalina_rewrite_reverted(self):
        import aggregator
        a = {"id": "322c9d922994", "source": "Fightful", "raw_title": "AAA on FOX Results (10/17): La Catalina Appears, Tag Title Bout", "kind": {"type": "results"},
             "summary_src": "Lucha Libre AAA aired the latest episode of AAA on FOX on October 17. The event aired on Fox Latin America and YouTube. Full results are below.",
             "body": "Lucha Libre AAA aired the latest episode of AAA on FOX on October 17.",
             "title": "AAA on FOX Results: La Catalina Debuts in Tag Title Match",
             "summary": "Lucha Libre AAA presented its latest episode on October 17. The show featured the in-ring debut appearance of La Catalina along with a tag team title match."}
        aggregator.claim_guard(a)
        self.assertNotIn("debut", a["title"].lower()); self.assertNotIn("debut", a["summary"].lower())
    def test_supported_debut_kept(self):
        import aggregator
        a = {"id": "x", "source": "Fightful", "raw_title": "Ilja Dragunov Makes AEW Debut At WrestleDream", "kind": {"type": "news"}, "summary_src": "", "body": "",
             "title": "Ilja Dragunov Debuts For AEW At WrestleDream", "summary": "Ilja Dragunov made his AEW debut at WrestleDream."}
        aggregator.claim_guard(a); self.assertEqual(a["title"], "Ilja Dragunov Debuts For AEW At WrestleDream"); self.assertIn("debut", a["summary"])

if __name__ == "__main__": unittest.main(verbosity=1)
